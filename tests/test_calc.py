"""Independent hand-calculated numerical and boundary tests (stdlib only)."""

from dataclasses import replace
from itertools import product
import math
import unittest

from pvstring.calc import (
    cell_temperature, check_design, cold_voc, corrected_isc, design_metrics,
    evaluate, hot_vmp, nec_voltage_factor, string_limits, suggest,
)
from pvstring.models import Array, InputError, Inverter, Module, Site


def fixtures():
    module = Module(name="Hand calculation", pmax_stc=400, voc=49.5, isc=11,
                    vmp=40, imp=10, beta_voc=-0.27, alpha_isc=0.05,
                    gamma_pmax=-0.35, gamma_vmp=-0.3, noct=45,
                    max_system_voltage=1000, max_series_fuse_rating=25)
    inverter = Inverter(name="Test inverter", max_dc_voltage=600, start_voltage=100,
                        mppt_min=100, mppt_max=550, full_power_mppt_min=200,
                        full_power_mppt_max=500, nominal_dc_voltage=400,
                        num_mppts=2, max_input_current_per_mppt=40,
                        max_isc_per_mppt=60, strings_per_mppt=3,
                        max_dc_power=30000, ac_rated_power=10000)
    site = Site(name="Test site", tmin=-18, thigh=33, fixed_delta_t=25,
                typical_cell_temperature=45, degradation_percent_per_year=0.5,
                design_years=10)
    return module, inverter, site


