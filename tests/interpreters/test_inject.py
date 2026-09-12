r"""Unit tests for the Inject interpreter."""

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

# A corrected truth machine:.
# interpreter's module.
# forever on "1".
# because that module pulls in.
# not inline -- a module-level.
# any mutant runs.
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
    r"""Run ``program`` and return everything it printed."""
    io = ScriptedIO(stdin)
    run(program, io)
    return io.getvalue()


def _machine(program: Any) -> _Machine:
    return _Machine(program, ScriptedIO("0\n"))


class TestWikiExamples:
    def test_hello_world(self) -> None:
        r"""The block is sent, then skipped over rather than executed."""
        assert _run(HELLO_WORLD) == "Hello, world!\n"

    def test_cat_echoes_until_an_empty_line(self) -> None:
        r"""Each line is echoed; the empty line empties the block and stops."""
        assert _run(CAT, "ab\ncd\n\n") == "ab\ncd\n"

    def test_cat_without_a_terminating_blank_line_reads_past_its_input(self) -> None:
        r"""Input exhaustion is EOFError, distinct from the empty-line halt."""
        with pytest.raises(EOFError):
            _run(CAT, "ab\n")

    def test_wiki_truth_machine_is_inverted(self) -> None:
        r"""The wiki's truth machine halts on 1 and loops on 0 -- backwards."""
        from esolangs.vm import run_until_halt_or_cycle

        # On "1" it halts after a.
        assert _run(WIKI_TRUTH_MACHINE, "1\n") == "1\n"

        # On "0" it loops forever --.
        # revisits a state, so it is.
        io = ScriptedIO("0\n")
        assert not run_until_halt_or_cycle(_Machine(WIKI_TRUTH_MACHINE, io))


class TestCorrectedTruthMachine:
    def test_zero_prints_and_halts(self) -> None:
        assert _run(INJECT_TRUTH_MACHINE, "0\n") == "0\n"

    def test_one_prints_and_loops(self) -> None:
        r"""The 1 branch loops, and revisits a state so the loop is proven."""
        from esolangs.vm import run_until_halt_or_cycle

        io = ScriptedIO("1\n")
        assert not run_until_halt_or_cycle(_Machine(INJECT_TRUTH_MACHINE, io))
        assert io.getvalue() == "1\n"


class TestCommands:
    def test_inject_substitutes_by_regex(self) -> None:
        r"""``inject`` rewrites a block through a regular expression."""
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
        r"""Only the first slash separates the pattern from the replacement."""
        program = "\n".join(
            ["inject data=b/x/y", "send data", "skip", "data;", "ab", "data;"]
        )
        assert _run(program) == "ax/y\n"

    def test_inject_backreference(self) -> None:
        r"""A group reference in the replacement is a real backreference."""
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
        r"""A rewrite before the pointer moves the pointer with the text."""
        program = "\n".join(["data;", "data;", "readto data", "send data"])
        assert _run(program, "x\ny\n") == "x\n"

    def test_a_rewrite_does_not_move_its_own_opening_delimiter(self) -> None:
        r"""Only positions strictly *after* the rewritten block's start move."""
        program = "\n".join(["d;", "d;", "readto d", "send d", "e;", "x", "e;"])
        assert _run(program, "A\nB\n") == "A\n"

    def test_skipif_does_not_fire_on_an_empty_block(self) -> None:
        r"""A false guard falls through to the next line instead of jumping."""
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
        r"""With two blocks enclosing the pointer, the inner one wins."""
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
        # The pointer sits in both.
        # which re-runs "send b" only.
        machine = _Machine(program, ScriptedIO(""))
        for _ in range(24):
            if machine.halted:
                break
            machine.step()
        assert machine.io.getvalue().startswith("A\nB\nB\n"), machine.io.getvalue()

    def test_overlapping_blocks_pick_the_shorter_span(self) -> None:
        r"""``_innermost`` ranks by span width, not by declaration order."""
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
        # The ``skip`` is inside both;.
        # the first ``send``, so the.
        # reaches the second one.
        # same on output, so the.
        # to the jump and read the.
        machine = _Machine(program, ScriptedIO(""))
        while machine.lines[machine.ind].strip() != "skip":
            machine.step()
        machine.step()
        assert machine.ind == 1, "clause 2 targets the narrow block's label"

    def test_skip_clause_three_exits(self) -> None:
        r"""A bare ``skip`` outside every block ends the program."""
        program = "\n".join(["skip", "send data", "data;", "unreachable", "data;"])
        assert _run(program) == ""

    def test_skip_before_a_non_label_line_exits(self) -> None:
        r"""``skip`` whose next line is a command, not a label, is clause 3."""
        assert _run("skip\nsend d\nd;\nx\nd;") == ""

    def test_skip_as_the_final_line_exits(self) -> None:
        r"""There is no next line to inspect, so clause 3 ends the program."""
        assert _run("skip") == ""

    def test_a_non_command_line_is_data(self) -> None:
        r"""A line whose first word is not a command executes as a no-op."""
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


class TestStateView(StateViewContract):
    machine = staticmethod(_machine)
    # Inject's cursor is a *line*.
    # block's line count, so the.
    state_views: ClassVar[tuple[str, ...]] = ("ip", "memory")
    # HELLO_WORLD moves only the.
    viewing_program: ClassVar[list[str]] = [
        "data;",
        "data;",
        "readto data",
        "send data",
    ]


class TestCycle(CycleContract):
    machine = staticmethod(_machine)
    halting_program: ClassVar[str] = HELLO_WORLD
    # The corrected truth machine's.
    # with the input already.
    looping_program: ClassVar[str] = "\n".join(
        ["loop;", "send data", "skip", "loop;", "data;", "x", "data;"]
    )


def test_main_block_runs_a_file(tmp_path: Any, capsys: Any) -> None:
    r"""The ``__main__`` entry point reads a program file and runs it."""
    path = tmp_path / "hello.inj"
    path.write_text(HELLO_WORLD, encoding="utf-8")
    run(path.read_text(encoding="utf-8"), IO())
    assert capsys.readouterr().out == "Hello, world!\n"
