"""ROTfuck through the shared API, CLI and machinery."""

import pytest

import esolangs
from esolangs import run
from esolangs.vm import complete_vm, make_vm
from tests.support.cli_support import _failure, _program, call_both


@pytest.mark.parametrize(
    "isolated", [False, pytest.param(True, marks=pytest.mark.medium)]
)
def test_rotfuck_rotation_reaches_every_execution_path(
    isolated, capsys, tmp_path
) -> None:
    """The wiki cat ``,[`` echoes backward; forward, ``,,`` does instead.

    The generator follows the choice: it emits a forward program that answers
    the table when run forward.
    """
    api = esolangs.Language("Rotfuck")
    forward = api.settings(rotation="forward")
    assert run("ROTfuck", ",[", stdin="x", isolated=isolated).unwrap().output == "x"
    assert (
        run("ROTfuck", ",,", stdin="x", settings=forward, isolated=isolated)
        .unwrap()
        .output
        == "x"
    )
    assert (
        complete_vm(make_vm("ROTfuck", ",,", stdin="x", settings=forward), 100) == "x"
    )
    assert complete_vm(make_vm("ROTfuck", ",,", stdin="x"), 100) == ""
    generated = esolangs.generate("ROTfuck", "01", settings=forward)
    assert (
        run("ROTfuck", generated, stdin="0", settings=forward, isolated=isolated)
        .unwrap()
        .output
        == "0"
    )
    assert (
        run("ROTfuck", generated, stdin="1", settings=forward, isolated=isolated)
        .unwrap()
        .output
        == "1"
    )

    prepared = api.prepare(",,", settings=forward)
    left, right = prepared.make_vm(stdin="A"), prepared.make_vm(stdin="B")
    before = right.snapshot()
    assert complete_vm(left, 100) == "A"
    assert right.snapshot() == before
    assert complete_vm(right, 100) == "B"
    assert prepared.run(stdin="C", isolated=isolated).unwrap().output == "C"
    if not isolated:
        _check_cli_text_dialect_settings(api, capsys, tmp_path)


def _check_cli_text_dialect_settings(api, capsys, tmp_path) -> None:
    for command in ("generate", "run"):
        with pytest.raises(SystemExit) as caught:
            call_both([command, "--help"], capsys)
        assert caught.value.code == 0
        help_text, diagnostics = capsys.readouterr()
        assert not diagnostics
        assert "text and gzip" in help_text
        assert "non-default --settings or --set" in help_text
        assert "PNG files carry their dialect settings." in help_text

    settings = ["--set", "rotation=forward"]
    source, diagnostics = call_both(["generate", *settings, api.name, "01"], capsys)
    assert source
    assert not diagnostics
    path = _program(tmp_path, source)
    for bit in "01":
        stdin = api.encode_inputs([int(bit)])
        output, diagnostic = _failure(
            ["run", api.name, path], capsys, code=1, stdin=stdin
        )
        assert output == ""
        assert "read past the end of input" in diagnostic
        assert call_both(["run", *settings, api.name, path], capsys, stdin=stdin) == (
            bit,
            "",
        )
