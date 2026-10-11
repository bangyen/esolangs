"""Unit tests for the Packlang interpreter and its generator."""

import contextlib
from functools import partial
from typing import Any, ClassVar

import pytest

import esolangs
from esolangs.exceptions import HaltError
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.other.packlang import _get, _Machine, _node, run
from esolangs.interpreters.other.packlang._parse import _Parser
from esolangs.tools.packlang import packlang
from esolangs.vm import run_until_halt_or_cycle
from tests.fixtures import text
from tests.interpreters.contract import (
    CycleContract,
    EmptyProgramContract,
    SnapshotContract,
)
from tests.interpreters.runner import run_program
from tests.support.raises import assert_rejected_with_hint

# The wiki's five example programs, verbatim.
HELLO, TRUTH_MACHINE, CAT, PLUS_OR_MINUS, DEPENDENCY = (
    text(f"packlang/{name}.txt")
    for name in ("hello", "truth_machine", "cat", "plus_or_minus", "dependency")
)

# The dependency example with every literal rewritten binary -> decimal,
# and nothing else changed.
DEPENDENCY_REBASED = (
    DEPENDENCY.replace("110000", "48")
    .replace("equals(101, 011)", "equals(5, 3)")
    .replace("equals(001, 001)", "equals(1, 1)")
)


_run = partial(run_program, run)


def _machine(code: str) -> _Machine:
    return _Machine(code, ScriptedIO("0\n" * 8))


class TestWikiExamples:
    """Every example on the wiki page, run rather than read."""

    def test_truth_machine_zero_halts_printing_zero(self) -> None:
        assert _run(TRUTH_MACHINE, "0\n") == "0"

    def test_truth_machine_one_loops_printing_ones(self) -> None:
        """``While 1 Do`` never exits, so this is checked by stepping."""
        machine = _Machine(TRUTH_MACHINE, io := ScriptedIO("1\n"))
        for _ in range(60):
            machine.step()
        assert io.getvalue() == "1" * io.getvalue().count("1")
        assert set(io.getvalue()) == {"1"}

    def test_cat_reaches_its_newline_terminator_at_eof(self) -> None:
        machine = _Machine(CAT, io := ScriptedIO("hi"))
        for _ in range(1000):
            machine.step()
            if io.getvalue() == "hi\r\n":
                break
        assert io.getvalue() == "hi\r\n"

    def test_plus_or_minus_runs(self) -> None:
        """Its ``: code`` names a package variable, not a parameter."""
        assert _run(PLUS_OR_MINUS) == ""


class TestLiteralBase:
    """The wiki's conflicting literal-base examples, pinned both ways."""

    def test_the_binary_authored_example_is_declared_wrong(self) -> None:
        """As written it prints mojibake, not the ``0110`` its comments claim."""
        assert _run(DEPENDENCY) == "°±±°"

    def test_rebasing_that_example_gives_the_wikis_stated_output(self) -> None:
        """Its *logic* is right; only the base its literals were written in."""
        assert _run(DEPENDENCY_REBASED) == "0110"

    def test_a_pure_binary_reading_cannot_lex_four_examples(self) -> None:
        """The literals that refute reading every number as binary."""
        for literal in ("72", "108", "44", "255", "13", "48", "49"):
            assert any(c not in "01" for c in literal), literal

    def test_the_wikis_own_binary_for_48_is_a_typo(self) -> None:
        """The comment says ``48 (1100000)``; 48 is ``110000``, six digits."""
        assert format(48, "b") == "110000"
        assert int("1100000", 2) == 96


