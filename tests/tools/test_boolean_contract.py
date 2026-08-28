"""Contract tests every boolean generator must satisfy.

These are cross-cutting invariants rather than per-language behaviour: they
sweep every registered boolean generator instead of asserting against one.
"""

import contextlib
import importlib

import pytest

import esolangs.tools.boolean as boolean
from esolangs.interpreters.io import ScriptedIO
from esolangs.registry import BY_FUNCTION, LANGUAGES

# Tables that exercise the constant-table paths alongside a normal one.  The
# constants are the interesting cases: a generator that special-cases them can
# lose the input reads that the non-constant path emits.
_TABLES = ["00000000", "11111111", "01101001", "00000001", "11111110"]


def _input_reading_generators() -> list[tuple[str, object]]:
    """Every boolean generator whose language actually reads input."""
    found = []
    for name in sorted(boolean.__all__):
        fn = getattr(boolean, name, None)
        lang = BY_FUNCTION.get(name)
        if not callable(fn) or lang is None or lang.interpreter is None:
            continue
        try:
            run = importlib.import_module(
                f"esolangs.interpreters.{lang.interpreter}"
            ).run
        except Exception:  # pragma: no cover - interpreter lives outside the pkg
            continue
        found.append((name, (fn, lang, run)))
    return found


def _reads(entry: tuple, table: str) -> int:
    """Run the generated program and report how many inputs it consumed."""
    fn, lang, run = entry
    program = str(fn(table))
    io = ScriptedIO("0\n" * 8)
    # A program may halt through its own error path or call exit; either way the
    # read count up to that point is what matters here.
    with contextlib.suppress(Exception, SystemExit):
        run(
            program.splitlines() if lang.split else program,
            io=io,
            **dict(lang.kwargs),
        )
    return io.position()


@pytest.mark.parametrize(
    ("name", "entry"),
    _input_reading_generators(),
    ids=lambda v: v if isinstance(v, str) else "",
)
def test_every_table_reads_the_same_number_of_inputs(name: str, entry: tuple) -> None:
    """A generator reads its ``n`` inputs whatever the truth table says.

    An input-capable language reads each of its ``n`` inputs exactly once per
    run, and that must not depend on the *contents* of the table.  A generator
    that special-cases a constant table by printing the answer outright skips
    the reads, which leaves the caller's bits unread on the input stream for
    whatever runs next, and drops the per-read prompts that a prompting
    language (3x) emits -- prompts ``scripts/verify_extra_generators.py``
    filters precisely because they are part of the observable output.

    Shortening the *body* for a constant table is fine and worth doing; the
    reads are the interface and have to stay.
    """
    counts = {table: _reads(entry, table) for table in _TABLES}
    baseline = counts["01101001"]
    if baseline == 0:
        pytest.skip(f"{name} does not read input in this harness")
    assert set(counts.values()) == {baseline}, (
        f"{name} reads a different number of inputs depending on the table: "
        f"{counts} -- a constant table must still consume all {baseline}"
    )


def _exported_generators() -> dict[str, str]:
    """Every boolean generator the package exports, mapped to its language.

    A generator function is named for its language's canonical id, so the id
    is the join.  Two naming conventions sit on top of it: a ``_boolean``
    suffix distinguishes the boolean generator where the text one already
    owns the plain name (``forbin_boolean``, ``ztoalc_l_boolean``), and a
    few ids drop an underscore (``bf_pda`` -> ``bfpda``).  ``BY_FUNCTION``
    covers the languages whose text generator shares the name.
    """
    by_id = {lang.id: name for name, lang in LANGUAGES.items()}
    squashed = {lang.id.replace("_", ""): name for name, lang in LANGUAGES.items()}
    found = {}
    for fn in boolean.__all__:
        if fn in ("BOOLEAN", "instantiate") or not callable(getattr(boolean, fn, None)):
            continue
        base = fn.removesuffix("_boolean")
        display = (
            by_id.get(base)
            or squashed.get(base.replace("_", ""))
            or (BY_FUNCTION[fn].name if fn in BY_FUNCTION else None)
        )
        if display is not None:
            found[fn] = display
    return found


def test_boolean_set_lists_exactly_the_exported_generators() -> None:
    """``BOOLEAN`` and the package's exports name the same languages.

    ``BOOLEAN`` is what :func:`esolangs.describe` reports as
    ``boolean_generator``, but it is a second, hand-maintained list of what
    the package already exports -- so the two can disagree, and the way they
    disagree is silent.  Adding a generator and updating the import and
    ``__all__`` but not ``BOOLEAN`` leaves a working generator that
    ``describe`` reports as absent, with every other check still passing
    (``set(LANGUAGES) >= BOOLEAN`` only catches a name that is not a
    language at all).

    This pins both directions so that omission fails loudly instead.
    """
    exported = _exported_generators()
    missing = {d for d in exported.values() if d not in boolean.BOOLEAN}
    assert not missing, (
        f"these languages export a boolean generator but are absent from "
        f"BOOLEAN, so describe() reports boolean_generator=False for them: "
        f"{sorted(missing)} -- add them to BOOLEAN in tools/boolean/__init__.py"
    )
    stale = boolean.BOOLEAN - set(exported.values())
    assert not stale, (
        f"BOOLEAN names these languages but the package exports no generator "
        f"resolving to them: {sorted(stale)} -- remove them from BOOLEAN, or "
        f"export the generator from tools/boolean/__init__.py"
    )