class NumericalTests(unittest.TestCase):
    def setUp(self):
        self.module, self.inverter, self.site = fixtures()

    def result(self, array=None, module=None, inverter=None, site=None):
        return evaluate(module or self.module, inverter or self.inverter,
                        site or self.site, array or Array(8, (1, 1)))

    def status(self, result, name):
        return next(check.status for check in result.checks if check.name == name)

    def test_cold_voc_percent_hand_calculation(self):
        self.assertAlmostEqual(cold_voc(self.module, -18), 55.24695, places=10)

    def test_cold_voc_absolute_coefficient(self):
        self.assertAlmostEqual(cold_voc(replace(self.module, beta_voc="-0.134 V/°C"), -18),
                               55.262, places=10)

    def test_stc_voltage_identity(self):
        self.assertEqual(cold_voc(self.module, 25), 49.5)
        self.assertEqual(hot_vmp(self.module, 25), 40)

    def test_hot_vmp_explicit_coefficient(self):
        self.assertAlmostEqual(hot_vmp(self.module, 58), 36.04)

    def test_hot_vmp_proxy_is_fractional(self):
        module = replace(self.module, beta_voc="-0.134 V/°C", gamma_vmp=None)
        expected = 40 * (1 - (0.134 / 49.5) * 33)
        self.assertAlmostEqual(hot_vmp(module, 58), expected)
        self.assertEqual(self.status(self.result(module=module), "Vmp coefficient proxy"), "WARN")

    def test_noct_hot_cell(self):
        site = replace(self.site, fixed_delta_t=None, irradiance=800)
        self.assertEqual(cell_temperature(site, self.module), 58)
        self.assertEqual(cell_temperature(replace(site, irradiance=1000), self.module), 64.25)

    def test_nmot_takes_precedence(self):
        site = replace(self.site, fixed_delta_t=None, irradiance=800)
        self.assertEqual(cell_temperature(site, replace(self.module, nmot=42)), 55)

    def test_fixed_delta_t_overrides_noct_and_irradiance(self):
        self.assertEqual(cell_temperature(replace(self.site, irradiance=1200),
                                          replace(self.module, noct=60, nmot=50)), 58)

    def test_missing_thermal_model_raises(self):
        with self.assertRaises(InputError):
            cell_temperature(replace(self.site, fixed_delta_t=None),
                             replace(self.module, noct=None, nmot=None))

    def test_hot_cell_over_150_raises(self):
        with self.assertRaises(InputError):
            cell_temperature(replace(self.site, fixed_delta_t=118), self.module)

    def test_exact_150_cell_allowed(self):
        self.assertEqual(cell_temperature(replace(self.site, fixed_delta_t=117), self.module), 150)

    def test_eol_linear_voltage_allowance(self):
        metrics = design_metrics(self.module, self.inverter, self.site)
        self.assertAlmostEqual(metrics["vmp_hot_eol"], 34.238)
        self.assertAlmostEqual(metrics["vmp_hot"], 36.04)
        self.assertAlmostEqual(metrics["vmp_typical"], 37.6)

    def test_zero_degradation(self):
        metrics = design_metrics(self.module, self.inverter, replace(self.site, design_years=0))
        self.assertEqual(metrics["vmp_hot_eol"], metrics["vmp_hot"])

    def test_corrected_current_and_125_factor(self):
        metrics = design_metrics(self.module, self.inverter, self.site)
        self.assertAlmostEqual(metrics["isc_hot"], 11.1815)
        self.assertAlmostEqual(metrics["isc_design"], 13.976875)
        self.assertAlmostEqual(metrics["imp_hot"], 10.165)

    def test_bifacial_gain_and_irradiance(self):
        module = replace(self.module, bifacial=True, bifaciality=0.7)
        site = replace(self.site, rear_irradiance_ratio=0.2, irradiance=800)
        self.assertAlmostEqual(corrected_isc(module, site), 11.1815 * 0.8 * 1.14)
        # Rear-side current gain is not installed front-side STC nameplate power.
        self.assertEqual(self.result(module=module, site=site).metrics["dc_power"], 6400)

    def test_monofacial_rear_gain_ignored_with_warning(self):
        site = replace(self.site, rear_irradiance_ratio=0.2)
        self.assertAlmostEqual(corrected_isc(self.module, site), 11.1815)
        self.assertEqual(self.status(self.result(site=site), "Rear irradiance ignored"), "WARN")

    def test_current_limit_equality_passes(self):
        inverter = replace(self.inverter, max_input_current_per_mppt=10 * 1.0165 * 2,
                           max_isc_per_mppt=11 * 1.0165 * 1.25 * 2)
        result = self.result(Array(8, (2, 0)), inverter=inverter)
        self.assertEqual(self.status(result, "MPPT 1 maximum Isc"), "PASS")
        self.assertEqual(self.status(result, "MPPT 1 operating current"), "PASS")

    def test_short_circuit_excess_is_hard_failure(self):
        inverter = replace(self.inverter, max_input_current_per_mppt=20, max_isc_per_mppt=25)
        result = self.result(Array(8, (2, 0)), inverter=inverter)
        self.assertEqual(self.status(result, "MPPT 1 maximum Isc"), "FAIL")
        self.assertEqual(result.status, "FAIL")
        self.assertEqual(result.exit_code, 2)

    def test_operating_excess_only_warns(self):
        result = self.result(Array(8, (2, 0)), inverter=replace(self.inverter, max_input_current_per_mppt=20))
        self.assertEqual(self.status(result, "MPPT 1 operating current"), "WARN")
        self.assertEqual(self.status(result, "MPPT 1 maximum Isc"), "PASS")
        self.assertEqual(result.status, "WARN")
        self.assertEqual(result.exit_code, 1)

    def test_three_strings_require_explicit_fuse(self):
        result = self.result(Array(8, (3, 0)))
        self.assertEqual(self.status(result, "MPPT 1 series fusing"), "FAIL")

    def test_two_strings_can_trigger_backfeed_fuse(self):
        result = self.result(Array(8, (2, 0)), module=replace(self.module, max_series_fuse_rating=13))
        self.assertEqual(self.status(result, "MPPT 1 series fusing"), "FAIL")

    def test_unused_mppt_has_no_current_or_fusing_check(self):
        names = [check.name for check in self.result(Array(8, (1, 0))).checks]
        self.assertIn("MPPT 2 string capacity", names)
        self.assertNotIn("MPPT 2 maximum Isc", names)
        self.assertNotIn("MPPT 2 operating current", names)
        self.assertNotIn("MPPT 2 series fusing", names)

    def test_mppt_count_mismatch_raises(self):
        with self.assertRaises(InputError):
            self.result(Array(8, (1,)))

    def test_physical_string_capacity_is_hard_failure(self):
        result = self.result(Array(8, (4, 0), 20))
        self.assertEqual(self.status(result, "MPPT 1 string capacity"), "FAIL")

    def test_limits_hand_floor_and_ceil(self):
        self.assertEqual(string_limits(self.module, self.inverter, self.site),
                         {"min_modules": 3, "max_modules": 10,
                          "recommended_min": 6, "recommended_max": 10})

    def test_maximum_voltage_floor_never_rounds_up(self):
        # Use the literal string-voltage boundary, avoiding an extra rounding
        # operation from multiplying an already rounded module-voltage literal.
        exact = 552.4695
        for limit, expected in ((exact, 10), (math.nextafter(exact, -math.inf), 9)):
            with self.subTest(limit=limit):
                inverter = replace(self.inverter, max_dc_voltage=limit)
                self.assertEqual(string_limits(self.module, inverter, self.site)["max_modules"], expected)

    def test_module_system_rating_also_caps_count(self):
        module = replace(self.module, max_system_voltage=500)
        self.assertEqual(string_limits(module, self.inverter, self.site)["max_modules"], 9)
        self.assertEqual(self.status(self.result(Array(10, (1, 0)), module=module),
                                     "Cold Voc / module system voltage"), "FAIL")

    def test_minimum_hot_eol_ceil_boundary(self):
        boundary = 34.238 * 4
        for minimum, expected in ((boundary, 4), (math.nextafter(boundary, math.inf), 5)):
            with self.subTest(minimum=minimum):
                inverter = replace(self.inverter, mppt_min=minimum)
                self.assertEqual(string_limits(self.module, inverter, self.site)["min_modules"], expected)

    def test_start_voltage_controls_minimum(self):
        inverter = replace(self.inverter, start_voltage=190)
        self.assertEqual(string_limits(self.module, inverter, self.site)["min_modules"], 5)
        self.assertEqual(self.status(self.result(Array(4, (1, 0)), inverter=inverter), "Start voltage"), "FAIL")

    def test_cold_operating_voltage_controls_maximum(self):
        inverter = replace(self.inverter, mppt_max=400, full_power_mppt_max=400)
        self.assertEqual(string_limits(self.module, inverter, self.site)["max_modules"], 8)
        self.assertEqual(self.status(self.result(Array(9, (1, 0)), inverter=inverter),
                                     "Cold Vmp / MPPT maximum"), "FAIL")

    def test_full_power_warning_is_distinct_from_operating_failure(self):
        result = self.result(Array(4, (1, 0)))
        self.assertEqual(self.status(result, "Hot EOL Vmp / MPPT minimum"), "PASS")
        self.assertEqual(self.status(result, "Typical Vmp / full-power window"), "WARN")
        self.assertNotEqual(result.status, "FAIL")

    def test_full_power_limits_use_typical_voltage_not_nominal(self):
        inverter = replace(self.inverter, full_power_mppt_min=250, full_power_mppt_max=350)
        expected = {"min_modules": 3, "max_modules": 10,
                    "recommended_min": 7, "recommended_max": 9}
        self.assertEqual(string_limits(self.module, inverter, self.site), expected)
        self.assertEqual(string_limits(self.module, replace(inverter, nominal_dc_voltage=300), self.site), expected)

    def test_table_comparison_does_not_override_coefficient(self):
        # Table Voc is 58.41 V, so ten modules exceed 570 V, while beta Voc is safe.
        inverter = replace(self.inverter, max_dc_voltage=570)
        result = self.result(Array(10, (1, 0)), inverter=inverter)
        self.assertAlmostEqual(result.metrics["voc_cold_table"], 58.41)
        self.assertEqual(self.status(result, "Cold Voc / inverter maximum"), "PASS")
        self.assertEqual(result.limits["max_modules"], 10)

    def test_below_table_range_still_uses_manufacturer_voc(self):
        result = self.result(site=replace(self.site, tmin=-41))
        self.assertIsNone(result.metrics["voc_cold_table"])
        self.assertAlmostEqual(result.metrics["voc_cold"], 49.5 * (1 + 0.0027 * 66))
        self.assertEqual(self.status(result, "NEC table comparison"), "WARN")

    def test_dc_power_and_ratio(self):
        result = self.result(Array(8, (2, 1)))
        self.assertEqual(result.metrics["dc_power"], 9600)
        self.assertEqual(result.metrics["dc_ac_ratio"], 0.96)
        self.assertEqual(self.status(self.result(inverter=replace(self.inverter, max_dc_power=6399)),
                                     "Maximum DC power"), "FAIL")

    def test_pass_exit_code_and_check_design_consistency(self):
        array = Array(10, (2, 1))
        result = self.result(array)
        self.assertEqual(result.status, "PASS")
        self.assertEqual(result.exit_code, 0)
        self.assertEqual(check_design(self.module, self.inverter, self.site, array), result.checks)

    def test_thermal_ordering_rejected(self):
        with self.assertRaises(InputError):
            design_metrics(self.module, self.inverter, replace(self.site, typical_cell_temperature=59))