class TestSemantics:
    def test_xor_is_the_comparison_operator(self) -> None:
        code = """
Package : IO {
  Integer main {
    If 5 ^ 5 Then { charPut(65); }
    If 5 ^ 3 Then { charPut(66); }
    0;
  }
} p;
"""
        assert _run(code) == "B"

    def test_negation_turns_a_nonzero_into_one(self) -> None:
        code = """
Package : IO {
  Integer main {
    charPut(48 ^ !(7 ^ 7));
    charPut(48 ^ !(7 ^ 6));
    charPut(48 ^ !!(7 ^ 6));
    0;
  }
} p;
"""
        assert _run(code) == "101"

    def test_incr_and_decr_walk_a_variable(self) -> None:
        code = """
Package : IO {
  Integer a;
  Integer main {
    INIT a;
    INCR a; INCR a; INCR a; INCR a; INCR a;
    INCR a; INCR a; INCR a;
    DECR a;
    charPut(a ^ 0);
    0;
  }
} p;
"""
        assert _run(code) == "\x07"

    def test_bounded_integer_wraps_to_its_named_values(self) -> None:
        """``Integer(0, 1, 1, 0)``: incrementing past 1 gives the overflow 0."""
        code = """
Package : IO {
  Integer(0, 1, 1, 0) b;
  Integer main {
    INIT b;
    INCR b;
    charPut(48 ^ b);
    INCR b;
    charPut(48 ^ b);
    0;
  }
} p;
"""
        assert _run(code) == "10"

    def test_array_length_and_indexing(self) -> None:
        code = """
Package : IO {
  Array(Char, 3) a;
  Integer main {
    INIT a;
    INCR a(1);
    charPut(48 ^ a(length));
    charPut(48 ^ a(1));
    charPut(48 ^ a(0));
    0;
  }
} p;
"""
        assert _run(code) == "310"

    def test_init_resets_a_whole_array(self) -> None:
        code = """
Package : IO {
  Array(Char, 2) a;
  Integer main {
    INIT a;
    INCR a(0);
    INIT a;
    charPut(48 ^ a(0));
    0;
  }
} p;
"""
        assert _run(code) == "0"

    def test_comments_are_stripped(self) -> None:
        code = """
% a line comment
Package : IO {
  Integer main {
    %$ a block
    comment %
    charPut(65); % trailing
    0;
  }
} p;
"""
        assert _run(code) == "A"

    def test_newline_input_is_preserved(self) -> None:
        """A supplied blank line remains distinct from EOF."""
        code = """
Package : IO {
  Char c;
  Integer main {
    charGet(c);
    charPut(c);
    0;
  }
} p;
"""
        assert _run(code, "\n") == "\n"


class TestErrors:
    def test_unbalanced_block_is_malformed(self) -> None:
        """A block that is never closed runs the parser off the end."""
        with pytest.raises(ValueError, match="unbalanced"):
            _run("Package : IO {\n  Integer main {\n    charPut(65);\n")
        # A partial close leaves the cursor mid-declaration, so the first
        # check the parser reaches is the datatype one.
        with pytest.raises(ValueError, match="unknown datatype"):
            _run("Package : IO {\n  Integer main {\n    0;\n} p;")

    def test_unbounded_recursion_grows_frames_without_crashing(self) -> None:
        """No depth ceiling: frames grow on the heap, not Python's stack."""
        program = (
            "Package : IO {\n"
            "  Integer f {\n    f();\n    0;\n  }\n"
            "  Integer main {\n    f();\n    0;\n  }\n"
            "} app;"
        )
        machine = _Machine(program, ScriptedIO())
        for _ in range(4000):
            machine.step()
        # Far past Python's own recursion limit, and still going.
        assert len(machine.frames) > 1000
        assert not machine.halted

    def test_a_loop_inside_a_called_function_is_provable(self) -> None:
        """The reason calls are framed rather than evaluated inline."""
        program = (
            "Package : IO {\n"
            "  Integer spin {\n    While 1 Do {\n      charPut(65);\n    }\n"
            "    0;\n  }\n"
            "  Integer main {\n    spin();\n    0;\n  }\n"
            "} app;"
        )
        io = ScriptedIO()
        assert run_until_halt_or_cycle(_Machine(program, io)) is False
        assert set(io.getvalue()) == {"A"}

    def test_undefined_variable_halts(self) -> None:
        with pytest.raises(HaltError, match="undefined variable"):
            _run("Package : IO {\n  Integer main {\n    INCR nope;\n    0;\n  }\n} p;")

    def test_undefined_function_halts(self) -> None:
        with pytest.raises(HaltError, match="undefined function"):
            _run("Package : IO {\n  Integer main {\n    nope(1);\n    0;\n  }\n} p;")

    def test_calling_an_undeclared_dependency_halts(self) -> None:
        """The wiki grants access only to a package's declared dependencies."""
        undeclared = """
Dependency {
  Integer helper : Integer a {
    a;
  }
} myDependency;
Package : IO {
  Integer main {
    charPut(48 ^ helper(1));
    0;
  }
} myPackage;
"""
        with pytest.raises(HaltError, match="does not depend on"):
            _run(undeclared)
        # Positive control: declaring the dependency makes the same call work.
        declared = undeclared.replace("Package : IO {", "Package : IO, myDependency {")
        assert _run(declared) == "1"

    def test_a_dependency_of_a_dependency_is_reachable(self) -> None:
        """The wiki says dependencies may have dependencies; resolution
        follows the chain rather than stopping one level down.
        """
        code = """
Dependency {
  Integer deep : Integer a {
    a;
  }
} inner;
Dependency : inner {
  Integer middle : Integer a {
    a;
  }
} outer;
Package : IO, outer {
  Integer main {
    charPut(48 ^ deep(1));
    0;
  }
} myPackage;
"""
        assert _run(code) == "1"

    def test_io_inside_a_called_function_works(self) -> None:
        """A callee's ``charPut`` reaches the shell, in call order."""
        code = """
Dependency {
  Integer shout : Integer a {
    charPut(65);
    a;
  }
} d;
Package : IO, d {
  Integer main {
    charPut(48 ^ shout(1));
    0;
  }
} p;
"""
        assert _run(code) == "A1"

    def test_input_inside_a_called_function_works(self) -> None:
        """The read port reaches a callee too, not only the entry function."""
        code = """
Dependency {
  Integer echo : Integer a {
    Char c;
    charGet(c);
    c;
  }
} d;
Package : IO, d {
  Integer main {
    charPut(echo(0));
    0;
  }
} p;
"""
        assert _run(code, "Z\n") == "Z"

    def test_index_outside_an_array_halts(self) -> None:
        code = """
Package : IO {
  Array(Char, 2) a;
  Integer main {
    INIT a;
    charPut(a(9));
    0;
  }
} p;
"""
        with pytest.raises(HaltError, match="outside"):
            _run(code)

    def test_reading_past_the_input_yields_newline(self) -> None:
        code = """
Package : IO {
  Char c;
  Integer main {
    charGet(c);
    charPut(c);
    0;
  }
} p;
"""
        assert _run(code) == "\n"

    @pytest.mark.parametrize(
        "program",
        [
            "",
            "   ",
            "%$ only a comment %",
            "Package",
            "Package : IO {",
            "Package {} p;",
            "Package : IO { Integer main { } } p;",
        ],
    )
    def test_robustness_never_crashes_unexpectedly(self, program: str) -> None:
        """Malformed input raises ValueError/HaltError, never anything else."""
        with contextlib.suppress(ValueError, HaltError, EOFError):
            _run(program)


