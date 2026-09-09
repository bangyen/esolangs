"""Unit tests for the Packlang interpreter and its two generators.

The wiki's five examples are the ground truth here, and two of them
disagree with the other three about what base a numeric literal is in.
:class:`TestLiteralBase` pins the resolution from both directions: the
three examples decimal keeps are asserted byte-exact, and the two it
declares wrong are asserted to produce the *wrong* output as shipped and
the wiki's stated output once their literals are converted binary to
decimal -- which is what shows the defect is the base the author wrote,
not the interpreter's arithmetic.
"""

import contextlib
from typing import Any, ClassVar

import pytest

import esolangs
from esolangs.exceptions import HaltError
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.other.packlang import _Machine, run
from esolangs.tools.boolean.packlang import packlang as packlang_boolean
from esolangs.tools.text.other import packlang as packlang_text
from esolangs.vm import run_until_halt_or_cycle
from tests.interpreters.contract import (
    CycleContract,
    EmptyProgramContract,
    SnapshotContract,
)
from tests.interpreters.runner import run_program

HELLO = """
Package : IO {
  Integer main {
    charPut(72);
    charPut(101);
    charPut(108);
    charPut(108);
    charPut(111);
    charPut(44);
    charPut(32);
    charPut(87);
    charPut(111);
    charPut(114);
    charPut(108);
    charPut(100);
    charPut(33);
    charPut(13);
    charPut(10);
    0;
  }
} helloWorld;
"""

TRUTH_MACHINE = """
Package : IO {
  Char input;
  Integer main {
    charGet(input);
    If input ^ 48 Then {
      While 1 Do {
        charPut(49);
      }
    }
    charPut(48);
  }
} truthMachine;
"""

CAT = """
Package : IO {
  Array(Char, 100) input;
  Char c;
  Integer i;
  Integer j;
  Integer main {
    While 1 Do {
      INIT input;
      INIT c;
      INIT i;
      INIT j;
      charGet(c);
      While c ^ 10 Do {
        While c Do {
          INCR input(i);
          DECR c;
        }
        INCR i;
        charGet(c);
      }
      While j ^ i Do {
        charPut(input(j));
        INCR j;
      }
      charPut(13);
      charPut(10);
    }
    0;
  }
} cat;
"""

PLUS_OR_MINUS = """
Package : IO {
  String code;
  Integer i;
  Integer(0, 255, 255, 0) acc;
  Integer plusOrMinus : code {
    INIT i;
    INIT acc;
    While i ^ code(length) Do {
      If !(code(i) ^ 101011) Then {
        INCR acc;
      }
      If !(code(i) ^ 101101) Then {
        charPut(acc);
        DECR acc;
      }
      INCR i;
    }
    0;
  }
} plusOrMinus;
"""

DEPENDENCY = """
Dependency {
  Integer equals : Integer a, Integer b {
    !(a ^ b);
  }
  Integer nequals : Integer a, Integer b {
    !!(a ^ b);
  }
} myDependency;
Package : IO, myDependency {
  Integer main {
    charPut(110000 ^ equals(101, 011));
    charPut(110000 ^ equals(001, 001));
    charPut(110000 ^ nequals(101, 011));
    charPut(110000 ^ nequals(001, 001));
    0;
  }
} myPackage;
"""

# The dependency example with every literal rewritten binary -> decimal,
# and nothing else changed.
DEPENDENCY_REBASED = (
    DEPENDENCY.replace("110000", "48")
    .replace("equals(101, 011)", "equals(5, 3)")
    .replace("equals(001, 001)", "equals(1, 1)")
)


def _run(code: str, stdin: str = "") -> str:
    return run_program(run, code, stdin)


def _machine(code: str) -> _Machine:
    return _Machine(code, ScriptedIO("0\n" * 8))