class SuggestionTests(unittest.TestCase):
    def setUp(self):
        self.module, self.inverter, self.site = fixtures()

    def test_only_nonfailing_designs_and_auto_fuses(self):
        suggestions = suggest(self.module, self.inverter, self.site)
        self.assertTrue(suggestions)
        self.assertTrue(any(max(s.array.strings_per_mppt) == 3 for s in suggestions))
        for suggestion in suggestions:
            self.assertFalse(any(c.status == "FAIL" for c in suggestion.result.checks))
            self.assertNotEqual(evaluate(self.module, self.inverter, self.site, suggestion.array).status, "FAIL")
            if max(suggestion.array.strings_per_mppt) >= 3:
                self.assertEqual(suggestion.array.fuse_rating, 18)

    def test_symmetry_representatives_complete_and_unique(self):
        # Independently enumerate ordered physical mappings, then canonicalize.
        expected = set()
        for n, first, second in product(range(3, 11), range(4), range(4)):
            if first + second == 0:
                continue
            fuse = 18 if max(first, second) >= 3 else None
            array = Array(n, (first, second), fuse)
            if evaluate(self.module, self.inverter, self.site, array).status != "FAIL":
                expected.add((n, tuple(sorted((first, second), reverse=True))))
        suggestions = suggest(self.module, self.inverter, self.site)
        actual = [(s.array.modules_per_string, s.array.strings_per_mppt) for s in suggestions]
        self.assertEqual(len(actual), len(set(actual)))
        self.assertEqual(set(actual), expected)
        self.assertTrue(all(mapping == tuple(sorted(mapping, reverse=True)) for _, mapping in actual))

    def test_target_power_changes_top_rank(self):
        for target in (3.2, 6.4, 12.8):
            with self.subTest(target=target):
                suggestions = suggest(self.module, self.inverter, self.site, target_dc_kw=target)
                self.assertEqual(suggestions[0].result.metrics["dc_power"], target * 1000)
                self.assertEqual([s.score for s in suggestions], sorted(s.score for s in suggestions))

    def test_balanced_mapping_preferred_for_same_count_and_power(self):
        suggestions = suggest(self.module, self.inverter, self.site, target_dc_kw=12.8)
        scores = {s.array.strings_per_mppt: s.score for s in suggestions if s.array.modules_per_string == 8}
        self.assertLess(scores[(2, 2)], scores[(3, 1)])

    def test_nominal_voltage_influences_equal_power_ranking(self):
        for nominal, expected in ((300, 8), (400, 10)):
            with self.subTest(nominal=nominal):
                ranked = suggest(self.module, replace(self.inverter, nominal_dc_voltage=nominal), self.site, 16)
                first = next(s for s in ranked if s.array.modules_per_string == 8 and s.array.strings_per_mppt == (3, 2))
                second = next(s for s in ranked if s.array.modules_per_string == 10 and s.array.strings_per_mppt == (2, 2))
                self.assertEqual(first.result.metrics["dc_power"], 16000)
                self.assertEqual(second.result.metrics["dc_power"], 16000)
                preferred = min((first, second), key=lambda s: s.score)
                self.assertEqual(preferred.array.modules_per_string, expected)

    def test_impossible_voltage_window_empty(self):
        inverter = replace(self.inverter, start_voltage=600)
        self.assertEqual(suggest(self.module, inverter, self.site), [])

    def test_impossible_current_empty(self):
        inverter = replace(self.inverter, max_input_current_per_mppt=5, max_isc_per_mppt=10)
        self.assertEqual(suggest(self.module, inverter, self.site), [])

    def test_impossible_dc_power_empty(self):
        self.assertEqual(suggest(self.module, replace(self.inverter, max_dc_power=100), self.site), [])

    def test_impossible_fuses_exclude_three_parallel(self):
        module = replace(self.module, max_series_fuse_rating=17)
        suggestions = suggest(module, self.inverter, self.site)
        self.assertTrue(suggestions)
        self.assertTrue(all(max(s.array.strings_per_mppt) < 3 for s in suggestions))


