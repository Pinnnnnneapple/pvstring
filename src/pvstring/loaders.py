"""Strict JSON loaders with path-aware, user-facing errors."""

from __future__ import annotations

import json
from dataclasses import MISSING, fields
from pathlib import Path
from typing import Any, Dict, Type, TypeVar, Union

from .models import Array, InputError, Inverter, Module, Site

Model = TypeVar("Model", Module, Inverter, Site, Array)


def from_dict(model: Type[Model], data: Dict[str, Any]) -> Model:
    """Validate a JSON object against a model, rejecting unknown/missing fields."""
    if not isinstance(data, dict):
        raise InputError(f"{model.__name__}: expected a JSON object")
    definitions = {field.name: field for field in fields(model)}
    unknown = set(data) - set(definitions)
    if unknown:
        raise InputError(f"{model.__name__}: unknown field(s): {', '.join(sorted(unknown))}")
    missing = [name for name, field in definitions.items()
               if name not in data and field.default is MISSING and field.default_factory is MISSING]
    if missing:
        raise InputError(f"{model.__name__}: missing required field(s): {', '.join(missing)}")
    try:
        return model(**data)
    except (ValueError, TypeError, OverflowError) as error:
        raise InputError(f"{model.__name__}: {error}") from None


def _pairs(pairs: Any) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise InputError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _constant(value: str) -> None:
    raise InputError(f"invalid JSON number: {value}; numbers must be finite")


def load_json(path: Union[str, Path], model: Type[Model]) -> Model:
    """Read a UTF-8 JSON datasheet/site/array and report contextual input errors."""
    try:
        with Path(path).open(encoding="utf-8") as handle:
            data = json.load(handle, object_pairs_hook=_pairs, parse_constant=_constant)
        return from_dict(model, data)
    except (OSError, UnicodeError, ValueError, RecursionError) as error:
        raise InputError(f"{path}: {error}") from None


def load_module(path: Union[str, Path]) -> Module:
    """Load a module JSON file (or explicit ``builtin:`` library identifier)."""
    if str(path).startswith("builtin:"):
        from .library import load_builtin
        return load_builtin("module", str(path)[8:])
    return load_json(path, Module)


def load_inverter(path: Union[str, Path]) -> Inverter:
    """Load an inverter JSON file (or explicit ``builtin:`` library identifier)."""
    if str(path).startswith("builtin:"):
        from .library import load_builtin
        return load_builtin("inverter", str(path)[8:])
    return load_json(path, Inverter)


def load_site(path: Union[str, Path]) -> Site:
    """Load a site JSON file."""
    return load_json(path, Site)


def load_array(path: Union[str, Path]) -> Array:
    """Load an array configuration JSON file."""
    return load_json(path, Array)
