"""Report contract tests; fixtures use the public to_dict result interface."""

import copy
import json
import re
import unittest
import xml.etree.ElementTree as ET
from types import SimpleNamespace
from dataclasses import replace

from pvstring.calc import evaluate
from pvstring.library import load_builtin
from pvstring.models import Array, Site
from pvstring.report import html_report, json_report, markdown_report


def make_result():
    data = {
        "schema_version": 1,
        "module": {"name": "Generic 410", "vmp": 31.5, "pmax_stc": 410},
        "inverter": {
            "name": "Generic 5 kW", "max_dc_voltage": 600, "start_voltage": 100,
            "mppt_min": 80, "mppt_max": 550,
            "full_power_mppt_min": 200, "full_power_mppt_max": 500,
            "num_mppts": 2, "max_input_current_per_mppt": 25,
            "max_isc_per_mppt": 30,
        },
        "site": {"name": "test", "tmin": -18, "thigh": 33},
        "array": {"modules_per_string": 12, "strings_per_mppt": [2, 0], "fuse_rating": None},
        "metrics": {
            "cell_temperature_hot": 65, "voc_cold": 42, "voc_cold_table": 43,
            "vmp_hot": 27, "vmp_hot_eol": 26, "vmp_cold": 35,
            "vmp_typical": 30, "isc_hot": 14, "isc_design": 16,
            "imp_hot": 12, "dc_power": 9840, "dc_ac_ratio": 1.968,
        },
        "limits": {"min_modules": 8, "max_modules": 14,
                   "recommended_min": 9, "recommended_max": 13},
        "checks": [{"name": "DC limit", "status": "PASS", "value": 504,
                    "limit": 600, "explanation": "Cold Voc within limit", "reference": "Datasheet"}],
        "status": "WARN", "exit_code": 1,
    }
    return SimpleNamespace(to_dict=lambda: copy.deepcopy(data)), data


def svg_tree(document):
    return ET.fromstring(re.search(r"<svg\b.*?</svg>", document, re.S).group())


