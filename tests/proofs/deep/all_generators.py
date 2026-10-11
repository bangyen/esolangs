"""A deep proof for every boolean generator in the registry."""

from __future__ import annotations

import sys
from pathlib import Path

# Run as a script (not under pytest), the repo root is not on the path.
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from concurrent.futures import ProcessPoolExecutor
from multiprocessing import get_context

import esolangs.tools as boolean
from esolangs.registry import BY_BOOLEAN
from tests.proofs._ledger import Row, load
from tests.proofs.deep._lemmas import (
    Result,
    UnprovenError,
    check_coverage,
    check_determinism,
    check_embedding,
    check_ladder,
    check_rows,
)

# The suite's own table shapes, not a local stand-in: _dense is the
# worst case to fold and _parity the table with no constant subtree, and the
# contract sweep is keyed by (name, shape) because a generator can cover one
# and refuse the other.
from tests.support.witness_tables import dense as _dense
from tests.support.witness_tables import parity as _parity

#: Cost band; see ``__main__.py``. Registry-wide, so its scope is every generator:
#: too broad to re-run on every local edit, cheap enough that CI should never skip
#: it.
BAND = "ci"
COST = 22.0

_SHAPES = (("dense", _dense), ("parity", _parity))

#: Shared bound: the complete CI band through eight inputs fits 30 seconds.
_GROWTH_MAX = 8

#: Generators that may refuse tables the others accept are read from the
#: ledger's own ``cap``/``exception`` labels, not listed here, so a row that
#: gains or loses the label changes the battery in one place.


def _refuses_everything(_table: str) -> str:
    """A builder with no construction at all."""
    raise ValueError("no construction")


def _builds_first_arity_only(table: str) -> str:
    """A builder whose ceiling sits just past n=1."""
    if len(table) != 2:
        raise ValueError("past the ceiling")
    return "x"


def _blind_to_rows(_table: str) -> str:
    """A builder that ignores the table it is handed."""
    return "constant"


_flip_flop_state = [0]


def _flip_flops(table: str) -> str:
    """A builder that returns a different string on every call."""
    _flip_flop_state[0] += 1
    return f"{table}{_flip_flop_state[0] % 2}"


def _assert_the_lemmas_bite() -> None:
    """Each counting lemma must fail on a builder that breaks it."""
    _flip_flop_state[0] = 0
    cases = [
        ("coverage refuses everything", check_coverage, _refuses_everything, {}),
        (
            "coverage refuses past n=1",
            check_coverage,
            _builds_first_arity_only,
            {"max_n": 3},
        ),
        (
            "ladder stops at n=1",
            check_ladder,
            _builds_first_arity_only,
            {"max_n": 3, "shapes": _SHAPES},
        ),
        ("rows blind to a flip", check_rows, _blind_to_rows, {}),
        ("determinism flip-flops", check_determinism, _flip_flops, {}),
    ]
    for label, check, fn, kwargs in cases:
        try:
            check(fn, **kwargs)
        except (AssertionError, UnprovenError):
            continue
        raise AssertionError(f"{label}: the lemma passed a builder that breaks it")
    check_coverage(_builds_first_arity_only, max_n=3, allow_refusals=True)


def battery(row: Row, key: str) -> Result:
    """Run every applicable lemma for one generator."""
    fn = getattr(boolean, key)
    scheme = row.schemes[0] if row.schemes else "exception"
    allow = "cap" in row.labels or "exception" in row.labels
    result = Result(generator=row.generator, scheme=scheme)
    result.record("coverage  ", lambda: check_coverage(fn, allow_refusals=allow))
    result.record("determinism", lambda: check_determinism(fn))
    result.record("rows      ", lambda: check_rows(fn))
    result.record(
        "ladder    ",
        lambda: check_ladder(fn, _GROWTH_MAX, _SHAPES, allow_refusals=allow),
    )
    result.record("embedding ", lambda: check_embedding(fn))
    return result


def main() -> int:
    """Run the battery for every ledger row and summarize."""
    _assert_the_lemmas_bite()
    ledger = load()
    by_display = {lang.name: key for key, lang in BY_BOOLEAN.items()}
    rows = sorted(ledger.rows, key=lambda r: r.generator.lower())

    # Independent batteries share two workers; serial raster checks exceeded CI.
    with ProcessPoolExecutor(max_workers=2, mp_context=get_context("spawn")) as pool:
        results = list(
            pool.map(battery, rows, [by_display[row.generator] for row in rows])
        )
    for row, result in zip(rows, results, strict=True):
        status = f"{len(result.passed)}/5"
        if "cap" in row.labels or "exception" in row.labels:
            status += "  (cap/exception row: refusals allowed)"
        print(f"{row.generator:34s} {result.scheme:26s} {status}")
        for note in result.notes:
            print(note)

    print(f"\n{len(results)} generators, one proof each")
    total_passed = sum(len(r.passed) for r in results)
    print(f"  lemmas established : {total_passed}")

    unproven: dict[str, list[str]] = {}
    for result in results:
        for lemma, reason in result.unproven:
            unproven.setdefault(f"{lemma.strip()}: {reason}", []).append(
                result.generator
            )
    print(f"  lemmas inapplicable: {sum(len(v) for v in unproven.values())}")
    for reason, who in sorted(unproven.items()):
        shown = ", ".join(sorted(who)[:6])
        more = f" (+{len(who) - 6} more)" if len(who) > 6 else ""
        print(f"    {reason}\n      {shown}{more}")

    # The three lemmas that apply to every construction, parameterized or not.
    # Anything short of all three is a generator whose counting argument is not
    # actually established, and this file must not report success for it.
    core = {"coverage", "determinism", "rows", "ladder"}
    weak = [
        r.generator
        for r in results
        if not core <= {lemma.strip() for lemma in r.passed}
    ]
    assert len(results) == len(BY_BOOLEAN), (
        f"{len(results)} generators, expected {len(BY_BOOLEAN)}"
    )
    assert not weak, f"core lemmas not established for: {sorted(weak)}"
    print("\nall generator batteries passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
