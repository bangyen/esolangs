"""The search-free Minifuck boolean generator.

:mod:`esolangs.tools.boolean.minifuck_closed` builds a template by arithmetic
and a linear solve rather than by searching, and nothing imports it yet -- it
sits beside the searching generator while its coverage is established arity by
arity.  That makes it unreachable from the sweeps in
``test_boolean_parameterized.py``, which walk the registry, so its own tests
live here.

The generator simulates every row as it emits and raises rather than returning
a template it has not seen print the table.  These tests therefore check the
*interpreter* agrees with that simulation, which is the only thing self-
verification cannot establish on its own -- exactly the contract
``TestParameterizedMinifuck`` holds the searching generator to.

Cost is why the sweep here is small.  A table costs one region build plus a
linear solve, and measured on this machine that is ~7s at one input and ~21s
at two, so the whole two-input space is about seven minutes.  The tables below
are picked to cover the construction's routes rather than to enumerate it --
they reach 95% of the module, and the twelve statements they miss are the
inconsistent-solve and unreachable-coset arms, which no *buildable* table can
exercise.  The full sweep is left to the module's own development.
"""

import pytest

from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.tape_based.minifuck import run
from esolangs.tools.boolean.examples import _fill_minifuck
from esolangs.tools.boolean.minifuck_closed import minifuck_closed


def _check(table: str) -> None:
    """Build ``table``, run every row, and assert the printed digits match.

    Also pins the instantiated width: the ``{Xi}`` placeholders become ``[<``
    for a one and ``xx`` for a zero, both two characters, so a program must
    not leak its inputs through its length.
    """
    n = (len(table) - 1).bit_length()
    template = minifuck_closed(table)
    widths = set()
    for combo in range(len(table)):
        bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
        program = _fill_minifuck(template, bits)
        widths.add(len(program))
        io_ = ScriptedIO("")
        run(program, io_)
        assert io_.getvalue() == table[combo], f"{table} inputs {bits}"
    assert len(widths) == 1, (table, widths)


@pytest.mark.slow  # 26.4s: a region build and a linear solve per table
def test_every_one_input_table_computes_its_function() -> None:
    """All four one-input tables build and print what they promise.

    ``00`` and ``11`` take the constant route, which emits a fixed walk and
    never plans reads at all; ``01`` and ``10`` are the two orientations of
    the identity, and they matter as a pair because the generator carries two
    pool spellings differing only in cell 7 -- the cell that decides which
    landing cell prints which digit.  A build that lost one spelling would
    still satisfy one of these and fail the other.
    """
    for table in ("00", "01", "10", "11"):
        _check(table)


@pytest.mark.slow  # 42.0s: two tables at ~21s each
def test_two_input_tables_computes_their_function() -> None:
    """Two-input tables build through the planned reads.

    ``0110`` is XOR, the one two-input table with no constant subtree above a
    single row, so nothing about it can fold -- it is the case that must go
    all the way through the read planner.  ``0001`` is AND, whose answer
    classes are a single long run: the *coarse* shape the module's docstring
    calls the hard case for splitting reads, not the easy one.
    """
    for table in ("0110", "0001"):
        _check(table)


@pytest.mark.slow  # 5.0s: the region model is built before the plan is refused
def test_a_table_it_cannot_build_raises_rather_than_returning() -> None:
    """Failure is reported, not papered over.

    The generator's contract is that it raises rather than returning a
    template it has not seen print the table, so a depth too small to plan
    the reads must raise.  ``depth=0`` admits no reads at all, which no
    non-constant table can be built from.
    """
    with pytest.raises(ValueError, match="no closed-form schedule") as caught:
        minifuck_closed("0110", depth=0)
    # ``match`` is a substring search, so it passes on a message that has
    # grown extra text; pin the whole thing, including the table and depth
    # it names -- an error that cannot say which build failed is not much
    # of a report.
    assert str(caught.value) == "no closed-form schedule for '0110' at depth 0"
