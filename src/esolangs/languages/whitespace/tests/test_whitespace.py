"""Execution tests for the Whitespace interpreter."""

import subprocess
import sys
from dataclasses import replace

import pytest

from esolangs import ExecutionLimits, ExecutionResult, Language, encode_inputs
from esolangs.debugger import Debugger
from esolangs.exceptions import (
    ArgumentError,
    HaltError,
    InputExhaustedError,
    ProgramError,
)
from esolangs.languages.whitespace.interpreter import _Machine, run
from esolangs.results import Completion, CompletionReport
from esolangs.runtime.io import IO, ScriptedIO
from esolangs.vm import complete_vm
from tests.interpreters.runner import run_program
from tests.support.vm_support import assert_rejected_output_retry

S, T, L = " ", "\t", "\n"


def push(value: int) -> str:
    """Assemble a push of ``value``."""
    sign = T if value < 0 else S
    digits = "".join(T if bit == "1" else S for bit in f"{abs(value):b}")
    return S + S + sign + digits + L


def number(value: int) -> str:
    """Assemble a bare number argument (copy, slide)."""
    sign = T if value < 0 else S
    digits = "".join(T if bit == "1" else S for bit in f"{abs(value):b}")
    return sign + digits + L


SWAP, DISCARD = S + L + T, S + L + L
ADD, SUB, MUL, DIV, MOD = (
    T + S + S + S,
    T + S + S + T,
    T + S + S + L,
    T + S + T + S,
    T + S + T + T,
)
STORE, RETRIEVE = T + T + S, T + T + T
OUT_CHAR, OUT_NUM = T + L + S + S, T + L + S + T
READ_CHAR, READ_NUM = T + L + T + S, T + L + T + T
END = L + L + L


def copy(depth: int) -> str:
    return S + T + S + number(depth)


def slide(depth: int) -> str:
    return S + T + L + number(depth)


def jump(label: str) -> str:
    return L + S + L + label + L


RETURN = L + T + L


def wrun(program: str, stdin: str = "") -> str:
    return run_program(run, program, stdin)


def test_malformed_programs_are_rejected() -> None:
    with pytest.raises(ProgramError, match="ends inside"):
        run("   ", IO())  # ends inside the push
    with pytest.raises(ProgramError, match="empty"):
        run("", IO())
    # An unknown arithmetic subcommand is malformed, not a crash: the bare
    # dict lookup let this escape as KeyError until the fuzzer hit it.
    with pytest.raises(ProgramError, match="no command"):
        run(T + S + L + T, IO())
    # A flow command whose third token is not ``line feed`` is malformed too.
    with pytest.raises(ProgramError, match="flow command"):
        run(L + L + S, IO())


def test_a_pop_from_an_empty_stack_halts() -> None:
    for program in (ADD, SWAP, DISCARD, STORE, RETRIEVE, OUT_NUM, OUT_CHAR):
        with pytest.raises(HaltError, match="empty"):
            run(program + END, IO())


def test_slide_on_an_empty_stack_halts() -> None:
    with pytest.raises(HaltError, match="slide"):
        run(slide(1) + END, IO())


def test_a_read_with_no_input_halts() -> None:
    for command in (READ_CHAR, READ_NUM):
        machine = _Machine(push(0) + command, ScriptedIO(""))
        machine.step()
        with pytest.raises(EOFError):
            machine.step()
        assert machine.stack == [0]


@pytest.mark.parametrize(
    ("command", "stdin"),
    [(READ_CHAR, "A"), (READ_CHAR, ""), (READ_NUM, "7\n"), (READ_NUM, "x\n")],
)
def test_missing_read_destination_fault_does_not_consume_input(command, stdin) -> None:
    api = Language("Whitespace")
    source = command + END
    for options, steps in (
        ({}, None),
        ({"limits": ExecutionLimits(max_steps=2)}, 0),
        ({"isolated": True}, None),
    ):
        outcome = api.run(source, stdin=stdin, **options)
        assert isinstance(outcome.error, HaltError)
        assert str(outcome.error) == "the stack is empty, so there is no top to pop"
        assert outcome.observation == ExecutionResult("", 0, 0, 0, steps=steps)

    debugger = api.make_debugger(source, stdin=stdin)
    snapshot = debugger.snapshot()
    for _ in range(2):
        with pytest.raises(HaltError, match="the stack is empty") as caught:
            debugger.step()
        assert debugger.snapshot() == snapshot
        assert not debugger.halted
        assert caught.value.observation == ExecutionResult("", 0, 0, 0, steps=0)


def test_char_read_with_destination_still_echoes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api = Language("Whitespace")
    source = push(0) + READ_CHAR + push(0) + RETRIEVE + OUT_CHAR + END
    result = api.run(source, stdin="A", isolated=True).unwrap()
    assert result == api.run(source, stdin="A").unwrap()
    assert (result.output, result.input_position, result.input_reads) == ("A", 1, 1)

    for program, value in ((push(14) + OUT_NUM, 14), (push(65) + OUT_CHAR, "A")):
        assert_rejected_output_retry(
            "Whitespace",
            program + END,
            value,
            str(value),
            prefix=1,
            monkeypatch=monkeypatch,
        )


