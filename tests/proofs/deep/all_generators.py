"""A deep proof for every boolean generator in the registry.

Run:  just proofs   (or python tests/proofs/deep/all_generators.py)

Every one of the 59 rows in ``docs/proofs.md`` gets the lemma battery in
:mod:`tests.proofs.deep._lemmas` instantiated against its own construction and
its own ledger scheme.  Four generators additionally have a hand-derived proof
of their *specific* argument in the files beside this one; those are deeper,
and this does not replace them.

Read the depth honestly.  What is established here, per generator, is the
counting half of its scheme: every row of the table participates in the
program, and the program's size respects the scheme's bound as arity grows.
That is what makes "finite object, bounded by a function of n, covering every
row" checkable.  What it does *not* establish is that the construction computes
the right answer -- the execution sweeps in ``tests/tools/test_boolean_contract.py``
are that evidence, and the bespoke files are where a particular construction's
own reasoning gets mechanized.

Where a lemma does not apply, it is recorded as UNPROVEN with its reason and
counted separately.  A silent skip would let this file grow into exactly the
kind of green-but-vacuous check the ledger work was about.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Run as a script (not under pytest), the repo root is not on the path.
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import esolangs.tools as boolean
from esolangs.registry import BY_BOOLEAN
from tests.proofs._ledger import load
from tests.proofs.deep._lemmas import (
    Result,
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
from tests.tools.test_boolean_contract import _dense, _parity

#: Cost band; see ``__main__.py``. Registry-wide, so its scope is every generator:
#: too broad to re-run on every local edit, cheap enough that CI should never skip
#: it.
BAND = "ci"
COST = 12.0

_SHAPES = (("dense", _dense), ("parity", _parity))

#: Highest arity the ladder climbs.  Measured, not guessed: a calibration
#: sweep built every registry generator at rising arity under a per-build
#: alarm, and all 59 reach n=10 in under a second each except
#: ``circuit_diagram``, which needs 2s by n=9 and times out past it.  Seven
#: keeps that one affordable; eight is comfortable for the rest.
_GROWTH_MAX = 8
_GROWTH_OVERRIDE = {"circuit_diagram": 7}

#: Generators that may refuse tables the others accept, so their batteries
#: routinely report refusals.  Listed to keep that expected rather than
#: surprising.  None remain: the ``exception`` row and the ``cap`` rows in
#: the ledger left with their languages.
_MAY_REFUSE = frozenset()


def battery(name: str, scheme: str, key: str) -> Result:
    """Run every applicable lemma for one generator."""
    fn = getattr(boolean, key)
    result = Result(generator=name, scheme=scheme)
    top = _GROWTH_OVERRIDE.get(key, _GROWTH_MAX)
    result.record("coverage  ", lambda: check_coverage(fn))
    result.record("determinism", lambda: check_determinism(fn))
    result.record("rows      ", lambda: check_rows(fn))
    result.record("ladder    ", lambda: check_ladder(fn, top, _SHAPES))
    result.record("embedding ", lambda: check_embedding(fn))
    return result


def main() -> int:
    """Run the battery for every ledger row and summarize."""
    ledger = load()
    by_display = {lang.name: key for key, lang in BY_BOOLEAN.items()}
    rows = sorted(ledger.rows, key=lambda r: r.generator.lower())

    results = []
    for row in rows:
        key = by_display[row.generator]
        scheme = row.schemes[0] if row.schemes else "exception"
        result = battery(row.generator, scheme, key)
        results.append(result)
        status = f"{len(result.passed)}/5"
        if row.generator in _MAY_REFUSE:
            status += "  (exception row: refusals expected)"
        print(f"{row.generator:34s} {scheme:26s} {status}")
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
    assert len(results) == 59, f"{len(results)} generators, expected 59"
    assert not weak, f"core lemmas not established for: {sorted(weak)}"
    print("\nall generator batteries passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
