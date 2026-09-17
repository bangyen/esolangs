"""Reusable lemmas every generator's deep proof instantiates.

These are *not* a substitute for the hand-derived proofs beside them.  The
bespoke files -- ``a_painter_ant.py``, ``arrowqueue.py``, ``container.py``,
``bio.py`` -- mechanize one construction's own argument: where its leaves sit,
what its literal spells, which adjustment sits at which nesting level.  Nothing
generic can reach that, and this module does not pretend to.

What it does reach is the part of each scheme's argument that is about
*counting*, and that part is uniform.  Every scheme in ``docs/proofs.md``
proves totality the same way: the construction is a finite object whose size is
bounded by a function of the arity, and every row of the table participates in
it.  Both halves are falsifiable per generator:

``rows``      flipping any single table entry must change the emitted program.
              A construction that ignores a row cannot be computing the table,
              so this is the coverage half of every scheme's claim, and at the
              arities it enumerates it is exhaustive rather than sampled.

``ladder``    the construction completes at every arity of the ladder, on both
              of the suite's table shapes.  This is the totality claim itself,
              carried past the arities the exhaustive lemma can reach.

              It deliberately asserts nothing about *size*.  Two size
              formulations were tried and both are false for sound reasons.  A
              per-step doubling bound breaks on legitimate regime changes: 123
              jumps x5.80 at n=4 when its geometry switches, then settles at
              x1.96.  Monotonicity breaks at every dispatch crossover, where
              the wide route is *smaller* than the tree it replaces -- A
              Painter Ant drops 405 chars to 244 at n=5, Container 5674 to
              1200 at n=7.  Neither is a defect, and no ledger scheme claims a
              character count: the schemes bound nodes and entries, and size
              claims live in `docs/limitations.md`.  The crossover is reported
              as a note instead of asserted.

``coverage``  every table of a small arity builds, enumerated exhaustively.

``determinism`` the same table twice gives the same program.  Cheap, and every
              inductive argument above silently assumes it.

A lemma that does not apply to a generator must be recorded as inapplicable
*with its reason*, never skipped quietly -- :class:`UnprovenError` is how, and the
runner counts those separately from passes.
"""

from __future__ import annotations

import itertools
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field

# The suite's own shapes, not a local stand-in: ``_dense`` is the worst case to
# fold and ``_parity`` the table with no constant subtree above a single row.
from tests.tools.test_boolean_contract import _dense, _parity


class UnprovenError(Exception):
    """A lemma does not apply here, and this is why.

    Raised rather than returned so that a lemma cannot be silently skipped by
    a caller that forgets to inspect a result.
    """


@dataclass
class Result:
    """What one generator's battery established."""

    generator: str
    scheme: str
    passed: list[str] = field(default_factory=list)
    unproven: list[tuple[str, str]] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def record(self, lemma: str, run: Callable[[], str]) -> None:
        """Run one lemma, filing it as passed or as unproven-with-reason."""
        try:
            self.notes.append(f"    {lemma}: {run()}")
        except UnprovenError as exc:
            self.unproven.append((lemma, str(exc)))
            self.notes.append(f"    {lemma}: UNPROVEN -- {exc}")
        else:
            self.passed.append(lemma)


Builder = Callable[[str], str]


def tables_at(n: int, limit: int | None = None) -> Iterator[str]:
    """Every table of arity ``n``, or the first ``limit`` of them."""
    size = 1 << n
    for i, bits in enumerate(itertools.product("01", repeat=size)):
        if limit is not None and i >= limit:
            return
        yield "".join(bits)


def build(fn: Builder, table: str) -> str | None:
    """Build ``table``, or ``None`` where the generator refuses it.

    A ``ValueError`` is the documented refusal for a table outside a
    generator's domain, and is information rather than failure; anything else
    propagates, because a crash is not a refusal.
    """
    try:
        return str(fn(table))
    except ValueError:
        return None


def check_coverage(fn: Builder, max_n: int = 3) -> str:
    """Every table of every arity up to ``max_n`` builds, enumerated."""
    built = refused = 0
    for n in range(1, max_n + 1):
        for table in tables_at(n):
            if build(fn, table) is None:
                refused += 1
            else:
                built += 1
    if built == 0:
        raise UnprovenError(f"refuses every table through n={max_n}")
    return f"{built} tables built, {refused} refused, exhaustive to n={max_n}"


def check_determinism(fn: Builder, max_n: int = 4) -> str:
    """Building a table twice gives the same program."""
    checked = 0
    for n in range(1, max_n + 1):
        for table in tables_at(n, limit=8):
            first, second = build(fn, table), build(fn, table)
            if first is None:
                continue
            assert first == second, f"{table!r} built two different programs"
            checked += 1
    if not checked:
        raise UnprovenError("nothing built to compare")
    return f"{checked} tables rebuilt identically"


