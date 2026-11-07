# pvstring

**Vendor-neutral PV string sizing, temperature correction, and inverter compatibility checks from JSON datasheets.**

[![CI](https://github.com/Pinnnnnneapple/pvstring/actions/workflows/ci.yml/badge.svg)](https://github.com/Pinnnnnneapple/pvstring/actions/workflows/ci.yml)
[![MIT license](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python 3.9–3.13](https://img.shields.io/badge/python-3.9%20%E2%80%93%203.13-blue.svg)](pyproject.toml)

## Why

Installers and small EPCs often move between brand-specific sizing websites
and spreadsheets. A string that looks fine at STC can exceed an inverter's
DC voltage limit on a cold morning, fall below its tracking window on a hot
roof, or overload an MPPT when strings run in parallel.

`pvstring` makes those assumptions and limits visible. Supply module,
inverter, and site JSON files; receive individual **PASS / WARN / FAIL** checks,
an auditable calculation record, and a printable report. Use the same engine
from Python or an automated design pipeline.

> **Design aid only.** Verify manufacturer datasheets, sizing tools, listing
> instructions, and locally adopted code. Obtain licensed professional
> sign-off before construction. PASS is not certification. All bundled
> equipment and site examples are **illustrative**, not real products or
> verified weather stations.

## Features

- Manufacturer-coefficient cold Voc, with the NEC Table 690.7(A) factor method
  alongside it for comparison.
- NOCT/NMOT or fixed racking temperature rise; hot Vmp, cold Vmp, startup,
  operating MPPT limits, and the separate full-power voltage window.
- Explicit end-of-life voltage allowance, missing-Vmp-coefficient warning,
  irradiance scaling, and bifacial current gain.
- Separate per-MPPT short-circuit hard limits and operating-current clipping
  warnings; input capacity, preliminary series fusing, DC power, and ILR.
- Ranked feasible string configurations with MPPT balance and voltage scoring.
- Standalone HTML with inline SVG voltage-window and current-headroom charts,
  print styles, and automatic light/dark appearance; Markdown and versioned JSON.
- Python standard library only at runtime. No account, network, or vendor API
  is needed to run a calculation.

## Install

Python **3.9 or newer**:

```sh
pip install git+https://github.com/Pinnnnnneapple/pvstring
```

Or from source:

```sh
git clone https://github.com/Pinnnnnneapple/pvstring
cd pvstring
python -m pip install -e '.[dev]'
pvstring --version
```

Without installation, run `PYTHONPATH=src python3 -m pvstring` in place of
`pvstring`. The source tree needs no downloaded runtime dependencies.

## Quickstart

The residential example uses **−18 °C** minimum ambient, **33 °C** hot ambient,
a generic 410 W module, and a generic 5 kW inverter. Eight modules on each of
two strings gives 6.56 kW DC.

```sh
pvstring check \
  --module examples/residential/module.json \
  --inverter examples/residential/inverter.json \
  --site examples/residential/site.json \
  --modules-per-string 8 --strings-per-mppt 1,1 \
  --html report.html --json report.json --md report.md
```

Actual output from the supplied files:

```text
pvstring — PASS
Design: 8 modules/string; strings/MPPT 1,1
DC: 6.560 kW | AC: 5.000 kW | ILR: 1.312
Hot cell: 64.25 °C | String range: 5–14

PASS  Cold Voc / inverter maximum: 333.044 (limit 600)
PASS  Cold Voc / module system voltage: 333.044 (limit 1000)
PASS  Hot EOL Vmp / MPPT minimum: 208.667 (limit 120)
PASS  Cold Vmp / MPPT maximum: 285.765 (limit 550)
PASS  Start voltage: 266.777 (limit 120)
PASS  Typical Vmp / full-power window: 235.123 (limit [180, 480])
PASS  NEC table comparison: 352.112 (limit comparison only (V/string))
PASS  MPPT 1 string capacity: 1 (limit 2)
PASS  MPPT 1 maximum Isc: 17.716 (limit 25)
PASS  MPPT 1 operating current: 13.314 (limit 16)
PASS  MPPT 1 series fusing: 1 (limit 3 parallel strings trigger simplified fuse rule)
PASS  MPPT 2 string capacity: 1 (limit 2)
PASS  MPPT 2 maximum Isc: 17.716 (limit 25)
PASS  MPPT 2 operating current: 13.314 (limit 16)
PASS  MPPT 2 series fusing: 1 (limit 3 parallel strings trigger simplified fuse rule)
PASS  Maximum DC power: 6560 (limit 7500)
PASS  DC/AC ratio (ILR): 1.312 (limit [1.1, 1.35])

Design aid only. Verify the original manufacturer datasheets and tools, equipment listing instructions, and local code with the authority having jurisdiction. Obtain licensed professional sign-off before construction. PASS is not certification.
```

Each voltage check is in V/string, current check in A/MPPT, and power check
in W. The JSON retains unrounded values and explains every check.

Open the committed [passing HTML report](examples/output/residential-pass.html)
in a browser and print it, or inspect the [JSON](examples/output/residential-pass.json)
and [Markdown](examples/output/residential-pass.md). HTML reports have no
external resources and work offline.

### Catch a cold over-voltage design

```sh
pvstring check \
  --module examples/residential/module.json \
  --inverter examples/residential/inverter.json \
  --site examples/residential/site.json \
  --array examples/residential/failing-array.json
```

This exits **2**. Selected actual output:

```text
pvstring — FAIL
Design: 16 modules/string; strings/MPPT 1,1
DC: 13.120 kW | AC: 5.000 kW | ILR: 2.624
Hot cell: 64.25 °C | String range: 5–14

FAIL  Cold Voc / inverter maximum: 666.088 (limit 600)
```

The [failing report](examples/output/residential-fail.html) also exposes the
cold tracking-window and maximum DC-power failures, rather than stopping at
the first issue.

### Find a range and rank alternatives

```sh
pvstring range --module examples/residential/module.json \
  --inverter examples/residential/inverter.json --site examples/residential/site.json

pvstring suggest --module examples/residential/module.json \
  --inverter examples/residential/inverter.json --site examples/residential/site.json \
  --target-kw 6.5 --top 5
```

`range` gives the inclusive operating count limits and a typical full-power
recommendation. It does not establish acceptable currents or total power.
`suggest` returns options with **no FAIL checks**, ordered by target power,
MPPT balance, nominal voltage proximity, voltage headroom, and warning count.
WARN checks remain visible. Identical MPPT permutations are represented once;
`0` means an unused MPPT. All strings in a design use the same series count.

Use `--tmin -25 --thigh 35 --racking roof` on `check`, `range`, or `suggest`
to override site assumptions. An explicit racking choice replaces the NOCT
model. The 1500 V example is in [examples/commercial_1500v](examples/commercial_1500v)
with its [generated report](examples/output/commercial-1500v-pass.html).

### JSON pipelines

```sh
pvstring check --module m.json --inverter inv.json --site site.json \
  --modules-per-string 12 --strings-per-mppt 2,1 --json -
```

`--json -` emits only JSON on stdout; input errors go to stderr. Check exit
codes still communicate the design status. `--md -` similarly emits only
Markdown. `range` and `suggest` also accept `--json PATH` or `--json -`.
Reports include `schema_version: 1`; all input assumptions accompany a full
design result. See [the input and API reference](docs/input-reference.md).

## Use from Python

```python
from pvstring import Array
from pvstring.calc import evaluate, suggest
from pvstring.loaders import load_inverter, load_module, load_site
from pvstring.report import html_report

module = load_module("examples/residential/module.json")
inverter = load_inverter("examples/residential/inverter.json")
site = load_site("examples/residential/site.json")

result = evaluate(module, inverter, site, Array(8, (1, 1)))
assert result.status == "PASS"
print(result.metrics["dc_ac_ratio"])  # 1.312
with open("report.html", "w", encoding="utf-8") as handle:
    handle.write(html_report(result))

for option in suggest(module, inverter, site, target_dc_kw=6.5)[:5]:
    print(option.array, option.result.status, option.score)
```

`check_design(...)` returns the list of `Check` objects. `evaluate(...)`
adds the inputs, limits, and intermediate metrics. `result.to_dict()` and
`json_report(result)` preserve calculation precision. Raw voltage metrics
are **per module** and raw current metrics **per string**; check-table values
already account for the relevant series or parallel count.

## Add real datasheets

```sh
pvstring library
pvstring show-template module > my-module.json
pvstring show-template inverter > my-inverter.json
pvstring show-template site > my-site.json
```

Replace every illustrative value with a documented rating from the product's
current datasheet and installation manual. Record manufacturer, revision,
source, climate station, and temperature basis in your project records.
Names can contain the identifying revision; unknown JSON keys are rejected to
catch typos. Do not substitute whole-inverter current for per-MPPT current or
confuse the full-power window with the wider operating MPPT window. Present
models assume uniform ratings across the inverter's MPPTs.

| Built-in ID | Illustrative equipment |
| --- | --- |
| `generic-410` | 410 W mono PERC 108-cell module |
| `generic-550` | 550 W 144-cell bifacial module |
| `generic-5kw` | 5 kW, 2-MPPT string inverter |
| `generic-10kw` | 10 kW, 3-phase, 3-MPPT inverter |
| `generic-100kw-1500v` | 100 kW, 1500 V, 10-MPPT inverter |

Select packaged equipment with `--module builtin:generic-410` and
`--inverter builtin:generic-5kw`. No real brands are included or endorsed.

### Units and reference assumptions

| Input | Convention |
| --- | --- |
| Power / voltage / current | W / V / A |
| Temperature / irradiance / altitude | °C / W/m² / m |
| Numeric coefficients | Percent/°C: `-0.27` means `-0.27%/°C` |
| Explicit coefficient strings | `"-0.27%/°C"`; voltage coefficients also accept `"-0.134 V/°C"` |
| Bifaciality / rear ratio | Fractions, e.g. `0.7` / `0.15` |
| Default lifetime allowance | `0.5` percent/year × `10` years; 95% voltage retention sensitivity |
| Typical ILR screening band | 1.10–1.35; advisory, project-dependent |

| `--racking` | Illustrative fixed cell-to-ambient rise |
| --- | ---: |
| `open-rack` | +25 °C |
| `roof` | +30 °C |
| `bipv` | +40 °C |

Without `--racking`, the default is the module's NOCT/NMOT irradiance model.
A site can instead specify `fixed_delta_t`; do not combine it with `racking`.
These rises are assumptions to verify for the actual mounting arrangement.

## Methodology

With coefficients converted to fractions per °C:

```text
Tcell_hot = Thigh + (NOCT - 20) / 800 * G
Voc_cold = Voc_stc * [1 + beta_Voc * (Tmin - 25)]
Vmp_hot_eol = Vmp_stc * [1 + gamma_Vmp * (Tcell_hot - 25)] * retention
Nmax_voltage = floor(min(inverter_Vmax, module_system_Vmax) / Voc_cold)
Nmin_tracking = ceil(MPPT_min / Vmp_hot_eol)
Isc_corrected = Isc_stc * [1 + alpha_Isc * (Tcell_hot - 25)]
                * G/1000 * (1 + bifaciality * rear_ratio)
Imax_circuit_per_MPPT = Isc_corrected * 1.25 * parallel_strings
ILR = installed_front_STC_DC_power / rated_AC_power
```

The string range also includes the cold-Vmp operating ceiling and a hot-Voc
startup screen. Manufacturer-coefficient Voc controls; the factor-table result
is a comparison, not an additional independent limit. Missing `gamma_vmp`
uses the relative `beta_voc` with a warning. The current model uses `alpha_isc`
for Imp as a disclosed proxy. Three or more parallel strings require an
explicit per-string fuse rating under the simplified protection screen.

Read [methodology.md](docs/methodology.md) for the full factor table, formulas,
rounding rules, assumptions, and references to NEC **2023** 690.7, 690.8,
690.9, [IEC 62548-1](https://webstore.iec.ch/en/publication/110893), ASHRAE
climatic design conditions, and the
[Solar ABCs Expedited Permit Process](https://www.solarabcs.org/about/publications/reports/expedited-permit/)
design-temperature resources. IEC is context for non-US users; this release
does not implement an IEC compliance mode.

## Exit codes

| Code | Meaning |
| ---: | --- |
| 0 | `check`: all checks PASS; other commands completed / feasible options found |
| 1 | `check`: at least one WARN, no FAIL |
| 2 | `check`: at least one FAIL; `range`/`suggest`: no feasible result |
| 3 | Input, argument, JSON validation, or file I/O error |

Warnings deserve review; scripts should handle exit 1 explicitly. A proposed
configuration from `suggest` can still contain WARNs even though the command
successfully exits 0. Inspect each option's status and check list.

## Limitations and disclaimer

This is preliminary engineering screening, not an energy-yield simulation,
manufacturer approval, permit drawing, or electrical-code compliance engine.
It does not verify conductor ampacity, complete OCPD/protection coordination,
rapid shutdown, arc-fault protection, grounding, grid interconnection,
equipment listing, dwelling voltage restrictions, altitude insulation limits,
or all manufacturer backfeed constraints. Fusing checks are deliberately
simplified and proposed integer-A ratings may not be commercially available.

The model assumes crystalline-silicon coefficients, a common series count,
uniform MPPT ratings, and equal strings without shade or mismatch. It omits
irradiance-dependent voltage, transient thermal conditions, radiant
supercooling, and wiring losses. A power-degradation rate applied to voltage
is a sensitivity allowance, not a validated aging law. The site minimum must
be chosen conservatively for the project; ASHRAE extreme annual mean minima
and absolute observed record lows are different statistics.

**Verify every input and result with manufacturer tools and the authority
having jurisdiction. A licensed professional must review and sign off on the
actual design. Use at your own risk; see the MIT warranty disclaimer.**

## Development and roadmap

```sh
PYTHONPATH=src python3 -m pytest -q
```

CI covers Python 3.9–3.13 on Ubuntu, Windows, and macOS, installs the package,
runs the tests, and checks the residential CLI example. Tests cover hand
calculations, coefficient units, factor-table boundaries, current and fuse
rules, feasible-option ranking, input errors, CLI exit codes, and escaped
standalone reports.

Potential future work: individual MPPT/input ratings, mixed string lengths,
manufacturer-specific startup and derating curves, explicitly selected code
profiles, validated voltage-aging inputs, and datasheet provenance metadata.
The current generic library will remain clearly separated from real products.

Contributions are welcome; see [CONTRIBUTING.md](CONTRIBUTING.md) and
[CHANGELOG.md](CHANGELOG.md). Report a reproducible input and the expected
engineering behavior when opening an issue.

## License

[MIT](LICENSE). Copyright (c) 2026 pvstring contributors.
