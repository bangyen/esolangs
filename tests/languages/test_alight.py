"""Alight through the shared API, CLI and machinery."""

import json
from pathlib import Path

import pytest

import esolangs
import esolangs.debugger as debugger_api
from esolangs import DialectSettings
from esolangs._evaluate import _evaluate
from tests.api.test_dialects import Unreadable
from tests.reference import REFERENCE
from tests.support.cli_support import call_both
from tests.vm.test_debug import _step_to_halt
from tests.vm.test_vm_protocol import assert_one_row_moves_along_it


def test_set_pairs_match_settings_json(capsys):
    by_set, _ = call_both(
        ["generate", "--set", "expression_syntax=postfix", "Alight", "0110"], capsys
    )
    by_json, _ = call_both(
        [
            "generate",
            "--settings",
            '{"expression_syntax":"postfix"}',
            "Alight",
            "0110",
        ],
        capsys,
    )
    assert by_set == by_json


def test_unknown_settings_key_suggests_the_fix(capsys):
    with pytest.raises(SystemExit) as caught:
        call_both(
            [
                "generate",
                "--settings",
                '{"expressoin_syntax":"postfix"}',
                "Alight",
                "0110",
            ],
            capsys,
        )
    assert caught.value.code == 2
    error = capsys.readouterr().err
    assert "did you mean expression_syntax" in error
    assert "Alight accepts: expression_syntax" in error


@pytest.mark.parametrize("inputs", [1, 6])
def test_balanced_postfix_chunks_execute(inputs):
    table = "01" * (1 << (inputs - 1))
    settings = DialectSettings(expression_syntax="postfix")
    program = esolangs.generate("Alight", table, balance=True, settings=settings)
    assert _evaluate("Alight", program, inputs=inputs, settings=settings) == table


@pytest.mark.medium
def test_cli_generate_and_run_share_settings(tmp_path: Path, capsys):
    choices = '{"expression_syntax":"postfix"}'
    generated, _ = call_both(
        ["generate", "--settings", choices, "Alight", "0110"], capsys
    )
    path = tmp_path / "alight.txt"
    path.write_text(generated)
    for isolated in ([], ["--isolated"]):
        output, _ = call_both(
            ["run", "--settings", choices, *isolated, "Alight", str(path)],
            capsys,
            stdin="10",
        )
        assert output.strip() == "1"


def test_single_choice_languages_refuse_other_keys():
    with pytest.raises(esolangs.ArgumentError):
        esolangs.run("Alight", Unreadable(), settings=DialectSettings(cell_modulus=255))


@pytest.mark.medium
def test_postfix_one_entry_chunks():
    # Width 1 forces 64 one-entry chunks; parity would hide reversed inputs.
    table = "".join(str(((row * 37) ^ (row >> 1)).bit_count() % 2) for row in range(64))
    settings = DialectSettings(expression_syntax="postfix")
    source = esolangs.generate("Alight", table, width=1, settings=settings)
    assert _evaluate("Alight", source, inputs=6, settings=settings) == table


def test_foreign_language_guard_precedes_retained_choices():
    source = esolangs.generate(
        "Alight", "01", settings=DialectSettings(expression_syntax="postfix")
    )
    with pytest.raises(esolangs.ProgramError, match="generated for"):
        esolangs.run("Brainfuck", source)


def test_short_settings_and_portable_flags(capsys, tmp_path):
    output, error = call_both(
        [
            "generate",
            "-p",
            "-s",
            '{"expression_syntax":"postfix"}',
            "Alight",
            "0110",
        ],
        capsys,
    )
    assert error == ""
    assert json.loads(output)["language"] == "Alight"
    path = tmp_path / "program.json"
    path.write_text(output, encoding="utf-8")
    output, error = call_both(["generate", "-p", REFERENCE, "0110"], capsys)
    assert error == ""
    path.write_text(output, encoding="utf-8")
    stdin = esolangs.encode_inputs(REFERENCE, [1, 0], truth_table="0110")
    output, error = call_both(["run", "-p", str(path)], capsys, stdin)
    assert output.strip() == "1"
    assert error == ""


class TestBreakAtChecksTheKindOfPosition:
    """Both wrong-kind breakpoints were stored and could never fire."""

    def test_a_tuple_is_refused_where_the_ip_is_an_index(self) -> None:
        """brainfuck's ip is an int."""
        program = esolangs.generate(REFERENCE, "0110")
        debugger = debugger_api.make_debugger(REFERENCE, program, stdin="0\n1\n")
        # The message names the kind ("an index"), not the value at hand.
        with pytest.raises(esolangs.ArgumentError, match=r"is an index.*never fire"):
            debugger.break_at((1, 2))

    def test_an_index_is_refused_where_the_ip_is_a_coordinate(self) -> None:
        """Alight's is a 4-tuple."""
        program = esolangs.generate("Alight", "0110")
        debugger = debugger_api.make_debugger("Alight", program, stdin="0\n1\n")
        with pytest.raises(esolangs.ArgumentError, match="could never fire"):
            debugger.break_at(10)

    def test_the_right_kind_is_accepted(self) -> None:
        """And still fires, which is the point of checking the other."""
        program = esolangs.generate(REFERENCE, "0110")
        debugger = debugger_api.make_debugger(REFERENCE, program, stdin="0\n1\n")
        debugger.break_at(0)
        assert debugger.run(max_steps=100) == "breakpoint"

    def test_the_arity_is_not_checked(self) -> None:
        """It varies within a run, so checking it would refuse valid ones."""
        program = esolangs.generate("Alight", "0110")
        debugger = debugger_api.make_debugger("Alight", program, stdin="0\n1\n")
        debugger.break_at((1, 2))  # wrong arity for Alight, accepted


def test_alight_refuses_instead_of_warning() -> None:
    """The documented exception, pinned so it stays a *loud* one."""
    program = esolangs.generate("Alight", "0110")
    full = esolangs.encode_inputs("Alight", [1, 0])
    short = "\n".join(full.split("\n")[:-2]) + "\n"
    dbg = debugger_api.make_debugger("Alight", program, stdin=short)
    with pytest.raises(esolangs.HaltError, match="eof"):
        _step_to_halt(dbg)


def test_its_one_row_program_moves_along_the_columns() -> None:
    """The row component of ``VM.ip`` stays put on a one-row program."""
    assert_one_row_moves_along_it("Alight")
