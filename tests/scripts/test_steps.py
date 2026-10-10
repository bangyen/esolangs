"""Step screens distinguish generation refusals from execution failures."""

from unittest.mock import patch

import pytest

from scripts.screens import steps


def test_execution_failure_is_not_a_refusal() -> None:
    with (
        patch.object(
            steps.esolangs, "describe", return_value={"answer_mode": "printed"}
        ),
        patch.object(steps, "TABLES", ["00000000"]),
        patch.object(steps.esolangs, "generate", return_value="bad"),
        patch.object(steps, "_commands", side_effect=ValueError("wrong answer")),
        pytest.raises(ValueError, match="wrong answer"),
    ):
        steps.screen("fixture", 100)


def test_refusals_and_timeouts_are_counted_separately() -> None:
    with (
        patch.object(
            steps.esolangs, "describe", return_value={"answer_mode": "printed"}
        ),
        patch.object(steps, "TABLES", ["00000000", "11111111", "00000001"]),
        patch.object(
            steps, "total", side_effect=[steps.GenerationRefusalError("cap"), None, 8]
        ),
    ):
        result = steps.screen("fixture", 100)
    assert result[5:7] == (1, 1)


def test_generation_refusal_is_reported_even_without_priced_tables() -> None:
    with (
        patch.object(
            steps.esolangs, "describe", return_value={"answer_mode": "printed"}
        ),
        patch.object(steps, "TABLES", ["00000000"]),
        patch.object(steps.esolangs, "generate", side_effect=ValueError("cap")),
    ):
        result = steps.screen("fixture", 100)
    assert result[:7] == (0, 0.0, 0.0, 0.0, 0.0, 0, 1)