# Literal reference values, independent of calc.NEC_FACTORS. Each endpoint and
# fractional transition is its own test so unittest reports parameter cases.
_BANDS = ((20, 24, 1.02), (15, 19, 1.04), (10, 14, 1.06), (5, 9, 1.08),
          (0, 4, 1.10), (-5, -1, 1.12), (-10, -6, 1.14), (-15, -11, 1.16),
          (-20, -16, 1.18), (-25, -21, 1.20), (-30, -26, 1.21),
          (-35, -31, 1.23), (-40, -36, 1.25))


class ParameterCases(unittest.TestCase):
    pass


def factor_case(temperature, expected):
    def test(self):
        self.assertEqual(nec_voltage_factor(temperature), expected)
    return test


for _index, (_lo, _hi, _factor) in enumerate(_BANDS):
    setattr(ParameterCases, "test_nec_band_{}_lower".format(_index), factor_case(_lo, _factor))
    setattr(ParameterCases, "test_nec_band_{}_upper".format(_index), factor_case(_hi, _factor))
    setattr(ParameterCases, "test_nec_band_{}_decimal_floor".format(_index), factor_case(_hi + 0.9, _factor))
for _index, (_temperature, _factor) in enumerate(((25, 1), (25.1, 1), (40, 1),
                                                (19.99, 1.04), (-0.01, 1.12), (-35.01, 1.25))):
    setattr(ParameterCases, "test_nec_extra_{}".format(_index), factor_case(_temperature, _factor))


