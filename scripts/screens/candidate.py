"""Check a candidate generator against the shipped one, every row on the interpreter.

``python scripts/screens/candidate.py LANG FILE.py:FUNC [--target MODULE:ATTR]``

``FUNC`` stands in for the language's registered generator, or for
``MODULE:ATTR`` (an inner piece such as ``esolangs.tools.minifuck:_solve``),
while ``esolangs.generate`` runs, so the candidate gets the shipped wrapping,
width and template provenance.  Each arity gets random tables, tiled ones
(subtrees repeat) and ignored-input ones (a random table plus an input it
never reads, first, middle and last).  Rows run through ``benchmark``'s
executor, all of them up to ``--rows`` per table and a sample above.

Per family: tables, changed, wrong rows, larger, the new/old size ratio
(min, mean) and the worst steps of a row, old -> new.  Any wrong row, or a
table the candidate raises on, exits 1.
"""

import argparse
import importlib
import importlib.util
import math
import random
import sys
from collections import defaultdict
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _build import ignore, random_table, source_size, tiled
from benchmark import _execute

import esolangs
from esolangs.registry import LANGUAGES, resolve

#: Steps one row may take before it counts as wrong.
CAP = 10**7


def _load(spec: str) -> Callable[..., object]:
    """Return ``FUNC`` from ``FILE.py:FUNC``, importing the file by path."""
    path, _, name = spec.rpartition(":")
    sys.path.insert(0, str(Path(path).resolve().parent))
    module_spec = importlib.util.spec_from_file_location(Path(path).stem, path)
    assert module_spec is not None, path
    assert module_spec.loader is not None, path
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    return getattr(module, name)  # type: ignore[no-any-return]


@dataclass
class _Tally:
    tables: int = 0
    changed: int = 0
    wrong: int = 0
    larger: int = 0
    ratios: list[float] = field(default_factory=list)
    old_steps: int = 0
    new_steps: int = 0


@contextmanager
def _patched(
    language: str, target: str | None, fn: Callable[..., object]
) -> Iterator[None]:
    """Run the body with ``fn`` in place of the generator or ``target``."""
    if target is None:
        owner: object = LANGUAGES[language]
        attr = "boolean"
    else:
        module_name, _, attr = target.partition(":")
        owner = importlib.import_module(module_name)
    old = getattr(owner, attr)
    object.__setattr__(owner, attr, fn)  # Language is a frozen dataclass
    try:
        yield
    finally:
        object.__setattr__(owner, attr, old)


def _tables(n: int, rng: random.Random, count: int) -> Iterator[tuple[str, str]]:
    """Yield ``(family, table)`` at arity ``n``."""
    for _ in range(count):
        yield "random", random_table(n, rng)
    for _ in range(count if n >= 3 else 0):
        yield "tiled", tiled(n, rng)
    for at in sorted({0, n // 2, n - 1}):
        for _ in range(count):
            yield "ignored", ignore(random_table(n - 1, rng), at)


def _worst(
    language: str,
    program: esolangs.Program,
    table: str,
    rows: list[int],
    timeout: float = 30.0,
) -> tuple[int, int]:
    """Return ``(wrong rows, worst steps)``; an unanswered row is wrong."""
    wrong = worst = 0
    for row in rows:
        result = _execute(language, program, table, row, CAP, timeout)
        wrong += result["matches"] is not True
        worst = max(worst, result["commands"] or 0)
    return wrong, worst


def main(argv: list[str] | None = None) -> int:
    """Print the per-family tallies; 1 on any wrong row or candidate crash."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("language")
    parser.add_argument("candidate", help="FILE.py:FUNC")
    parser.add_argument("--target", help="MODULE:ATTR to replace instead")
    parser.add_argument("--n", type=int, nargs=2, default=(3, 7), metavar=("LO", "HI"))
    parser.add_argument("--count", type=int, default=4, help="tables per family")
    parser.add_argument("--rows", type=int, default=64, help="rows per table")
    parser.add_argument("--timeout", type=float, default=30.0, help="seconds per row")
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args(argv)

    if not math.isfinite(args.timeout) or args.timeout <= 0:
        parser.error("--timeout must be positive and finite")
    if args.rows < 1 or args.count < 1:
        parser.error("--rows and --count must be positive")
    if not 1 <= args.n[0] <= args.n[1]:
        parser.error("--n requires 1 <= LO <= HI")

    language = resolve(args.language)
    fn = _load(args.candidate)
    rng = random.Random(args.seed)
    stats: dict[str, _Tally] = defaultdict(_Tally)
    failed = 0
    for n in range(args.n[0], args.n[1] + 1):
        for family, table in _tables(n, rng, args.count):
            old = esolangs.generate(language, table)
            try:
                with _patched(language, args.target, fn):
                    new = esolangs.generate(language, table)
            except Exception as error:
                print(f"{family} n={n} {table}: {type(error).__name__}: {error}")
                failed += 1
                continue
            rows = list(range(1 << n))
            if len(rows) > args.rows:
                rows = sorted(rng.sample(rows, args.rows))
            tally = stats[family]
            tally.tables += 1
            tally.changed += str(new) != str(old)
            tally.ratios.append(source_size(language, new) / source_size(language, old))
            tally.larger += tally.ratios[-1] > 1
            wrong, steps = _worst(language, new, table, rows, args.timeout)
            tally.wrong += wrong
            tally.new_steps = max(tally.new_steps, steps)
            tally.old_steps = max(
                tally.old_steps, _worst(language, old, table, rows, args.timeout)[1]
            )

    print(f"{'family':<8} tables changed wrong larger  ratio min/mean  worst steps")
    for family, tally in stats.items():
        ratios = tally.ratios
        print(
            f"{family:<8} {tally.tables:>6} {tally.changed:>7} {tally.wrong:>5}"
            f" {tally.larger:>6}  {min(ratios):.3f}/{sum(ratios) / len(ratios):.3f}"
            f"     {tally.old_steps} -> {tally.new_steps}"
        )
    wrong = sum(tally.wrong for tally in stats.values())
    return 1 if wrong or failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