# The tree generators that pick their input split order by measuring, and the
# builder that emits one fixed order, so a test can compare the two.
def _reordering_generators() -> list[tuple[str, object, object]]:
    from esolangs.tools.boolean.helpers import _decision_tree_program
    from esolangs.tools.boolean.other import _between_ordered
    from esolangs.tools.boolean.parameterized import (
        _bitdeque_ordered,
        _lamfunc_ordered,
        _ram0_ordered,
    )
    from esolangs.tools.boolean.ztoalc_l import _ztoalc_ordered

    return [
        (
            "brainfuck",
            boolean.brainfuck,
            lambda t, p: _decision_tree_program(t, ">", "<", p),
        ),
        (
            "dimensional",
            boolean.dimensional,
            lambda t, p: _decision_tree_program(t, ">0", "<0", p),
        ),
        ("ram0", boolean.ram0, _ram0_ordered),
        ("between", boolean.between, _between_ordered),
        ("lamfunc", boolean.lamfunc, _lamfunc_ordered),
        ("bitdeque", boolean.bitdeque, _bitdeque_ordered),
        ("ztoalc_l_boolean", boolean.ztoalc_l_boolean, _ztoalc_ordered),
    ]


@pytest.mark.parametrize(("name", "fn", "ordered"), _reordering_generators())
def test_reordering_never_grows_a_program(
    name: str, fn: object, ordered: object
) -> None:
    """Choosing the input order can only shrink the emitted program.

    The identity order is one of the candidates, so the winner is at worst a
    tie with what the generator emitted before reordering existed -- which
    is what makes this optimization safe to apply unconditionally.
    """
    for n in (1, 2, 3):
        for value in range(2 ** (2**n)):
            table = bin(value)[2:].zfill(2**n)
            baseline = ordered(table, tuple(range(n)))
            # A searching generator returns "" for an order it cannot place
            # (ZTOALC L); there is no baseline to be no worse than, and any
            # order that *did* place is an improvement on not building.
            if not baseline:
                continue
            assert len(fn(table)) <= len(baseline), f"{name} grew on {table}"


@pytest.mark.parametrize(("name", "fn", "ordered"), _reordering_generators())
def test_reordering_shrinks_the_tables_it_should(
    name: str, fn: object, ordered: object
) -> None:
    """A table only one input order folds well is emitted from that order.

    ``10101010`` depends solely on the *last* input, so splitting on it
    first folds the whole tree to a single leaf, while the identity order
    folds nothing until the bottom level.
    """
    table = "10101010"
    assert len(fn(table)) < len(ordered(table, (0, 1, 2))), (
        f"{name} did not reorder a table that only reordering folds"
    )


def test_reorder_permutation_preserves_the_function() -> None:
    """Permuting the table renames the inputs without changing the function."""
    from esolangs.tools.boolean.helpers import permute_truth_table

    table = "01101001"
    n = 3
    for perm in [(0, 1, 2), (2, 0, 1), (2, 1, 0)]:
        permuted = permute_truth_table(table, perm)
        for row in range(2**n):
            bits = [(row >> (n - 1 - level)) & 1 for level in range(n)]
            original = sum(bits[level] << (n - 1 - i) for level, i in enumerate(perm))
            assert permuted[row] == table[original]


def test_wide_tables_skip_the_exhaustive_search() -> None:
    """Above the cap the order is picked greedily, so wide tables stay fast.

    ``12!`` is 479 million orders; an uncapped search never returns.  The
    greedy fallback still may not emit more than the identity order does.
    """
    from esolangs.tools.boolean.helpers import _ORDER_SEARCH_MAX, _decision_tree_program

    n = _ORDER_SEARCH_MAX + 2
    table = "0" * (2**n - 1) + "1"
    assert len(boolean.brainfuck(table)) <= len(
        _decision_tree_program(table, ">", "<", tuple(range(n)))
    )


def test_greedy_order_is_correct_when_it_is_not_the_identity() -> None:
    """A greedily-ordered program still computes its table.

    Above ``_ORDER_SEARCH_MAX`` the order is picked greedily rather than
    searched, and this is the only path where a *non-identity* order is
    chosen without every candidate having been built and measured, so it
    gets run rather than merely sized.  ``"01" * 64`` depends only on its
    last input, which the greedy pick fronts.
    """
    import io as _io
    from contextlib import redirect_stdout
    from unittest.mock import patch

    from esolangs.interpreters.io import IO
    from esolangs.interpreters.tape_based.brainfuck import run
    from esolangs.tools.boolean.helpers import _greedy_input_order

    n = 7
    table = "01" * 64
    assert _greedy_input_order(table, n) != tuple(range(n)), (
        "this table must exercise a non-identity greedy order"
    )
    program = boolean.brainfuck(table)
    for combo in range(2**n):
        bits = [str((combo >> (n - 1 - i)) & 1) for i in range(n)]
        buffer = _io.StringIO()
        with (
            patch("builtins.input", side_effect=bits),
            redirect_stdout(buffer),
            contextlib.suppress(SystemExit),
        ):
            run(program, io=IO())
        assert buffer.getvalue() == table[combo], f"inputs {bits}"