class TestRegistry:
    def test_registered_interpreter_runs(self) -> None:
        assert esolangs.run("Packlang", HELLO) == "Hello, World!\r\n"


class TestCharPut:
    def test_successive_charput_calls_print_their_code_points(self) -> None:
        """A minimal package: two ``charPut`` calls and a 0 return."""
        program = (
            "Package : IO {\n"
            "  Integer main {\n"
            "    charPut(104);\n"
            "    charPut(105);\n"
            "    0;\n"
            "  }\n"
            "} printer;\n"
        )
        assert _run(program) == "hi"


class TestBooleanGenerator:
    """Executed over complete truth tables, not inspected as source."""

    def test_the_construction_paints_only_the_rows_that_differ(self) -> None:
        """One write per row the block does not already hold."""
        assert packlang("0001").count("INCR t(") == 1
        assert packlang("0110").count("INCR t(") == 2
        assert packlang("01101001").count("INCR t(") == 4
        assert packlang("0000").count("INCR t(") == 0
        assert "While q^7Do{" in packlang("11111110")
        assert packlang("11111110").count("DECR t(") == 0
        assert packlang("1110").count("INCR t(") == 3
        assert "charPut(48^t(" in packlang("1110")

    @pytest.mark.medium
    def test_three_input_steps_and_sizes(self) -> None:
        """The three-input totals over all 256 tables, pinned."""
        size = steps = 0
        for value in range(256):
            program = packlang(format(value, "08b"))
            size += len(program)
            for row in range(8):
                bits = "".join(f"{row >> (2 - i) & 1}" for i in range(3))
                machine = _Machine(program, ScriptedIO(bits))
                while not machine.halted:
                    machine.step()
                    steps += 1
        assert (size, steps) == (80562, 55632)

    def test_full_table_growth_is_linear(self) -> None:
        """Parity paints half the rows, and its emitted size still doubles."""
        sizes = []
        for n in (7, 8):
            table = "".join(str(row.bit_count() & 1) for row in range(1 << n))
            sizes.append(len(packlang(table)))
        assert sizes[1] < 2 * sizes[0]

    def test_a_one_entry_table_is_refused(self) -> None:
        with pytest.raises(ValueError, match="at least one input"):
            packlang("0")


