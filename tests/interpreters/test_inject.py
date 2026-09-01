"""Unit tests for the Inject interpreter.

The three wiki examples are the ground truth here, and one of them is
*wrong on its own terms*: the truth machine's two branches are exchanged
under the wiki's own prose.  ``TestWikiExamples`` runs all three and
asserts what each actually does, with the discrepancy named rather than
smoothed over, and ``TestCorrectedTruthMachine`` carries a program that
behaves the way a truth machine is supposed to.
"""

from typing import Any, ClassVar

import pytest

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import IO, ScriptedIO
from esolangs.interpreters.other.inject import _Machine, run
from tests.interpreters.contract import CycleContract, SnapshotContract
from tests.raises import raises_message

HELLO_WORLD = "\n".join(
    [
        "send data",
        "skip",
        "data;",
        "Hello, world!",
        "data;",
    ]
)

WIKI_TRUTH_MACHINE = "\n".join(
    [
        "readto data",
        "loop;",
        "send data",
        "skipq data 0",
        "loop;",
        "skip",
        "data;",
        "data;",
        "0;",
        "0",
        "0;",
    ]
)

# A corrected truth machine: the wiki's own is inverted (see the
# interpreter's module docstring).  Halts on "0" after printing it, loops
# forever on "1".  Defined here rather than imported from ``tests.samples``
# because that module pulls in the registry, which the mutation bundle does
# not inline -- a module-level import of it fails collection there before
# any mutant runs.  ``tests.samples`` imports this name instead.
INJECT_TRUTH_MACHINE = "\n".join(
    [
        "readto data",
        "skipq data 0",
        "loop;",
        "send data",
        "skip",
        "loop;",
        "send data",
        "skip",
        "data;",
        "data;",
        "0;",
        "0",
        "0;",
    ]
)

CAT = "\n".join(
    [
        "loop;",
        "readto data",
        "send data",
        "skipif data",
        "loop;",
        "data;",
        "data;",
    ]
)


def _run(program: str, stdin: str = "") -> str:
    """Run ``program`` and return everything it printed."""
    io = ScriptedIO(stdin)
    run(program, io)
    return io.getvalue()


def _machine(program: Any) -> _Machine:
    return _Machine(program, ScriptedIO("0\n"))


class TestWikiExamples:
    def test_hello_world(self) -> None:
        """The block is sent, then skipped over rather than executed."""
        assert _run(HELLO_WORLD) == "Hello, world!\n"

    def test_cat_echoes_until_an_empty_line(self) -> None:
        """Each line is echoed; the empty line empties the block and stops.

        This is the example that pins two readings: ``send`` terminates
        every line it writes (otherwise the echo would run together), and
        an empty input line stores an *empty* block, so ``skipif``'s "at
        least one line" fails and the loop ends.
        """
        assert _run(CAT, "ab\ncd\n\n") == "ab\ncd\n"

    def test_cat_without_a_terminating_blank_line_reads_past_its_input(self) -> None:
        """Input exhaustion is EOFError, distinct from the empty-line halt."""
        with pytest.raises(EOFError):
            _run(CAT, "ab\n")

    def test_wiki_truth_machine_is_inverted(self) -> None:
        """The wiki's truth machine halts on 1 and loops on 0 -- backwards.

        A truth machine prints its input, then halts on 0 and loops on 1.
        This program does the opposite, and the wiki's own prose is why:
        ``skipq data 0`` fires exactly when the input *is* ``0``, the next
        line (``loop;``) closes rather than opens a block, so ``skip``'s
        first clause does not apply and its second loops back.  The prose
        is kept and the example treated as the error, because ``skipif`` is
        specified with the identical "only executes if" wording and the cat
        example depends on that wording being literal.
        """
        from esolangs.vm import run_until_halt_or_cycle

        # On "1" it halts after a single print -- the 0 case's behaviour.
        assert _run(WIKI_TRUTH_MACHINE, "1\n") == "1\n"

        # On "0" it loops forever -- the 1 case's behaviour -- and the loop
        # revisits a state, so it is provable rather than merely slow.
        io = ScriptedIO("0\n")
        assert not run_until_halt_or_cycle(_Machine(WIKI_TRUTH_MACHINE, io))


class TestCorrectedTruthMachine:
    def test_zero_prints_and_halts(self) -> None:
        assert _run(INJECT_TRUTH_MACHINE, "0\n") == "0\n"

    def test_one_prints_and_loops(self) -> None:
        """The 1 branch loops, and revisits a state so the loop is proven."""
        from esolangs.vm import run_until_halt_or_cycle

        io = ScriptedIO("1\n")
        assert not run_until_halt_or_cycle(_Machine(INJECT_TRUTH_MACHINE, io))
        assert io.getvalue() == "1\n"


