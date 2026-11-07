# PV string design report

Status: PASS

Design aid only. Verify manufacturer specifications and installation instructions, applicable local electrical codes, and site conditions. Obtain qualified professional review and licensed professional sign-off before installation.

Voltage metrics: per module (V); currents: per string (A); temperatures: °C; power: W.

## Module

| Field | Value |
| --- | --- |
| name | Generic 550W 144-cell bifacial (illustrative) |
| pmax\_stc | 550 |
| voc | 49.5 |
| isc | 13.9 |
| vmp | 41.8 |
| imp | 13.16 |
| beta\_voc | -0.27%/°C |
| alpha\_isc | 0.05%/°C |
| gamma\_pmax | -0.35%/°C |
| gamma\_vmp | -0.32%/°C |
| noct | 45 |
| nmot | — |
| bifacial | True |
| bifaciality | 0.7 |
| max\_system\_voltage | 1,500 |
| max\_series\_fuse\_rating | 30 |

## Inverter

| Field | Value |
| --- | --- |
| name | Generic 100kW 1500V 10-MPPT inverter (illustrative) |
| max\_dc\_voltage | 1,500 |
| start\_voltage | 550 |
| mppt\_min | 500 |
| mppt\_max | 1,450 |
| full\_power\_mppt\_min | 600 |
| full\_power\_mppt\_max | 1,200 |
| nominal\_dc\_voltage | 900 |
| num\_mppts | 10 |
| max\_input\_current\_per\_mppt | 32 |
| max\_isc\_per\_mppt | 50 |
| strings\_per\_mppt | 2 |
| max\_dc\_power | 150,000 |
| ac\_rated\_power | 100,000 |

## Site

| Field | Value |
| --- | --- |
| name | Illustrative 1500 V commercial site (not a measured station) |
| tmin | -18 |
| thigh | 35 |
| irradiance | 1,000 |
| rear\_irradiance\_ratio | 0.15 |
| altitude | — |
| racking | — |
| fixed\_delta\_t | — |
| typical\_cell\_temperature | 45 |
| degradation\_percent\_per\_year | 0.5 |
| design\_years | 10 |

## Array

| Field | Value |
| --- | --- |
| modules\_per\_string | 22 |
| strings\_per\_mppt | (1, 1, 1, 1, 1, 1, 1, 1, 1, 1) |
| fuse\_rating | — |

## Metrics

| Field | Value |
| --- | --- |
| cell\_temperature\_hot | 66.25 |
| voc\_cold | 55.25 |
| voc\_cold\_table | 58.41 |
| voc\_hot | 43.99 |
| vmp\_hot | 36.28 |
| vmp\_hot\_eol | 34.47 |
| vmp\_cold | 47.55 |
| vmp\_typical | 39.12 |
| isc\_hot | 15.68 |
| isc\_design | 19.6 |
| imp\_hot | 14.84 |
| dc\_power | 121,000 |
| dc\_ac\_ratio | 1.21 |

## Limits

| Field | Value |
| --- | --- |
| min\_modules | 15 |
| max\_modules | 27 |
| recommended\_min | 16 |
| recommended\_max | 27 |

## Checks