class TestEmptyProgram(EmptyProgramContract):
    run: ClassVar[Any] = staticmethod(_run)
    empty_raises: ClassVar[str | None] = "empty program"


class TestSnapshot(SnapshotContract):
    machine: ClassVar[Any] = staticmethod(_machine)
    stepping_program: ClassVar[Any] = HELLO


class TestCycle(CycleContract):
    machine: ClassVar[Any] = staticmethod(_machine)
    halting_program: ClassVar[Any] = HELLO
    # ``While 1 Do { charPut(49); }`` revisits its snapshot: the store and
    # the cursor both return to where they were, and it reads no input, so
    # the position cannot advance either.
    looping_program: ClassVar[Any] = """
Package : IO {
  Integer main {
    While 1 Do {
      charPut(49);
    }
    0;
  }
} looper;
"""


_TWO_GS = """Dependency {
  Integer g : Integer a {
    1;
  }
} d1;
Dependency {
  Integer g : Integer a {
    2;
  }
} d2;
Package : IO, d1, d2 {
  Integer main {
    charPut(48 ^ g(0));
    0;
  }
} p;"""


def test_a_call_two_dependencies_answer_is_ambiguous() -> None:
    """The last-parsed ``g`` used to win silently."""
    with pytest.raises(HaltError, match="ambiguous function 'g'"):
        _run(_TWO_GS)


_MAIN = "Package : IO {\n  Integer main {\n    charPut(49);\n    0;\n  }\n} p;"
_HEAD = "{\n  Integer main"


@pytest.mark.parametrize(
    ("code", "error"),
    [
        (_MAIN.replace(_HEAD, "{\n  Integer(5, 1, 0, 0) x;" + _HEAD[1:]), "exceeds"),
        (
            _MAIN.replace(_HEAD, "{\n  Integer(0 255 0 0) x;" + _HEAD[1:]),
            "expected ','",
        ),
        (_MAIN + "\n" + _MAIN.replace("} p;", "} q;"), "multiple parameterless"),
        (_MAIN.replace("} p;", "  Integer main {\n    0;\n  }\n} p;"), "duplicate"),
        pytest.param(
            "Package : IO { Integer main { ); } } p;",
            "unexpected token",
            id="an_operator_cannot_start_an_expression",
        ),
        pytest.param(
            "Dependency {\n  Integer f : Integer a {\n    a;\n  }\n} d;",
            "no parameterless entry",
            id="a_program_with_no_entry_is_malformed",
        ),
        pytest.param(
            "~~~ not packlang @@@", "not Packlang tokens", id="garbage_is_malformed"
        ),
    ],
)
def test_malformed_declarations_are_rejected(code: str, error: str) -> None:
    with pytest.raises(ValueError, match=error):
        _run(code)


@pytest.mark.medium
def test_malformed_source_carries_a_repair_hint() -> None:
    assert_rejected_with_hint("Packlang", "?", "punctuation")


def test_datatype_typo_uses_the_parser_vocabulary():
    with pytest.raises(ValueError, match="unknown datatype") as caught:
        _Parser(["Intger"]).parse_type()
    assert caught.value.__notes__ == ["hint: did you mean 'Integer'?"]


def test_variable_suggestions_use_the_live_scope():
    with pytest.raises(HaltError) as caught:
        _get((("COUNT", 1),), "COUTN")
    assert caught.value.__notes__ == ["hint: did you mean 'COUNT'?"]


def test_internal_tree_errors_and_explicit_aborts_have_no_repair_hint():
    with pytest.raises(HaltError) as caught:
        _node("broken internal tree")
    assert not hasattr(caught.value, "__notes__")
    assert not hasattr(HaltError(), "__notes__")


@pytest.mark.medium
def test_dependency_readings_under_each_literal_policy():
    for policy, expected in (("decimal", "°±±°"), ("binary_digits", "0110")):
        io = ScriptedIO("")
        run(DEPENDENCY, io, literal_policy=policy)
        assert io.getvalue() == expected


@pytest.mark.parametrize("policy", ["decimal", "binary_digits"])
def test_literal_roundtrip(policy):
    from esolangs.interpreters.other.packlang._literals import PacklangLiterals

    literals = PacklangLiterals(policy)
    for value in (0, 1, 2, 10, 48, 128, 255):
        assert literals.parse(literals.emit(value)) == value
    assert literals.parse("255") == 255
