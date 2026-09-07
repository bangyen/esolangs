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
"""

import importlib
import inspect
import re

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


# A blank-line guard spelled at a call site rather than deferred to the
# shared primitive.  Matches ``ord(x[0]) if x else <n>`` and the ``acc +``
# variant, which is how the divergent guards were actually written.
_HAND_ROLLED = re.compile(
    r"ord\(\s*\w+\[0\]\s*\)\s*(?:[-+]\s*\d+\s*)?if\s+\w+\s+else\s+(\d+)"
)


def _interpreter_sources() -> list[tuple[str, str]]:
    """(language name, module source) for every registered interpreter."""
    out = []
    for name, spec in sorted(LANGUAGES.items()):
        if spec.interpreter is None:
            continue
        mod = importlib.import_module(f"esolangs.interpreters.{spec.interpreter}")
        out.append((name, inspect.getsource(mod)))
    return out


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
    """
    offenders: list[str] = []
    for name, src in _interpreter_sources():
        for match in _HAND_ROLLED.finditer(src):
            if int(match.group(1)) != BLANK_LINE:
                offenders.append(f"{name}: {match.group(0)}")
    assert not offenders, (
        "these read a blank line as something other than "
        f"{BLANK_LINE}: {offenders}"
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
