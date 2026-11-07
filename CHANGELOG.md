# Changelog

## 0.1.0 — 2026-11-07

Initial release for vendor-neutral preliminary PV string sizing.

- Validated module, inverter, site, and array JSON models; five clearly labelled
  illustrative generic module/inverter records.
- Cold voltage correction, NEC table comparison, hot/EOL tracking and startup
  screens, bifacial current correction, MPPT limits, preliminary fusing, and ILR.
- `check`, `range`, `suggest`, `library`, and `show-template` commands with
  documented exit codes and JSON output for automation.
- Standalone HTML/SVG, Markdown, and JSON design reports; generated residential
  passing/failing examples and a 1500 V commercial example.
- Methodology, input reference, contribution guide, MIT license, and CI for
  Python 3.10–3.14 on Ubuntu, Windows, and macOS.

The runtime uses only the Python standard library. Results are design aids,
not manufacturer approval or code-compliance certification.

### Platform support and fixes before release

- Require Python 3.10 or newer; test Python 3.10–3.14 on Ubuntu, Windows,
  and macOS.
- Fix Windows UTF-8 file handling, accept UTF-8 BOMs in JSON inputs, and
  improve temperature-coefficient parsing and console encoding compatibility.
