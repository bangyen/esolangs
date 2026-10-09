"""Reusable lemmas every generator's deep proof instantiates."""

from __future__ import annotations

import itertools
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field

# The suite's own shapes, not a local stand-in: ``_dense`` is the worst case to
# fold and ``_parity`` the table with no constant subtree above a single row.
from tests.witness_tables import dense as _dense
from tests.witness_tables import parity as _parity


class UnprovenError(Exception):
    """A lemma does not apply here, and this is why."""


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


Builder = Callable[[str], object]


def tables_at(n: int, limit: int | None = None) -> Iterator[str]:
    """Every table of arity ``n``, or the first ``limit`` of them."""
    size = 1 << n
    for i, bits in enumerate(itertools.product("01", repeat=size)):
        if limit is not None and i >= limit:
            return
        yield "".join(bits)


def build(fn: Builder, table: str) -> object | None:
    """Build ``table``, or ``None`` where the generator refuses it."""
    try:
        return fn(table)
    except ValueError:
        return None


def check_coverage(fn: Builder, max_n: int = 3, *, allow_refusals: bool = False) -> str:
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
    if refused and not allow_refusals:
        raise AssertionError(
            f"{refused} of {built + refused} tables refused through n={max_n}; "
            "only a cap/exception row may refuse, and this one is not marked so"
        )
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
    """Flipping any single table entry changes the emitted program."""
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


def check_ladder(
    fn: Builder,
    max_n: int,
    shapes: object,
    *,
    allow_refusals: bool = False,
) -> str:
    """The construction completes at every arity, on both table shapes."""
    built: dict[str, list[tuple[int, int]]] = {}
    refused = 0
    for name, make in shapes:  # type: ignore[misc]
        for n in range(1, max_n + 1):
            program = build(fn, make(n))
            if program is None:
                refused += 1
                continue
            from tests.source_support import source_units

            built.setdefault(name, []).append((n, source_units(program)))
    if not built:
        raise UnprovenError(f"builds no shape at any arity through n={max_n}")
    expected = list(range(1, max_n + 1))
    for name, _make in shapes:  # type: ignore[misc]
        reached = [n for n, _size in built.get(name, [])]
        if reached != expected and not allow_refusals:
            raise AssertionError(
                f"{name}: built arities {reached}, not {expected}; a total row "
                "must build every arity on both shapes"
            )
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
    """Each input embeds exactly once, at a width independent of the bit."""
    import esolangs
    from esolangs.registry import LANGUAGES, parameterized_ids
    from esolangs.tools.helpers import runs

    name = _language_of(fn)
    if name is None or LANGUAGES[name].id not in parameterized_ids():
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
