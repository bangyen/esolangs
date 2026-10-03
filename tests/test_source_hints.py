"""Source-repair hints survive interpreter, API, VM and CLI error paths."""

from pathlib import Path

import pytest

import esolangs
from esolangs._execution import interpreter_errors
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.other.packlang import _Parser
from esolangs.interpreters.source_hints import keyword_hint
from esolangs.raster import Raster
from esolangs.vm import make_vm
from tests.cli_support import call_both

# Actual malformed sources, including runtime validation and shared parsers.
_BAD_SOURCE = [
    ("AddSubJump", "ASJ 1", "2 to 4 address operands"),
    ("A Painter Ant", "?", "n/e/s/w"),
    ("Alight", "begin;vra x;end;", "did you mean 'var'"),
    ("Algebraic Programming Language", "1(2)", "1*(2)"),
    ("Back", "", "* halts"),
    ("B-tapemark", ">a!", "uppercase"),
    ("BF-PDA", "[", "close this '['"),
    ("brainfuck", "[", "close this '['"),
    ("BFStack", ">[", "close the loop"),
    ("BIO", "?", "complete BIO"),
    ("bit~", "{", "loop opener"),
    ("Bitdeque", "PUHS", "did you mean 'PUSH'"),
    ("Bitwise Cyclic Tag", "x,1", "program,data"),
    ("Cyclic tag", "0,1;", "semicolons only before"),
    ("Boolfuck", "[", "close this '['"),
    ("Subleq", "x", "decimal integers"),
    ("BrainIf", "if 0 move up", "move left or move right"),
    ("Circlefuck", r"\xG0", "two hex digits"),
    ("Circuit Diagram", "?", "supported Circuit Diagram"),
    ("Clockwise", "", "ring"),
    ("Collatz Multiverse", "?", "DO PRINT"),
    ("CV(N)(C)", "ŋ", "non-nasal consonant"),
    ("Unary", "1", "only 0"),
    ("Decleq", "x", "decimal integers"),
    ("Container", "a+1", "name:"),
    ("Crement", "J 0 0", "+A, -A, +D, -D, +J or -J"),
    ("Dig", "", "@ halts"),
    ("Dimensional", "=g0", "hexadecimal digits"),
    ("EGL", "1,1:(", "pair every ("),
    ("Fargo", "% 0\n$", "pending prefix call"),
    ("Flowchart", "?", "Flowchart nodes"),
    ("Forbin", "", "main"),
    ("Grapheme", "a", "uppercase Latin"),
    ("Home Row", "l", "loop opener"),
    ("Inject", "name;", "repeat the opening"),
    ("Jaune", "?", "decimal number"),
    ("Minsky Swap", "~", "1-based jump target"),
    ("Modulous", "[JMP F]", "required operand"),
    ("NoComment", " ", "spaces and tabs"),
    ("Packlang", "?", "punctuation"),
    ("Polynomial", "x", "f(x) ="),
    ("Qoibl", "tt", "complete each expression"),
    ("RAM0", "1" * 4301, "PYTHONINTMAXSTRDIGITS"),
    ("S*bleq", "-4 0 0", "nonnegative memory address"),
    ("3D Brainfuck", "[", "close this '['"),
    ("Sophie", "#$#[", "matching partner"),
    ("Streetcode", "", "two-cell-wide street"),
    ("Super SNUSP", "", "nonempty grid"),
    ("Suffolk", "", "nonempty program"),
    ("Taglate", "\x001\ngy", "loop opener"),
    ("Vandevelo", "x?", "assign the variable"),
    ("Befunge", "", "@ halts"),
    ("FALSE", "[", "close the lambda"),
    ("FRACTRAN", "2 3/0", "nonzero denominator"),
    ("Fish", "", "; halts"),
    ("Malbolge", "?", "position-dependent"),
    ("Smallfuck", "[", "close this '['"),
    ("Thue", "a::=b", "line containing only ::="),
    ("Unlambda", "`i", "exactly two expressions"),
]


@pytest.mark.medium
@pytest.mark.parametrize(("language", "source", "hint"), _BAD_SOURCE)
def test_rejected_source_retains_a_repair_hint(language, source, hint):
    with pytest.raises(ValueError, match=r".+") as caught:
        esolangs.run(language, source, timeout=0.2)
    assert any(hint in note for note in caught.value.__notes__)


