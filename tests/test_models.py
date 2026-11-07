"""Model and coefficient contracts, independent of loaders and built-in data."""

from dataclasses import FrozenInstanceError, replace

import pytest

from pvstring.calc import evaluate
from pvstring.models import Array, InputError, Inverter, Module, Site, finite_number, parse_coefficient


def module(**changes):
    values = dict(name="Test module", pmax_stc=400, voc=50, isc=11,
                  vmp=40, imp=10, beta_voc=-0.27, alpha_isc=0.05,
                  gamma_pmax=-0.35, gamma_vmp=-0.3)
    values.update(changes)
    return Module(**values)


def inverter(**changes):
    values = dict(name="Test inverter", max_dc_voltage=600, start_voltage=120,
                  mppt_min=100, mppt_max=550, full_power_mppt_min=200,
                  full_power_mppt_max=500, nominal_dc_voltage=320,
                  num_mppts=2, max_input_current_per_mppt=20,
                  max_isc_per_mppt=30, strings_per_mppt=2,
                  max_dc_power=10000, ac_rated_power=5000)
    values.update(changes)
    return Inverter(**values)


def site(**changes):
    values = dict(name="Test site", tmin=-10, thigh=35)
    values.update(changes)
    return Site(**values)


@pytest.mark.parametrize("value", [-0.27, "-0.27%/°C", "-0.27 % / degC", "-0.27%/C", " -2.7e-1 %/DEGC "])
def test_relative_coefficient_units(value):
    assert parse_coefficient(value) == pytest.approx(-0.0027)


@pytest.mark.parametrize("value", ["-0.134 V/°C", "-0.134 V/degC", "-0.134 v/C"])
def test_absolute_coefficient_uses_reference_voltage(value):
    assert parse_coefficient(value, 50) == pytest.approx(-0.134 / 50)


@pytest.mark.parametrize("value", ["-0.27", "-0.27 A/°C", "-0.27 W/degC", "-0.27%/K", "-0.27V", "nan%/C", "inf%/C", "-0.27%/C extra", ""])
def test_bad_coefficient_units_explain_supported_forms(value):
    with pytest.raises(InputError, match="coefficient:.*%/°C"):
        parse_coefficient(value)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf"), True, None, "10", 10**1000])
def test_finite_number_rejects_nonfinite_and_non_numeric_types(value):
    with pytest.raises(InputError, match="rating: expected a finite number"):
        finite_number(value, "rating")


@pytest.mark.parametrize("value", [0, -3, 2.5])
def test_finite_number_accepts_real_numbers(value):
    assert finite_number(value, "rating") == float(value)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf"), True, None, "1e309%/C"])
def test_coefficient_rejects_nonfinite_and_wrong_types(value):
    with pytest.raises(InputError, match="coefficient:.*finite number"):
        parse_coefficient(value)


def test_absolute_coefficient_requires_voltage_reference():
    with pytest.raises(InputError, match="requires a reference voltage"):
        parse_coefficient("-0.134 V/°C")


@pytest.mark.parametrize("reference", [0, -1, float("nan"), True])
def test_absolute_coefficient_rejects_invalid_voltage_reference(reference):
    with pytest.raises(InputError, match="reference_voltage:"):
        parse_coefficient("-0.134 V/°C", reference)


def test_dataclasses_accept_explicit_units_and_are_frozen():
    value = module(beta_voc="-0.134 V/degC", gamma_vmp="-0.12 V/°C",
                   alpha_isc="0.05 %/C", gamma_pmax="-0.35%/degC")
    assert value.pmax_stc == 400
    with pytest.raises(FrozenInstanceError):
        value.voc = 55


@pytest.mark.parametrize("factory", [module, inverter, site])
@pytest.mark.parametrize("name", ["", "  ", None, 123])
def test_names_require_nonempty_strings(factory, name):
    with pytest.raises(InputError, match="name: must be a nonempty string"):
        factory(name=name)


@pytest.mark.parametrize("power", [100, 1000])
def test_inconsistent_nameplate_power_has_actionable_error(power):
    with pytest.raises(InputError, match="pmax_stc:.*5%.*W/V/A"):
        module(pmax_stc=power)


@pytest.mark.parametrize("power", [400 / 1.04, 400 / 0.96])
def test_consistent_power_tolerates_datasheet_rounding(power):
    assert module(pmax_stc=power).pmax_stc == power


@pytest.mark.parametrize("changes", [dict(vmp=50, pmax_stc=500), dict(imp=12, pmax_stc=480)])
def test_module_voltage_and_current_relationships(changes):
    with pytest.raises(InputError, match="Vmp < Voc and Imp <= Isc"):
        module(**changes)


@pytest.mark.parametrize("field,value", [("beta_voc", 0), ("beta_voc", 0.1), ("alpha_isc", -0.1), ("gamma_pmax", 0), ("gamma_vmp", 0.1)])
def test_coefficient_sign_validation_identifies_field(field, value):
    with pytest.raises(InputError, match=field + ":"):
        module(**{field: value})


@pytest.mark.parametrize("field", ["alpha_isc", "gamma_pmax"])
def test_non_voltage_coefficients_reject_absolute_voltage_units(field):
    with pytest.raises(InputError, match="this field requires %/°C"):
        module(**{field: "-0.1 V/°C"})


def test_optional_vmp_coefficient_and_zero_current_coefficient():
    assert module(gamma_vmp=None, alpha_isc=0).gamma_vmp is None


