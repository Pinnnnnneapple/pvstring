"""Console interface. ``main(argv)`` returns documented automation exit codes."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from dataclasses import replace
from pathlib import Path
from typing import Any, Dict, Optional, Sequence, Tuple

from . import __version__
from .calc import DISCLAIMER, DesignResult, design_metrics, evaluate, string_limits, suggest
from .library import list_library, template
from .loaders import load_array, load_inverter, load_module, load_site
from .models import Array, InputError, Inverter, Module, Site
from .report import html_report, json_report, markdown_report


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise InputError(message)


def _parser() -> argparse.ArgumentParser:
    parser = _Parser(prog="pvstring", description="Vendor-neutral PV string sizing — design aid, not certification.")
    parser.add_argument("--version", action="version", version=f"pvstring {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)
    for name, help_text in (("check", "Check one array design"), ("range", "Explain inclusive string-length limits"), ("suggest", "Rank feasible designs (WARNs remain visible)")):
        command = sub.add_parser(name, help=help_text)
        command.add_argument("--module", required=True, help="Module JSON path or builtin:generic-410")
        command.add_argument("--inverter", required=True, help="Inverter JSON path or builtin:generic-5kw")
        command.add_argument("--site", required=True, help="Site JSON path")
        command.add_argument("--tmin", type=float, help="Override lowest design ambient °C")
        command.add_argument("--thigh", type=float, help="Override high design ambient °C")
        command.add_argument("--racking", choices=("open-rack", "roof", "bipv"), help="Use illustrative fixed temperature rise instead of NOCT")
        command.add_argument("--json", metavar="PATH", help="Write JSON; '-' emits JSON only to stdout")
        if name == "check":
            command.add_argument("--modules-per-string", type=int)
            command.add_argument("--strings-per-mppt", help="Comma-separated counts in MPPT order, e.g. 2,1 (0 = unused)")
            command.add_argument("--fuse-rating", type=float, help="Installed/proposed per-string fuse rating, A")
            command.add_argument("--array", help="Array JSON alternative to the three design flags")
            command.add_argument("--html", metavar="PATH", help="Write a standalone printable HTML report")
            command.add_argument("--md", metavar="PATH", help="Write Markdown; '-' emits Markdown only to stdout")
        elif name == "suggest":
            command.add_argument("--target-kw", type=float, help="Target front-side STC DC kW (default 1.2 × AC rating)")
            command.add_argument("--top", type=int, default=5)
    sub.add_parser("library", help="List bundled illustrative generic datasets")
    show = sub.add_parser("show-template", help="Print an editable JSON template")
    show.add_argument("kind", choices=("module", "inverter", "site"))
    return parser


def _inputs(args: argparse.Namespace) -> Tuple[Module, Inverter, Site]:
    module = load_module(args.module)
    inverter = load_inverter(args.inverter)
    site = load_site(args.site)
    overrides: Dict[str, Any] = {}
    for field in ("tmin", "thigh", "racking"):
        value = getattr(args, field)
        if value is not None:
            overrides[field] = value
    if args.racking is not None:
        overrides["fixed_delta_t"] = None
    return module, inverter, replace(site, **overrides)


def _array(args: argparse.Namespace) -> Array:
    if args.array:
        if any(x is not None for x in (args.modules_per_string, args.strings_per_mppt, args.fuse_rating)):
            raise InputError("--array cannot be combined with --modules-per-string, --strings-per-mppt, or --fuse-rating")
        return load_array(args.array)
    if args.modules_per_string is None or args.strings_per_mppt is None:
        raise InputError("check requires --modules-per-string and --strings-per-mppt (or --array)")
    try:
        mapping = tuple(int(value.strip()) for value in args.strings_per_mppt.split(","))
    except ValueError:
        raise InputError("--strings-per-mppt: expected comma-separated integers, e.g. 2,1") from None
    return Array(args.modules_per_string, mapping, args.fuse_rating)


def _write(path: str, contents: str) -> None:
    if path == "-":
        sys.stdout.write(contents)
        return
    target = Path(path)
    temporary: Optional[str] = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=str(target.parent), delete=False) as handle:
            temporary = handle.name
            handle.write(contents)
        os.replace(temporary, target)
    finally:
        if temporary is not None and os.path.exists(temporary):
            os.unlink(temporary)


def _dump(data: Any) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False, allow_nan=False) + "\n"


def _number(value: Any) -> str:
    if isinstance(value, (int, float)):
        return f"{value:.3f}".rstrip("0").rstrip(".")
    if isinstance(value, (list, tuple)):
        return "[" + ", ".join(_number(x) for x in value) + "]"
    return str(value)


def _check_text(result: DesignResult) -> str:
    lines = [f"pvstring — {result.status}",
             f"Design: {result.array.modules_per_string} modules/string; strings/MPPT {','.join(map(str, result.array.strings_per_mppt))}",
             f"DC: {result.metrics['dc_power'] / 1000:.3f} kW | AC: {result.inverter.ac_rated_power / 1000:.3f} kW | ILR: {result.metrics['dc_ac_ratio']:.3f}",
             f"Hot cell: {result.metrics['cell_temperature_hot']:.2f} °C | String range: {result.limits['min_modules']}–{result.limits['max_modules']}", ""]
    for check in result.checks:
        lines.append(f"{check.status:4}  {check.name}: {_number(check.value)} (limit {_number(check.limit)})")
        if check.status != "PASS":
            lines.append(f"      {check.explanation}")
    lines += ["", DISCLAIMER]
    return "\n".join(lines) + "\n"


def _check(args: argparse.Namespace, module: Module, inverter: Inverter, site: Site) -> int:
    result = evaluate(module, inverter, site, _array(args))
    outputs = [(args.html, html_report), (args.json, json_report), (args.md, markdown_report)]
    destinations = [str(Path(path).absolute()) if path != "-" else path for path, _ in outputs if path]
    if len(set(destinations)) != len(destinations):
        raise InputError("report output paths must be distinct (at most one '-' stdout output)")
    input_paths = {str(Path(path).absolute()) for path in (args.module, args.inverter, args.site, args.array) if path and not str(path).startswith("builtin:")}
    if input_paths.intersection(destinations):
        raise InputError("report output cannot overwrite an input JSON file")
    rendered = [(path, render(result)) for path, render in outputs if path]
    for path, contents in rendered:
        _write(path, contents)
    if "-" not in destinations:
        sys.stdout.write(_check_text(result))
    return result.exit_code


def _range(args: argparse.Namespace, module: Module, inverter: Inverter, site: Site) -> int:
    limits = string_limits(module, inverter, site)
    metrics = design_metrics(module, inverter, site)
    feasible = limits["min_modules"] <= limits["max_modules"]
    data = {"schema_version": 1, "status": "PASS" if feasible else "FAIL", "limits": limits, "metrics": metrics, "disclaimer": DISCLAIMER}
    if args.json:
        _write(args.json, _dump(data))
    if args.json != "-":
        print(f"Modules per string: {limits['min_modules']}–{limits['max_modules']}" if feasible else "No feasible string length")
        print(f"Minimum: ceil(MPPT min {inverter.mppt_min:g} V / hot EOL Vmp {metrics['vmp_hot_eol']:.3f} V), also hot-Voc startup")
        print(f"Maximum: floor(min(inverter {inverter.max_dc_voltage:g} V, module {module.max_system_voltage:g} V) / cold Voc {metrics['voc_cold']:.3f} V), also cold-Vmp operating maximum")
        if limits["recommended_min"] <= limits["recommended_max"]:
            print(f"Typical full-power recommendation: {limits['recommended_min']}–{limits['recommended_max']} modules/string")
        else:
            print("No string length lies in the typical full-power window")
        print(f"Hot cell temperature: {metrics['cell_temperature_hot']:.2f} °C; coefficient method controls cold Voc")
        if module.gamma_vmp is None:
            print("WARN: missing gamma_vmp; fractional beta_voc proxy used")
        print("Current, power, and fusing must also pass a complete design check.")
    return 0 if feasible else 2


def _suggest(args: argparse.Namespace, module: Module, inverter: Inverter, site: Site) -> int:
    if args.top < 1:
        raise InputError("--top: must be a positive integer")
    options = suggest(module, inverter, site, args.target_kw)[:args.top]
    if args.json:
        _write(args.json, _dump({"schema_version": 1, "options": [s.to_dict() for s in options], "disclaimer": DISCLAIMER}))
    if args.json != "-":
        if not options:
            print("No feasible configurations (no options without FAIL checks).")
        else:
            print("Rank  Modules  Strings/MPPT            DC kW    ILR  Status   Score  Fuse A")
            for rank, option in enumerate(options, 1):
                metrics = option.result.metrics
                mapping = ",".join(map(str, option.array.strings_per_mppt))
                fuse = "—" if option.array.fuse_rating is None else f"{option.array.fuse_rating:g}"
                print(f"{rank:>4}  {option.array.modules_per_string:>7}  {mapping:<22} {metrics['dc_power'] / 1000:>6.3f}  {metrics['dc_ac_ratio']:>5.3f}  {option.result.status:<6} {option.score:>7.4f}  {fuse}")
            print("Feasible means no FAIL checks; WARNs remain. Identical MPPT permutations are represented once.")
            print("Proposed fuses are preliminary integer-A ratings; verify available/listed sizes and the complete protection design.")
    return 0 if options else 2


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Run the CLI, returning 0 pass, 1 warnings, 2 failures, or 3 input/I/O error."""
    # Legacy console code pages may not represent every report/help character.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")
    try:
        args = _parser().parse_args(argv)
        if args.command == "library":
            print("Illustrative generic examples ONLY — not real brand products.")
            for kind, entries in list_library().items():
                for entry in entries:
                    print(f"{kind:8} builtin:{entry['id']:<24} {entry['name']}")
            return 0
        if args.command == "show-template":
            sys.stdout.write(_dump(template(args.kind)))
            return 0
        module, inverter, site = _inputs(args)
        return {"check": _check, "range": _range, "suggest": _suggest}[args.command](args, module, inverter, site)
    except (InputError, OSError, UnicodeError, OverflowError) as error:
        print(f"pvstring: input error: {error}", file=sys.stderr)
        return 3
    except SystemExit as error:
        return int(error.code or 0)


if __name__ == "__main__":
    sys.exit(main())