@pytest.mark.parametrize("resume", ["complete_vm", "debugger"])
def test_debugger_sees_recovery_through_another_driver(resume) -> None:
    api = Language("Whitespace")
    source = push(0) + READ_NUM + push(0) + RETRIEVE + OUT_CHAR + END
    debugger = api.make_debugger(source, stdin="bad\n65\n")
    debugger.step()
    with pytest.raises(ArgumentError) as caught:
        debugger.step()
    fault = ExecutionResult("", 4, 1, 0, steps=1)
    assert debugger.observation == caught.value.observation == fault

    other = Debugger(debugger.vm)
    if resume == "debugger":
        assert other.run(limits=ExecutionLimits(max_steps=5)) == "halted"
    else:
        assert complete_vm(debugger.vm, max_steps=5) == "A"
    assert debugger.run(limits=ExecutionLimits(max_steps=0)) == "halted"
    report = CompletionReport(Completion.HALTED)
    result = ExecutionResult("A", 7, 2, 0, steps=1, completion=report)
    assert debugger.observation == result
    assert other.observation == replace(result, steps=5 if resume == "debugger" else 0)
    assert caught.value.observation == fault


def test_advancing_a_done_state_is_a_no_op() -> None:
    machine = _Machine(END, ScriptedIO(""))
    machine.step()
    done = machine.snapshot()
    machine.step()
    assert machine.snapshot() == done


@pytest.mark.parametrize(
    ("program", "message"),
    [
        (push(1) + push(0) + DIV + END, "zero"),
        (push(1) + push(0) + MOD + END, "zero"),
        (push(1) + copy(5) + END, "copy"),
        (RETURN + END, "return"),
        (jump(T) + END, "undefined label"),
    ],
)
def test_invalid_operations_halt(program: str, message: str) -> None:
    with pytest.raises(HaltError, match=message):
        run(program, IO())


def test_the_wiki_cat_program_echoes_until_eof() -> None:
    """The page's Cat program loops on a read, so EOF ends it, after the echo."""
    cat = (
        "\n   \n   \t\n\t\n\t    \t\n\t\t\t\t\n     \t\n\t\t\t\n\t \t\n"
        "\n \n \n\n  \t\n\n\n\n"
    )
    io = ScriptedIO("ab\n")
    with pytest.raises(InputExhaustedError):
        run(cat, io)
    assert io.getvalue() == "ab\n"


def test_signed_division_and_remainder_match_reference() -> None:
    for left, right in ((-7, 3), (7, -3), (-7, -3), (-(2**80) - 1, 7)):
        for command, value in zip((DIV, MOD), divmod(left, right), strict=True):
            assert wrun(push(left) + push(right) + command + OUT_NUM + END) == str(
                value
            )


def test_first_duplicate_label_wins(monkeypatch) -> None:
    mark = L + S + S + T + L
    for transfer, stop, expected in (
        (jump(T), END, "1"),
        (L + S + T + T + L, RETURN, "19"),
    ):
        first = mark + push(1) + OUT_NUM + stop
        second = mark + push(2) + OUT_NUM + stop
        assert wrun(transfer + push(9) + OUT_NUM + END + first + second) == expected

    from esolangs.languages.whitespace import interpreter
    from tests.support.prepared_support import check_image_reuse

    check_image_reuse(
        "Whitespace",
        jump(T) + mark + push(1) + OUT_NUM + END + mark + push(2) + OUT_NUM + END,
        interpreter,
        "_prepare_source",
        monkeypatch,
        cases=(("", "1"),) * 3,
    )


def test_untaken_branches_skip_missing_label_lookup() -> None:
    for branch, value in ((L + T + S, 1), (L + T + T, 0)):
        assert wrun(push(value) + branch + T + L + push(7) + OUT_NUM + END) == "7"
        with pytest.raises(HaltError, match="undefined label"):
            wrun(push(-1 if value == 0 else 0) + branch + T + L + END)
        with pytest.raises(HaltError, match="empty"):
            wrun(branch + T + L + END)


def test_character_output_uses_the_code_point_range(tmp_path) -> None:
    for value in (0, 255, 256, 0xD800, 0xDFFF, 0x10000, 0x10FFFF):
        assert wrun(push(value) + OUT_CHAR + END) == chr(value)
    for value in (-1, 0x110000, -(2**80), 2**80):
        io = ScriptedIO()
        with pytest.raises(HaltError, match="character output"):
            run(push(65) + OUT_CHAR + push(value) + OUT_CHAR + END, io)
        assert io.getvalue() == "A"
    _check_lossless_containers(tmp_path)


