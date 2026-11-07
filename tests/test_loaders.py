"""Strict input validation, packaged resources, and reproducible templates."""

from __future__ import annotations

import json
from dataclasses import asdict

import pytest

from pvstring.library import list_library, load_builtin, template
from pvstring.loaders import from_dict, load_array, load_inverter, load_module, load_site
from pvstring.models import Array, InputError, Inverter, Module, Site


@pytest.mark.parametrize("kind,identifier", [
    ("module", "generic-410"), ("module", "generic-550"),
    ("inverter", "generic-5kw"), ("inverter", "generic-10kw"),
    ("inverter", "generic-100kw-1500v"),
])
def test_packaged_generics_valid_and_labelled(kind, identifier):
    model = load_builtin(kind, identifier)
    assert "Generic" in model.name
    assert "illustrative" in model.name
    assert from_dict(type(model), asdict(model)) == model


@pytest.mark.parametrize("kind", ["module", "inverter", "site"])
def test_templates_roundtrip(tmp_path, kind):
    data = template(kind)
    path = tmp_path / "input.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    model = {"module": load_module, "inverter": load_inverter, "site": load_site}[kind](path)
    assert model.name == data["name"]


@pytest.mark.parametrize("bom", [b"", b"\xef\xbb\xbf"], ids=["utf8", "utf8-bom"])
@pytest.mark.parametrize("kind", ["module", "inverter", "site"])
def test_utf8_datasheet_bytes_roundtrip(tmp_path, kind, bom):
    data = template(kind)
    data["name"] = "Datasheet – 25 °C / 模块"
    if kind == "module":
        data["beta_voc"] = "-0.27%/°C"
    path = tmp_path / (kind + ".json")
    path.write_bytes(bom + json.dumps(data, ensure_ascii=False).encode("utf-8"))
    loader = {"module": load_module, "inverter": load_inverter, "site": load_site}[kind]
    loaded = loader(path)
    assert asdict(loaded) == data


def test_array_roundtrip(tmp_path):
    path = tmp_path / "array.json"
    path.write_text('{"modules_per_string": 8, "strings_per_mppt": [1, 0]}', encoding="utf-8")
    assert load_array(path) == Array(8, (1, 0))


@pytest.mark.parametrize("contents,expected", [
    ("{", "Expecting"), ("[]", "expected a JSON object"),
    ('{"name":"test"}', "missing required"),
    ('{"name":"test", "tmin":-18, "thigh":33, "thig":34}', "unknown field(s): thig"),
    ('{"name":"test", "tmin":NaN, "thigh":33}', "invalid JSON number"),
    ('{"name":"test", "tmin":-Infinity, "thigh":33}', "invalid JSON number"),
    ('{"name":"test", "tmin":-18, "thigh":1e400}', "finite number"),
    ('{"name":"test", "tmin":-18, "tmin":-20, "thigh":33}', "duplicate JSON key: tmin"),
    ('{"name":"test", "tmin":"-18", "thigh":33}', "finite number"),
    ('{"name":"test", "tmin":true, "thigh":33}', "finite number"),
    ('{"name":"test", "tmin":34, "thigh":33}', "must not exceed"),
])
def test_loading_errors_are_path_aware(tmp_path, contents, expected):
    path = tmp_path / "bad-site.json"
    path.write_text(contents, encoding="utf-8")
    with pytest.raises(InputError) as error:
        load_site(path)
    assert str(path) in str(error.value)
    assert expected in str(error.value)


def test_missing_file_clear(tmp_path):
    with pytest.raises(InputError, match="absent.json"):
        load_site(tmp_path / "absent.json")


def test_bad_unicode_clear(tmp_path):
    path = tmp_path / "bad.json"
    path.write_bytes(b'\xff')
    with pytest.raises(InputError, match="bad.json"):
        load_module(path)


@pytest.mark.parametrize("kind,identifier", [("site", "generic-410"), ("module", "../generic-410"), ("inverter", "generic-410")])
def test_library_identifier_validation(kind, identifier):
    with pytest.raises(InputError, match="unknown"):
        load_builtin(kind, identifier)


def test_explicit_builtin_loaders():
    assert isinstance(load_module("builtin:generic-410"), Module)
    assert isinstance(load_inverter("builtin:generic-5kw"), Inverter)
    assert len(list_library()["module"]) == 2
    assert len(list_library()["inverter"]) == 3


def test_invalid_template_kind():
    with pytest.raises(InputError, match="choose"):
        template("array")


def test_wrong_object_type():
    with pytest.raises(InputError, match="JSON object"):
        from_dict(Site, None)
