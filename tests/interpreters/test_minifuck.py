"""Unit tests for the Minifuck interpreter."""

from esolangs.interpreters.tape_based.minifuck import run
from tests.interpreters.contract import (
    CycleContract,
    EmptyProgramContract,
    SnapshotContract,
)
from tests.interpreters.runner import run_program


def run_and_capture(code: str, inputs: list[str] | None = None) -> str:
    return run_program(run, code, "".join(f"{line}\n" for line in inputs or []))


class TestMinifuck:
    def test_cat_program(self) -> None:
        """The canonical cat program echoes its input.

        ``.`` is the whole of the language's I/O, and it has two faces: it
        prints cells 0-7 as one byte, except when those eight cells are
        zero, where it reads a byte of input into them instead.  The cat is
        the shortest program showing both -- its first ``.`` lands on a zero
        window and reads, its second lands on the byte that read left and
        prints it.
        """
        assert run_and_capture("<[<.[<.", inputs=["A"]) == "A"
        assert run_and_capture("<[<.[<.", inputs=["B"]) == "B"

    def test_comment_characters_ignored(self) -> None:
        """Non-command characters are ignored."""
        assert run_and_capture("abc", inputs=["A"]) == ""

    def test_tape_grows_past_the_initial_eight_cells(self) -> None:
        """The tape extends once the pointer nears its end, and . reads 8 cells.

        Every other test stays inside the first few cells, where the tape
        never has to grow: the eight it starts with are enough.  Seven ``[``
        walk the pointer to 7, which already appends a ninth cell, and the
        ``.`` takes it to 8 and appends a tenth.  That ``.`` still prints
        cells 0-7 only -- 0b01111111 -- so the print window stays eight wide
        no matter how long the tape has become.
        """
        assert run_and_capture("[[[[[[[.") == "\x7f"

    def test_an_unlisted_character_is_not_a_command(self) -> None:
        """A character that is neither ``<`` nor ``.`` nor ``[`` does nothing.

        ``test_comment_characters_ignored`` uses ``abc``, and every letter
        in it is outside the command set no matter how that set is spelled.
        A stray ``X`` is the same kind of comment, but it catches a command
        set widened to include it: as a command it would advance the
        pointer and flip a cell, so the byte the following ``.`` prints
        changes.
        """
        assert run_and_capture("X.") == "@"
        assert run_and_capture("X") == ""

    def test_the_skip_flips_the_cell_after_the_pointer(self) -> None:
        """``[`` collapsing to 0 flips ``ptr + 1``, not ``ptr - 1``.

        The cat program exercises this branch only at the origin, where the
        two are hard to tell apart.  Walking out to cell 7 and back with
        ``<`` lands ``[`` on a cell already holding 1, so the flip goes
        1 -> 0 and the skip fires deep in the tape, where the cell it
        touches is unambiguous.

        The trailing ``<.`` is what reads the answer back out.  The ``<`` is
        there to be swallowed -- a collapsing ``[`` skips whatever follows
        it, so a bare ``.`` would be skipped too and print nothing either
        way.  The ``.`` then lands on cell 6 and prints a window whose sixth
        bit says which neighbour the skip flipped: 0b01111011 if it was the
        one after the pointer, 0b01110001 if it was the one before.
        """
        assert run_and_capture("[[[[[[[<<<[<.") == "{"  # 0b01111011

    def test_the_skip_passes_exactly_one_instruction(self) -> None:
        """``[`` that flips a cell to 0 skips one instruction, not two.

        The skip is a cursor bump on top of the one every step does, so
        skipping two lands a whole instruction further on.  It needs a
        program where the difference is reachable: the second ``<`` moves
        the pointer only if it is executed, and the trailing ``.`` turns
        where the pointer ended up into a byte.  Passing one instruction
        leaves it at the origin, so the ``.`` flips cell 1 and prints
        0b01100000; passing two would leave it a cell further right.
        """
        assert run_and_capture("[<[<<.") == "`"  # 0b01100000

    def test_a_read_keeps_the_cell_past_the_print_window(self) -> None:
        """A read replaces cells 0-7 and leaves cell 8 alone, shown in output.

        ``test_a_read_keeps_the_tape_past_the_print_window`` asserts the
        same boundary on the tape directly.  This one forces it through
        ``run``, which takes construction: cell 8 is outside the print
        window, so its value reaches the output by exactly one route -- a
        ``[`` executed at cell 7 lands on cell 8 and branches on the bit it
        finds there.

        So the program is built in four parts.  Eight ``[`` walk the pointer
        out to cell 8, setting cells 1-8 on the way and leaving the 1 that
        has to survive.  ``<<.`` seven times clears cells 7 down to 1, each
        ``.`` landing on the cell below the pointer; the seventh empties the
        window, which is what makes it a read rather than a print.  Six
        ``.`` walk back out to cell 7.  Then ``[`` lands on cell 8: finding
        the 1 still there, it flips it to 0 and skips the final ``.``.  A
        read that had cleared cell 8 would leave a 0, the ``[`` would flip
        it to 1, nothing would be skipped, and that ``.`` would print one
        more byte than it should.
        """
        witness = "[" * 8 + "<<." * 7 + "." * 6 + "[."
        assert run_and_capture(witness, inputs=["A"]) == "~|xp`@aqy}\x7f~"


