"""Transparent screening calculations, not a code-compliance certification."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from itertools import combinations_with_replacement
from typing import Any, Dict, List, Optional, Tuple

from .models import Array, InputError, Inverter, Module, Site, finite_number, parse_coefficient

# (inclusive integer lower temperature, inclusive upper temperature, factor).
# Per NEC Table 690.7(A), crystalline/multicrystalline silicon modules only.
NEC_FACTORS: Tuple[Tuple[int, int, float], ...] = (
    (20, 24, 1.02), (15, 19, 1.04), (10, 14, 1.06), (5, 9, 1.08),
    (0, 4, 1.10), (-5, -1, 1.12), (-10, -6, 1.14), (-15, -11, 1.16),
    (-20, -16, 1.18), (-25, -21, 1.20), (-30, -26, 1.21),
    (-35, -31, 1.23), (-40, -36, 1.25),
)
RACKING_DELTA_T: Dict[str, float] = {"open-rack": 25.0, "roof": 30.0, "bipv": 40.0}
DISCLAIMER = (
    "Design aid only. Verify the original manufacturer datasheets and tools, equipment "
    "listing instructions, and local code with the authority having jurisdiction. "
    "Obtain licensed professional sign-off before construction. PASS is not certification."
)


@dataclass(frozen=True)
class Check:
    """One auditable design check with its units in value/limit or explanation."""

    name: str
    status: str
    value: Any
    limit: Any
    explanation: str
    reference: str


@dataclass(frozen=True)
class DesignResult:
    """Inputs, intermediate quantities, limits, and checks for a complete design."""

    module: Module
    inverter: Inverter
    site: Site
    array: Array
    metrics: Dict[str, Any]
    limits: Dict[str, int]
    checks: List[Check]

    @property
    def status(self) -> str:
        """Return the worst check status."""
        if any(c.status == "FAIL" for c in self.checks):
            return "FAIL"
        return "WARN" if any(c.status == "WARN" for c in self.checks) else "PASS"

    @property
    def exit_code(self) -> int:
        """Return the automation exit code (PASS=0, WARN=1, FAIL=2)."""
        return {"PASS": 0, "WARN": 1, "FAIL": 2}[self.status]

    def to_dict(self) -> Dict[str, Any]:
        """Return JSON-ready inputs and results, including the interpretation notice."""
        result = asdict(self)
        result.update(schema_version=1, status=self.status, exit_code=self.exit_code, disclaimer=DISCLAIMER)
        return result


@dataclass(frozen=True)
class Suggestion:
    """One feasible option. WARN checks may remain; FAIL checks never do."""

    array: Array
    score: float
    result: DesignResult

    def to_dict(self) -> Dict[str, Any]:
        """Return a serializable ranked option."""
        return {"score": self.score, "array": asdict(self.array), "result": self.result.to_dict()}


def nec_voltage_factor(temperature: float) -> float:
    """Look up the comparison factor per NEC Table 690.7(A).

    Decimal temperatures round *down* to the colder integer before lookup;
    temperatures at/above 25 °C use 1.0, below -40 °C require another method.
    """
    temperature = finite_number(temperature, "temperature")
    if temperature >= 25:
        return 1.0
    if temperature < -40:
        raise InputError("NEC table: below -40 °C is outside the tabulated range; use manufacturer coefficients")
    integer_temperature = math.floor(temperature)
    for lower, upper, factor in NEC_FACTORS:
        if lower <= integer_temperature <= upper:
            return factor
    raise InputError("NEC table: temperature outside supported bands")


def cell_temperature(site: Site, module: Module) -> float:
    """Return hot cell °C using fixed racking ΔT or the simplified NOCT/NMOT model."""
    if site.fixed_delta_t is not None:
        result = site.thigh + site.fixed_delta_t
    elif site.racking is not None:
        result = site.thigh + RACKING_DELTA_T[site.racking]
    else:
        # NMOT, when supplied, takes precedence over the default NOCT.
        nominal = module.nmot if module.nmot is not None else module.noct
        if nominal is None:
            raise InputError("thermal model: supply module noct/nmot or site racking/fixed_delta_t")
        result = site.thigh + (nominal - 20) / 800 * site.irradiance
    if not math.isfinite(result) or result > 150:
        raise InputError("thermal model: hot cell temperature exceeds 150 °C; check inputs")
    return result


def cold_voc(module: Module, temperature: float) -> float:
    """Return single-module Voc in V using manufacturer βVoc at cell temperature."""
    temperature = finite_number(temperature, "temperature")
    value = module.voc * (1 + parse_coefficient(module.beta_voc, module.voc) * (temperature - 25))
    if not math.isfinite(value) or value <= 0:
        raise InputError("cold Voc: coefficient/temperature gives a nonpositive or nonfinite voltage")
    return value


def hot_vmp(module: Module, temperature: float, retention: float = 1.0) -> float:
    """Return single-module Vmp in V, optionally with a voltage-retention allowance.

    Missing γVmp uses the fractional βVoc proxy, not the absolute V/°C slope.
    """
    temperature = finite_number(temperature, "temperature")
    retention = finite_number(retention, "retention")
    if not 0 < retention <= 1:
        raise InputError("retention: must be in (0, 1]")
    coefficient = (parse_coefficient(module.gamma_vmp, module.vmp)
                   if module.gamma_vmp is not None else parse_coefficient(module.beta_voc, module.voc))
    value = module.vmp * (1 + coefficient * (temperature - 25)) * retention
    if not math.isfinite(value) or value <= 0:
        raise InputError("Vmp: coefficient/temperature/retention gives a nonpositive or nonfinite voltage")
    return value


def corrected_isc(module: Module, site: Site, temperature: Optional[float] = None) -> float:
    """Return hot short-circuit A/string before the NEC 1.25 circuit-current factor."""
    temperature = cell_temperature(site, module) if temperature is None else finite_number(temperature, "temperature")
    gain = 1 + (module.bifaciality * site.rear_irradiance_ratio if module.bifacial else 0)
    result = module.isc * (1 + parse_coefficient(module.alpha_isc) * (temperature - 25)) * (site.irradiance / 1000) * gain
    if not math.isfinite(result) or result <= 0:
        raise InputError("Isc: assumptions give nonpositive or nonfinite current")
    return result


def design_metrics(module: Module, inverter: Inverter, site: Site) -> Dict[str, Any]:
    """Compute per-module voltages and per-string currents without rounding."""
    hot = cell_temperature(site, module)
    if hot < site.tmin or site.typical_cell_temperature > hot:
        raise InputError("thermal assumptions: require tmin <= typical cell temperature <= hot cell temperature")
    isc = corrected_isc(module, site, hot)
    try:
        table_voc: Optional[float] = module.voc * nec_voltage_factor(site.tmin)
    except InputError:
        table_voc = None
    values = {
        "cell_temperature_hot": hot,
        "voc_cold": cold_voc(module, site.tmin),
        "voc_cold_table": table_voc,
        "voc_hot": cold_voc(module, hot),
        "vmp_hot": hot_vmp(module, hot),
        "vmp_hot_eol": hot_vmp(module, hot, 1 - site.degradation_percent_per_year * site.design_years / 100),
        "vmp_cold": hot_vmp(module, site.tmin),
        "vmp_typical": hot_vmp(module, site.typical_cell_temperature),
        "isc_hot": isc,
        "isc_design": isc * 1.25,
        # No Imp coefficient in this simplified datasheet model. Use the same
        # temperature/irradiance multiplier as Isc and disclose this assumption.
        "imp_hot": module.imp * isc / module.isc,
    }
    for key, value in values.items():
        if value is not None and not math.isfinite(value):
            raise InputError(f"{key}: overflow; check datasheet magnitudes")
    return values


def _floor_ratio(limit: float, value: float) -> int:
    # No epsilon: maximum voltage safety must never round an actual excess down.
    return math.floor(limit / value)


def string_limits(module: Module, inverter: Inverter, site: Site) -> Dict[str, int]:
    """Return inclusive operating and typical full-power counts (empty if min > max).

    Operating minimum includes hot-EOL tracking and a hot-Voc startup screen.
    Operating maximum includes cold Voc and cold Vmp tracking. The manufacturer's
    coefficient method controls; the NEC table is a comparison, not a second cap.
    """
    metrics = design_metrics(module, inverter, site)
    minimum = max(1, math.ceil(inverter.mppt_min / metrics["vmp_hot_eol"]),
                  math.ceil(inverter.start_voltage / metrics["voc_hot"]))
    maximum = min(_floor_ratio(min(inverter.max_dc_voltage, module.max_system_voltage), metrics["voc_cold"]),
                  _floor_ratio(inverter.mppt_max, metrics["vmp_cold"]))
    return {
        "min_modules": minimum,
        "max_modules": maximum,
        "recommended_min": max(minimum, math.ceil(inverter.full_power_mppt_min / metrics["vmp_typical"])),
        "recommended_max": min(maximum, _floor_ratio(inverter.full_power_mppt_max, metrics["vmp_typical"])),
    }


def evaluate(module: Module, inverter: Inverter, site: Site, array: Array) -> DesignResult:
    """Check a design, retaining hard failures and advisory warnings independently."""
    if len(array.strings_per_mppt) != inverter.num_mppts:
        raise InputError(f"strings_per_mppt: expected {inverter.num_mppts} counts, got {len(array.strings_per_mppt)} (use 0 for unused MPPTs)")
    metrics = design_metrics(module, inverter, site)
    limits = string_limits(module, inverter, site)
    n = array.modules_per_string
    checks: List[Check] = []

    def finite_check_value(value: Any, label: str) -> None:
        if isinstance(value, (int, float)):
            finite_number(value, label)
        elif isinstance(value, (tuple, list)):
            for item in value:
                finite_check_value(item, label)

    def add(name: str, status: str, value: Any, limit: Any, explanation: str, reference: str) -> None:
        # Finite datasheet inputs can still overflow when multiplied by parallel
        # counts or fuse factors. Reject the derived result before reporting it.
        finite_check_value(value, f"{name} value")
        finite_check_value(limit, f"{name} limit")
        checks.append(Check(name, status, value, limit, explanation, reference))

    def hard(name: str, ok: bool, value: float, limit: float, explanation: str, reference: str) -> None:
        add(name, "PASS" if ok else "FAIL", value, limit, explanation, reference)

    voc = n * metrics["voc_cold"]
    hard("Cold Voc / inverter maximum", voc <= inverter.max_dc_voltage, voc, inverter.max_dc_voltage,
         "V/string at cold design temperature; manufacturer coefficient method. Dawn cell temperature is approximated by ambient.", "NEC 2023 690.7(A)(1); inverter datasheet")
    hard("Cold Voc / module system voltage", voc <= module.max_system_voltage, voc, module.max_system_voltage,
         "V/string must respect the module insulation/system-voltage rating as well as the inverter.", "Module datasheet; NEC 2023 690.7")
    hard("Hot EOL Vmp / MPPT minimum", n * metrics["vmp_hot_eol"] >= inverter.mppt_min,
         n * metrics["vmp_hot_eol"], inverter.mppt_min,
         "V/string after the explicit linear voltage-degradation allowance; minimum operating tracking voltage.", "Inverter datasheet; design allowance")
    hard("Cold Vmp / MPPT maximum", n * metrics["vmp_cold"] <= inverter.mppt_max,
         n * metrics["vmp_cold"], inverter.mppt_max,
         "V/string at cold design temperature must stay within the operating tracking window.", "Inverter datasheet")
    hard("Start voltage", n * metrics["voc_hot"] >= inverter.start_voltage,
         n * metrics["voc_hot"], inverter.start_voltage,
         "Hot open-circuit V/string screens restart capability. Low-light start behavior requires manufacturer verification.", "Inverter datasheet; simplified startup screen")
    typical = n * metrics["vmp_typical"]
    add("Typical Vmp / full-power window", "PASS" if inverter.full_power_mppt_min <= typical <= inverter.full_power_mppt_max else "WARN",
        typical, [inverter.full_power_mppt_min, inverter.full_power_mppt_max],
        "V/string at the assumed typical cell temperature; full-power window is advisory and distinct from the operating window.", "Inverter datasheet")

    if module.gamma_vmp is None:
        add("Vmp coefficient proxy", "WARN", "fractional beta_voc", "manufacturer gamma_vmp preferred",
            "Missing Vmp temperature coefficient: the relative Voc coefficient is used as a proxy. Obtain manufacturer Vmp data.", "Model assumption")
    if metrics["voc_cold_table"] is None:
        add("NEC table comparison", "WARN", site.tmin, ">= -40 °C",
            "Cold temperature is outside the comparison table; manufacturer coefficient calculation remains available.", "Per NEC Table 690.7(A)")
    else:
        add("NEC table comparison", "PASS", n * metrics["voc_cold_table"], "comparison only (V/string)",
            "Table result is informative. The available manufacturer coefficient controls this design, so methods are not mixed.", "Per NEC Table 690.7(A)")

    for index, count in enumerate(array.strings_per_mppt, 1):
        label = f"MPPT {index}"
        hard(f"{label} string capacity", count <= inverter.strings_per_mppt, count, inverter.strings_per_mppt,
             "Parallel string count versus physical/manufacturer input capacity; 0 denotes unused.", "Inverter datasheet")
        if count == 0:
            continue
        isc_design = metrics["isc_design"] * count
        operating = metrics["imp_hot"] * count
        hard(f"{label} maximum Isc", isc_design <= inverter.max_isc_per_mppt, isc_design, inverter.max_isc_per_mppt,
             "A/MPPT: temperature- and irradiance-corrected Isc × bifacial gain × 1.25 × parallel strings. Conservative comparison to inverter short-circuit rating.", "NEC 2023 690.8(A)(1); inverter datasheet")
        add(f"{label} operating current", "PASS" if operating <= inverter.max_input_current_per_mppt else "WARN",
            operating, inverter.max_input_current_per_mppt,
            "A/MPPT: Imp uses the Isc temperature/irradiance multiplier as a screening proxy. Exceeding operating input current may clip production.", "Inverter datasheet; Imp model assumption")

        # A simplified sufficient trigger, not a replacement for manufacturer
        # reverse-current/OCPD instructions. Also catch excessive backfeed with
        # only two unusually high-current strings.
        reverse_current = metrics["isc_design"] * (count - 1)
        fuses_required = count >= 3 or reverse_current > module.max_series_fuse_rating
        minimum_fuse = metrics["isc_design"] * 1.25
        if fuses_required and array.fuse_rating is None:
            add(f"{label} series fusing", "FAIL", "no fuse specified", module.max_series_fuse_rating,
                f"{count} parallel strings require series fuses under this simplified screen; select an explicit fuse_rating (A) and verify the complete protection design.", "NEC 2023 690.9 (simplified)")
        elif array.fuse_rating is not None:
            rating = array.fuse_rating
            hard(f"{label} series fuse rating", minimum_fuse <= rating <= module.max_series_fuse_rating,
                 rating, [minimum_fuse, module.max_series_fuse_rating],
                 "Per-string fuse A must be >= 1.25 × maximum circuit current and <= module maximum series fuse. Discrete standard ratings, conductors, and inverter backfeed require separate verification.", "NEC 2023 690.8/690.9 (simplified)")
        else:
            add(f"{label} series fusing", "PASS", count, "3 parallel strings trigger simplified fuse rule",
                "No series fuse triggered by this screen. Manufacturer instructions and inverter backfeed may still require protection.", "NEC 2023 690.9 (simplified)")

    dc = module.pmax_stc * n * sum(array.strings_per_mppt)
    if not math.isfinite(dc):
        raise InputError("dc_power: overflow; check configuration magnitudes")
    ratio = dc / inverter.ac_rated_power
    if not math.isfinite(ratio):
        raise InputError("dc_ac_ratio: overflow; check inverter AC rating")
    metrics.update(dc_power=dc, dc_ac_ratio=ratio)
    hard("Maximum DC power", dc <= inverter.max_dc_power, dc, inverter.max_dc_power,
         "Installed front-side STC nameplate W versus inverter permitted array power. Bifacial energy gain is not added to STC nameplate power.", "Inverter datasheet")
    add("DC/AC ratio (ILR)", "PASS" if 1.1 <= ratio <= 1.35 else "WARN", ratio, [1.1, 1.35],
        "STC DC W / AC rated W. The typical 1.10–1.35 screening band is project-dependent, not a code requirement.", "Design guidance")
    if site.rear_irradiance_ratio and not module.bifacial:
        add("Rear irradiance ignored", "WARN", site.rear_irradiance_ratio, "bifacial module required",
            "Rear irradiance contributes no current for a monofacial module.", "Module model assumption")
    if site.altitude is not None and site.altitude > 2000:
        add("Altitude derating", "WARN", site.altitude, "manufacturer altitude rating required",
            "Altitude above 2000 m may require voltage/power/insulation derating. This model does not apply altitude corrections.", "Manufacturer installation instructions")
    return DesignResult(module, inverter, site, array, metrics, limits, checks)


def check_design(module: Module, inverter: Inverter, site: Site, array: Array) -> List[Check]:
    """Return the full list of PASS/WARN/FAIL checks for a design."""
    return evaluate(module, inverter, site, array).checks


def suggest(module: Module, inverter: Inverter, site: Site, target_dc_kw: Optional[float] = None) -> List[Suggestion]:
    """Enumerate feasible configurations, ranked by target power, balance, and voltage.

    Electrically equivalent permutations of identically rated MPPTs are represented
    once, with counts descending. Unused MPPTs are allowed. Every returned design
    has no FAIL checks; WARN checks remain visible. A required fuse is proposed
    only if an integer-A rating fits the simplified allowable interval.
    """
    if target_dc_kw is not None:
        if finite_number(target_dc_kw, "target_dc_kw") <= 0:
            raise InputError("target_dc_kw: must be positive")
        target_w = target_dc_kw * 1000
    else:
        target_w = inverter.ac_rated_power * 1.2
    if not math.isfinite(target_w):
        raise InputError("target_dc_kw: exceeds supported range")
    limits = string_limits(module, inverter, site)
    metrics = design_metrics(module, inverter, site)
    max_strings = min(inverter.strings_per_mppt, math.floor(inverter.max_isc_per_mppt / metrics["isc_design"]))
    if max_strings == 0 or limits["min_modules"] > limits["max_modules"]:
        return []
    possibilities = math.comb(max_strings + inverter.num_mppts, inverter.num_mppts) - 1
    count_lengths = limits["max_modules"] - limits["min_modules"] + 1
    if possibilities * count_lengths > 250_000:
        raise InputError("suggest: search exceeds 250000 configurations; reduce inverter MPPT/string capacities")
    ranked: List[Suggestion] = []
    for n in range(limits["min_modules"], limits["max_modules"] + 1):
        for ascending in combinations_with_replacement(range(max_strings + 1), inverter.num_mppts):
            if not any(ascending):
                continue
            mapping = tuple(reversed(ascending))
            if n * sum(mapping) * module.pmax_stc > inverter.max_dc_power:
                continue
            fuse: Optional[float] = None
            if mapping[0] >= 3 or metrics["isc_design"] * (mapping[0] - 1) > module.max_series_fuse_rating:
                fuse = float(math.ceil(metrics["isc_design"] * 1.25))
                if fuse > module.max_series_fuse_rating:
                    continue
            result = evaluate(module, inverter, site, Array(n, mapping, fuse))
            if result.status == "FAIL":
                continue
            target_distance = abs(result.metrics["dc_power"] - target_w) / target_w
            mean = sum(mapping) / len(mapping)
            balance = sum((x - mean) ** 2 for x in mapping) / len(mapping) / max(1, mean ** 2)
            voltage_distance = abs(n * metrics["vmp_typical"] - inverter.nominal_dc_voltage) / inverter.nominal_dc_voltage
            headroom = n * metrics["voc_cold"] / min(inverter.max_dc_voltage, module.max_system_voltage)
            warnings = sum(c.status == "WARN" for c in result.checks)
            score = target_distance + 0.05 * balance + 0.02 * voltage_distance + 0.01 * headroom + 0.005 * warnings
            ranked.append(Suggestion(result.array, score, result))
    ranked.sort(key=lambda s: (s.score, s.array.modules_per_string, s.array.strings_per_mppt))
    return ranked
