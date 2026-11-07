# Input reference

Inputs use JSON objects with snake_case keys. Unknown fields are rejected;
spelling mistakes are not silently ignored. Numeric runtime values must be
finite: NaN and positive or negative infinity are invalid. Use JSON numbers,
not unit-bearing strings, except for the temperature coefficients described
below. All powers are W, voltages V, currents A, irradiances W/m², temperatures
°C, and altitude m. Ratios are fractions, not percentages.

## Module

| Key | Meaning | Default |
| --- | --- | --- |
| `name` | Equipment label | Required |
| `pmax_stc` | STC maximum power, W | Required |
| `voc` | STC open-circuit voltage, V | Required |
| `isc` | STC short-circuit current, A | Required |
| `vmp` | STC maximum-power voltage, V | Required |
| `imp` | STC maximum-power current, A | Required |
| `beta_voc` | Voc temperature coefficient | Required |
| `alpha_isc` | Isc temperature coefficient | Required |
| `gamma_pmax` | Pmax temperature coefficient | Required |
| `gamma_vmp` | Vmp temperature coefficient | `null`, warned relative `beta_voc` proxy |
| `noct` | Nominal operating cell temperature, °C | `45` |
| `nmot` | Optional nominal module operating temperature, °C; when supplied, used for the nominal-temperature model | `null` |
| `bifacial` | Whether rear irradiance contributes | `false` |
| `bifaciality` | Rear/front response fraction | `0` |
| `max_system_voltage` | Module system-voltage rating, V | `1000` |
| `max_series_fuse_rating` | Module maximum series fuse rating, A | `25` |

`beta_voc` accepts a numeric percent per °C, such as `-0.27`, an explicit
percent string such as `"-0.27%/°C"`, or an absolute string such as
`"-0.134 V/°C"`. `gamma_vmp` supports the same relative or absolute voltage
forms. Absolute coefficients are normalized by `voc` or `vmp`, respectively.
`alpha_isc` and `gamma_pmax` accept numeric percent per °C or explicit percent
strings. Temperature unit spellings `°C`, `degC`, and `C` are accepted in
coefficient strings, case-insensitively. Unitless numeric strings and units
such as A/°C or W/°C are rejected. A numeric `-0.27` is not `-0.27 V/°C` and is not a fractional
coefficient of `-0.27 /°C`. `gamma_pmax` does not determine `gamma_vmp`.
Require positive electrical ratings, `vmp < voc`, and `imp <= isc`.
`vmp * imp / pmax_stc` must be within 5% of 1; a larger discrepancy raises
an error identifying possible W/V/A unit confusion. `beta_voc`, `gamma_pmax`,
and supplied `gamma_vmp` must be negative; `alpha_isc` is nonnegative.
Supplied NOCT/NMOT values must be strictly between 20 and 100 °C.
`bifacial` must be a boolean; bifaciality must be in [0, 1], positive for a
bifacial module, and zero for a monofacial module.

## Inverter

All fields below are supplied explicitly. Current and string limits are per
MPPT, rather than totals across the inverter.

| Key | Meaning |
| --- | --- |
| `name` | Equipment label |
| `max_dc_voltage` | Absolute maximum DC input voltage, V |
| `start_voltage` | Startup voltage threshold, V |
| `mppt_min`, `mppt_max` | Tracking voltage range, V |
| `full_power_mppt_min`, `full_power_mppt_max` | Full-power tracking voltage range, V |
| `nominal_dc_voltage` | Nominal DC operating voltage, V |
| `num_mppts` | Number of independent MPPTs |
| `max_input_current_per_mppt` | Maximum operating input current per MPPT, A |
| `max_isc_per_mppt` | Maximum short-circuit input current per MPPT, A |
| `strings_per_mppt` | Maximum parallel strings allowed on each MPPT |
| `max_dc_power` | Maximum accepted array STC nameplate power, W |
| `ac_rated_power` | Rated AC power, W |