class TestWikiExamples:
    """Every example on the wiki page, run rather than read."""

    def test_hello_world(self) -> None:
        assert _run(HELLO) == "Hello, World!\r\n"

    def test_truth_machine_zero_halts_printing_zero(self) -> None:
        assert _run(TRUTH_MACHINE, "0\n") == "0"

    def test_truth_machine_one_loops_printing_ones(self) -> None:
        """``While 1 Do`` never exits, so this is checked by stepping."""
        machine = _Machine(TRUTH_MACHINE, io := ScriptedIO("1\n"))
        for _ in range(60):
            machine.step()
        assert io.getvalue() == "1" * io.getvalue().count("1")
        assert set(io.getvalue()) == {"1"}

    def test_cat_parses_and_accumulates_but_cannot_reach_its_terminator(
        self,
    ) -> None:
        """The wiki cat assumes a byte stream; this package reads lines.

        Its inner loop ends on ``c ^ 10``, a literal newline *byte* from
        ``charGet``.  Input here arrives through ``splitlines``, so a line
        never begins with byte 10 -- a blank line is ``""`` and reads as
        the package-wide 0 -- and the terminator is unreachable by
        construction rather than by a bug.  What is checked is that the
        program runs and consumes its input; the echo phase it never
        reaches is asserted by the rewritten cat below.
        """
        io = ScriptedIO("h\ni\n\n")
        with pytest.raises(EOFError):
            run(CAT, io)
        assert io.position() == 3

    def test_a_line_terminated_cat_echoes(self) -> None:
        """The same construction with the terminator this IO can deliver.

        Only the guard changes -- ``c ^ 10`` becomes ``c``, so the loop
        ends on the 0 a blank line reads as. The copy-by-countdown body,
        the array indexing and the echo loop are the wiki's unchanged,
        which is what makes this evidence that the cat's *mechanism* runs.
        """
        assert (
            _run(CAT.replace("While c ^ 10 Do", "While c Do"), "h\ni\n\n") == "hi\r\n"
        )

    def test_plus_or_minus_runs(self) -> None:
        """Its ``: code`` names a package variable, not a parameter.

        ``String code`` has no literal syntax on the wiki to fill it, so
        the array is empty and the interpreter loop body never runs. What
        this pins is that the program *parses and executes* -- the entry
        rule reaches a function whose colon clause is a bare name.
        """
        assert _run(PLUS_OR_MINUS) == ""


class TestLiteralBase:
    """The wiki's conflicting literal-base examples, pinned both ways.

    Three examples only work read as decimal and two only as binary; a
    pure binary reading is refused outright, since four of the five
    contain literals with digits outside 0-1 (PlusOrMinus's own
    ``Integer(0, 255, 255, 0)`` among them).  Decimal wins the remaining
    tie, so these two examples are declared wrong.
    """

    def test_the_decimal_examples_are_byte_exact(self) -> None:
        assert _run(HELLO) == "Hello, World!\r\n"
        assert _run(TRUTH_MACHINE, "0\n") == "0"
        # The cat's own terminator is unreachable under line-based input
        # (see TestWikiExamples); its decimal literals are what is pinned
        # here -- 100 as an array length and 13/10 as the CRLF it echoes.
        assert (
            _run(CAT.replace("While c ^ 10 Do", "While c Do"), "h\ni\n\n") == "hi\r\n"
        )

    def test_the_binary_authored_example_is_declared_wrong(self) -> None:
        """As written it prints mojibake, not the ``0110`` its comments claim.

        ``110000`` read as decimal is 110000, and ``charPut`` prints
        ``value % 256`` -- 176, not the 48 the author meant.
        """
        assert _run(DEPENDENCY) == "°±±°"

    def test_rebasing_that_example_gives_the_wikis_stated_output(self) -> None:
        """Its *logic* is right; only the base its literals were written in.

        Converting the literals binary -> decimal and changing nothing
        else yields exactly the ``0``/``1``/``1``/``0`` the wiki's inline
        comments claim, which is what makes this an author-side base error
        rather than an interpreter bug.
        """
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

    def test_a_dependency_function_is_callable(self) -> None:
        assert _run(DEPENDENCY_REBASED) == "0110"

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

    def test_empty_input_line_reads_as_zero(self) -> None:
        """The package-wide blank-line convention, which beats the wiki.

        The wiki says empty input returns a newline; every interpreter
        here reads a blank line as 0 instead, and
        ``tests/interpreters/test_input_convention.py`` pins that across
        the whole package, so the shared convention wins.
        """
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
        assert _run(code, "\n") == "\x00"


