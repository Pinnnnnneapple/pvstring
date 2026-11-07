"""Exercise main(argv) directly plus the module execution entry point."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from pvstring.cli import main

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "residential"
INPUTS = ["--module", str(EXAMPLE / "module.json"), "--inverter", str(EXAMPLE / "inverter.json"), "--site", str(EXAMPLE / "site.json")]
PASS = ["check"] + INPUTS + ["--modules-per-string", "8", "--strings-per-mppt", "1,1"]


def test_passing_exit_zero(capsys):
    assert main(PASS) == 0
    output = capsys.readouterr()
    assert "pvstring — PASS" in output.out
    assert "333.044" in output.out
    assert not output.err


def test_failure_exit_two(capsys):
    args = ["check"] + INPUTS + ["--modules-per-string", "16", "--strings-per-mppt", "1,1"]
    assert main(args) == 2
    output = capsys.readouterr().out
    assert "FAIL  Cold Voc / inverter maximum" in output
    assert "666.088" in output


def test_warning_exit_one(capsys):
    args = ["check"] + INPUTS + ["--modules-per-string", "6", "--strings-per-mppt", "1,1"]
    assert main(args) == 1
    assert "WARN  DC/AC ratio" in capsys.readouterr().out


@pytest.mark.parametrize("extra", [
    [], ["--modules-per-string", "8"],
    ["--modules-per-string", "eight", "--strings-per-mppt", "1,1"],
    ["--modules-per-string", "0", "--strings-per-mppt", "1,1"],
    ["--modules-per-string", "8", "--strings-per-mppt", "a,1"],
    ["--modules-per-string", "8", "--strings-per-mppt", "1,"],
    ["--modules-per-string", "8", "--strings-per-mppt", "1"],
    ["--modules-per-string", "8", "--strings-per-mppt", "0,0"],
    ["--modules-per-string", "8", "--strings-per-mppt", "-1,1"],
    ["--unknown"],
])
def test_input_exit_three(extra, capsys):
    assert main(["check"] + INPUTS + extra) == 3
    output = capsys.readouterr()
    assert "input error:" in output.err
    assert "Traceback" not in output.err


def test_parser_missing_inputs(capsys):
    assert main(["check"]) == 3
    assert "required" in capsys.readouterr().err


def test_unknown_subcommand(capsys):
    assert main(["unknown"]) == 3
    assert "invalid choice" in capsys.readouterr().err


def test_reports_all_formats(tmp_path, capsys):
    html, md, json_path = [tmp_path / f"r.{extension}" for extension in ("html", "md", "json")]
    assert main(PASS + ["--html", str(html), "--md", str(md), "--json", str(json_path)]) == 0
    assert "<svg" in html.read_text(encoding="utf-8")
    assert "| Check |" in md.read_text(encoding="utf-8")
    data = json.loads(json_path.read_text())
    assert data["status"] == "PASS"
    assert data["array"]["strings_per_mppt"] == [1, 1]
    assert data["metrics"]["dc_power"] == 6560
    assert data["schema_version"] == 1


def test_stdout_json_is_machine_readable(capsys):
    assert main(PASS + ["--json", "-"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["exit_code"] == 0


def test_stdout_markdown(capsys):
    assert main(PASS + ["--md", "-"]) == 0
    assert capsys.readouterr().out.startswith("# PV string design report")


def test_stdout_output_conflict(capsys):
    assert main(PASS + ["--json", "-", "--md", "-"]) == 3
    assert "distinct" in capsys.readouterr().err


def test_output_does_not_overwrite_input(capsys):
    original = (EXAMPLE / "module.json").read_bytes()
    assert main(PASS + ["--json", str(EXAMPLE / "module.json")]) == 3
    assert (EXAMPLE / "module.json").read_bytes() == original
    assert "overwrite" in capsys.readouterr().err


def test_output_io_error(tmp_path, capsys):
    assert main(PASS + ["--html", str(tmp_path / "absent" / "r.html")]) == 3
    assert "input error" in capsys.readouterr().err


def test_site_overrides_and_racking(capsys):
    assert main(PASS + ["--tmin", "-25", "--thigh", "35", "--racking", "roof", "--json", "-"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["site"]["tmin"] == -25
    assert data["metrics"]["cell_temperature_hot"] == 65


@pytest.mark.parametrize("extra", [["--tmin", "nan"], ["--thigh", "inf"], ["--racking", "unknown"], ["--tmin", "40"]])
def test_invalid_overrides(extra, capsys):
    assert main(PASS + extra) == 3
    assert "input error" in capsys.readouterr().err


def test_array_json(capsys):
    assert main(["check"] + INPUTS + ["--array", str(EXAMPLE / "passing-array.json")]) == 0


def test_array_flags_conflict(capsys):
    assert main(PASS + ["--array", str(EXAMPLE / "passing-array.json")]) == 3
    assert "cannot be combined" in capsys.readouterr().err


def test_range_with_reasons(capsys):
    assert main(["range"] + INPUTS) == 0
    output = capsys.readouterr().out
    assert "Modules per string: 5–14" in output
    assert "ceil(MPPT" in output
    assert "floor(min(inverter" in output


def test_range_json(capsys):
    assert main(["range"] + INPUTS + ["--json", "-"]) == 0
    assert json.loads(capsys.readouterr().out)["limits"]["max_modules"] == 14


def test_suggest_ranked_valid(capsys):
    assert main(["suggest"] + INPUTS + ["--target-kw", "6.5", "--top", "3", "--json", "-"]) == 0
    options = json.loads(capsys.readouterr().out)["options"]
    assert len(options) == 3
    assert options[0]["array"]["modules_per_string"] == 8
    assert options[0]["array"]["strings_per_mppt"] == [1, 1]
    assert all(option["result"]["status"] != "FAIL" for option in options)
    assert [option["score"] for option in options] == sorted(option["score"] for option in options)


def test_suggest_table(capsys):
    assert main(["suggest"] + INPUTS + ["--top", "2"]) == 0
    output = capsys.readouterr().out
    assert "Rank  Modules" in output
    assert "no FAIL" in output


@pytest.mark.parametrize("extra", [["--top", "0"], ["--top", "bad"], ["--target-kw", "0"], ["--target-kw", "nan"]])
def test_suggest_invalid(extra, capsys):
    assert main(["suggest"] + INPUTS + extra) == 3


def test_library(capsys):
    assert main(["library"]) == 0
    output = capsys.readouterr().out
    assert "generic-100kw-1500v" in output
    assert "not real brand products" in output


@pytest.mark.parametrize("kind", ["module", "inverter", "site"])
def test_show_template(kind, capsys):
    assert main(["show-template", kind]) == 0
    assert "name" in json.loads(capsys.readouterr().out)


def test_builtin_cli(capsys):
    assert main(["check", "--module", "builtin:generic-410", "--inverter", "builtin:generic-5kw", "--site", str(EXAMPLE / "site.json"), "--modules-per-string", "8", "--strings-per-mppt", "1,1"]) == 0


@pytest.mark.parametrize("args,text", [(["--help"], "usage: pvstring"), (["--version"], "pvstring 0.1.0"), (["check", "--help"], "--strings-per-mppt")])
def test_help_and_version(args, text, capsys):
    assert main(args) == 0
    assert text in capsys.readouterr().out


def test_python_module_entrypoint():
    environment = dict(os.environ, PYTHONPATH=str(ROOT / "src"))
    completed = subprocess.run([sys.executable, "-m", "pvstring", "--version"], env=environment, capture_output=True, text=True, check=False)
    assert completed.returncode == 0
    assert completed.stdout.strip() == "pvstring 0.1.0"


@pytest.mark.parametrize("command", ["range", "suggest"])
def test_infeasible_range_or_suggestions_exit_two(tmp_path, command, capsys):
    data = json.loads((EXAMPLE / "inverter.json").read_text())
    data["start_voltage"] = 600  # Startup needs more modules than cold Voc permits.
    path = tmp_path / "inverter.json"
    path.write_text(json.dumps(data))
    arguments = [command] + INPUTS.copy()
    arguments[arguments.index("--inverter") + 1] = str(path)
    assert main(arguments + ["--json", "-"]) == 2
    output = json.loads(capsys.readouterr().out)
    if command == "range":
        assert output["status"] == "FAIL"
        assert output["limits"]["min_modules"] > output["limits"]["max_modules"]
    else:
        assert output["options"] == []


def test_huge_integer_design_is_input_error_not_traceback(capsys):
    arguments = ["check"] + INPUTS + ["--modules-per-string", "1" + "0" * 400, "--strings-per-mppt", "1,1"]
    assert main(arguments) == 3
    assert "input error" in capsys.readouterr().err


def test_derived_fuse_overflow_is_input_error(tmp_path, capsys):
    module = json.loads((EXAMPLE / "module.json").read_text())
    module.update(isc=1.3e308, imp=1, pmax_stc=31.4, alpha_isc=0)
    site = json.loads((EXAMPLE / "site.json").read_text())
    site.update(tmin=0, thigh=25, typical_cell_temperature=25, fixed_delta_t=0)
    for name, data in (("module", module), ("site", site)):
        (tmp_path / (name + ".json")).write_text(json.dumps(data))
    args = PASS.copy()
    for name in ("module", "site"):
        args[args.index("--" + name) + 1] = str(tmp_path / (name + ".json"))
    assert main(args + ["--fuse-rating", "25", "--json", "-"]) == 3
    output = capsys.readouterr()
    assert "finite number" in output.err
    assert "Traceback" not in output.err
    assert not output.out
