"""Run the deep proofs of one cost band.

    python -m tests.proofs.deep verify    # the local gate, ~2s
    python -m tests.proofs.deep ci        # CI, ~25s
    python -m tests.proofs.deep all       # everything, ~2m  (`just proofs`)
    python -m tests.proofs.deep --list    # the registry, run nothing

Why this exists
---------------
The proofs under ``deep/`` are scripts rather than pytest tests on purpose:
each one prints a report meant to be *read*, and pytest would swallow it.  The
cost of that choice was that every consumer had to name them by path.  Six
proofs were spelled out across fourteen references in four files -- the
justfile, ``ci.yml``, and ``scripts/verify.py`` twice -- and the rule deciding
which of them gate, "cheap ones do", was re-argued as prose in each.  Adding a
seventh meant four edits and a fourth copy of the argument.

So the rule moved next to the proofs.  Each module declares ``BAND`` and
``COST``, this runner selects on them, and the three consumers each invoke one
band.

The bands are cumulative, ordered by how often they run:

``verify``   also runs in CI and by hand.  Cheap and narrowly scoped, so
             ``scripts/verify.py`` can afford it on every local run.
``ci``       also runs by hand.  Too broad or too slow to re-run on every local
             edit -- ``all_generators`` touches every generator, so scoping it
             would mean running it almost always -- but cheap enough that CI
             should never skip it.
``by-hand``  ``just proofs`` only.  Measured in tens of seconds.

A band is a claim about cost, so ``tests/proofs/test_bands.py`` holds each one
to a ceiling and checks that every module here is in exactly one.  Without that
check this indirection would be a way to silently stop running a proof, which
is precisely the failure it was built to prevent: the ``slow`` marker kept
``_DOCUMENTED_SIZES`` green while COD's pinned size was wrong by a factor of
3,200, straight through the commit that changed it.
"""

from __future__ import annotations

import argparse
import importlib
import pkgutil
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType

# Run as a script, the repo root is not on the path.
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

#: Bands from most to least often run.  Selecting one runs it and everything
#: before it, so ``ci`` includes ``verify``.
BANDS = ("verify", "ci", "by-hand")

#: What each band is allowed to cost in total, in seconds.  ``test_bands``
#: checks the declared costs against these; the declarations are hand-kept and
#: only as honest as the last person to time the band (``ci`` measured ~25s).
BUDGET = {"verify": 5.0, "ci": 30.0, "by-hand": 180.0}


#: A leading underscore means a helper, not a proof -- ``_lemmas`` today.  The
#: rule is a convention rather than a list so that adding a second helper does
#: not fail discovery with a confusing "declares no BAND"; the flip side, a
#: proof named with an underscore being skipped, is caught by
#: ``test_bands.py``, which checks the plain-named files are all registered.
def _is_helper(name: str) -> bool:
    """Whether a module under ``deep/`` is support code rather than a proof."""
    return name.startswith("_")


@dataclass(frozen=True)
class Proof:
    """One deep proof and the band it declares."""

    name: str
    band: str
    cost: float
    module: ModuleType


def discover() -> list[Proof]:
    """Every deep proof, in band order then by cost."""
    package = importlib.import_module("tests.proofs.deep")
    found = []
    for info in pkgutil.iter_modules(package.__path__):
        if _is_helper(info.name) or info.name.startswith("test_"):
            continue
        module = importlib.import_module(f"tests.proofs.deep.{info.name}")
        band = getattr(module, "BAND", None)
        cost = getattr(module, "COST", None)
        assert band is not None, (
            f"{info.name} declares no BAND -- a proof with no band runs nowhere, "
            "which is exactly the silent skip this runner exists to prevent"
        )
        assert band in BANDS, f"{info.name}: unknown band {band!r}, expected {BANDS}"
        assert isinstance(cost, int | float), f"{info.name} declares no COST"
        assert callable(getattr(module, "main", None)), (
            f"{info.name} has no main() -- every deep proof returns an exit code"
        )
        found.append(Proof(info.name, band, float(cost), module))
    return sorted(found, key=lambda p: (BANDS.index(p.band), p.cost))


def selected(band: str) -> list[Proof]:
    """Every proof in ``band`` or a band that runs more often."""
    if band == "all":
        return discover()
    assert band in BANDS, f"unknown band {band!r}, expected one of {BANDS} or 'all'"
    ceiling = BANDS.index(band)
    return [p for p in discover() if BANDS.index(p.band) <= ceiling]


def main(argv: list[str] | None = None) -> int:
    """Run one band and summarize."""
    parser = argparse.ArgumentParser(prog="python -m tests.proofs.deep")
    parser.add_argument("band", nargs="?", default="all", choices=[*BANDS, "all"])
    parser.add_argument(
        "--list", action="store_true", help="print the registry and run nothing"
    )
    args = parser.parse_args(argv)

    proofs = selected(args.band)
    if args.list:
        for proof in discover():
            print(f"{proof.band:8s} {proof.cost:6.1f}s  {proof.name}")
        return 0

    budget = sum(p.cost for p in proofs)
    print(f"deep proofs: band {args.band!r}, {len(proofs)} proofs, ~{budget:.0f}s\n")

    failed = []
    band_start = time.time()
    for proof in proofs:
        print(f"{'=' * 70}\n=== {proof.name}  [{proof.band}]\n{'=' * 70}")
        start = time.time()
        # A proof that reads sys.argv must not see the band name: arrowqueue
        # takes flags of its own, and argparse exited 2 on "verify" before a
        # single lemma ran.  Its main() now takes an explicit argv, and this
        # keeps any future one from repeating the fault.
        saved, sys.argv = sys.argv, [proof.name]
        try:
            code = proof.module.main()
        except Exception as exc:  # report and keep going
            # Proofs use bare ``assert``; without this a single failure would
            # abort the band and hide every proof after it, which the justfile
            # comment promises cannot happen.
            code = 1
            print(f"    raised {type(exc).__name__}: {exc}")
        finally:
            sys.argv = saved
        elapsed = time.time() - start
        if code:
            failed.append(proof.name)
        print(f"--- {proof.name}: {'FAILED' if code else 'ok'} in {elapsed:.1f}s\n")

    wall = time.time() - band_start
    if failed:
        print(f"{len(failed)} of {len(proofs)} deep proofs failed: {', '.join(failed)}")
        return 1
    # The declared costs are hand-kept; this is the only place the band's real
    # wall time is compared to its budget.  A warning rather than a failure,
    # because a loaded CI box would otherwise turn a cost overrun into a flake.
    ceiling = BUDGET.get(args.band, budget)
    if wall > ceiling:
        print(
            f"warning: band {args.band!r} took {wall:.1f}s, over its {ceiling}s "
            "budget -- raise BUDGET or the proofs' COST"
        )
    print(
        f"all {len(proofs)} deep proofs in band {args.band!r} passed "
        f"({wall:.1f}s, budget {ceiling}s)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