class TestErrors:
    def test_unbalanced_block_is_malformed(self) -> None:
        """A block that is never closed runs the parser off the end.

        The message is whichever check the parser reaches first -- an
        unbalanced ``{`` here, a bad token where a partial close leaves the
        cursor mid-declaration -- so both cases are pinned as ValueError
        rather than by one wording.
        """
        with pytest.raises(ValueError, match="unbalanced"):
            _run("Package : IO {\n  Integer main {\n    charPut(65);\n")
        # A partial close leaves the cursor mid-declaration, so the first
        # check the parser reaches is the datatype one.
        with pytest.raises(ValueError, match="unknown datatype"):
            _run("Package : IO {\n  Integer main {\n    0;\n} p;")

    def test_a_program_with_no_entry_is_malformed(self) -> None:
        with pytest.raises(ValueError, match="no parameterless entry"):
            _run("Dependency {\n  Integer f : Integer a {\n    a;\n  }\n} d;")

    def test_unbounded_recursion_grows_frames_without_crashing(self) -> None:
        """No depth ceiling: frames grow on the heap, not Python's stack.

        There was a ceiling here, and it never fired -- the count restarted
        at every call and the value stood above the ~198 language depth 5
        Python frames per call allowed, so a self-calling program raised
        ``RecursionError``.  Framing calls removes the cause rather than
        retuning the number: recursion no longer touches Python's stack at
        all.  Such a program revisits no state, so nothing can prove it
        halts and the wall-clock ``timeout`` is the backstop, as in
        ``grapheme.py``.  What is asserted is that it stays *steppable*.
        """
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
        """The reason calls are framed rather than evaluated inline.

        A ``While`` in a called function used to run to completion inside
        the caller's single ``step()``, so an endless one hung with the
        frame stack never observed growing and nothing for the cycle
        detector to see.  Framed, every lap reaches ``snapshot`` and the
        repeat proves the hang.

        The loop holds its state fixed -- no read, no counter -- because a
        state that grows is the separate class only the timeout covers.
        """
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

    def test_garbage_is_malformed(self) -> None:
        with pytest.raises(ValueError, match="not Packlang tokens"):
            _run("~~~ not packlang @@@")

    def test_undefined_variable_halts(self) -> None:
        with pytest.raises(HaltError, match="undefined variable"):
            _run("Package : IO {\n  Integer main {\n    INCR nope;\n    0;\n  }\n} p;")

    def test_undefined_function_halts(self) -> None:
        with pytest.raises(HaltError, match="undefined function"):
            _run("Package : IO {\n  Integer main {\n    nope(1);\n    0;\n  }\n} p;")

    def test_calling_an_undeclared_dependency_halts(self) -> None:
        """The wiki grants access only to a package's declared dependencies.

        The function exists and is callable -- the positive control below
        is the same program with the dependency declared -- so this pins
        the visibility rule rather than a name lookup.
        """
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
        follows the chain rather than stopping one level down."""
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
        """A callee's ``charPut`` reaches the shell, in call order.

        This was refused, on the rationale that a call was evaluated
        inside a statement and so had no point at which the shell could
        perform its ports.  Framing calls removed that rationale: a
        callee's statements are stepped like any other, so the same shell
        performs its IO.  ``A`` precedes the caller's own output because
        the argument is evaluated before ``charPut`` runs.
        """
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

    def test_reading_past_the_input_raises_eof(self) -> None:
        code = """
