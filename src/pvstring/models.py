"""Validated datasheet models. Voltages are V, currents A, powers W, temperatures °C.

Numeric temperature coefficients use datasheet percent/°C (``-0.27`` means
``-0.27%/°C``). Explicit voltage coefficients must include their units.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Optional, Tuple, Union

Coefficient = Union[float, str]


class InputError(ValueError):
    """An invalid datasheet, site assumption, or array configuration."""


def finite_number(value: object, name: str) -> float:
    """Validate a finite real number without accepting booleans or numeric strings."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise InputError(f"{name}: expected a finite number")
    try:
        number = float(value)
    except (OverflowError, ValueError):
        raise InputError(f"{name}: expected a finite number") from None
    if not math.isfinite(number):
        raise InputError(f"{name}: expected a finite number")
    return number


def parse_coefficient(value: Coefficient, reference_voltage: Optional[float] = None) -> float:
    """Return fractional change/°C from percent/°C or an explicit V/°C value.

    For example, ``-0.27`` and ``'-0.27%/°C'`` both yield ``-0.0027``.
    ``'-0.134 V/°C'`` requires the relevant STC reference voltage and yields
    ``-0.134 / reference_voltage``. Unitless numeric strings are rejected.
    """
    if isinstance(value, str):
        match = re.fullmatch(
            r"\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)\s*(%|V)\s*/\s*(?:°\s*C|degC|C)\s*",
            value,
            flags=re.IGNORECASE,
        )
        if not match:
            raise InputError("coefficient: use a number in %/°C or a string such as '-0.27%/°C' or '-0.134 V/°C'")
        number = float(match.group(1))
        if not math.isfinite(number):
            raise InputError("coefficient: expected a finite number")
        if match.group(2).lower() == "v":
            if reference_voltage is None:
                raise InputError("coefficient: V/°C requires a reference voltage; this field requires %/°C")
            voltage = finite_number(reference_voltage, "reference_voltage")
            if voltage <= 0:
                raise InputError("reference_voltage: must be positive")
            return number / voltage
        return number / 100
    return finite_number(value, "coefficient") / 100