Ratings must be positive; `num_mppts` and the string capacity must be positive
integers, excluding booleans and integer-valued floats. Voltage windows must
satisfy `mppt_min <= full_power_mppt_min <= full_power_mppt_max <= mppt_max
<= max_dc_voltage`. Nominal voltage must be within the operating window,
startup voltage cannot exceed maximum DC voltage, and operating current
cannot exceed the short-circuit current rating.

## Site

| Key | Meaning | Default |
| --- | --- | --- |
| `name` | Site label | Required |
| `tmin` | Design minimum ambient temperature, °C | Required |
| `thigh` | Design hot ambient temperature, °C | Required |
| `irradiance` | Front irradiance for hot/current calculations, W/m² | `1000` |
| `rear_irradiance_ratio` | Rear irradiance divided by front irradiance | `0` |
| `altitude` | Altitude metadata, m; no automatic correction | `null` |
| `racking` | Fixed-rise selection: `open-rack`, `roof`, or `bipv` | `null` |
| `fixed_delta_t` | Explicit nonnegative cell-to-ambient rise, °C; mutually exclusive with racking | `null` |
| `typical_cell_temperature` | Cell temperature for typical operating voltage, °C | `45` |
| `degradation_percent_per_year` | Linear annual degradation, percent/year | `0.5` |
| `design_years` | Years used in the retention sensitivity check | `10` |

Fixed racking rises are illustrative: `open-rack` = 25 °C, `roof` = 30 °C,
and `bipv` = 40 °C. With no racking or explicit rise, use the NOCT/NMOT
irradiance model. Do not add a fixed rise to the NOCT/NMOT rise.
Site inputs specifying both `fixed_delta_t` and `racking` are rejected.
The CLI `--racking` override clears a site's existing `fixed_delta_t` before
revalidating the site, so it replaces an explicit rise with the selected
racking assumption.
All three site temperatures must lie in [-100, 100] °C, with `tmin <= thigh`
and `typical_cell_temperature >= tmin`. Evaluation additionally requires the
typical cell temperature not exceed modeled hot cell temperature. Irradiance
must be positive; rear irradiance ratio must be in [0, 1]. Annual degradation
is nonnegative, design years is a nonnegative integer, and their product must
be less than 100%. Booleans and numeric strings are not accepted as numbers.
The default retention is 0.95; applying it to voltage is a heuristic,
not a verified physical voltage-degradation prediction.

## Array

| Key | Meaning | Default |
| --- | --- | --- |
| `modules_per_string` | Positive integer series module count | Required |
| `strings_per_mppt` | Per-MPPT string counts, in MPPT order | Required |
| `fuse_rating` | Explicit per-string fuse rating, A | `null` |

In the Python model, `strings_per_mppt` is a tuple of integer counts; its JSON
representation is an array and its CLI representation is comma-separated
counts. Include one count per MPPT, including `0` for an unused MPPT. These
are actual counts; the inverter's identically named field is a capacity limit.
Each count must be a nonnegative integer, excluding booleans and floats;
the list must be nonempty and at least one count must be positive. Array
construction converts a list to a tuple. Evaluation rejects a count-list
length different from `inverter.num_mppts`. A supplied fuse rating must be
positive and finite.
At least three parallel strings on any MPPT conservatively require an explicit
`fuse_rating`. Two-string reverse-current screening also applies. See the
[methodology](methodology.md) for current factors and preliminary fuse limits.

## Files, built-ins, and CLI

Equipment options accept a JSON path or a `builtin:` reference. Available
generic module references are `generic-410` and `generic-550`; generic inverter
references are `generic-5kw`, `generic-10kw`, and `generic-100kw-1500v`.
For example, select a module with `--module builtin:generic-410`.
These records are generic examples, not verified branded datasheets.

The `check` subcommand evaluates a supplied array. `range` calculates series
bounds and `suggest` ranks feasible configurations; both take the same module,
inverter, and site options. The residential check uses separate input files:

```sh
pvstring check --module examples/residential/module.json --inverter examples/residential/inverter.json --site examples/residential/site.json --modules-per-string 8 --strings-per-mppt 1,1
```

Confirm equipment ratings and climate provenance before using a calculation
for a project. A passing report does not provide certification or final
conductor, OCPD, arc-fault, rapid-shutdown, grid, or protection verification.