Package : IO {
  Char c;
  Integer main {
    charGet(c);
    0;
  }
} p;
"""
        with pytest.raises(EOFError):
            run_program(run, code, "", suppress_eof=False)

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

    def test_registered_text_generator_round_trips(self) -> None:
        program = esolangs.generate("Packlang", "hi")
        assert esolangs.run("Packlang", program) == "hi"


class TestTextGenerator:
    @pytest.mark.parametrize(
        "text",
        [
            "",
            "A",
            "Hello, World!",
            "line\nbreak",
            "tab\there",
            "".join(chr(c) for c in range(32, 127)),
        ],
    )
    def test_generated_program_prints_the_text(self, text: str) -> None:
        assert _run(packlang_text(text)) == text

    def test_non_ascii_is_refused(self) -> None:
        with pytest.raises(ValueError, match="ASCII"):
            packlang_text("é")


def _boolean_rows(table: str, n: int) -> list[str]:
    """Run the generated program on every row and collect what it printed."""
    program = packlang_boolean(table)
    out = []
    for row in range(2**n):
        bits = [(row >> (n - 1 - i)) & 1 for i in range(n)]
        out.append(_run(program, "".join(f"{b}\n" for b in bits)))
    return out


class TestBooleanGenerator:
    """Executed over complete truth tables, not inspected as source."""

    @pytest.mark.parametrize("n", [1, 2, 3])
    def test_every_table_at_this_arity(self, n: int) -> None:
        """Exhaustive: all ``2**(2**n)`` tables, each over all ``2**n`` rows."""
        for value in range(2 ** (2**n)):
            table = bin(value)[2:].zfill(2**n)
            assert _boolean_rows(table, n) == list(table), table

    @pytest.mark.parametrize(
        "table",
        [
            "0" * 16,
            "1" * 16,
            "0110100110010110",  # parity at n == 4
            "1000100010001000",
            "0000000000000001",  # AND, the densest ANF at this arity
        ],
    )
    def test_four_input_tables(self, table: str) -> None:
        assert _boolean_rows(table, 4) == list(table)

    @pytest.mark.slow
    def test_a_five_input_table(self) -> None:
        table = "".join(str(bin(r).count("1") % 2) for r in range(32))
        assert _boolean_rows(table, 5) == list(table)

    @pytest.mark.parametrize("n", [1, 2, 3, 4])
    def test_a_constant_table_still_reads_every_input(self, n: int) -> None:
        """The read-count contract: the reads are the interface.

        A constant table has no ANF terms at all, so this is the case
        where skipping the reads would be tempting and wrong.
        """
        for table in ("0" * 2**n, "1" * 2**n):
            io = ScriptedIO("0\n" * 8)
            run(packlang_boolean(table), io)
            assert io.position() == n, table

    def test_the_construction_is_the_anf(self) -> None:
        """The term count is the ANF's, and each term's depth its degree.

        ``INCR acc`` appears once per nonzero coefficient, so it counts
        *terms*; ``If`` counts the guards, which is the sum of the terms'
        degrees.  The two separate the shapes: AND is one term of degree
        n, parity is n terms of degree 1, and both have the same number of
        rows -- so a construction that had collapsed into a minterm sum
        would show here even though every output stayed correct.
        """
        # x0 & x1: one term, degree 2.
        assert packlang_boolean("0001").count("INCR acc") == 1
        assert packlang_boolean("0001").count("If ") == 2
        # x0 ^ x1: two terms, degree 1 each.
        assert packlang_boolean("0110").count("INCR acc") == 2
        assert packlang_boolean("0110").count("If ") == 2
        # 3-way parity: three terms, degree 1 each.
        assert packlang_boolean("01101001").count("INCR acc") == 3
        assert packlang_boolean("01101001").count("If ") == 3
        # A constant table has only the degree-zero coefficient: an
        # unguarded INCR, or none at all.
        assert packlang_boolean("1111").count("If ") == 0
        assert packlang_boolean("1111").count("INCR acc") == 1
        assert packlang_boolean("0000").count("INCR acc") == 0

    def test_a_one_entry_table_is_refused(self) -> None:
        with pytest.raises(ValueError, match="at least one input"):
            packlang_boolean("0")


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
