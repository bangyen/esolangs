r"""Every interpreter must read a blank input line the same way."""

import ast
import importlib
import inspect

import pytest

import esolangs
from esolangs.interpreters.io import IO, ScriptedIO
from esolangs.registry import LANGUAGES

# : The value every interpreter.
# : immediately.
BLANK_LINE = 0


def test_input_char_reads_a_blank_line_as_the_convention() -> None:
    r"""The shared primitive answers with the convention."""
    io_obj = ScriptedIO("\n")
    assert io_obj.input_char() == BLANK_LINE


def test_exhausted_input_is_still_distinct_from_a_blank_line() -> None:
    r"""Only running out of input is EOF; a blank line is a value."""
    io_obj = ScriptedIO("\n")
    assert io_obj.input_char() == BLANK_LINE
    with pytest.raises(EOFError):
        io_obj.input_char()


def _reads_first_character(node: ast.expr, line: str) -> bool:
    r"""Whether ``node`` takes ``ord(line[0])`` anywhere inside it."""
    return any(
        isinstance(sub, ast.Call)
        and isinstance(sub.func, ast.Name)
        and sub.func.id == "ord"
        and len(sub.args) == 1
        and isinstance(sub.args[0], ast.Subscript)
        and isinstance(sub.args[0].value, ast.Name)
        and sub.args[0].value.id == line
        and isinstance(sub.args[0].slice, ast.Constant)
        and sub.args[0].slice.value == 0
        for sub in ast.walk(node)
    )


def _constant_byte(node: ast.expr) -> int | None:
    r"""Return the byte a fallback expression yields, or None if it is not."""
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "ord"
        and len(node.args) == 1
        and isinstance(node.args[0], ast.Constant)
        and isinstance(node.args[0].value, str)
        and len(node.args[0].value) == 1
    ):
        return ord(node.args[0].value)
    if isinstance(node, ast.Constant) and isinstance(node.value, int):
        # bool is an int subclass, and.
        return None if isinstance(node.value, bool) else node.value
    return None


def _blank_line_guards(source: str) -> list[tuple[ast.expr, str]]:
    r"""Return every ``<reads line[0]> if line else <fallback>`` and its."""
    found = []
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.IfExp) or not isinstance(node.test, ast.Name):
            continue
        if _reads_first_character(node.body, node.test.id):
            found.append((node.orelse, ast.unparse(node)))
    return found


def _interpreter_sources() -> list[tuple[str, str]]:
    r"""(language name, module source) for every registered interpreter."""
    out = []
    for name, spec in sorted(LANGUAGES.items()):
        if spec.interpreter is None:
            continue
        mod = importlib.import_module(f"esolangs.interpreters.{spec.interpreter}")
        out.append((name, inspect.getsource(mod)))
    return out


def test_the_scan_finds_the_guards_that_are_really_there() -> None:
    r"""The detector fires on live code, not only on constructed input."""
    found = {name for name, src in _interpreter_sources() if _blank_line_guards(src)}
    assert {
        "Alight",
        "DINAC",
        "Jaune",
        "LaserFuck",
        "Streetcode",
        "Suffolk",
    } <= found, found


@pytest.mark.parametrize(
    ("guard", "expected"),
    [
        ('ord(line[0]) if line else ord("\\n")', 10),
        ("ord(line[0]) if line else 10", 10),
        ("ord(line[0]) if line else 0", 0),
        ("ord(ch[0]) - 48 if ch else 0", 0),
        ("acc + ord(inp[0]) if inp else 0", 0),
    ],
)
def test_a_guard_is_read_by_shape_not_by_spelling(guard: str, expected: int) -> None:
    r"""Every way of writing the fallback resolves to the byte it yields."""
    guards = _blank_line_guards(guard)
    assert len(guards) == 1, guard
    assert _constant_byte(guards[0][0]) == expected


def test_a_guard_with_no_byte_to_yield_is_not_a_disagreement() -> None:
    r"""``None`` is not a value that can differ from the convention."""
    guards = _blank_line_guards("byte = ord(val[0]) if val else None")
    assert len(guards) == 1
    assert _constant_byte(guards[0][0]) is None