class TestCommands:
    def test_inject_substitutes_by_regex(self) -> None:
        """``inject`` rewrites a block through a regular expression."""
        program = "\n".join(
            [
                "inject data=l+/L",
                "send data",
                "skip",
                "data;",
                "hello",
                "data;",
            ]
        )
        assert _run(program) == "heLo\n"

    def test_inject_replacement_may_contain_slashes(self) -> None:
        """Only the first slash separates the pattern from the replacement."""
        program = "\n".join(
            ["inject data=b/x/y", "send data", "skip", "data;", "ab", "data;"]
        )
        assert _run(program) == "ax/y\n"

    def test_inject_backreference(self) -> None:
        """A group reference in the replacement is a real backreference.

        Spelled with a raw string in the source: ``"\\1"`` written
        non-raw is the character ``chr(1)``, which substitutes silently and
        wrongly.
        """
        program = "\n".join(
            [
                r"inject data=(a)(b)/\2\1",
                "send data",
                "skip",
                "data;",
                "ab",
                "data;",
            ]
        )
        assert _run(program) == "ba\n"

    def test_invalid_regex_is_a_halt_error(self) -> None:
        program = "\n".join(
            ["inject data=(/x", "send data", "skip", "data;", "a", "data;"]
        )
        with raises_message(HaltError, "invalid regex: ("):
            _run(program)

    def test_readto_overwrites_the_block(self) -> None:
        program = "\n".join(
            ["readto data", "send data", "skip", "data;", "old", "data;"]
        )
        assert _run(program, "new\n") == "new\n"

    def test_readto_into_an_earlier_block_keeps_the_pointer_on_its_line(self) -> None:
        """A rewrite before the pointer moves the pointer with the text.

        The program text is also the code being executed, so growing an
        *earlier* block pushes every later line down -- the currently
        executing one included.  Without that shift the pointer would be
        left one line short and re-run the ``readto``, consuming a second
        line of input and never advancing.  The block here starts empty and
        gains a line, which is exactly the boolean generator's shape.
        """
        program = "\n".join(["data;", "data;", "readto data", "send data"])
        assert _run(program, "x\ny\n") == "x\n"

    def test_skipif_does_not_fire_on_an_empty_block(self) -> None:
        """A false guard falls through to the next line instead of jumping."""
        program = "\n".join(
            [
                "empty;",
                "empty;",
                "skipif empty",
                "seen;",
                "send mark",
                "seen;",
                "skip",
                "mark;",
                "here",
                "mark;",
            ]
        )
        assert _run(program) == "here\n"

    def test_skip_clause_three_exits(self) -> None:
        """A bare ``skip`` outside every block ends the program."""
        program = "\n".join(["skip", "send data", "data;", "unreachable", "data;"])
        assert _run(program) == ""

    def test_skip_before_a_non_label_line_exits(self) -> None:
        """``skip`` whose next line is a command, not a label, is clause 3.

        The first clause asks whether the *next* line opens a block; a
        plain command answers no, so at top level the program exits rather
        than jumping.  Distinct from the case where ``skip`` is the final
        line and there is no next line at all.
        """
        assert _run("skip\nsend d\nd;\nx\nd;") == ""

    def test_skip_as_the_final_line_exits(self) -> None:
        """There is no next line to inspect, so clause 3 ends the program."""
        assert _run("skip") == ""

    def test_a_non_command_line_is_data(self) -> None:
        """A line whose first word is not a command executes as a no-op."""
        assert _run("not a command\nsend d\nskip\nd;\nx\nd;") == "x\n"


class TestMalformed:
    def test_a_third_occurrence_of_a_label_is_rejected(self) -> None:
        with raises_message(ValueError, "label written more than twice: a"):
            _run("a;\na;\na;")

    def test_an_unclosed_block_is_rejected(self) -> None:
        with raises_message(ValueError, "unclosed label-block: a"):
            _run("a;\nsend a")

    def test_an_unknown_label_is_rejected(self) -> None:
        with raises_message(ValueError, "unknown label: nowhere"):
            _run("send nowhere")

    def test_skip_takes_no_argument(self) -> None:
        with raises_message(ValueError, "skip takes no argument: skip please"):
            _run("skip please")

    def test_skipq_needs_two_labels(self) -> None:
        with raises_message(ValueError, "skipq takes two labels: skipq only"):
            _run("skipq only")

    def test_inject_needs_a_regex(self) -> None:
        with raises_message(ValueError, "inject needs a label and a regex: data"):
            _run("inject data")

    def test_inject_needs_a_replacement(self) -> None:
        with raises_message(ValueError, "inject needs a replacement: data=x"):
            _run("inject data=x")

    def test_an_empty_program_halts(self) -> None:
        assert _run("") == ""


class TestSnapshot(SnapshotContract):
    machine = staticmethod(_machine)
    stepping_program: ClassVar[str] = INJECT_TRUTH_MACHINE


class TestCycle(CycleContract):
    machine = staticmethod(_machine)
    halting_program: ClassVar[str] = HELLO_WORLD
    # The corrected truth machine's "1" branch: it re-enters the loop block
    # with the input already consumed, so the state repeats exactly.
    looping_program: ClassVar[str] = "\n".join(
        ["loop;", "send data", "skip", "loop;", "data;", "x", "data;"]
    )


def test_main_block_runs_a_file(tmp_path: Any, capsys: Any) -> None:
    """The ``__main__`` entry point reads a program file and runs it."""
    path = tmp_path / "hello.inj"
    path.write_text(HELLO_WORLD, encoding="utf-8")
    run(path.read_text(encoding="utf-8"), IO())
    assert capsys.readouterr().out == "Hello, world!\n"
