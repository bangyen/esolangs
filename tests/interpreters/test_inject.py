"""Unit tests for the Inject interpreter."""

from functools import partial
from typing import Any, ClassVar

import pytest

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import IO, ScriptedIO
from esolangs.interpreters.other.inject import _Machine, run
from tests.interpreters.contract import (
    CycleContract,
    SnapshotContract,
    StateViewContract,
)
from tests.interpreters.runner import run_program
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


_run = partial(run_program, run, suppress_eof=False)


def _machine(program: Any) -> _Machine:
    return _Machine(program, ScriptedIO("0\n"))


class TestWikiExamples:
    def test_hello_world(self) -> None:
        """The block is sent, then skipped over rather than executed."""
        assert _run(HELLO_WORLD) == "Hello, world!\n"

    def test_cat_echoes_until_an_empty_line(self) -> None:
        """Each line is echoed; the empty line empties the block and stops."""
        assert _run(CAT, "ab\ncd\n\n") == "ab\ncd\n"

    def test_cat_without_a_terminating_blank_line_reads_past_its_input(self) -> None:
        """Input exhaustion is EOFError, distinct from the empty-line halt."""
        with pytest.raises(EOFError):
            _run(CAT, "ab\n")

    def test_wiki_truth_machine_is_inverted(self) -> None:
        """The wiki's truth machine halts on 1 and loops on 0 -- backwards."""
        from esolangs.vm import run_until_halt_or_cycle

        # On "1" it halts after a single print -- the 0 case's behaviour.
        assert _run(WIKI_TRUTH_MACHINE, "1\n") == "1\n"

        # On "0" it loops forever -- the 1 case's behaviour -- and the loop
        # revisits a state, so it is provable rather than merely slow.
        io = ScriptedIO("0\n")
        assert not run_until_halt_or_cycle(_Machine(WIKI_TRUTH_MACHINE, io))


class TestCorrectedTruthMachine:
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

    def test_inject_backreference(self) -> None:
        """A group reference in the replacement is a real backreference."""
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

    def test_a_rewrite_does_not_move_its_own_opening_delimiter(self) -> None:
        """Only positions strictly *after* the rewritten block's start move."""
        program = "\n".join(["d;", "d;", "readto d", "send d", "e;", "x", "e;"])
        assert _run(program, "A\nB\n") == "A\n"

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

    def test_clause_two_returns_to_the_innermost_block(self) -> None:
        """With two blocks enclosing the pointer, the inner one wins."""
        program = "\n".join(
            [
                "outer;",
                "send a",
                "inner;",
                "send b",
                "skipif empty",
                "skip",
                "inner;",
                "outer;",
                "a;",
                "A",
                "a;",
                "b;",
                "B",
                "b;",
                "empty;",
                "empty;",
            ]
        )
        # The pointer sits in both blocks; ``skip`` returns to ``inner``,
        # which re-runs "send b" only -- never "send a" a second time.
        machine = _Machine(program, ScriptedIO(""))
        for _ in range(24):
            if machine.halted:
                break
            machine.step()
        assert machine.io.getvalue().startswith("A\nB\nB\n"), machine.io.getvalue()

    def test_overlapping_blocks_pick_the_shorter_span(self) -> None:
        """``_innermost`` ranks by span width, not by declaration order."""
        program = "\n".join(
            [
                "wide;",
                "narrow;",
                "send mark",
                "skip",
                "narrow;",
                "send mark",
                "wide;",
                "mark;",
                "M",
                "mark;",
            ]
        )
        # The ``skip`` is inside both; returning to ``narrow`` re-runs only
        # the first ``send``, so the output is a stream of M and never
        # reaches the second one.  Returning to ``wide`` would look the
        # same on output, so the landing line is what separates them: step
        # to the jump and read the pointer.
        machine = _Machine(program, ScriptedIO(""))
        while machine.lines[machine.ind].strip() != "skip":
            machine.step()
        machine.step()
        assert machine.ind == 1, "clause 2 targets the narrow block's label"

    def test_skip_clause_three_exits(self) -> None:
        """A bare ``skip`` outside every block ends the program."""
        program = "\n".join(["skip", "send data", "data;", "unreachable", "data;"])
        assert _run(program) == ""

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

    def test_inject_needs_a_regex(self) -> None:
        with raises_message(ValueError, "inject needs a label and a regex: data"):
            _run("inject data")


class TestSnapshot(SnapshotContract):
    machine = staticmethod(_machine)
    stepping_program: ClassVar[str] = INJECT_TRUTH_MACHINE


class TestStateView(StateViewContract):
    machine = staticmethod(_machine)
    # Inject's cursor is a *line* index and its memory is each labelled
    # block's line count, so the two are different shapes over one program.
    state_views: ClassVar[tuple[str, ...]] = ("ind", "memory")
    # HELLO_WORLD moves only the cursor; this one writes the store too.
    viewing_program: ClassVar[list[str]] = [
        "data;",
        "data;",
        "readto data",
        "send data",
    ]


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


def test_a_malformed_replacement_is_a_halt() -> None:
    """``\\2`` names a missing group; re's error becomes HaltError."""
    program = "inject data=a/\\2\nsend data\nskip\ndata;\na\ndata;"
    with pytest.raises(HaltError, match="invalid replacement"):
        run(program, ScriptedIO(""))


def test_a_rewrite_cannot_erase_a_nested_block_s_delimiters() -> None:
    """Anchors are fixed at parse; ``send in`` once printed ``data;``."""
    program = "readto data\nsend in\nskip\ndata;\nin;\nx\nin;\ndata;"
    with pytest.raises(HaltError, match="another block's delimiters"):
        run(program, ScriptedIO("q\n"))


def test_skip_as_the_last_line_exits() -> None:
    """No next line to be a label: the outermost ``skip`` ends the program."""
    assert _run("send d\nd;\nx\nd;\nskip") == "x\n"


def test_inject_needs_a_replacement_and_skip_forms_are_checked() -> None:
    with pytest.raises(ValueError, match="inject needs a replacement: d=x"):
        _run("d;\nd;\ninject d=x")
    with pytest.raises(ValueError, match="skip takes no argument"):
        _run("skip now")
    with pytest.raises(ValueError, match="skipq takes two labels"):
        _run("a;\na;\nskipq a")


def test_a_rewrite_cannot_move_the_pointer_before_the_program() -> None:
    """An empty ``readto`` inside its own block deletes lines around the pointer."""
    program = "a;\nreadto a\nx\ny\na;"
    with pytest.raises(HaltError, match="before the program"):
        run(program, ScriptedIO("\n"))