def check_rows(fn: Builder, max_n: int = 4) -> str:
    """Flipping any single table entry changes the emitted program.

    This is the coverage half of every scheme's argument.  A construction that
    leaves a row out of its tree, its sum or its stored table would answer that
    row wrongly, and the emitted text would not move when the row moved.
    """
    checked = blind = 0
    for n in range(1, max_n + 1):
        size = 1 << n
        # The enumerated tables are the lexicographically first ones, which are
        # near-empty and the most biased base a flip test could have.  The
        # suite's two worst cases go in beside them so the lemma is exercised
        # on tables that fold nothing.
        bases = [*tables_at(n, limit=6), _dense(n), _parity(n)]
        for table in bases:
            base = build(fn, table)
            if base is None:
                continue
            for i in range(size):
                flipped = table[:i] + str(1 - int(table[i])) + table[i + 1 :]
                other = build(fn, flipped)
                if other is None:
                    continue
                checked += 1
                if other == base:
                    blind += 1
    if not checked:
        raise UnprovenError("no table pair could be built")
    assert blind == 0, f"{blind} of {checked} row flips left the program identical"
    return f"{checked} single-row flips, every one visible in the program"


def check_ladder(fn: Builder, max_n: int, shapes: object) -> str:
    """The construction completes at every arity, on both table shapes.

    Both shapes, because a generator can cover one and refuse the other: the
    suite's own sweep is keyed by ``(name, shape)`` for exactly that reason,
    and a single-shape ladder reports the wrong ceiling.

    Size is not asserted -- see the module docstring for the two formulations
    that were tried and why both are false.  The crossover a dispatching
    generator shows, where the wide route comes in smaller than the tree it
    replaces, is reported because it is informative, not because it is
    required.
    """
    built: dict[str, list[tuple[int, int]]] = {}
    refused = 0
    for name, make in shapes:  # type: ignore[misc]
        for n in range(1, max_n + 1):
            program = build(fn, make(n))
            if program is None:
                refused += 1
                continue
            built.setdefault(name, []).append((n, len(program)))
    if not built:
        raise UnprovenError(f"builds no shape at any arity through n={max_n}")
    drops = []
    for name, series in built.items():
        for (_a, before), (b, after) in itertools.pairwise(series):
            if after < before:
                drops.append(f"{name} n={b}")
    reached = {name: series[-1][0] for name, series in built.items()}
    note = ", ".join(f"{name} to n={top}" for name, top in sorted(reached.items()))
    if refused:
        note += f"; {refused} refused"
    if drops:
        note += f"; route crossover at {', '.join(drops)}"
    return note


def _language_of(fn: Builder) -> str | None:
    """The registry name of the generator ``fn`` is, if it is one."""
    import esolangs.tools as boolean
    from esolangs.registry import BY_BOOLEAN

    for key, lang in BY_BOOLEAN.items():
        if getattr(boolean, key, None) is fn:
            return lang.name
    return None


def check_embedding(fn: Builder, max_n: int = 4) -> str:
    """Each input embeds exactly once, at a width independent of the bit.

    Only meaningful for the parameterized generators: an input-reading language
    has no runs to count.  The public template spells each input as one run
    of the language's character, as wide as its setter, and :func:`runs`
    accounts for every occurrence of the character, so a template with
    ``n`` spans embeds each of its ``n`` inputs exactly once.
    """
    import esolangs
    from esolangs.registry import parameterized_ids, resolve
    from esolangs.tools.helpers import runs

    name = _language_of(fn)
    if name is None or resolve(name) not in parameterized_ids():
        raise UnprovenError("not a parameterized generator: no runs to count")
    checked = 0
    for n in range(2, max_n + 1):
        # _dense, not the alternating table: that one depends on a single
        # input, so a folding generator returns a near-trivial template -- the
        # weakest possible witness for an exactly-once claim.  The same
        # degenerate shape corrupted the arity ladder before it was caught.
        if build(fn, _dense(n)) is None:
            continue
        template = esolangs.generate(name, _dense(n))
        assert "{X" not in template, f"n={n}: marks left in the public template"
        setters = template.setters  # type: ignore[attr-defined]
        spans = runs(str(template), template.char, setters)  # type: ignore[attr-defined]
        assert len(spans) == n, f"n={n}: {len(spans)} runs for {n} inputs"
        checked += 1
    if not checked:
        raise UnprovenError("nothing built to inspect")
    return f"{checked} arities, every input embedded exactly once"
