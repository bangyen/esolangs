"""Validated witnesses for language-owned generator measurements."""

from __future__ import annotations

import random
import tomllib
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from esolangs.registry import LANGUAGES

PACKAGES = Path(__file__).resolve().parents[2] / "src/esolangs/languages"
_RULES = frozenset({"parity", "and", "or", "majority", "zero", "random"})
_UNITS = frozenset({"chars", "codels", "pixels"})


@dataclass(frozen=True)
class TableWitness:
    """A named truth table with an explicit random seed when needed."""

    arity: int
    rule: str
    seed: int | None = None

    def __post_init__(self) -> None:
        """Reject unnamed rules, invalid arities and implicit random seeds."""
        if type(self.arity) is not int or self.arity < 1:
            raise ValueError("witness arity must be a positive integer")
        if not isinstance(self.rule, str) or self.rule not in _RULES:
            raise ValueError(f"unknown witness rule: {self.rule}")
        if (self.rule == "random") != (self.seed is not None):
            raise ValueError("only random witnesses require a seed")
        if self.seed is not None and type(self.seed) is not int:
            raise ValueError("witness seed must be an integer")

    @property
    def name(self) -> str:
        """Return the docstring's table label."""
        return f"random {self.seed}" if self.rule == "random" else self.rule

    def table(self) -> str:
        """Return the witness in MSB-first row order."""
        n = self.arity
        if self.rule == "random":
            return format(random.Random(self.seed).getrandbits(1 << n), f"0{1 << n}b")
        rules: dict[str, Callable[[int], int]] = {
            "parity": lambda ones: ones % 2,
            "and": lambda ones: ones == n,
            "or": lambda ones: ones > 0,
            "majority": lambda ones: 2 * ones > n,
            "zero": lambda _: 0,
        }
        rule = rules[self.rule]
        return "".join(str(int(rule(row.bit_count()))) for row in range(1 << n))


@dataclass(frozen=True)
class SourceAnchor:
    """An emitted size at scale one, tied to its backend construction."""

    witness: TableWitness
    size: int
    unit: str
    construction: str

    @property
    def text(self) -> str:
        """Return the required docstring anchor."""
        return f"n={self.witness.arity} {self.witness.name}: {self.size:,} {self.unit}"


def parse_anchors(language: str, data: dict[str, Any]) -> tuple[SourceAnchor, ...]:
    """Validate versioned measurement records; refuse unknown fields."""
    if (
        not isinstance(data, dict)
        or set(data) != {"version", "anchors"}
        or type(data["version"]) is not int
    ):
        raise ValueError("evidence requires version and anchors")
    if data["version"] != 1 or not isinstance(data["anchors"], list):
        raise ValueError("unsupported evidence schema")
    backend = LANGUAGES[language].backend
    if backend is None:
        raise ValueError("source anchors require a Boolean generator")
    generate = backend.generate
    construction = f"{generate.__module__}:{generate.__name__}"
    found = []
    for row in data["anchors"]:
        required = {"arity", "rule", "size", "unit", "scale", "construction"}
        if not isinstance(row, dict) or set(row) - {"seed"} != required:
            raise ValueError("invalid source anchor fields")
        if type(row["size"]) is not int or row["size"] < 1:
            raise ValueError("anchor size must be a positive integer")
        if not isinstance(row["unit"], str) or row["unit"] not in _UNITS:
            raise ValueError("unknown source anchor unit")
        if (row["unit"] == "chars") == (
            LANGUAGES[language].runtime.source_kind == "raster"
        ):
            raise ValueError("source anchor unit does not match the source kind")
        if type(row["scale"]) is not int or row["scale"] != 1:
            raise ValueError("source anchors measure default scale one")
        if row["construction"] != construction:
            raise ValueError("source anchor construction does not match its backend")
        found.append(
            SourceAnchor(
                TableWitness(row["arity"], row["rule"], row.get("seed")),
                row["size"],
                row["unit"],
                construction,
            )
        )
    if not found or len({(a.witness, a.unit) for a in found}) != len(found):
        raise ValueError("source anchors must be nonempty and unique")
    return tuple(found)


def source_anchors(language: str) -> tuple[SourceAnchor, ...]:
    """Read the language's structured measurements, independent of prose."""
    path = PACKAGES / LANGUAGES[language].id / "language.toml"
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    return parse_anchors(language, data["evidence"])