def below_table_case(temperature):
    def test(self):
        with self.assertRaises(InputError):
            nec_voltage_factor(temperature)
    return test


for _index, _temperature in enumerate((-40.001, -41, -100)):
    setattr(ParameterCases, "test_nec_below_table_{}".format(_index), below_table_case(_temperature))


def racking_case(racking, expected):
    def test(self):
        module, _, site = fixtures()
        self.assertEqual(cell_temperature(replace(site, fixed_delta_t=None, racking=racking), module), expected)
    return test


for _racking, _hot in (("open-rack", 58), ("roof", 63), ("bipv", 73)):
    setattr(ParameterCases, "test_racking_" + _racking.replace("-", "_"), racking_case(_racking, _hot))


def fuse_case(rating, status):
    def test(self):
        module, inverter, site = fixtures()
        result = evaluate(module, inverter, site, Array(8, (3, 0), rating))
        check = next(c for c in result.checks if c.name == "MPPT 1 series fuse rating")
        self.assertEqual(check.status, status)
    return test


for _index, (_rating, _status) in enumerate(((20, "PASS"), (25, "PASS"), (26, "FAIL"),
                                           (15, "FAIL"), (17.47109375, "PASS"))):
    setattr(ParameterCases, "test_fuse_rating_{}".format(_index), fuse_case(_rating, _status))


def invalid_retention_case(retention):
    def test(self):
        module, _, _ = fixtures()
        with self.assertRaises(InputError):
            hot_vmp(module, 58, retention)
    return test


for _index, _retention in enumerate((0, -0.1, 1.01, float("nan"))):
    setattr(ParameterCases, "test_invalid_retention_{}".format(_index), invalid_retention_case(_retention))


def invalid_target_case(target):
    def test(self):
        module, inverter, site = fixtures()
        with self.assertRaises(InputError):
            suggest(module, inverter, site, target_dc_kw=target)
    return test


for _index, _target in enumerate((0, -1, True, float("nan"), float("inf"))):
    setattr(ParameterCases, "test_invalid_target_{}".format(_index), invalid_target_case(_target))


if __name__ == "__main__":
    unittest.main()
