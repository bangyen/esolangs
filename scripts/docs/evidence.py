"""Validated witnesses for language-owned generator measurements."""

from __future__ import annotations

import hashlib
import random
import re
import tomllib
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from esolangs.registry import LANGUAGES

PACKAGES = Path(__file__).resolve().parents[2] / "src/esolangs/languages"
_RULES = frozenset(
    {"parity", "and", "or", "majority", "zero", "one", "random", "dense"}
)
SOURCE_ANCHOR = re.compile(
    r"n=(\d+)\s+(parity|and|or|majority|zero|one|dense|random\s+-?\d+):\s*"
    r"([\d,]+)\s+(chars|codels|pixels)"
)
_UNITS = frozenset({"chars", "codels", "pixels"})


def dense(n: int, key: bytes | None = None) -> str:
    """A deterministic pseudo-random table, the worst case to fold.

    With ``key`` every arity extends the one below it; without, each
    arity draws its own bits.
    """
    digest = hashlib.sha256(key or f"dense:{n}".encode()).digest()
    bits: list[str] = []
    block = 0
    while len(bits) < 1 << n:
        digest = hashlib.sha256(digest + bytes([block & 255])).digest()
        bits.extend(str(byte & 1) for byte in digest)
        block += 1
    return "".join(bits[: 1 << n])


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
        if self.rule == "dense":
            return dense(n)
        if self.rule == "random":
            return format(random.Random(self.seed).getrandbits(1 << n), f"0{1 << n}b")
        rules: dict[str, Callable[[int], int]] = {
            "parity": lambda ones: ones % 2,
            "and": lambda ones: ones == n,
            "or": lambda ones: ones > 0,
            "majority": lambda ones: 2 * ones > n,
            "zero": lambda _: 0,
            "one": lambda _: 1,
        }
        rule = rules[self.rule]
        return "".join(str(int(rule(row.bit_count()))) for row in range(1 << n))


def construction_boundaries(
    language: str, *, benchmark_only: bool = False
) -> dict[str, tuple[TableWitness, ...]]:
    """Read named witnesses for construction boundaries from their owner."""
    path = PACKAGES / LANGUAGES[language].id / "language.toml"
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    records = data.get("construction_boundaries", {})
    if not isinstance(records, dict):
        raise ValueError(f"{path}: construction boundaries must be named")
    found = {}
    measured: set[TableWitness] = set()
    for label, record in records.items():
        if (
            not label.isidentifier()
            or not isinstance(record, dict)
            or set(record) != {"tables", "benchmark"}
            or type(record["benchmark"]) is not bool
            or not isinstance(record["tables"], list)
            or not record["tables"]
        ):
            raise ValueError(f"{path}: invalid construction boundary {label!r}")
        rows = record["tables"]
        witnesses: list[TableWitness] = []
        for row in rows:
            if not isinstance(row, dict) or set(row) - {"seed"} != {"arity", "rule"}:
                raise ValueError(f"{path}: invalid boundary witness for {label}")
            witness = TableWitness(row["arity"], row["rule"], row.get("seed"))
            if witness in witnesses or (record["benchmark"] and witness in measured):
                raise ValueError(f"{path}: repeated boundary witness {witness}")
            witnesses.append(witness)
        if record["benchmark"]:
            measured.update(witnesses)
        if record["benchmark"] or not benchmark_only:
            found[label] = tuple(witnesses)
    return found


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


def render_source_anchors(source: str, anchors: tuple[SourceAnchor, ...]) -> str:
    """Refresh only measured sizes in a module docstring from declared evidence.

    Witness names, units and construction prose remain authored. Refuse absent,
    duplicated or undeclared witnesses instead of manufacturing an anchor.
    """
    import ast
    import tokenize
    from io import StringIO

    parsed = ast.parse(source)
    if not ast.get_docstring(parsed):
        raise ValueError("source anchors require a module docstring")
    token = next(
        t
        for t in tokenize.generate_tokens(StringIO(source).readline)
        if t.type == tokenize.STRING
    )
    expected = {(a.witness.arity, a.witness.name, a.unit): a for a in anchors}
    seen = set()

    def replace(match: re.Match[str]) -> str:
        key = int(match[1]), " ".join(match[2].split()), match[4]
        if key not in expected or key in seen:
            raise ValueError(f"undeclared or duplicate source anchor: {key}")
        seen.add(key)
        start, end = match.span(3)
        return (
            match[0][: start - match.start()]
            + f"{expected[key].size:,}"
            + match[0][end - match.start() :]
        )

    refreshed = SOURCE_ANCHOR.sub(replace, token.string)
    if seen != set(expected):
        raise ValueError(f"missing source anchors: {set(expected) - seen}")
    lines = source.splitlines(keepends=True)
    start = sum(map(len, lines[: token.start[0] - 1])) + token.start[1]
    end = sum(map(len, lines[: token.end[0] - 1])) + token.end[1]
    return source[:start] + refreshed + source[end:]


def update_source_anchors(*, root: Path = PACKAGES, check: bool = False) -> bool:
    """Refresh docstring views; emitted size and execution checks stay independent."""
    changes: list[tuple[Path, str]] = []
    for language, declaration in LANGUAGES.items():
        if declaration.backend is None:
            continue
        package = root / declaration.id
        path = package / "generator.py"
        if not path.is_file():
            path = package / "generator" / "__init__.py"
        source = path.read_text(encoding="utf-8")
        rendered = render_source_anchors(source, source_anchors(language))
        if source != rendered:
            changes.append((path, rendered))
    # Validate every view before changing any file.
    if not check:
        for path, rendered in changes:
            path.write_text(rendered, encoding="utf-8")
    return bool(changes)
