"""FALSE through the shared API, CLI and machinery."""

import pytest

from tests.duration_policy import limits


@pytest.mark.parametrize("value", ["", "0", "false"])
def test_an_unset_or_falsey_ci_keeps_the_local_ceiling(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    monkeypatch.setenv("CI", value)
    assert limits() == (1.0, 5.0)