@pytest.mark.medium
def test_cli_runs_generated_whitespace_without_an_empty_source_note(tmp_path) -> None:
    command = [sys.executable, "-m", "esolangs"]
    generated = subprocess.run(
        [*command, "generate", "Whitespace", "01"],
        capture_output=True,
        timeout=15,
        check=True,
    )
    assert generated.stdout
    assert not generated.stdout.strip()
    path = tmp_path / "program.ws"
    path.write_bytes(generated.stdout)
    for bit in (0, 1):
        result = subprocess.run(
            [*command, "run", "Whitespace", str(path)],
            input=encode_inputs("Whitespace", [bit]).encode(),
            capture_output=True,
            timeout=15,
            check=True,
        )
        assert (result.stdout, result.stderr) == (str(bit).encode(), b"")


@pytest.mark.medium
@pytest.mark.parametrize(
    ("options", "code"), [([], 1), (["--isolated"], 1), (["--max-steps", "4"], 124)]
)
def test_cli_rejects_surrogate_output_on_a_pipe(tmp_path, options, code) -> None:
    source = push(65) + OUT_CHAR + push(0xD800) + OUT_CHAR + END
    assert wrun(source).encode("utf-8", "surrogatepass") == b"A\xed\xa0\x80"
    path = tmp_path / "surrogate.ws"
    path.write_text(source, encoding="utf-8")
    result = subprocess.run(
        [sys.executable, "-m", "esolangs", "run", *options, "Whitespace", str(path)],
        input=b"",
        capture_output=True,
        timeout=15,
        check=False,
    )
    assert (result.returncode, result.stdout) == (code, b"A" if code == 124 else b"")
    assert b"surrogate at character 1" in result.stderr
    assert b"UTF-8" in result.stderr
    if code == 124:
        assert b"omitted the rest of partial output" in result.stderr
        assert b"execution stopped at the max_steps bound" in result.stderr


def _check_lossless_containers(tmp_path):
    import gzip
    import io
    import json

    import esolangs

    api = esolangs.Language("Whitespace")
    source = (push(65) + OUT_CHAR + END).replace("\n", "\r\n")
    path = tmp_path / "source.ws"
    artifact = api.from_source(source)
    api.to_file(artifact, path)
    assert path.read_bytes() == source.encode()
    assert api.from_file(path).source == source
    assert api.from_file(path, normalize=True).source == source
    for program in (
        source,
        source.encode(),
        path,
        artifact,
        io.StringIO(source),
        io.BytesIO(source.encode()),
    ):
        prepared = api.prepare(program)
        assert prepared.artifact.source == source
        assert prepared.run().unwrap().output == "A"
        assert (
            prepared.run(limits=ExecutionLimits(max_steps=100)).unwrap().output == "A"
        )
    assert (
        api.run(path, isolated=True, limits=ExecutionLimits(max_steps=100))
        .unwrap()
        .output
        == "A"
    )
    assert api.run(path).unwrap().output == "A"
    archive = io.BytesIO()
    with gzip.GzipFile("original.ws", "wb", fileobj=archive, mtime=123) as member:
        member.write(source.encode())
    data = archive.getvalue()
    path.write_bytes(data)
    compressed = api.from_file(path)
    assert isinstance(compressed.source, esolangs.CompressedText)
    assert compressed.source.to_gzip() == data
    assert str(compressed.source) == source
    normalized = api.from_file(path, normalize=True)
    assert normalized == compressed
    document = api.to_json(normalized)
    assert document == api.to_json(path)
    assert json.loads(document)["kind"] == "gzip"
    restored = api.from_json(document)
    assert restored == compressed
    api.to_file(restored, path, gzip=True, normalize=True)
    assert path.read_bytes() == data
    assert api.run(compressed).unwrap().output == "A"
    assert api.run(restored).unwrap().output == "A"
    assert api.run(path).unwrap().output == "A"
    # Raw text names no language; normalize appended "\n", which is code here.
    esolangs.to_file("Whitespace", source, path, normalize=True)
    assert path.read_bytes() == source.encode()
    with pytest.raises(esolangs.ProgramError, match="Whitespace"):
        esolangs.to_file("Brainfuck", artifact, path)


def test_numeric_reads_consume_one_complete_line() -> None:
    read = push(65) + OUT_CHAR + push(0) + READ_NUM
    code = read + push(0) + RETRIEVE + OUT_NUM + END
    valid = {"12\nQ": "12", " -12 \nQ": "-12", "+7": "7", "3\r\nQ": "3"}
    for stdin, expected in valid.items():
        io = ScriptedIO(stdin)
        run(code, io)
        assert io.getvalue() == "A" + expected
        end = stdin.find("\n") + 1 if "\n" in stdin else len(stdin)
        assert (io.position(), io.reads) == (end, 1)
    for stdin in ("", "\n7\n", " \n7\n", "2 3\nQ", "12 x\nQ", "1_0\nQ", "٣\nQ"):
        io = ScriptedIO(stdin)
        with pytest.raises(ArgumentError if stdin else InputExhaustedError):
            run(code, io)
        assert io.getvalue() == "A"
        assert (io.position(), io.reads) == (stdin.find("\n") + 1, int(bool(stdin)))
