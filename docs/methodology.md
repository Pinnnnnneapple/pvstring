# Calculation methodology

pvstring supports preliminary photovoltaic string sizing. A passing result is
not certification, equipment approval, or a finding of code compliance.
Generic built-in equipment records are illustrative inputs, not verified
manufacturer datasheets. Confirm ratings, installation instructions, local code
adoption, and site conditions for an actual design.

## Units and coefficient conventions

STC means a cell temperature of 25 °C and front irradiance of 1000 W/m².
Temperatures are in °C, voltages in V, currents in A, and powers in W.
A numeric temperature coefficient is percent per °C: `-0.27` means
`-0.27%/°C`, or a relative coefficient of `-0.0027 /°C`.
For an absolute voltage coefficient `b` in V/°C, the relative coefficient
is `b / V_stc` for the corresponding voltage. Thus:

```text
V(T) = V_stc * (1 + b_relative * (T - 25))
     = V_stc + b_absolute * (T - 25)
```

Use manufacturer coefficients where supplied. A missing `gamma_vmp` uses the
relative `beta_voc` as an explicit, warned proxy for the Vmp coefficient.
`gamma_pmax` alone cannot determine `gamma_vmp`: power depends on voltage and
current, whose temperature responses need not be interchangeable.

## Cold open-circuit voltage

The cold case assumes cell temperature equals `tmin`. At dawn a module can be
near ambient while sufficient light establishes open-circuit voltage. Do not
scale cold Voc linearly with irradiance. Radiant supercooling below ambient is
not modeled; site-specific assessment may require a lower design temperature.

```text
voc_cold = voc * (1 + beta_voc_relative * (tmin - 25))
string_voc_cold = modules_per_string * voc_cold
voltage_limit = min(inverter.max_dc_voltage, module.max_system_voltage)
maximum_voc_series_count = floor(voltage_limit / voc_cold)
```

Manufacturer temperature-coefficient correction is the preferred approach
under NEC 2023 690.7(A)(1), subject to the equipment instructions and the
authority having jurisdiction. The following Table 690.7(A) factors are offered
for comparison only; they do not replace the coefficient calculation or define
a separate compliance mode. The comparison is `voc * factor` per module.

| Minimum ambient temperature (°C), integer lookup | Factor |
| --- | ---: |
| 25 and above | 1.00 |
| 24 to 20 | 1.02 |
| 19 to 15 | 1.04 |
| 14 to 10 | 1.06 |
| 9 to 5 | 1.08 |
| 4 to 0 | 1.10 |
| -1 to -5 | 1.12 |
| -6 to -10 | 1.14 |
| -11 to -15 | 1.16 |
| -16 to -20 | 1.18 |
| -21 to -25 | 1.20 |
| -26 to -30 | 1.21 |
| -31 to -35 | 1.23 |
| -36 to -40 | 1.25 |

For a continuous temperature below 25 °C, conservatively use `floor(temperature)`
toward the colder integer for lookup: 19.9 °C becomes 19 °C and gives 1.04.
Temperatures at or above 25 °C use 1.00.
For any temperature below -40 °C the table comparison is unavailable. The
manufacturer coefficient calculation still works within the validity of that
coefficient.

## Hot cell temperature and operating voltage

With NOCT (or supplied NMOT as the nominal operating-temperature input), the
simple irradiance model is:

```text
T_cell_hot = thigh + (T_nominal - 20) * irradiance / 800
```

NOCT and NMOT have different measurement conditions; treating either as the
nominal-temperature input is a simplified estimate. The fixed-rise alternative
is `T_cell_hot = thigh + fixed_delta_t`. Illustrative racking rises are
25 °C for `open-rack`, 30 °C for `roof`, and 40 °C for `bipv`. These are
assumptions, not validated installation temperatures. Supplying
`fixed_delta_t` together with `racking` in site inputs is rejected. The CLI
`--racking` override clears an existing `fixed_delta_t` before site validation.
With neither a fixed rise nor a racking selection, use
the nominal operating-temperature model. NMOT takes precedence over NOCT when
supplied. If both are absent, a fixed rise or racking selection is required.
Hot cell temperatures above 150 °C are rejected, and evaluation requires
`tmin <= typical_cell_temperature <= T_cell_hot`.

```text
vmp_hot = vmp * (1 + gamma_vmp_relative * (T_cell_hot - 25))
vmp_cold = vmp * (1 + gamma_vmp_relative * (tmin - 25))
vmp_typical = vmp * (1 + gamma_vmp_relative * (typical_cell_temperature - 25))
voc_hot = voc * (1 + beta_voc_relative * (T_cell_hot - 25))
retention = 1 - (degradation_percent_per_year / 100) * design_years
vmp_hot_eol = vmp_hot * retention
```

The default retention is `1 - 0.005 * 10 = 0.95`. Applying power degradation
retention to voltage is a heuristic sensitivity check, not a physically
verified prediction of voltage aging. Reject parameters that make retention
non-positive. Startup compares hot open-circuit string voltage with the startup
threshold to screen hot restart. Tracking checks use hot end-of-life Vmp for
the minimum and cold Vmp for the maximum. The full-power MPPT range is an
advisory check at `typical_cell_temperature`.
A voltage threshold alone does not establish actual startup under weak light.

The inclusive operating and recommended series bounds are:

```text
minimum_series_count = max(1, ceil(inverter.mppt_min / vmp_hot_eol),
                           ceil(inverter.start_voltage / voc_hot))
maximum_series_count = min(floor(voltage_limit / voc_cold),
                           floor(inverter.mppt_max / vmp_cold))
recommended_min = max(minimum_series_count,
                      ceil(inverter.full_power_mppt_min / vmp_typical))
recommended_max = min(maximum_series_count,
                      floor(inverter.full_power_mppt_max / vmp_typical))
```

