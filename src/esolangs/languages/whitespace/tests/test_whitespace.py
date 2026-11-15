"""Execution tests for the Whitespace interpreter."""

import subprocess
import sys

import pytest

from esolangs import ExecutionLimits, encode_inputs
from esolangs.exceptions import (
    ArgumentError,
    HaltError,
    InputExhaustedError,
    ProgramError,
)
from esolangs.languages.whitespace.interpreter import _advance, run
from esolangs.runtime.io import IO, ScriptedIO
from tests.interpreters.runner import run_program

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
    # ``_advance`` is called with no value supplied; the shell's read raises
    # EOF before reaching this guard, so this is a direct-call contract.
    for kind in ("read_char", "read_num"):
        with pytest.raises(HaltError, match="input left"):
            _advance((0, (0,), (), (), False), [(kind, 0)], {})


def test_advancing_a_done_state_is_a_no_op() -> None:
    done = (0, (), (), (), True)
    assert _advance(done, [], {}) == (done, None)


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
    assert (result.returncode, result.stdout) == (code, b"")
    assert b"surrogate at character 1" in result.stderr
    assert b"UTF-8" in result.stderr
    if code == 124:
        assert b"omitted partial output" in result.stderr
        assert b"execution stopped at the max_steps bound" in result.stderr


def _check_lossless_containers(tmp_path):
    import io

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
        assert prepared.run().output == "A"
        assert prepared.run(limits=ExecutionLimits(max_steps=100)).output == "A"
    assert (
        api.run(path, isolated=True, limits=ExecutionLimits(max_steps=100)).output
        == "A"
    )
    assert api.execute(path).unwrap().output == "A"
    api.to_file(artifact, path, gzip=True)
    assert api.from_file(path).source == source
    assert api.run(path).output == "A"
    # Raw text names no language; normalize appended "\n", which is code here.
    esolangs.to_file("Whitespace", source, path, normalize=True)
    assert path.read_bytes() == source.encode()
    with pytest.raises(esolangs.ProgramError, match="Whitespace"):
        esolangs.to_file("Brainfuck", artifact, path)


def test_numeric_reads_consume_one_complete_line() -> None:
    read = push(65) + OUT_CHAR + push(0) + T + L + T + T
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
