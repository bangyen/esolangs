"""Unit tests for the Factor interpreter."""

import pytest

from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.tape_based.factor import decode, run

# The wiki's published programs, decoded from their prime factorizations.
CAT = 310861643  # 17 * 29 * 71 * 83 * 107 -> ,[.,]
TRUTH = int(
    "233915737501853959241591127266540514014498928384925170744745"
    "371936977107366667491950094954248611898080571424768"
)


def run_program(number: int, stdin: str = "") -> str:
    io = ScriptedIO(stdin)
    run(str(number), io)
    return io.getvalue()


class TestDecode:
    def test_repeated_instruction(self) -> None:
        """9 = 3^2 decodes to two increments."""
        assert decode(9) == "++"

    def test_instructions_sort_ascending(self) -> None:
        """Factors sort ascending, so the residues map to that order."""
        assert decode(3 * 23) == "+>"  # 3 -> '+', 23 -> '>'
        assert decode(23 * 3) == "+>"  # same multiset, same order

    def test_wiki_cat(self) -> None:
        """The wiki's cat number decodes to ,[.,]."""
        assert decode(CAT) == ",[.,]"

    def test_wiki_truth_machine(self) -> None:
        """The wiki's polyglot truth machine decodes to the dbfi program."""
        assert decode(TRUTH) == "<" * 18 + ",[>+>+<<-]++++++[>--------<-]>[>.<]>."

    def test_zero_and_one(self) -> None:
        """1 has no prime factors; 0's factor 0 has residue 0, both ignored."""
        assert decode(1) == ""
        assert decode(0) == ""


class TestRun:
    def test_empty_program(self) -> None:
        assert run_program(1) == ""

    def test_comment_characters_ignored(self) -> None:
        """Non-digits are comments: 'Hi 15!' is just 15."""
        io = ScriptedIO()
        run("Hi 15!", io)
        assert io.getvalue() == "\x01"

    def test_single_instruction(self) -> None:
        """15 = 3*5 decodes to '+.' which prints chr(1)."""
        assert run_program(15) == "\x01"

    def test_print_letter(self) -> None:
        """3^65 * 5 decodes to 65 increments then a print (ASCII 'A')."""
        assert run_program(3**65 * 5) == "A"

    def test_wiki_cat_echoes(self) -> None:
        """The cat program echoes input, then EOF raises like brainfuck."""
        io = ScriptedIO("h\ni")
        with pytest.raises(EOFError):
            run(str(CAT), io)
        assert io.getvalue() == "hi"

    def test_wiki_truth_machine_zero(self) -> None:
        """Input 0 prints 0 and halts."""
        assert run_program(TRUTH, "0") == "0"

    def test_unbalanced_brackets_rejected(self) -> None:
        """7 decodes to '[' alone, which is malformed."""
        with pytest.raises(ValueError, match="unmatched"):
            run_program(7)


class TestStepMachine:
    def test_a_program_with_no_digits_is_the_number_one(self) -> None:
        """No digits means 1, which factors to nothing and runs no commands.

        ``test_empty_program`` and ``test_comment_characters_ignored``
        both cover the digit-free case, but only through the output: 1 and
        2 decode to ``''`` and ``'<'``, and a lone ``<`` prints nothing
        either, so the empty string does not say which number was used.
        The decoded program does.
        """
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.factor import _Machine

        assert _Machine("", ScriptedIO()).bf.code == ""
        assert _Machine("no digits here", ScriptedIO()).bf.code == ""

    def test_step_tracks_the_decoded_tape(self) -> None:
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.factor import _Machine

        machine = _Machine("15", ScriptedIO())
        assert (machine.bf.ind, list(machine.bf.tape)) == (0, [0])
        machine.step()  # + increments the cell
        assert list(machine.bf.tape) == [1]
        machine.step()  # . prints it
        assert machine.io.getvalue() == "\x01"
        assert machine.halted

    def test_snapshot_is_hashable(self) -> None:
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.factor import _Machine

        assert hash(_Machine("15", ScriptedIO()).snapshot()) is not None

    def test_halting_program_is_detected(self) -> None:
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.factor import _Machine
        from esolangs.vm import run_until_halt_or_cycle

        assert run_until_halt_or_cycle(_Machine("15", ScriptedIO())) is True

    def test_looping_decoded_program_is_detected_as_a_cycle(self) -> None:
        """3567 = 3 * 29 * 41 decodes to +[] (residues 3, 7, 8)."""
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.factor import _Machine
        from esolangs.vm import run_until_halt_or_cycle

        assert run_until_halt_or_cycle(_Machine("3567", ScriptedIO())) is False