class ReportTests(unittest.TestCase):
    def setUp(self):
        self.result, self.data = make_result()

    def test_html_self_contained_accessible_and_printable(self):
        output = html_report(self.result)
        self.assertTrue(output.startswith("<!doctype html>"))
        self.assertIn("prefers-color-scheme:dark", output)
        self.assertIn("@media print", output)
        self.assertIn('lang="en"', output)
        self.assertNotRegex(output, r"<(?:script|link|iframe|img)\b")
        self.assertNotRegex(output, r"(?:src|href)\s*=")
        self.assertNotIn("@import", output)
        self.assertNotIn("url(", output)
        chart = svg_tree(output)
        self.assertEqual(chart.attrib["role"], "img")
        self.assertIsNotNone(chart.find("{http://www.w3.org/2000/svg}title"))
        self.assertIsNotNone(chart.find("{http://www.w3.org/2000/svg}desc"))
        self.assertIn("manufacturer", output)
        self.assertIn("local electrical codes", output)
        self.assertIn("sign-off", output)

    def test_all_input_text_is_escaped(self):
        attack = '<script>alert("x")</script>&'
        for key in ("module", "inverter", "site"):
            self.data[key]["name"] = attack
        self.data["checks"][0].update(name=attack, explanation=attack, reference=attack)
        self.data["status"] = attack
        output = html_report(self.result)
        self.assertNotIn("<script>", output)
        self.assertIn("&lt;script&gt;", output)
        self.assertIn("&quot;x&quot;", output)
        svg_tree(output)
        self.assertNotIn("<script>", markdown_report(self.result))

    def test_svg_string_voltages_and_bands(self):
        chart = svg_tree(html_report(self.result))
        titles = [node.text for node in chart.iter("{http://www.w3.org/2000/svg}title")]
        self.assertIn("Cold Voc: 504 V at 12 modules", titles)
        self.assertIn("Hot Vmp: 324 V at 12 modules", titles)
        self.assertIn("STC Vmp: 378 V at 12 modules", titles)
        self.assertEqual(sum(" at " in title for title in titles), 7 * 3)
        text = " ".join(chart.itertext())
        for label in ("MPPT operating: 80–550 V", "Full power MPPT: 200–500 V",
                      "Max DC: 600 V", "Start: 100 V", "12* modules"):
            self.assertIn(label, text)

    def test_current_headroom_including_idle_mppt(self):
        output = html_report(self.result)
        self.assertIn("Operating current: 24 / 25 A; 1 A headroom", output)
        self.assertIn("Design short-circuit current: 32 / 30 A; -2 A headroom", output)
        self.assertIn("Operating current: 0 / 25 A; 25 A headroom", output)
        self.assertIn('class="fill over"', output)
        self.assertNotIn("width:106", output)

    def test_large_range_is_capped_and_includes_design(self):
        self.data["limits"].update(min_modules=1, max_modules=10000)
        self.data["array"]["modules_per_string"] = 5000
        chart = svg_tree(html_report(self.result))
        titles = [node.text for node in chart.iter("{http://www.w3.org/2000/svg}title")]
        bars = [title for title in titles if " at " in title]
        self.assertLessEqual(len(bars), 40 * 3)
        self.assertIn("Cold Voc: 210,000 V at 5000 modules", bars)

    def test_design_outside_range_is_included(self):
        self.data["array"]["modules_per_string"] = 100
        chart = svg_tree(html_report(self.result))
        self.assertIn("100* modules", " ".join(chart.itertext()))

    def test_exactly_forty_candidates_are_all_shown(self):
        self.data["limits"].update(min_modules=1, max_modules=40)
        chart = svg_tree(html_report(self.result))
        titles = [node.text for node in chart.iter("{http://www.w3.org/2000/svg}title")]
        self.assertEqual(sum(" at " in title for title in titles), 120)
        self.assertIn("Cold Voc: 1,680 V at 40 modules", titles)

    def test_empty_infeasible_and_optional_limits(self):
        for limits in ({}, {"min_modules": 20, "max_modules": 4},
                       {"min_modules": None, "max_modules": None}):
            with self.subTest(limits=limits):
                self.data["limits"] = limits
                self.data["array"]["strings_per_mppt"] = []
                self.data["inverter"]["full_power_mppt_min"] = None
                self.data["inverter"]["full_power_mppt_max"] = None
                self.data["inverter"]["max_isc_per_mppt"] = None
                output = html_report(self.result)
                svg_tree(output)
                self.assertIn("12* modules", output)
                self.assertIn("MPPT 2 · 0 strings", output)
                self.assertIn("limit unavailable", output)
        self.data["inverter"]["num_mppts"] = 0
        self.assertIn("No MPPT inputs configured", html_report(self.result))

    def test_markdown_tables_escape_delimiters(self):
        self.data["module"]["name"] = "A|B\n<script>*x*_[link]"
        output = markdown_report(self.result)
        self.assertIn("# PV string design report", output)
        self.assertIn("## Checks", output)
        self.assertIn(r"A\|B<br>&lt;script&gt;\*x\*\_\[link\]", output)
        self.assertIn("sign-off", output)

    def test_json_preserves_schema_values_and_does_not_mutate(self):
        before = copy.deepcopy(self.data)
        html_report(self.result)
        markdown_report(self.result)
        parsed = json.loads(json_report(self.result))
        self.assertEqual(parsed, before)
        self.assertEqual(self.data, before)
        self.assertIsInstance(parsed["metrics"]["dc_ac_ratio"], float)
        self.assertEqual(parsed["schema_version"], 1)

    def test_status_badges_are_allowlisted(self):
        for status in ("PASS", "WARN", "FAIL"):
            with self.subTest(status=status):
                self.data["checks"][0]["status"] = status
                self.assertIn('class="badge status-{}">{}</span>'.format(status.lower(), status), html_report(self.result))
        self.data["checks"][0]["status"] = '\" onmouseover="alert(1)'
        output = html_report(self.result)
        self.assertIn('class="badge status-unknown"', output)
        self.assertNotIn(' onmouseover="', output)
        self.assertIn("licensed professional sign-off", output)

    def test_real_design_result_integration(self):
        module = replace(load_builtin("module", "generic-410"), name="<script>unsafe</script>")
        inverter = load_builtin("inverter", "generic-5kw")
        result = evaluate(module, inverter, Site(name="test", tmin=-18, thigh=33), Array(10, (1, 0)))
        output = html_report(result)
        svg_tree(output)
        self.assertNotIn("<script>", output)
        self.assertIn("&lt;script&gt;unsafe&lt;/script&gt;", output)
        self.assertIn("MPPT 2 · 0 strings", output)
        self.assertIn(result.status, markdown_report(result))
        self.assertEqual(json.loads(json_report(result)), json.loads(json.dumps(result.to_dict())))


if __name__ == "__main__":
    unittest.main()