def _name(value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise InputError("name: must be a nonempty string")


def _positive(value: object, name: str, allow_zero: bool = False) -> None:
    number = finite_number(value, name)
    if number < 0 or (not allow_zero and number == 0):
        raise InputError(f"{name}: must be {'nonnegative' if allow_zero else 'positive'}")


def _integer(value: object, name: str, minimum: int = 1) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise InputError(f"{name}: must be an integer >= {minimum}")


@dataclass(frozen=True)
class Module:
    """A module datasheet, with numeric coefficients expressed in percent/°C."""

    name: str
    pmax_stc: float
    voc: float
    isc: float
    vmp: float
    imp: float
    beta_voc: Coefficient
    alpha_isc: Coefficient
    gamma_pmax: Coefficient
    gamma_vmp: Optional[Coefficient] = None
    noct: Optional[float] = 45.0
    nmot: Optional[float] = None
    bifacial: bool = False
    bifaciality: float = 0.0
    max_system_voltage: float = 1000.0
    max_series_fuse_rating: float = 25.0

    def __post_init__(self) -> None:
        _name(self.name)
        for key in ("pmax_stc", "voc", "isc", "vmp", "imp", "max_system_voltage", "max_series_fuse_rating"):
            _positive(getattr(self, key), key)
        if self.vmp >= self.voc or self.imp > self.isc:
            raise InputError("module: require Vmp < Voc and Imp <= Isc")
        if abs(self.vmp * self.imp / self.pmax_stc - 1) > 0.05:
            raise InputError("pmax_stc: differs from Vmp × Imp by more than 5%; check W/V/A units")
        if parse_coefficient(self.beta_voc, self.voc) >= 0:
            raise InputError("beta_voc: must be negative for this crystalline-silicon model")
        if parse_coefficient(self.alpha_isc) < 0:
            raise InputError("alpha_isc: must be nonnegative for this model")
        if parse_coefficient(self.gamma_pmax) >= 0:
            raise InputError("gamma_pmax: must be negative")
        if self.gamma_vmp is not None and parse_coefficient(self.gamma_vmp, self.vmp) >= 0:
            raise InputError("gamma_vmp: must be negative")
        for key in ("noct", "nmot"):
            if getattr(self, key) is not None:
                value = finite_number(getattr(self, key), key)
                if not 20 < value < 100:
                    raise InputError(f"{key}: expected a cell temperature between 20 and 100 °C")
        if not isinstance(self.bifacial, bool):
            raise InputError("bifacial: must be true or false")
        if not 0 <= finite_number(self.bifaciality, "bifaciality") <= 1:
            raise InputError("bifaciality: must be between 0 and 1")
        if not self.bifacial and self.bifaciality != 0:
            raise InputError("bifaciality: must be zero when bifacial is false")
        if self.bifacial and self.bifaciality == 0:
            raise InputError("bifaciality: must be positive when bifacial is true")


@dataclass(frozen=True)
class Inverter:
    """Uniform per-MPPT ratings; all powers are W, voltage windows inclusive."""

    name: str
    max_dc_voltage: float
    start_voltage: float
    mppt_min: float
    mppt_max: float
    full_power_mppt_min: float
    full_power_mppt_max: float
    nominal_dc_voltage: float
    num_mppts: int
    max_input_current_per_mppt: float
    max_isc_per_mppt: float
    strings_per_mppt: int
    max_dc_power: float
    ac_rated_power: float

    def __post_init__(self) -> None:
        _name(self.name)
        for key in ("max_dc_voltage", "start_voltage", "mppt_min", "mppt_max", "full_power_mppt_min", "full_power_mppt_max", "nominal_dc_voltage", "max_input_current_per_mppt", "max_isc_per_mppt", "max_dc_power", "ac_rated_power"):
            _positive(getattr(self, key), key)
        for key in ("num_mppts", "strings_per_mppt"):
            _integer(getattr(self, key), key)
        if not (self.mppt_min <= self.full_power_mppt_min <= self.full_power_mppt_max <= self.mppt_max <= self.max_dc_voltage):
            raise InputError("inverter: require operating min <= full-power min <= full-power max <= operating max <= max DC voltage")
        if not self.mppt_min <= self.nominal_dc_voltage <= self.mppt_max:
            raise InputError("nominal_dc_voltage: must be inside operating MPPT window")
        if self.start_voltage > self.max_dc_voltage:
            raise InputError("start_voltage: exceeds maximum DC voltage")
        if self.max_input_current_per_mppt > self.max_isc_per_mppt:
            raise InputError("max_input_current_per_mppt: exceeds max_isc_per_mppt")


@dataclass(frozen=True)
class Site:
    """Design temperatures and explicit thermal, irradiance, and aging assumptions."""

    name: str
    tmin: float
    thigh: float
    irradiance: float = 1000.0
    rear_irradiance_ratio: float = 0.0
    altitude: Optional[float] = None
    racking: Optional[str] = None
    fixed_delta_t: Optional[float] = None
    typical_cell_temperature: float = 45.0
    degradation_percent_per_year: float = 0.5
    design_years: int = 10

    def __post_init__(self) -> None:
        _name(self.name)
        for key in ("tmin", "thigh", "typical_cell_temperature"):
            value = finite_number(getattr(self, key), key)
            if not -100 <= value <= 100:
                raise InputError(f"{key}: expected a temperature between -100 and 100 °C")
        if self.tmin > self.thigh:
            raise InputError("tmin: must not exceed thigh")
        if self.typical_cell_temperature < self.tmin:
            raise InputError("typical_cell_temperature: must not be below tmin")
        _positive(self.irradiance, "irradiance")
        if not 0 <= finite_number(self.rear_irradiance_ratio, "rear_irradiance_ratio") <= 1:
            raise InputError("rear_irradiance_ratio: must be between 0 and 1")
        if self.altitude is not None:
            finite_number(self.altitude, "altitude")
        if self.racking not in (None, "open-rack", "roof", "bipv"):
            raise InputError("racking: choose open-rack, roof, or bipv")
        if self.fixed_delta_t is not None:
            _positive(self.fixed_delta_t, "fixed_delta_t", allow_zero=True)
            if self.racking is not None:
                raise InputError("choose fixed_delta_t or racking, not both")
        _positive(self.degradation_percent_per_year, "degradation_percent_per_year", allow_zero=True)
        _integer(self.design_years, "design_years", minimum=0)
        if self.degradation_percent_per_year * self.design_years >= 100:
            raise InputError("degradation: lifetime allowance must be less than 100%")


@dataclass(frozen=True)
class Array:
    """Equal modules per string and parallel counts in physical MPPT order.

    Zero denotes an unused MPPT. ``fuse_rating`` is the installed per-string fuse
    in A, not the module's maximum permitted fuse rating.
    """

    modules_per_string: int
    strings_per_mppt: Tuple[int, ...]
    fuse_rating: Optional[float] = None

    def __post_init__(self) -> None:
        _integer(self.modules_per_string, "modules_per_string")
        if not isinstance(self.strings_per_mppt, (tuple, list)) or not self.strings_per_mppt:
            raise InputError("strings_per_mppt: expected a nonempty list of integer counts")
        for count in self.strings_per_mppt:
            _integer(count, "strings_per_mppt count", minimum=0)
        if not any(self.strings_per_mppt):
            raise InputError("strings_per_mppt: at least one MPPT must be used")
        object.__setattr__(self, "strings_per_mppt", tuple(self.strings_per_mppt))
        if self.fuse_rating is not None:
            _positive(self.fuse_rating, "fuse_rating")
