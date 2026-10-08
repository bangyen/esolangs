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
