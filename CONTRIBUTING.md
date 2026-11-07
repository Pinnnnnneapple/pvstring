# Contributing

Use Python 3.9 or newer. The runtime must remain standard-library-only; pytest
is a development dependency. From the repository root:

```sh
python -m pip install -e '.[dev]'
python -m pytest -q
```

For an existing development environment, tests can also run directly from the
source tree:

```sh
PYTHONPATH=src python3 -m pytest -q
```

Run the residential example after changes affecting the public interface:

```sh
pvstring check --module examples/residential/module.json --inverter examples/residential/inverter.json --site examples/residential/site.json --modules-per-string 8 --strings-per-mppt 1,1
```

Keep calculations separate from input parsing and presentation. Include units,
assumptions, and an independently checked numerical example when changing a
formula. Add focused regression tests for calculation or validation changes,
including boundaries and rejected non-finite or unknown inputs. Preserve strict
JSON field validation and document public input changes in
[the input reference](docs/input-reference.md).

Use generic examples unless permission and provenance support a specific
manufacturer's data. Cite primary sources for standards-related changes and
state the applicable edition. Do not describe a passing calculation as code
compliance or certification. Explain behavior changes, verification performed,
and remaining limitations in a pull request; update the changelog as needed.
