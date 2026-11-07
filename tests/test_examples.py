"""Keep the committed reports reproducible from their checked-in JSON inputs."""

from __future__ import annotations

from pathlib import Path

import pytest

from pvstring.calc import evaluate
from pvstring.loaders import load_array, load_inverter, load_module, load_site
from pvstring.report import html_report, json_report, markdown_report

ROOT = Path(__file__).resolve().parents[1] / "examples"


@pytest.mark.parametrize("folder,array,prefix,exit_code", [
    ("residential", "passing-array", "residential-pass", 0),
    ("residential", "failing-array", "residential-fail", 2),
    ("commercial_1500v", "passing-array", "commercial-1500v-pass", 0),
])
def test_committed_reports_match_current_engine(folder, array, prefix, exit_code):
    source = ROOT / folder
    result = evaluate(load_module(source / "module.json"), load_inverter(source / "inverter.json"),
                      load_site(source / "site.json"), load_array(source / (array + ".json")))
    assert result.exit_code == exit_code
    for extension, renderer in (("html", html_report), ("json", json_report), ("md", markdown_report)):
        assert (ROOT / "output" / (prefix + "." + extension)).read_text(encoding="utf-8") == renderer(result)