@pytest.mark.parametrize("field", ["noct", "nmot"])
@pytest.mark.parametrize("value", [20, 100, float("nan")])
def test_nominal_temperature_boundaries(field, value):
    with pytest.raises(InputError, match=field + ":"):
        module(**{field: value})


def test_nominal_temperature_can_be_omitted_for_fixed_thermal_model():
    assert module(noct=None, nmot=None).noct is None


@pytest.mark.parametrize("changes", [dict(bifacial=1), dict(bifaciality=0.7), dict(bifacial=True), dict(bifacial=True, bifaciality=1.1)])
def test_bifacial_flag_and_response_are_consistent(changes):
    with pytest.raises(InputError, match="bifacial"):
        module(**changes)


def test_bifacial_response_accepts_positive_fraction():
    assert module(bifacial=True, bifaciality=0.7).bifaciality == 0.7


@pytest.mark.parametrize("factory,field", [(module, "voc"), (inverter, "max_dc_power"), (site, "irradiance")])
@pytest.mark.parametrize("value", [0, -1, True, "100", float("nan"), float("inf")])
def test_positive_finite_ratings(factory, field, value):
    with pytest.raises(InputError, match=field + ":"):
        factory(**{field: value})


@pytest.mark.parametrize("field", ["num_mppts", "strings_per_mppt"])
@pytest.mark.parametrize("value", [0, -1, True, 2.0, "2"])
def test_inverter_counts_require_positive_integers(field, value):
    with pytest.raises(InputError, match=field + ": must be an integer >= 1"):
        inverter(**{field: value})


@pytest.mark.parametrize("changes,pattern", [
    (dict(full_power_mppt_min=90), "inverter: require"),
    (dict(full_power_mppt_max=560), "inverter: require"),
    (dict(mppt_max=650), "inverter: require"),
    (dict(nominal_dc_voltage=50), "nominal_dc_voltage:"),
    (dict(start_voltage=601), "start_voltage:"),
    (dict(max_input_current_per_mppt=31), "max_input_current_per_mppt:"),
])
def test_inverter_relationship_errors(changes, pattern):
    with pytest.raises(InputError, match=pattern):
        inverter(**changes)


@pytest.mark.parametrize("changes,pattern", [
    (dict(tmin=40), "tmin:"),
    (dict(tmin=-101), "tmin:"),
    (dict(typical_cell_temperature=-11), "typical_cell_temperature:"),
    (dict(rear_irradiance_ratio=1.1), "rear_irradiance_ratio:"),
    (dict(altitude=float("inf")), "altitude:"),
    (dict(racking="unknown"), "racking:"),
    (dict(fixed_delta_t=-1), "fixed_delta_t:"),
    (dict(racking="roof", fixed_delta_t=30), "choose fixed_delta_t or racking"),
    (dict(degradation_percent_per_year=-0.5), "degradation_percent_per_year:"),
    (dict(degradation_percent_per_year=10, design_years=10), "degradation:"),
])
def test_site_constraints_identify_invalid_assumption(changes, pattern):
    with pytest.raises(InputError, match=pattern):
        site(**changes)


@pytest.mark.parametrize("value", [-1, True, 10.0, "10"])
def test_design_years_require_nonnegative_integer(value):
    with pytest.raises(InputError, match="design_years: must be an integer >= 0"):
        site(design_years=value)


def test_zero_years_degradation_and_fixed_rise_are_valid():
    assert site(design_years=0, degradation_percent_per_year=0, fixed_delta_t=0).design_years == 0


@pytest.mark.parametrize("value", [0, -1, True, 8.0, "8", float("nan"), float("inf")])
def test_series_count_requires_positive_integer(value):
    with pytest.raises(InputError, match="modules_per_string: must be an integer >= 1"):
        Array(value, (1, 1))


@pytest.mark.parametrize("counts", [(), [], "1,1", {1, 2}, None])
def test_parallel_counts_require_nonempty_list_or_tuple(counts):
    with pytest.raises(InputError, match="strings_per_mppt: expected a nonempty list"):
        Array(8, counts)


@pytest.mark.parametrize("count", [-1, True, 1.0, "1", float("nan"), float("inf")])
def test_parallel_counts_require_nonnegative_integers(count):
    with pytest.raises(InputError, match="strings_per_mppt count: must be an integer >= 0"):
        Array(8, (1, count))


def test_array_converts_list_to_immutable_tuple_preserving_unused_mppt():
    counts = [1, 0]
    value = Array(8, counts)
    counts[0] = 2
    assert value.strings_per_mppt == (1, 0)
    assert isinstance(value.strings_per_mppt, tuple)


def test_all_unused_mppts_are_invalid():
    with pytest.raises(InputError, match="at least one MPPT must be used"):
        Array(8, (0, 0))


@pytest.mark.parametrize("rating", [0, -1, True, "20", float("nan"), float("inf")])
def test_fuse_rating_requires_positive_finite_number(rating):
    with pytest.raises(InputError, match="fuse_rating:"):
        Array(8, (1, 1), rating)


@pytest.mark.parametrize("counts", [(1,), (1, 0, 1)])
def test_evaluation_rejects_wrong_mppt_count_with_expected_and_actual(counts):
    with pytest.raises(InputError, match=f"strings_per_mppt: expected 2 counts, got {len(counts)}"):
        evaluate(module(), inverter(), site(), Array(8, counts))


def test_dataclass_replace_revalidates_input():
    with pytest.raises(InputError, match="pmax_stc:.*W/V/A"):
        replace(module(), pmax_stc=1)
