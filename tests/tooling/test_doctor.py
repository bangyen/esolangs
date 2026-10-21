"""``doctor`` flags an old just and a missing hook, and passes a working setup."""

import pytest

from tests.tooling.script_support import REPO_ROOT, load

doctor = load(REPO_ROOT / "scripts" / "doctor.py")


@pytest.mark.parametrize(
    ("version", "ok"),
    [("just 1.58.0", True), ("just 1.37.0", True), ("just 1.36.9", False)],
)
def test_just_must_be_new_enough_to_parse_the_justfile(
    version: str, *, ok: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(doctor, "_output", lambda *_: version)
    assert (doctor._just() is None) is ok  # noqa: SLF001


@pytest.mark.parametrize(
    ("configured", "ok"),
    [(".githooks", True), (str(REPO_ROOT / ".githooks"), True), ("nowhere", False)],
)
def test_the_hook_path_may_be_relative_or_absolute(
    configured: str, *, ok: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(doctor, "_output", lambda *_: configured)
    assert (doctor._hooks() is None) is ok  # noqa: SLF001
