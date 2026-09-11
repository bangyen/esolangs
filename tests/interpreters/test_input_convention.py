"""Every interpreter must read a blank input line the same way.

The package used to answer this question twice.  ``io.input_char``
returned ``ord("\\n")`` for a line the user ended immediately, while every
interpreter calling ``io.input_str`` directly guarded the same case at its
own call site -- and each of those chose ``0``.  So ``,`` on a blank line
was 10 in brainfuck and 0 in Streetcode, and a brainfuck -> Streetcode
translation could not be correct on a program that read one.

The split was an artifact rather than a decision.  ``input_char`` was once
``ord(self.input_str(prompt)[0])``, an ``IndexError`` on a blank line that
leaked under 21 languages; the fix had to pick a value and picked the
newline, then verified six languages -- every one an ``input_char`` user.
The ``input_str`` callers never had the bug, so nothing prompted a look.

``input_char`` now returns 0, matching them.  These tests pin the
convention so the next interpreter cannot quietly reopen the split:
the source scan enumerates the **registry**, not a hand-written list, so
a language added later is covered without anyone remembering to add it.

The scan parses the source rather than matching it.  A regex did this
until an interpreter spelled its fallback ``ord("\\n")`` -- a call, where
the pattern wanted a digit -- and so read a blank line as 10 while this
file passed green.  A pattern has to enumerate the spellings; the AST
sees the shape, and the fallback is folded to the byte it actually
yields.
"""

import ast
import importlib
import inspect

import pytest

import esolangs
from esolangs.interpreters.io import IO, ScriptedIO
from esolangs.registry import LANGUAGES

#: The value every interpreter must read for a line the user ended
#: immediately.  Exhausted input is a different thing and still raises.
BLANK_LINE = 0


def test_input_char_reads_a_blank_line_as_the_convention() -> None:
    """The shared primitive answers with the convention."""
    io_obj = ScriptedIO("\n")
    assert io_obj.input_char() == BLANK_LINE


def test_exhausted_input_is_still_distinct_from_a_blank_line() -> None:
    """Only running out of input is EOF; a blank line is a value.

    This is the distinction the original fix was protecting, and it
    survives the change: ``"".splitlines()`` is ``[]`` (no line at all)
    while ``"\\n".splitlines()`` is ``[""]`` (one line, which is empty).
    """
    io_obj = ScriptedIO("\n")
    assert io_obj.input_char() == BLANK_LINE
    with pytest.raises(EOFError):
        io_obj.input_char()


def _reads_first_character(node: ast.expr, line: str) -> bool:
    """Whether ``node`` takes ``ord(line[0])`` anywhere inside it.

    Searched rather than matched at the root: the guards convert the byte
    they read (``ord(ch[0]) - 48``, ``acc + ord(inp[0])``), so the call is
    a subexpression of the branch rather than the branch itself.
    """
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
    """Return the byte a fallback expression yields, or None if it is not one.

    ``ord("\\n")`` is folded rather than skipped: that is the spelling the
    divergent guard used, and reading it as "not a literal" is how it went
    unnoticed.  A fallback that is not a byte at all -- ``None``, where
    there is no cell to write -- returns None and is not a disagreement.
    """
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
        # bool is an int subclass, and True is not a byte a read yields.
        return None if isinstance(node.value, bool) else node.value
    return None


def _blank_line_guards(source: str) -> list[tuple[ast.expr, str]]:
    """Return every ``<reads line[0]> if line else <fallback>`` and its text.

    Parsed rather than pattern-matched on the source.  A regex has to
    enumerate the spellings a fallback can take, and the one that reopened
    the split was spelled ``ord("\\n")`` -- a call, where the pattern
    wanted a digit -- so it matched nothing and the test passed green.
    The shape is what identifies a guard: a conditional whose test is the
    bare line and whose true branch reads that line's first character.
    """
    found = []
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.IfExp) or not isinstance(node.test, ast.Name):
            continue
        if _reads_first_character(node.body, node.test.id):
            found.append((node.orelse, ast.unparse(node)))
    return found


def _interpreter_sources() -> list[tuple[str, str]]:
    """(language name, module source) for every registered interpreter."""
    out = []
    for name, spec in sorted(LANGUAGES.items()):
        if spec.interpreter is None:
            continue
        mod = importlib.import_module(f"esolangs.interpreters.{spec.interpreter}")
        out.append((name, inspect.getsource(mod)))
    return out


def test_the_scan_finds_the_guards_that_are_really_there() -> None:
    """The detector fires on live code, not only on constructed input.

    A lint that matches nothing passes for the same reason a clean repo
    does.  These six are the guards actually in the tree -- two of them
    converting the byte they read, and Alight's falling back to a float --
    so a change that stops the walker seeing a real spelling fails here
    rather than going quiet.

    Named in full rather than as a sample: the set was assumed to be four
    while it was six, and an audit of where the blank-line 0 comes from
    took its population from this assertion.
    """
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
    """Every way of writing the fallback resolves to the byte it yields.

    The first case is the one that reopened the split: ``ord("\\n")`` is a
    call where the old pattern wanted a digit, so it matched nothing and
    the offending interpreter passed.  Folding it is the whole point of
    parsing instead of matching text.
    """
    guards = _blank_line_guards(guard)
    assert len(guards) == 1, guard
    assert _constant_byte(guards[0][0]) == expected


