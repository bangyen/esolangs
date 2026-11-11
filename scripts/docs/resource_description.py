"""Render proof cells from explicit claims and checked formatting templates."""

from __future__ import annotations

from dataclasses import dataclass
from string import Formatter
from typing import Any, NamedTuple

from .resource_formula import arity_cases, describe_cases, source_term_names

COLUMNS = frozenset({"scaling", "execution", "workspace"})
SCALING_CLASSES = frozenset(
    {"linear", "linear, time n log", "T log T", "measured", "open", "lower bound"}
)
EXECUTION_CLASSES = frozenset({"poly n", "linear", "unmeasured"})
WORKSPACE_CLASSES = EXECUTION_CLASSES | {"T log T"}
_FIELDS = frozenset({"claim", "formula", "unit", "first", "previous"})


@dataclass(frozen=True)
class ResourceDescription:
    """A rendered clause retaining its growth class, unit and claim kind."""

    growth: str
    clause: str
    unit: str | None
    claim: str | None

    @property
    def text(self) -> str:
        """Return the ledger's public text cell."""
        return f"{self.growth}: {self.clause}"

    @property
    def bounded(self) -> bool:
        """Whether this claim has a measured resource formula."""
        return self.claim is not None


class ResourceDescriptions(NamedTuple):
    """The three independent resource claims."""

    scaling: ResourceDescription
    execution: ResourceDescription
    workspace: ResourceDescription


def _growth(column: str, value: object) -> str:
    """Validate the declared growth class without inspecting prose."""
    classes = {
        "scaling": SCALING_CLASSES,
        "execution": EXECUTION_CLASSES,
        "workspace": WORKSPACE_CLASSES,
    }[column]
    if not isinstance(value, str) or value not in classes:
        raise ValueError("invalid resource growth class")
    return value


def source_terms(value: object) -> tuple[frozenset[str], str]:
    """Read source term declarations without importing their provider."""
    if (
        not isinstance(value, dict)
        or set(value) != {"names", "provider"}
        or not isinstance(value["provider"], str)
    ):
        raise ValueError("invalid resource source term declaration")
    return source_term_names(value["names"]), value["provider"]


def formula_record(data: dict[str, Any], column: str) -> dict[str, Any]:
    """Resolve a formula shared by two claims with separate scopes and units."""
    row: dict[str, Any] = data[column]
    if "formula_ref" not in row:
        return row
    reference = row["formula_ref"]
    formula_fields = {"expression", "cases", "source_terms"}
    if (
        not isinstance(reference, str)
        or reference not in COLUMNS - {column}
        or set(row) & (formula_fields | {"provider", "qualitative"})
    ):
        raise ValueError("invalid resource formula reference")
    owner = data[reference]
    if "formula_ref" in owner or len(set(owner) & {"expression", "cases"}) != 1:
        raise ValueError("resource formula reference needs a direct expression owner")
    return {key: value for key, value in row.items() if key != "formula_ref"} | {
        key: owner[key] for key in formula_fields & owner.keys()
    }


def _description(column: str, row: dict[str, Any]) -> ResourceDescription:
    """Validate and render one quantitative or qualitative resource claim."""
    if "qualitative" in row:
        raw = row["qualitative"]
        if (
            column != "scaling"
            or set(row) != {"qualitative"}
            or not isinstance(raw, dict)
            or set(raw) != {"growth", "text"}
            or not isinstance(raw["text"], str)
            or not raw["text"]
        ):
            raise ValueError("invalid qualitative resource description")
        return ResourceDescription(
            _growth(column, raw["growth"]), raw["text"], None, None
        )
    raw = row.get("description")
    fields = {"growth", "claim", "template"}
    kinds = {"expression", "cases", "provider"} & row.keys()
    if (
        len(kinds) != 1
        or not isinstance(raw, dict)
        or set(raw) != (fields | {"formula"} if "provider" in kinds else fields)
    ):
        raise ValueError("invalid resource description fields")
    names: frozenset[str] = frozenset()
    if "source_terms" in row:
        if "provider" in kinds:
            raise ValueError("resource source terms require an expression or cases")
        names, _ = source_terms(row["source_terms"])
    if not isinstance(raw["claim"], str) or raw["claim"] not in {
        "worst",
        "at most",
        "exact",
    }:
        raise ValueError("invalid resource claim kind")
    if raw["claim"] in {"worst", "exact"} and not row.get("exact"):
        raise ValueError("exact resource claim needs an exactness check")
    unit = row.get("unit")
    first = row.get("first")
    template = raw["template"]
    if (
        not isinstance(unit, str)
        or not unit
        or type(first) is not int
        or first < 1
        or not isinstance(template, str)
    ):
        raise ValueError("invalid resource description values")
    formula = (
        describe_cases(arity_cases(row["cases"], names), first, unit)
        if "cases" in row
        else row.get("expression", raw.get("formula"))
    )
    if not isinstance(formula, str) or not formula:
        raise ValueError("invalid resource description formula")
    placeholders = set()
    try:
        for _, field, spec, conversion in Formatter().parse(template):
            if field is not None:
                if field not in _FIELDS or spec or conversion:
                    raise ValueError("invalid resource description placeholder")
                placeholders.add(field)
    except ValueError as error:
        raise ValueError("invalid resource description template") from error
    if not {"claim", "formula"} <= placeholders:
        raise ValueError("resource description must render its claim and formula")
    clause = template.format(
        claim=raw["claim"],
        formula=formula,
        unit=unit,
        first=first,
        previous=first - 1,
    )
    return ResourceDescription(
        _growth(column, raw["growth"]), clause, unit, raw["claim"]
    )


def parse_descriptions(data: dict[str, Any]) -> ResourceDescriptions:
    """Validate every resource description without importing formula providers."""
    if (
        not isinstance(data, dict)
        or set(data) - {"witnesses", "corpus", "sparse"}
        != COLUMNS | {"version", "construction"}
        or type(data["version"]) is not int
        or data["version"] != 2
        or not isinstance(data["construction"], str)
        or not data["construction"]
        or any(
            not isinstance(data[key], str)
            for key in {"witnesses", "corpus"} & data.keys()
        )
        or ("sparse" in data and not isinstance(data["sparse"], dict))
        or any(not isinstance(data[c], dict) for c in COLUMNS)
    ):
        raise ValueError("invalid resource descriptions schema")
    return ResourceDescriptions(
        _description("scaling", formula_record(data, "scaling")),
        _description("execution", formula_record(data, "execution")),
        _description("workspace", formula_record(data, "workspace")),
    )
