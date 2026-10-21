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