@pytest.mark.medium
@pytest.mark.parametrize(
    "language", ["brainfuck", "BF-PDA", "Boolfuck", "3D Brainfuck"]
)
def test_vm_load_retains_the_delimiter_and_position(language):
    with pytest.raises(esolangs.ProgramError, match="unmatched") as caught:
        make_vm(language, "[", "")
    assert str(caught.value) == "unmatched '[' at position 0"
    assert caught.value.__notes__ == ["hint: close this '[' with ']'"]


@pytest.mark.medium
def test_vm_runtime_error_keeps_its_hint():
    vm = make_vm("Modulous", "[JMP F]", "")
    with pytest.raises(esolangs.ProgramError, match="missing operand") as caught:
        vm.step()
    assert "required operand" in caught.value.__notes__[0]


@pytest.mark.medium
def test_isolated_error_keeps_the_hint():
    with pytest.raises(esolangs.ProgramError, match="unmatched") as caught:
        esolangs.run("brainfuck", "[", isolated=True)
    assert caught.value.__notes__ == ["hint: close this '[' with ']'"]


@pytest.mark.medium
@pytest.mark.parametrize("command", ["run", "debug", "evaluate"])
def test_cli_prints_runtime_hints(command, tmp_path: Path, capsys):
    source = tmp_path / "bad.mod"
    source.write_text("[JMP F]", encoding="utf-8")
    args = [command, "--timeout", "1", "Modulous", str(source)]
    if command == "evaluate":
        args += ["--inputs", "1"]
    with pytest.raises(SystemExit):
        call_both(args, capsys)
    streams = capsys.readouterr()
    text = streams.out + streams.err
    assert "missing operand in JMP F" in text
    assert "hint: supply the required operand" in text


@pytest.mark.medium
@pytest.mark.parametrize(
    ("language", "source", "output"),
    [
        ("brainfuck", "[]", ""),
        ("Bitdeque", "PUSH", "0"),
        ("Alight", "begin;var x;end;", ""),
        ("Packlang", "Package { Integer main { 0; } } demo;", ""),
        ("Forbin", "main { return 0; }", ""),
        ("FRACTRAN", "2 3/2", "3"),
        ("CV(N)(C)", "ci", ""),
        ("Circlefuck", r"\x40", ""),
    ],
)
def test_suggested_syntax_executes(language, source, output):
    assert esolangs.run(language, source, timeout=1) == output


@pytest.mark.parametrize(
    ("word", "hint"),
    [
        ("push", "did you mean 'PUSH'?"),
        ("PUHS", "did you mean 'PUSH'?"),
        ("PRP", "use a command"),
        ("XYZ", "use a command"),
    ],
)
def test_keyword_hint_refuses_ambiguity(word, hint):
    assert keyword_hint(word, ("PUSH", "POP", "PRT"), "use a command") == hint


def test_datatype_typo_uses_the_parser_vocabulary():
    with pytest.raises(ValueError, match="unknown datatype") as caught:
        _Parser(["Intger"]).parse_type()
    assert caught.value.__notes__ == ["hint: did you mean 'Integer'?"]


@pytest.mark.medium
@pytest.mark.parametrize(
    ("language", "source", "stdin", "hint"),
    [
        ("Modulous", "[PSH INT nope]", "", "decimal integer"),
        ("Modulous", "[PSH INT -1][PRT]", "", "between 0 and 1114111"),
        ("Dimensional", "x", "oops", "base-16 integer"),
        ("3x", "?", "nope", "fraction with nonzero denominator"),
        ("Befunge", "&@", "nope", "whitespace-separated decimal integer"),
    ],
)
def test_builtin_value_errors_get_operand_or_input_hints(language, source, stdin, hint):
    with pytest.raises(ValueError, match=r".+") as caught:
        esolangs.run(language, source, stdin, timeout=1)
    assert any(hint in note for note in caught.value.__notes__)


def test_input_hint_is_available_to_direct_interpreter_callers():
    with pytest.raises(
        esolangs.ArgumentError, match="input must be an integer"
    ) as caught:
        ScriptedIO("oops").input_num()
    assert "decimal integer" in caught.value.__notes__[0]


