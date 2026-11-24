"""A mistyped argument is a one-line usage error, not a traceback."""

import pytest

from tests.support.reference import REFERENCE
from tests.tooling.script_support import REPO_ROOT, load


@pytest.mark.parametrize(
    ("script", "args", "message"),
    [
        ("benchmark", [REFERENCE[:-1], "0110"], f"did you mean {REFERENCE}"),
        ("benchmark", [REFERENCE, "011"], "power-of-two"),
        ("gendiff", [REFERENCE[:-1]], f"did you mean {REFERENCE}"),
        ("tracediff", [REFERENCE[:-1]], f"did you mean {REFERENCE}"),
    ],
)
def test_a_bad_argument_exits_2_with_the_reason(
    script: str, args: list[str], message: str, capsys: pytest.CaptureFixture[str]
) -> None:
    main = load(REPO_ROOT / "scripts" / f"{script}.py").main
    with pytest.raises(SystemExit) as exited:
        main(args)
    assert exited.value.code == 2
    assert message in capsys.readouterr().err


@pytest.mark.parametrize("script", ["gendiff", "tracediff"])
def test_diff_reads_the_mutant_before_checkout(script, tmp_path, monkeypatch, capsys):
    module = load(REPO_ROOT / "scripts" / f"{script}.py")
    monkeypatch.setattr(module, "_checkout", lambda *_: pytest.fail("checkout"))
    for path, message in (
        (tmp_path / "missing.py", "cannot read --mutant"),
        (tmp_path, "must be a regular file"),
    ):
        with pytest.raises(SystemExit) as exited:
            module.main([REFERENCE, "--mutant", str(path)])
        assert exited.value.code == 2
        captured = capsys.readouterr()
        assert captured.out == ""
        assert message in captured.err