| Check | Status | Value | Limit | Explanation | Reference |
| --- | --- | --- | --- | --- | --- |
| Cold Voc / inverter maximum | PASS | 1,215.43 | 1,500 | V/string at cold design temperature; manufacturer coefficient method. Dawn cell temperature is approximated by ambient. | NEC 2023 690.7(A)(1); inverter datasheet |
| Cold Voc / module system voltage | PASS | 1,215.43 | 1,500 | V/string must respect the module insulation/system-voltage rating as well as the inverter. | Module datasheet; NEC 2023 690.7 |
| Hot EOL Vmp / MPPT minimum | PASS | 758.3 | 500 | V/string after the explicit linear voltage-degradation allowance; minimum operating tracking voltage. | Inverter datasheet; design allowance |
| Cold Vmp / MPPT maximum | PASS | 1,046.14 | 1,450 | V/string at cold design temperature must stay within the operating tracking window. | Inverter datasheet |
| Start voltage | PASS | 967.71 | 550 | Hot open-circuit V/string screens restart capability. Low-light start behavior requires manufacturer verification. | Inverter datasheet; simplified startup screen |
| Typical Vmp / full-power window | PASS | 860.75 | \[600, 1200\] | V/string at the assumed typical cell temperature; full-power window is advisory and distinct from the operating window. | Inverter datasheet |
| NEC table comparison | PASS | 1,285.02 | comparison only (V/string) | Table result is informative. The available manufacturer coefficient controls this design, so methods are not mixed. | Per NEC Table 690.7(A) |
| MPPT 1 string capacity | PASS | 1 | 2 | Parallel string count versus physical/manufacturer input capacity; 0 denotes unused. | Inverter datasheet |
| MPPT 1 maximum Isc | PASS | 19.6 | 50 | A/MPPT: temperature- and irradiance-corrected Isc × bifacial gain × 1.25 × parallel strings. Conservative comparison to inverter short-circuit rating. | NEC 2023 690.8(A)(1); inverter datasheet |
| MPPT 1 operating current | PASS | 14.84 | 32 | A/MPPT: Imp uses the Isc temperature/irradiance multiplier as a screening proxy. Exceeding operating input current may clip production. | Inverter datasheet; Imp model assumption |
| MPPT 1 series fusing | PASS | 1 | 3 parallel strings trigger simplified fuse rule | No series fuse triggered by this screen. Manufacturer instructions and inverter backfeed may still require protection. | NEC 2023 690.9 (simplified) |
| MPPT 2 string capacity | PASS | 1 | 2 | Parallel string count versus physical/manufacturer input capacity; 0 denotes unused. | Inverter datasheet |
| MPPT 2 maximum Isc | PASS | 19.6 | 50 | A/MPPT: temperature- and irradiance-corrected Isc × bifacial gain × 1.25 × parallel strings. Conservative comparison to inverter short-circuit rating. | NEC 2023 690.8(A)(1); inverter datasheet |
| MPPT 2 operating current | PASS | 14.84 | 32 | A/MPPT: Imp uses the Isc temperature/irradiance multiplier as a screening proxy. Exceeding operating input current may clip production. | Inverter datasheet; Imp model assumption |
| MPPT 2 series fusing | PASS | 1 | 3 parallel strings trigger simplified fuse rule | No series fuse triggered by this screen. Manufacturer instructions and inverter backfeed may still require protection. | NEC 2023 690.9 (simplified) |
| MPPT 3 string capacity | PASS | 1 | 2 | Parallel string count versus physical/manufacturer input capacity; 0 denotes unused. | Inverter datasheet |
| MPPT 3 maximum Isc | PASS | 19.6 | 50 | A/MPPT: temperature- and irradiance-corrected Isc × bifacial gain × 1.25 × parallel strings. Conservative comparison to inverter short-circuit rating. | NEC 2023 690.8(A)(1); inverter datasheet |
| MPPT 3 operating current | PASS | 14.84 | 32 | A/MPPT: Imp uses the Isc temperature/irradiance multiplier as a screening proxy. Exceeding operating input current may clip production. | Inverter datasheet; Imp model assumption |
| MPPT 3 series fusing | PASS | 1 | 3 parallel strings trigger simplified fuse rule | No series fuse triggered by this screen. Manufacturer instructions and inverter backfeed may still require protection. | NEC 2023 690.9 (simplified) |
| MPPT 4 string capacity | PASS | 1 | 2 | Parallel string count versus physical/manufacturer input capacity; 0 denotes unused. | Inverter datasheet |
| MPPT 4 maximum Isc | PASS | 19.6 | 50 | A/MPPT: temperature- and irradiance-corrected Isc × bifacial gain × 1.25 × parallel strings. Conservative comparison to inverter short-circuit rating. | NEC 2023 690.8(A)(1); inverter datasheet |
| MPPT 4 operating current | PASS | 14.84 | 32 | A/MPPT: Imp uses the Isc temperature/irradiance multiplier as a screening proxy. Exceeding operating input current may clip production. | Inverter datasheet; Imp model assumption |
| MPPT 4 series fusing | PASS | 1 | 3 parallel strings trigger simplified fuse rule | No series fuse triggered by this screen. Manufacturer instructions and inverter backfeed may still require protection. | NEC 2023 690.9 (simplified) |
| MPPT 5 string capacity | PASS | 1 | 2 | Parallel string count versus physical/manufacturer input capacity; 0 denotes unused. | Inverter datasheet |
| MPPT 5 maximum Isc | PASS | 19.6 | 50 | A/MPPT: temperature- and irradiance-corrected Isc × bifacial gain × 1.25 × parallel strings. Conservative comparison to inverter short-circuit rating. | NEC 2023 690.8(A)(1); inverter datasheet |
| MPPT 5 operating current | PASS | 14.84 | 32 | A/MPPT: Imp uses the Isc temperature/irradiance multiplier as a screening proxy. Exceeding operating input current may clip production. | Inverter datasheet; Imp model assumption |
| MPPT 5 series fusing | PASS | 1 | 3 parallel strings trigger simplified fuse rule | No series fuse triggered by this screen. Manufacturer instructions and inverter backfeed may still require protection. | NEC 2023 690.9 (simplified) |
| MPPT 6 string capacity | PASS | 1 | 2 | Parallel string count versus physical/manufacturer input capacity; 0 denotes unused. | Inverter datasheet |
| MPPT 6 maximum Isc | PASS | 19.6 | 50 | A/MPPT: temperature- and irradiance-corrected Isc × bifacial gain × 1.25 × parallel strings. Conservative comparison to inverter short-circuit rating. | NEC 2023 690.8(A)(1); inverter datasheet |
| MPPT 6 operating current | PASS | 14.84 | 32 | A/MPPT: Imp uses the Isc temperature/irradiance multiplier as a screening proxy. Exceeding operating input current may clip production. | Inverter datasheet; Imp model assumption |
| MPPT 6 series fusing | PASS | 1 | 3 parallel strings trigger simplified fuse rule | No series fuse triggered by this screen. Manufacturer instructions and inverter backfeed may still require protection. | NEC 2023 690.9 (simplified) |
| MPPT 7 string capacity | PASS | 1 | 2 | Parallel string count versus physical/manufacturer input capacity; 0 denotes unused. | Inverter datasheet |
| MPPT 7 maximum Isc | PASS | 19.6 | 50 | A/MPPT: temperature- and irradiance-corrected Isc × bifacial gain × 1.25 × parallel strings. Conservative comparison to inverter short-circuit rating. | NEC 2023 690.8(A)(1); inverter datasheet |
| MPPT 7 operating current | PASS | 14.84 | 32 | A/MPPT: Imp uses the Isc temperature/irradiance multiplier as a screening proxy. Exceeding operating input current may clip production. | Inverter datasheet; Imp model assumption |
| MPPT 7 series fusing | PASS | 1 | 3 parallel strings trigger simplified fuse rule | No series fuse triggered by this screen. Manufacturer instructions and inverter backfeed may still require protection. | NEC 2023 690.9 (simplified) |
| MPPT 8 string capacity | PASS | 1 | 2 | Parallel string count versus physical/manufacturer input capacity; 0 denotes unused. | Inverter datasheet |
| MPPT 8 maximum Isc | PASS | 19.6 | 50 | A/MPPT: temperature- and irradiance-corrected Isc × bifacial gain × 1.25 × parallel strings. Conservative comparison to inverter short-circuit rating. | NEC 2023 690.8(A)(1); inverter datasheet |
| MPPT 8 operating current | PASS | 14.84 | 32 | A/MPPT: Imp uses the Isc temperature/irradiance multiplier as a screening proxy. Exceeding operating input current may clip production. | Inverter datasheet; Imp model assumption |
| MPPT 8 series fusing | PASS | 1 | 3 parallel strings trigger simplified fuse rule | No series fuse triggered by this screen. Manufacturer instructions and inverter backfeed may still require protection. | NEC 2023 690.9 (simplified) |
| MPPT 9 string capacity | PASS | 1 | 2 | Parallel string count versus physical/manufacturer input capacity; 0 denotes unused. | Inverter datasheet |
| MPPT 9 maximum Isc | PASS | 19.6 | 50 | A/MPPT: temperature- and irradiance-corrected Isc × bifacial gain × 1.25 × parallel strings. Conservative comparison to inverter short-circuit rating. | NEC 2023 690.8(A)(1); inverter datasheet |
| MPPT 9 operating current | PASS | 14.84 | 32 | A/MPPT: Imp uses the Isc temperature/irradiance multiplier as a screening proxy. Exceeding operating input current may clip production. | Inverter datasheet; Imp model assumption |
| MPPT 9 series fusing | PASS | 1 | 3 parallel strings trigger simplified fuse rule | No series fuse triggered by this screen. Manufacturer instructions and inverter backfeed may still require protection. | NEC 2023 690.9 (simplified) |
| MPPT 10 string capacity | PASS | 1 | 2 | Parallel string count versus physical/manufacturer input capacity; 0 denotes unused. | Inverter datasheet |
| MPPT 10 maximum Isc | PASS | 19.6 | 50 | A/MPPT: temperature- and irradiance-corrected Isc × bifacial gain × 1.25 × parallel strings. Conservative comparison to inverter short-circuit rating. | NEC 2023 690.8(A)(1); inverter datasheet |
| MPPT 10 operating current | PASS | 14.84 | 32 | A/MPPT: Imp uses the Isc temperature/irradiance multiplier as a screening proxy. Exceeding operating input current may clip production. | Inverter datasheet; Imp model assumption |
| MPPT 10 series fusing | PASS | 1 | 3 parallel strings trigger simplified fuse rule | No series fuse triggered by this screen. Manufacturer instructions and inverter backfeed may still require protection. | NEC 2023 690.9 (simplified) |
| Maximum DC power | PASS | 121,000 | 150,000 | Installed front-side STC nameplate W versus inverter permitted array power. Bifacial energy gain is not added to STC nameplate power. | Inverter datasheet |
| DC/AC ratio (ILR) | PASS | 1.21 | \[1.1, 1.35\] | STC DC W / AC rated W. The typical 1.10–1.35 screening band is project-dependent, not a code requirement. | Design guidance |