def test_registry_covers_the_interpreters_scanned() -> None:
    r"""The scan is registry-driven, so a new language is covered for free."""
    sources = _interpreter_sources()
    assert len(sources) >= 50, f"only {len(sources)} interpreters scanned"
    names = {n for n, _ in sources}
    assert {"brainfuck", "Streetcode", "LaserFuck"} <= names


def test_no_interpreter_hand_rolls_a_divergent_blank_line_guard() -> None:
    r"""A call-site guard must not disagree with the shared convention."""
    offenders: list[str] = []
    for name, src in _interpreter_sources():
        for fallback, text in _blank_line_guards(src):
            value = _constant_byte(fallback)
            if value is not None and value != BLANK_LINE:
                offenders.append(f"{name}: {text}")
    assert not offenders, (
        f"these read a blank line as something other than {BLANK_LINE}: {offenders}"
    )


@pytest.mark.parametrize(
    ("language", "program"),
    [
        ("brainfuck", ",."),
        ("3D Brainfuck", "su+dn,."),
        ("BFStack", ",."),
    ],
)
def test_reading_a_blank_line_agrees_across_languages(
    language: str, program: str
) -> None:
    r"""Executed, not merely read: a blank line is the same byte everywhere."""
    assert esolangs.run(language, program, stdin="\n") == chr(BLANK_LINE)


def test_streetcode_agrees_with_the_tape_languages() -> None:
    r"""The language that exposed the split now matches the rest."""
    grid = "\n".join(
        [
            "+------+",
            "|      |",
            "|CIO;  |",
            "+------+",
        ]
    )
    assert esolangs.run("Streetcode", grid, stdin="\n") == chr(BLANK_LINE)
    assert esolangs.run("brainfuck", ",.", stdin="\n") == chr(BLANK_LINE)


def test_the_convention_is_reachable_through_the_base_class() -> None:
    r"""``IO`` itself, not only ``ScriptedIO``, applies the convention."""
    from unittest.mock import patch

    with patch("builtins.input", return_value=""):
        assert IO().input_char() == BLANK_LINE


# : What a language does when a.
# : all.
# : between the two answers is.
#: here rather than inferred.
# :.
# : The default is that the.
# : catch it, so the caller.
# : answer differently, and.
# : statement about them, not a.
_EOF_IS_A_HALT: dict[str, str] = {
    # Reads until the input runs.
    # how its generated programs.
    "suffolk": "reads to exhaustion, so EOF is the halt",
    # Read their inputs before the.
    # a load-time answer rather.
    "fargo": "the interpreter reads before the program starts",
    "circuit_diagram": "resolves its inputs while laying the grid",
    "flowchart": "reads at the switch, which a program without one skips",
    "dinac": "its reads are guarded, so a missing line is a zero",
    "s*bleq": "a failed read leaves the cell alone and the program runs on",
}


@pytest.mark.parametrize("name", sorted(_EOF_IS_A_HALT))
def test_every_eof_exemption_names_a_real_language(name: str) -> None:
    r"""An exemption whose language is gone must not linger unnoticed."""
    from esolangs.tools.boolean.examples import BOOLEAN_EXAMPLES

    assert name in BOOLEAN_EXAMPLES


def _reading_languages() -> list[str]:
    r"""The examples whose programs read their inputs from the stream."""
    from esolangs.tools.boolean.examples import BOOLEAN_EXAMPLES

    return sorted(
        name
        for name, example in BOOLEAN_EXAMPLES.items()
        # A ``fill`` means the bits are.
        # the language has no input.
        if example.fill is None
        and name not in _EOF_IS_A_HALT
        # Suptiftam's read sits inside.
        # so an empty stream is a hang.
        and name != "suptiftam"
        # Alight raises its own error.
        and name != "alight"
    )


@pytest.mark.parametrize("name", _reading_languages())
def test_running_out_of_input_reaches_the_caller(name: str) -> None:
    r"""A program that reads, handed nothing, raises rather than inventing."""
    from esolangs.tools.boolean.examples import BOOLEAN_EXAMPLES

    example = BOOLEAN_EXAMPLES[name]
    module = importlib.import_module("esolangs.interpreters." + example.interpreter)
    program = example.generator("0110")
    argument = program.splitlines() if example.split else program
    extra = {key: value for key, value in example.kwargs if key != "seed"}
    with pytest.raises(EOFError):
        module.run(argument, io=ScriptedIO(""), **extra)
