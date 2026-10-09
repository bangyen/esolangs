"""A timed-out candidate cannot be certified as divergent."""

from unittest.mock import patch

from esolangs.exceptions import ExecutionTimeoutError
from scripts.screens import dead_code


def test_timeout_is_not_accepted_as_divergence() -> None:
    with (
        patch.object(dead_code.esolangs, "generate", return_value="source"),
        patch.object(
            dead_code,
            "describe",
            return_value={
                "answer_mode": "termination",
                "answer_encoding": ("halts", "diverges"),
            },
        ),
    ):
        program = dead_code._Program("fixture", "11", 0.001)  # noqa: SLF001
    with (
        patch.object(dead_code, "encode_inputs", return_value=""),
        patch(
            "esolangs._evaluate._terminates",
            side_effect=ExecutionTimeoutError("undecided"),
        ),
    ):
        assert not program.correct(program.text)
    with (
        patch.object(dead_code, "encode_inputs", return_value=""),
        patch("esolangs._evaluate._terminates", return_value="1"),
    ):
        assert program.correct(program.text)
