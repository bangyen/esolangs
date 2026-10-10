"""What every screen shares: the tables, and one build of each.

Run a screen from the repository root as ``python scripts/screens/<name>.py``;
each puts this directory on ``sys.path`` for the import, as
``check_generator_sizes.py`` does for ``benchmark``.
"""

import random
import sys
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

# ``_screen_evidence`` is one directory up, in ``scripts/``.  A screen run as
# a script reaches ``_budget`` first, which puts that directory on the path;
# importing ``scripts.screens.canonical`` reaches this module first, so it has
# to do it here rather than rely on the importer.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _screen_evidence import case_id, reused

from esolangs import describe
from esolangs.raster import Raster
from esolangs.registry import GENERATORS, resolve

#: Every two- and three-input table, MSB first.
PAIRS = [format(i, "04b") for i in range(16)]
TABLES = [format(i, "08b") for i in range(256)]


def source_size(name: str, program: object) -> int:
    """Return characters for text, rectangular cells for grids and raster."""
    if isinstance(program, Raster):
        return len(program.rows) * max(map(len, program.rows))
    source = str(program)
    if describe(name)["state_model"] == "grid":
        rows = source.splitlines()
        return len(rows) * max(map(len, rows), default=0)
    return len(source)


def source_measurement(name: str, program: object) -> dict[str, Any]:
    """Measure actual emitted area in pixels or grid cells; report scale separately."""
    if isinstance(program, Raster):
        return {
            "size": source_size(name, program),
            "unit": "pixels",
            "width": len(program.rows[0]),
            "height": len(program.rows),
            "scale": program.scale,
        }
    if describe(name)["state_model"] == "grid":
        rows = str(program).splitlines()
        return {
            "size": source_size(name, program),
            "unit": "cells",
            "width": max(map(len, rows), default=0),
            "height": len(rows),
            "scale": None,
        }
    return {"size": source_size(name, program), "unit": "characters"}


def generators() -> Iterator[tuple[str, Callable[[str], object]]]:
    """Yield ``(registry name, generator)`` for every Boolean generator."""
    yield from sorted(GENERATORS.items())


def sizes(
    name: str, gen: Callable[[str], object], tables: list[str], *, scope: str = "size"
) -> dict[str, int | None]:
    """Build every table once; ``None`` marks an arity the generator refuses.

    ``ValueError`` is the refusal; anything else is a real failure and
    propagates.
    """
    from _budget import completed

    out: dict[str, int | None] = {}
    for index, table in enumerate(tables):
        identifier = case_id(name, scope, index, table)
        cached = reused(identifier)
        if cached is not None:
            out[table] = cached["size"]
            completed(
                **{
                    key: value
                    for key, value in cached.items()
                    if key not in {"ordinal", "reused"}
                },
                reused=True,
            )
            continue
        try:
            program = gen(table)
            out[table] = source_size(name, program)
        except ValueError:
            out[table] = None
        completed(
            "refused" if out[table] is None else "measured",
            case_id=identifier,
            language=name,
            table_bits=len(table),
            size=out[table],
        )
    return out


def chosen(names: list[str]) -> list[tuple[str, Callable[[str], object]]]:
    """Return ``generators()`` narrowed to ``names``, or all of it for none.

    A name is resolved as ``esolangs`` resolves one, so a display name, a
    lower-case key or a punctuation-free spelling all select the language.
    """
    if not names:
        return list(generators())
    wanted = {resolve(name) for name in names}
    return [(key, gen) for key, gen in generators() if key in wanted]


def random_table(n: int, rng: random.Random) -> str:
    """Return a uniformly random ``n``-input table."""
    return format(rng.getrandbits(1 << n), f"0{1 << n}b")


def tiled(n: int, rng: random.Random) -> str:
    """Return an ``n``-input table tiled from two random smaller tables.

    Its subtrees repeat, which a random table's almost never do.
    """
    k = rng.randint(1, n - 2)
    blocks = [random_table(k, rng), random_table(k, rng)]
    return "".join(rng.choice(blocks) for _ in range(1 << (n - k)))


def ignore(table: str, at: int) -> str:
    """Return ``table`` with a new input at position ``at`` it never reads."""
    low = len(table).bit_length() - 1 - at  # inputs after the new one
    mask = (1 << low) - 1
    return "".join(
        table[(row >> (low + 1) << low) | (row & mask)] for row in range(2 * len(table))
    )


def size_cases(name: str, tables: list[str], scope: str = "size") -> list[str]:
    """Identify every build, including repeated tables in different roles."""
    return [case_id(name, scope, index, table) for index, table in enumerate(tables)]
