"""Generator round-trip checks for the development suite."""

import esolangs
from esolangs._evaluate import _DEFAULT, _Default, _evaluate
from tests.stdin_check import _validate_shape_for_evaluate


def evaluate_generated(
    language: str,
    table: str,
    timeout: float | _Default | None = _DEFAULT,
    width: int | None = None,
    *,
    isolated: bool = False,
) -> str:
    """Generate a table's program, then evaluate its observed answers."""
    inputs = _validate_shape_for_evaluate(table)
    program = esolangs.generate(language, table, width=width)
    return _evaluate(language, program, timeout, inputs=inputs, isolated=isolated)


def verify_generated(
    language: str,
    table: str,
    timeout: float | _Default | None = _DEFAULT,
    width: int | None = None,
    *,
    isolated: bool = False,
) -> bool:
    """Compare a generator's observed table with its requested table."""
    return (
        evaluate_generated(language, table, timeout, width, isolated=isolated) == table
    )


#: What a coverage failure for a new language says to do: ``check`` names
#: the file and the entry, so the messages need not repeat it.
CHECK = "`just check-language <name>` names the entry to add"


def assert_an_ignored_input_costs(name: str, n: int, cost: int) -> None:
    """An input the table ignores adds ``cost`` characters, read and dropped.

    Lifted at every position from an ``n``-input one-hot table.  A lookup
    indexed by the essential inputs still reads the ignored one; it used to
    grow as much as a real input, the table doubled over the bit.
    """
    from esolangs.registry import LANGUAGES

    inner = "".join(str(int(row.bit_count() == 1)) for row in range(2**n))
    build = LANGUAGES[name].boolean
    assert build is not None
    for at in (0, n // 2, n):
        low = n - at
        table = "".join(
            inner[row >> (low + 1) << low | row & ((1 << low) - 1)]
            for row in range(2 * len(inner))
        )
        assert len(build(table)) - len(build(inner)) == cost, at
    assert evaluate_generated(name, table, timeout=30) == table