def test_bad_png_hint_survives_exception_translation():
    with pytest.raises(esolangs.ProgramError, match="bad signature") as caught:
        Raster.from_png(b"not an image")
    assert "export the image as PNG" in caught.value.__notes__[0]


@pytest.mark.parametrize(
    ("message", "hint"),
    [
        ("could not convert string to float: 'x'", "decimal number"),
        ("bytes must be in range(0, 256)", "between 0 and 255"),
        ("malformed operand", "describe --spec 'A Painter Ant'"),
    ],
)
def test_unannotated_value_error_keeps_its_diagnostic(message, hint):
    with (
        pytest.raises(esolangs.ProgramError, match=r".+") as caught,
        interpreter_errors("recursion", language="A Painter Ant"),
    ):
        raise ValueError(message)
    assert str(caught.value) == message
    assert hint in caught.value.__notes__[0]


@pytest.mark.medium
@pytest.mark.parametrize(
    ("language", "scale", "hint"),
    [
        ("Line", None, "dark connected paths"),
        ("Piet", 2, "dividing both image dimensions"),
    ],
)
def test_raster_interpreters_retain_geometry_hints(language, scale, hint):
    image = Raster((((255, 255, 255),),))
    with pytest.raises(esolangs.ProgramError, match=r".+") as caught:
        esolangs.run(language, image, scale=scale, timeout=1)
    assert hint in caught.value.__notes__[0]


@pytest.mark.medium
def test_tui_displays_a_runtime_hint():
    from esolangs.tui import render, replay

    frame = replay("Modulous", "[JMP F]", "", step=1)
    assert "hint: supply the required operand" in render(frame, width=120)


@pytest.mark.medium
def test_hints_do_not_discard_partial_output():
    with pytest.raises(esolangs.ProgramError, match="missing operand") as caught:
        esolangs.run("Modulous", "[PSH INT 65][PRT][JMP F]", timeout=1)
    assert caught.value.partial_output == "A"
    assert "hint:" in caught.value.__notes__[0]
    assert "printed 'A'" in caught.value.__notes__[1]


@pytest.mark.medium
def test_text_encoding_hint_is_available_before_interpreter_loading():
    with pytest.raises(esolangs.ProgramError, match="invalid UTF-8") as caught:
        esolangs.run("brainfuck", b"\xff", timeout=1)
    assert caught.value.__notes__ == [
        "hint: save the text program as UTF-8 before running it"
    ]


@pytest.mark.parametrize(
    ("function", "expression", "message", "hint"),
    [
        ("_eval", [], "malformed expression", "nonempty"),
        ("_eval", ["e", "yr"], "malformed comparison", "operator"),
        ("_eval", ["e", "ry"], "malformed arithmetic", "operator"),
        (
            "_compare",
            ["e", "yr", "BAD", "yr", "e"],
            "unrecognized comparison operator",
            "after yr",
        ),
        (
            "_arithmetic",
            ["e", "ry", "BAD", "ry", "e"],
            "unrecognized arithmetic operator",
            "after ry",
        ),
    ],
)
def test_qoibl_hand_built_expression_guards(function, expression, message, hint):
    from esolangs.interpreters.register_based import qoibl

    with pytest.raises(ValueError, match=message) as caught:
        getattr(qoibl, function)(expression, {}, lambda: 0, lambda _: None)
    assert str(caught.value) == message
    assert hint in caught.value.__notes__[0]


def test_value_error_hint_without_language_context():
    with (
        pytest.raises(esolangs.ProgramError) as caught,
        interpreter_errors("recursion"),
    ):
        raise ValueError("malformed operand")
    assert str(caught.value) == "malformed operand"
    assert caught.value.__notes__ == [
        "hint: check the operands and input against the language's syntax"
    ]


def test_truncated_png_header_has_a_recovery_hint():
    import struct
    import zlib

    data = b"\x89PNG\r\n\x1a\n" + struct.pack(">I", 0) + b"IHDR"
    data += struct.pack(">I", zlib.crc32(b"IHDR") & 0xFFFFFFFF)
    with pytest.raises(esolangs.ProgramError, match="not a readable PNG") as caught:
        Raster.from_png(data)
    assert caught.value.__notes__ == [
        "hint: restore or re-export the drawing as a valid PNG"
    ]
