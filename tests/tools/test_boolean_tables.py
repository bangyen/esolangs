"""Run every generator's small truth tables through the shared evaluator.

Sweep all one- and two-input tables and representative three-input shapes.
Language-specific suites retain arity, layout, and size contracts.
"""

from __future__ import annotations

import pytest

from esolangs import evaluate
from esolangs.registry import GENERATORS, resolve
from esolangs.tools.examples import BOOLEAN_EXAMPLES
from tests.raises import raises_message

#: Every table over one and two inputs, then a set at three chosen for the
#: shapes a tree can get wrong: constant, one-variable, parity, majority,
#: AND, OR, and the two NANDs.
_TABLES: list[str] = [
    *(format(i, "02b") for i in range(4)),
    *(format(i, "04b") for i in range(16)),
    "00000000",
    "11111111",
    "00001111",
    "01010101",
    "10010110",  # parity
    "00010111",  # majority
    "00000001",  # AND3
    "11111110",  # NAND3
    "01111111",  # OR3
]


def _arity(table: str) -> int:
    return len(table).bit_length() - 1


@pytest.mark.parametrize("name", sorted(BOOLEAN_EXAMPLES))
@pytest.mark.medium
@pytest.mark.slow
def test_the_generated_program_computes_its_table(name: str) -> None:
    """Every row of every small table comes back as the table says.

    This is the generators' one shared claim, so a new generator is held
    to it by appearing in ``BOOLEAN_EXAMPLES`` -- there is no second list
    to remember.
    """
    example = BOOLEAN_EXAMPLES[name]
    for table in _TABLES:
        n = _arity(table)
        try:
            program = example.generator(table)
        except ValueError:
            # A generator may document an arity or shape it refuses; the
            # refusal itself is its own module's to pin.
            continue
        got = evaluate(name, program, inputs=n)
        assert got == table, f"{name} {table} gave {got!r}"


@pytest.mark.parametrize("name", sorted(BOOLEAN_EXAMPLES))
def test_a_table_of_the_wrong_length_is_refused(name: str) -> None:
    """A truth table whose length is not a power of two builds nothing.

    Every generator validates through the same helper, so the message is
    one message; asserting it whole here is what keeps it that way, since
    a generator that grew its own wording would no longer be checking the
    shared claim.
    """
    with raises_message(
        ValueError,
        "truth table must have a power-of-two number of entries (2**n), got 3"
        "; 3 is between 2 (1 input) and 4 (2 inputs)",
    ):
        BOOLEAN_EXAMPLES[name].generator("011")


@pytest.mark.parametrize("name", sorted(BOOLEAN_EXAMPLES))
def test_a_table_of_other_characters_is_refused(name: str) -> None:
    """A truth table carrying anything but ``0``/``1`` builds nothing."""
    # The message echoes the *argument* now, and names the offending
    # character and where it is: it used to print ``sorted(set(...))``, so
    # a reader who typed "nonsense" was told "got 'enos'".
    with raises_message(
        ValueError,
        "truth table must contain only '0' and '1', got '02' -- "
        "'2' at position 1 is not one of them",
    ):
        BOOLEAN_EXAMPLES[name].generator("02")


def test_the_sweep_covers_every_registered_generator() -> None:
    """The examples corpus must cover the registry without exemptions."""
    assert {resolve(name) for name in BOOLEAN_EXAMPLES} == set(GENERATORS)
