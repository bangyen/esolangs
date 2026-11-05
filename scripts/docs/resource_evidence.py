"""Resource formulas with explicit scope, units and execution witnesses."""

from __future__ import annotations

import importlib
import inspect
import tomllib
from collections.abc import Callable
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any, cast

from esolangs.registry import LANGUAGES

from .resource_formula import expression_formula

PACKAGES = Path(__file__).resolve().parents[2] / "src/esolangs/languages"
COLUMNS = frozenset({"execution", "workspace", "scaling"})
Formula = Callable[[int, str], int | float | Fraction]
_UNITS = frozenset(
    {
        "commands",
        "steps",
        "rewrites",
        "nodes",
        "instructions",
        "lines",
        "rows",
        "characters",
        "cells",
        "codels",
        "pixels",
        "bits",
    }
)


@dataclass(frozen=True)
class ResourceBound:
    """One bound and its existing measurement scope; exactness can vary by arity."""

    formula: Formula
    exact: bool | frozenset[int]
    arities: tuple[int, ...]
    first: int
    unit: str
    witnesses: str
    construction: str


def _arities(value: object) -> tuple[int, ...]:
    """Validate a nonempty sequence of distinct positive arities."""
    if (
        not isinstance(value, list)
        or not value
        or any(type(n) is not int or n < 1 for n in value)
        or len(set(value)) != len(value)
    ):
        raise ValueError("resource arities must be distinct positive integers")
    return tuple(value)


def _provider(language: str, reference: object) -> Formula:
    """Resolve only an owned, explicitly named formula provider."""
    if not isinstance(reference, str):
        raise ValueError("resource provider must be a module:function reference")
    module, separator, function = reference.partition(":")
    prefix = f"esolangs.languages.{LANGUAGES[language].id}."
    if not separator or not module.startswith(prefix) or not function.isidentifier():
        raise ValueError("resource provider must belong to its language")
    provider = getattr(importlib.import_module(module), function, None)
    if (
        not inspect.isfunction(provider)
        or provider.__module__ != module
        or provider.__name__ != function
    ):
        raise ValueError("resource provider is not an owned function")
    return cast(Formula, provider)


def parse_bounds(language: str, data: dict[str, Any]) -> dict[str, ResourceBound]:
    """Validate formula records without interpreting proof prose."""
    if (
        not isinstance(data, dict)
        or set(data) - COLUMNS != {"version"}
        or type(data.get("version")) is not int
        or data["version"] != 1
    ):
        raise ValueError("unsupported resource evidence schema")
    backend = LANGUAGES[language].backend
    if backend is None:
        raise ValueError("resource evidence requires a Boolean generator")
    generate = backend.generate
    construction = f"{generate.__module__}:{generate.__name__}"
    found = {}
    for column in COLUMNS & data.keys():
        row = data[column]
        required = {"exact", "arities", "first", "unit", "witnesses", "construction"}
        if not isinstance(row, dict) or set(row) not in (
            required | {"expression"},
            required | {"provider"},
        ):
            raise ValueError("invalid resource bound fields")
        arities = _arities(row["arities"])
        exact = row["exact"]
        if type(exact) is not bool:
            exact = frozenset(_arities(exact))
        if type(row["first"]) is not int or row["first"] < 1:
            raise ValueError("resource scope must start at a positive arity")
        unit = row["unit"]
        if not isinstance(unit, str) or unit not in _UNITS:
            raise ValueError("invalid resource unit")
        if column == "workspace" and unit != "bits":
            raise ValueError("workspace bounds measure bits")
        if column == "execution" and unit not in {
            "commands",
            "steps",
            "rewrites",
            "lines",
            "nodes",
            "instructions",
        }:
            raise ValueError("execution bounds require a command unit")
        if column == "scaling" and unit not in {
            "characters",
            "lines",
            "rows",
            "cells",
            "codels",
            "pixels",
        }:
            raise ValueError("scaling bounds require an emitted source unit")
        if row["witnesses"] != "tests.proofs.execution:tables":
            raise ValueError("resource witnesses must retain the execution corpus")
        if row["construction"] != construction:
            raise ValueError("resource construction does not match its backend")
        formula: Formula
        if "expression" in row:
            if not isinstance(row["expression"], str):
                raise ValueError("resource expression must be text")
            formula = expression_formula(row["expression"])
        else:
            formula = _provider(language, row["provider"])
        found[column] = ResourceBound(
            formula,
            exact,
            arities,
            row["first"],
            unit,
            row["witnesses"],
            construction,
        )
    if not {"execution", "workspace"} <= found.keys():
        raise ValueError("resource evidence requires execution and workspace bounds")
    return found


def resource_bounds(language: str) -> dict[str, ResourceBound]:
    """Read validated resource records from the owning language."""
    path = PACKAGES / LANGUAGES[language].id / "language.toml"
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    return parse_bounds(language, data["resource_evidence"])