class TestStepMachine:
    def test_step_tracks_tape_and_cursor(self) -> None:
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.minifuck import _Machine

        machine = _Machine(".", ScriptedIO())
        assert (machine.ind, machine.ptr) == (0, 0)
        machine.step()  # . advances, flips the second cell, prints the byte
        assert machine.io.getvalue() == "@"
        assert machine.halted
        machine.step()  # stepping a halted machine is a no-op
        assert machine.ind == 1

    def test_tape_state_when_the_pointer_runs_deep(self) -> None:
        """The grown tape's exact contents, not just the byte it prints.

        ``test_tape_grows_past_the_initial_eight_cells`` asserts the printed
        byte, which only reads cells 0-7 -- so where the tape *ends* and what
        the appended cells hold went unchecked.  Seven ``[`` leave the
        pointer at 7 on a nine-cell tape: one cell past the pointer, and the
        rest flipped to 1 on the way.
        """
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.minifuck import _Machine

        machine = _Machine("[[[[[[[", ScriptedIO())
        while not machine.halted:
            machine.step()
        assert machine.ptr == 7
        assert machine.tape == [0, 1, 1, 1, 1, 1, 1, 1, 0]

    def test_the_tape_starts_eight_cells_wide(self) -> None:
        """The tape starts eight cells wide, which no output can reveal.

        Every other test looks at the tape after something has run, by
        which point growth has already changed its length -- so the tape
        could start one cell too long and only the untouched trailing zero
        would show it.  Nor would anything else: the length only gates
        growth, growth only ever appends zeros, and a cell past the seventh
        never reaches the print window, so starting wider is invisible
        through ``run``.  That makes this the one assertion here with no
        black-box equivalent -- it pins the representation, not the
        language, and is the only place the width can be checked at all.
        """
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.minifuck import _Machine

        assert _Machine("", ScriptedIO()).tape == [0] * 8

    def test_a_read_keeps_the_tape_past_the_print_window(self) -> None:
        """Reading input replaces cells 0-7 and keeps everything after them.

        The eight bits of the byte are spliced in front of ``tape[8:]``, so
        the boundary is exactly the print window: taking the tail from 9
        instead would silently drop cell 8.  It only shows on a program
        that reads while the tape has already grown past the window, which
        needs the pointer to walk out and the first eight cells to be zero
        again by the time a ``.`` comes round.
        """
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.minifuck import _Machine

        machine = _Machine(".<<[<<<.[<<.<<<..[<[.[.[..", ScriptedIO("ABCDEFGH"))
        while not machine.halted:
            machine.step()
        assert machine.io.getvalue() == "@`p0\x10"
        assert machine.tape == [0, 1, 0, 0, 0, 0, 0, 1, 0]


def _machine(code: object) -> object:
    from esolangs.interpreters.io import ScriptedIO
    from esolangs.interpreters.tape_based.minifuck import _Machine

    return _Machine(code, ScriptedIO())


class TestContract(EmptyProgramContract, SnapshotContract, CycleContract):
    """The shared empty-program shape, with this language's data."""

    run = staticmethod(run_and_capture)
    machine = staticmethod(_machine)
    stepping_program = "."
    halting_program = "."