def test_a_guard_with_no_byte_to_yield_is_not_a_disagreement() -> None:
    """``None`` is not a value that can differ from the convention.

    The template guards this way where there is no cell to write to, and
    flagging it would make the lint cry wolf on correct code.
    """
    guards = _blank_line_guards("byte = ord(val[0]) if val else None")
    assert len(guards) == 1
    assert _constant_byte(guards[0][0]) is None


def test_registry_covers_the_interpreters_scanned() -> None:
    """The scan is registry-driven, so a new language is covered for free.

    A hand-written list would cancel out -- the thing it checks and the
    thing it is checked against would be the same edit -- so this asserts
    the scan actually sees a substantial set.
    """
    sources = _interpreter_sources()
    assert len(sources) >= 50, f"only {len(sources)} interpreters scanned"
    names = {n for n, _ in sources}
    assert {"brainfuck", "Streetcode", "LaserFuck"} <= names


def test_no_interpreter_hand_rolls_a_divergent_blank_line_guard() -> None:
    """A call-site guard must not disagree with the shared convention.

    Guarding locally is fine -- some languages convert the byte, or have
    no cell to write -- but the *value* for a blank line has to be the
    one :data:`BLANK_LINE` names.  A guard yielding anything else is the
    split coming back.

    The fallback is evaluated rather than read off the source text, so a
    guard spelling it ``ord("\\n")`` is caught the same as one spelling it
    ``10``.  A non-constant fallback (``None``, where there is no cell to
    write) is not a value that can disagree, so it is left alone.
    """
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
    """Executed, not merely read: a blank line is the same byte everywhere.

    These three are ``input_char`` users whose ``,`` echoes through ``.``
    and which halt on this program -- not every brainfuck-alike does, so
    the set is the ones actually checked rather than the ones assumed.
    Streetcode is checked separately because its program is a grid.
    """
    assert esolangs.run(language, program, stdin="\n") == chr(BLANK_LINE)


def test_streetcode_agrees_with_the_tape_languages() -> None:
    """The language that exposed the split now matches the rest."""
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
    """``IO`` itself, not only ``ScriptedIO``, applies the convention."""
    from unittest.mock import patch

    with patch("builtins.input", return_value=""):
        assert IO().input_char() == BLANK_LINE


#: What a language does when a *reading* program is handed no input at
#: all.  Twenty-two files pinned this one language at a time; the split
#: between the two answers is the interesting part, so it is written down
#: here rather than inferred.
#:
#: The default is that the ``EOFError`` escapes: the interpreter does not
#: catch it, so the caller sees a real end of input.  The languages below
#: answer differently, and each for a reason of its own -- so the set is a
#: statement about them, not a list of exceptions to ignore.
_EOF_IS_A_HALT: dict[str, str] = {
    # Reads until the input runs out and treats that as its stop, which is
    # how its generated programs terminate at all.
    "suffolk": "reads to exhaustion, so EOF is the halt",
    # Read their inputs before the program runs, so an exhausted stream is
    # a load-time answer rather than a step that fails.
    "fargo": "the interpreter reads before the program starts",
    "circuit_diagram": "resolves its inputs while laying the grid",
    "flowchart": "reads at the switch, which a program without one skips",
    "dinac": "its reads are guarded, so a missing line is a zero",
    "s*bleq": "a failed read leaves the cell alone and the program runs on",
}


@pytest.mark.parametrize("name", sorted(_EOF_IS_A_HALT))
def test_every_eof_exemption_names_a_real_language(name: str) -> None:
    """An exemption whose language is gone must not linger unnoticed.

    The roster is hard-coded, which is exactly the shape that silently
    deselects; comparing it against the registry is what stops an entry
    outliving the language it describes.
    """
    from esolangs.tools.boolean.examples import BOOLEAN_EXAMPLES

    assert name in BOOLEAN_EXAMPLES


def _reading_languages() -> list[str]:
    """The examples whose programs read their inputs from the stream."""
    from esolangs.tools.boolean.examples import BOOLEAN_EXAMPLES

    return sorted(
        name
        for name, example in BOOLEAN_EXAMPLES.items()
        # A ``fill`` means the bits are embedded in the program text, so
        # the language has no input command to run out of.
        if example.fill is None
        and name not in _EOF_IS_A_HALT
        # Suptiftam's read sits inside a loop that never ends without one,
        # so an empty stream is a hang rather than a raise.
        and name != "suptiftam"
        # Alight raises its own error before the read is reached.
        and name != "alight"
    )


@pytest.mark.parametrize("name", _reading_languages())
def test_running_out_of_input_reaches_the_caller(name: str) -> None:
    """A program that reads, handed nothing, raises rather than inventing.

    This is what makes the blank-line convention above meaningful: a
    language that swallowed the EOF would answer a missing line with the
    same byte as an empty one, and the two would stop being distinct.
    """
    from esolangs.tools.boolean.examples import BOOLEAN_EXAMPLES

    example = BOOLEAN_EXAMPLES[name]
    module = importlib.import_module("esolangs.interpreters." + example.interpreter)
    program = example.generator("0110")
    argument = program.splitlines() if example.split else program
    extra = {key: value for key, value in example.kwargs if key != "seed"}
    with pytest.raises(EOFError):
        module.run(argument, io=ScriptedIO(""), **extra)