Multiply each relevant module voltage by the series count to check a chosen
array. Apply the cold Voc ceiling independently. An empty intersection of
integer bounds means no series count meets those assumptions.

## Irradiance, bifacial gain, and current

Front-side irradiance first scales current by `irradiance / 1000`.
For a bifacial module, the simplified gain is
`1 + bifaciality * rear_irradiance_ratio`; for a monofacial module it is 1.
Rear ratio is relative to front irradiance. This ignores rear nonuniformity,
spectral effects, shading, and current mismatch.

```text
current_scale = (irradiance / 1000) * bifacial_gain
hot_current_factor = 1 + alpha_isc_relative * (T_cell_hot - 25)
isc_corrected = isc * current_scale * hot_current_factor
imp_operating = imp * current_scale * hot_current_factor
isc_design = 1.25 * isc_corrected
mppt_isc_design = strings_on_mppt * isc_design
mppt_imp_operating = strings_on_mppt * imp_operating
```

The operating Imp calculation explicitly uses `alpha_isc` as a proxy for the
Imp coefficient. It is not a manufacturer-specified Imp temperature model.
The 1.25 maximum-circuit-current factor is compared conservatively with the
inverter's maximum Isc per MPPT. Operating Imp is compared with the separate
maximum input-current rating, with an excess reported as a warning about
potential clipping. Exceeding maximum Isc is a failure.
Confirm the manufacturer's rating definitions;
this conservative comparison does not establish conductor or OCPD sizing.

## Parallel strings and preliminary fusing

For each MPPT with at least three parallel strings, this tool conservatively
requires an explicit `fuse_rating`. The preliminary per-string range is:

```text
minimum_fuse_rating = 1.25 * isc_design = 1.5625 * isc_corrected
minimum_fuse_rating <= fuse_rating <= module.max_series_fuse_rating
```

An empty range requires a design change. This check does not select a
commercial fuse, establish its DC voltage/interruption rating, or apply
temperature derating or equipment-specific exceptions. With two parallel
strings, check reverse current from the other string as well; a first-pass
estimate for `n` parallel strings is `(n - 1) * isc_design`, compared against
the module's maximum series fuse rating. Exceeding it also triggers a required
explicit fuse, including for two strings. A supplied fuse is checked against
the preliminary range on every used MPPT, even if no fuse requirement triggers.
That nameplate rating is a screening
limit here, not a separately verified reverse-current withstand rating.
Equipment instructions govern whether protection is required even where the
simple three-string rule does not trigger.

## Power and input limits

```text
module_count = modules_per_string * sum(strings_per_mppt)
array_power_stc = module_count * pmax_stc
dc_ac_ratio = array_power_stc / inverter.ac_rated_power
```

Compare `array_power_stc` to `inverter.max_dc_power` using STC nameplate power.
Do not replace this check with a temperature- or degradation-reduced power.
`gamma_pmax` is validated as a datasheet coefficient but is not used to
calculate operating power or energy yield. Check MPPT count, strings per MPPT, per-MPPT currents,
voltage windows, and module system-voltage limits independently. Unused MPPTs
have a zero string count. Nominal DC voltage is a reference operating point,
not a substitute for the inverter's specified voltage limits. A DC/AC ratio
outside 1.10–1.35 is an advisory warning, not a code failure. Rear irradiance
on a monofacial module and altitude above 2000 m also generate warnings;
neither applies an automatic rear-current or altitude correction.

## Climate sources, standards, and scope

Select a defensible local design minimum and hot ambient temperature.
ASHRAE extreme annual mean minimum dry-bulb and 2% annual dry-bulb conditions,
and the Solar ABCs design-temperature map, provide reference climate context;
they describe different statistical conditions and should be identified in
the project record. `altitude` is metadata and does not apply an automatic
voltage, current, or insulation correction.

Primary references:

- [NFPA 70 / NEC](https://www.nfpa.org/codes-and-standards/nfpa-70-standard-development/70): consult the 2023 edition, including 690.7(A)(1) and Table 690.7(A).
- [Solar ABCs expedited permitting resources](https://www.solarabcs.org/about/publications/reports/expedited-permit/): design-temperature and permitting context.
- [Littelfuse photovoltaic fuse sizing application guide](https://www.littelfuse.com/ja-jp/assetdocs/photovoltaic-fuse-sizing-application-guide?assetguid=1f1616ee-aada-4a68-b4fc-8ba2363bcad2): manufacturer application guidance with the voltage correction-factor table; not a module-specific datasheet or a substitute for the adopted NEC edition.
- [IEC 62548-1:2023+AMD1:2025](https://webstore.iec.ch/en/publication/110893): consolidated PV array design requirements, referenced for context; pvstring has no IEC compliance mode.
- [ASHRAE climatic design information](https://ashrae-meteo.info/): climate reference context.
- [ASHRAE Handbook—Fundamentals (2017), Chapter 14](https://handbook.ashrae.org/Handbooks/F17/IP/f17_ch14/f17_ch14_ip.aspx): definitions of annual design conditions and extreme annual temperatures; record the source edition and station period used.

These references do not certify the tool or any design. Final conductor and
OCPD sizing, arc-fault protection, rapid shutdown, grid interconnection,
grounding, protection coordination, and equipment/protection verification are
outside this calculation. The model also omits detailed thermal dynamics,
irradiance-dependent voltage, shading, mismatch, wiring losses, and energy
yield. Obtain the equipment instructions and qualified local design review.
