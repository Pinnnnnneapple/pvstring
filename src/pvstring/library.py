"""Bundled illustrative generic datasheets, never substitutes for real products."""

from __future__ import annotations

import json
from importlib import resources
from typing import Any, Dict, List, Union

from .loaders import from_dict
from .models import InputError, Inverter, Module, Site

_IDENTIFIERS = {
    "module": ("generic-410", "generic-550"),
    "inverter": ("generic-5kw", "generic-10kw", "generic-100kw-1500v"),
}


def load_builtin(kind: str, identifier: str) -> Union[Module, Inverter]:
    """Load a named illustrative dataset, rejecting arbitrary resource paths."""
    if kind not in _IDENTIFIERS or identifier not in _IDENTIFIERS[kind]:
        raise InputError(f"library: unknown {kind} '{identifier}'; run pvstring library")
    data = json.loads(resources.files("pvstring").joinpath("data").joinpath(identifier + ".json").read_text(encoding="utf-8"))
    return from_dict(Module if kind == "module" else Inverter, data)


def list_library() -> Dict[str, List[Dict[str, str]]]:
    """Return the identifiers and names of all illustrative generic datasheets."""
    return {kind: [{"id": identifier, "name": load_builtin(kind, identifier).name}
                   for identifier in identifiers] for kind, identifiers in _IDENTIFIERS.items()}


def template(kind: str) -> Dict[str, Any]:
    """Return an editable module, inverter, or site template in canonical units."""
    from dataclasses import asdict
    if kind == "module":
        return asdict(load_builtin("module", "generic-410"))
    if kind == "inverter":
        return asdict(load_builtin("inverter", "generic-5kw"))
    if kind == "site":
        return asdict(Site(name="Illustrative cold-location design temperatures", tmin=-18, thigh=33))
    raise InputError("template: choose module, inverter, or site")
