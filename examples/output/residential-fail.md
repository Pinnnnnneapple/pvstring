# PV string design report

Status: FAIL

Design aid only. Verify manufacturer specifications and installation instructions, applicable local electrical codes, and site conditions. Obtain qualified professional review and licensed professional sign-off before installation.

Voltage metrics: per module (V); currents: per string (A); temperatures: °C; power: W.

## Module

| Field | Value |
| --- | --- |
| name | Generic 410W mono PERC 108-cell (illustrative) |
| pmax\_stc | 410 |
| voc | 37.3 |
| isc | 13.9 |
| vmp | 31.4 |
| imp | 13.06 |
| beta\_voc | -0.27%/°C |
| alpha\_isc | 0.05%/°C |
| gamma\_pmax | -0.35%/°C |
| gamma\_vmp | -0.32%/°C |
| noct | 45 |
| nmot | — |
| bifacial | False |
| bifaciality | 0 |
| max\_system\_voltage | 1,000 |
| max\_series\_fuse\_rating | 25 |

## Inverter

| Field | Value |
| --- | --- |
| name | Generic 5kW 2-MPPT string inverter (illustrative) |
| max\_dc\_voltage | 600 |
| start\_voltage | 120 |
| mppt\_min | 120 |
| mppt\_max | 550 |
| full\_power\_mppt\_min | 180 |
| full\_power\_mppt\_max | 480 |
| nominal\_dc\_voltage | 300 |
| num\_mppts | 2 |
| max\_input\_current\_per\_mppt | 16 |
| max\_isc\_per\_mppt | 25 |
| strings\_per\_mppt | 2 |
| max\_dc\_power | 7,500 |
| ac\_rated\_power | 5,000 |

## Site

| Field | Value |
| --- | --- |
| name | Illustrative cold residential site (not a measured station) |
| tmin | -18 |
| thigh | 33 |
| irradiance | 1,000 |
| rear\_irradiance\_ratio | 0 |
| altitude | — |
| racking | — |
| fixed\_delta\_t | — |
| typical\_cell\_temperature | 45 |
| degradation\_percent\_per\_year | 0.5 |
| design\_years | 10 |

## Array

| Field | Value |
| --- | --- |
| modules\_per\_string | 16 |
| strings\_per\_mppt | (1, 1) |
| fuse\_rating | — |

## Metrics

| Field | Value |
| --- | --- |
| cell\_temperature\_hot | 64.25 |
| voc\_cold | 41.63 |
| voc\_cold\_table | 44.01 |
| voc\_hot | 33.35 |
| vmp\_hot | 27.46 |
| vmp\_hot\_eol | 26.08 |
| vmp\_cold | 35.72 |
| vmp\_typical | 29.39 |
| isc\_hot | 14.17 |
| isc\_design | 17.72 |
| imp\_hot | 13.31 |
| dc\_power | 13,120 |
| dc\_ac\_ratio | 2.62 |

## Limits

| Field | Value |
| --- | --- |
| min\_modules | 5 |
| max\_modules | 14 |
| recommended\_min | 7 |
| recommended\_max | 14 |

## Checks

| Check | Status | Value | Limit | Explanation | Reference |
| --- | --- | --- | --- | --- | --- |
| Cold Voc / inverter maximum | FAIL | 666.09 | 600 | V/string at cold design temperature; manufacturer coefficient method. Dawn cell temperature is approximated by ambient. | NEC 2023 690.7(A)(1); inverter datasheet |
| Cold Voc / module system voltage | PASS | 666.09 | 1,000 | V/string must respect the module insulation/system-voltage rating as well as the inverter. | Module datasheet; NEC 2023 690.7 |
| Hot EOL Vmp / MPPT minimum | PASS | 417.33 | 120 | V/string after the explicit linear voltage-degradation allowance; minimum operating tracking voltage. | Inverter datasheet; design allowance |
| Cold Vmp / MPPT maximum | FAIL | 571.53 | 550 | V/string at cold design temperature must stay within the operating tracking window. | Inverter datasheet |
| Start voltage | PASS | 533.55 | 120 | Hot open-circuit V/string screens restart capability. Low-light start behavior requires manufacturer verification. | Inverter datasheet; simplified startup screen |
| Typical Vmp / full-power window | PASS | 470.25 | \[180, 480\] | V/string at the assumed typical cell temperature; full-power window is advisory and distinct from the operating window. | Inverter datasheet |
| NEC table comparison | PASS | 704.22 | comparison only (V/string) | Table result is informative. The available manufacturer coefficient controls this design, so methods are not mixed. | Per NEC Table 690.7(A) |
| MPPT 1 string capacity | PASS | 1 | 2 | Parallel string count versus physical/manufacturer input capacity; 0 denotes unused. | Inverter datasheet |
| MPPT 1 maximum Isc | PASS | 17.72 | 25 | A/MPPT: temperature- and irradiance-corrected Isc × bifacial gain × 1.25 × parallel strings. Conservative comparison to inverter short-circuit rating. | NEC 2023 690.8(A)(1); inverter datasheet |
| MPPT 1 operating current | PASS | 13.31 | 16 | A/MPPT: Imp uses the Isc temperature/irradiance multiplier as a screening proxy. Exceeding operating input current may clip production. | Inverter datasheet; Imp model assumption |
| MPPT 1 series fusing | PASS | 1 | 3 parallel strings trigger simplified fuse rule | No series fuse triggered by this screen. Manufacturer instructions and inverter backfeed may still require protection. | NEC 2023 690.9 (simplified) |
| MPPT 2 string capacity | PASS | 1 | 2 | Parallel string count versus physical/manufacturer input capacity; 0 denotes unused. | Inverter datasheet |
| MPPT 2 maximum Isc | PASS | 17.72 | 25 | A/MPPT: temperature- and irradiance-corrected Isc × bifacial gain × 1.25 × parallel strings. Conservative comparison to inverter short-circuit rating. | NEC 2023 690.8(A)(1); inverter datasheet |
| MPPT 2 operating current | PASS | 13.31 | 16 | A/MPPT: Imp uses the Isc temperature/irradiance multiplier as a screening proxy. Exceeding operating input current may clip production. | Inverter datasheet; Imp model assumption |
| MPPT 2 series fusing | PASS | 1 | 3 parallel strings trigger simplified fuse rule | No series fuse triggered by this screen. Manufacturer instructions and inverter backfeed may still require protection. | NEC 2023 690.9 (simplified) |
| Maximum DC power | FAIL | 13,120 | 7,500 | Installed front-side STC nameplate W versus inverter permitted array power. Bifacial energy gain is not added to STC nameplate power. | Inverter datasheet |
| DC/AC ratio (ILR) | WARN | 2.62 | \[1.1, 1.35\] | STC DC W / AC rated W. The typical 1.10–1.35 screening band is project-dependent, not a code requirement. | Design guidance |
