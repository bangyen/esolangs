"""Unit tests for the Interprogck8 generators, boolean and text.

Every claim here is made by running the emitted program: the tree is
routed by ``DownAccLines``, whose off-by-one is the whole construction, so
reading the source proves nothing about where a branch lands.
"""

import pytest

from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.register_based.interprogck8 import _Machine, run
from esolangs.tools import text as gen
from esolangs.tools.boolean import interprogck8
from esolangs.tools.boolean.interprogck8 import (
    _PASSES,
    _REACH,
    _check,
    _emit,
    _index,
    _Jump,
    _relay,
    _resolve,
    _set_acc,
)
from esolangs.vm import run_until_halt_or_cycle
from tests.tools.boolean_runners import run_interprogck8


def _tables(n: int) -> list[str]:
    return [bin(v)[2:].zfill(2**n) for v in range(2 ** (2**n))]


class TestExhaustive:
    @pytest.mark.parametrize("n", [1, 2, 3])
    def test_every_table_of_every_arity(self, n: int) -> None:
        """All 4, 16 and 256 tables, every row, executed.

        This is the phase-1 gate answered by construction rather than by
        argument: a full decision tree routes through ``DownAccLines``
        alone, and the current-function slot is never touched.
        """
        for table in _tables(n):
            program = interprogck8(table)
            assert "<" not in program, "routing must not use the function slot"
            for row in range(2**n):
                bits = list(bin(row)[2:].zfill(n))
                assert run_interprogck8(program, bits) == table[row], (
                    f"{table} row {row}"
                )


class TestReads:
    @pytest.mark.parametrize("table", ["00000000", "11111111", "01101001"])
    def test_a_folded_table_still_consumes_its_inputs(self, table: str) -> None:
        """A constant subtree drops its branch, not its reads.

        The reads are the interface: leaving a bit unread desynchronises
        whatever runs on the same stream next.
        """
        program = interprogck8(table)
        io = ScriptedIO("0\n1\n1\n")
        machine = _Machine(program.splitlines(), io)
        run_until_halt_or_cycle(machine)
        assert io.position() == 3, "a constant table must still read all three"
        assert io.getvalue() == table[0b011]


class TestRelay:
    """Past n=3 the tree outgrows one hop, so hops chain through rungs."""

    @pytest.mark.parametrize("n", [4, 5])
    def test_a_tree_past_one_hop_still_computes_its_table(self, n: int) -> None:
        """Every row of a table too long to route in single hops.

        This is what the arity cap used to refuse.  The n=5 parity tree is
        2688 lines with crossings of over 1000 against a reach of 255, so
        it only works if the rungs relay -- and a rung that relays to the
        wrong place is a *wrong answer* rather than a refusal, which is why
        the assertion is on the output and not on the program building.
        """
        table = "".join(str(bin(row).count("1") & 1) for row in range(2**n))
        program = interprogck8(table)
        assert "<" not in program, "routing must not use the function slot"
        for row in range(2**n):
            bits = list(bin(row)[2:].zfill(n))
            assert run_interprogck8(program, bits) == table[row], f"n={n} row {row}"

    def test_every_hop_in_a_relayed_program_is_inside_the_reach(self) -> None:
        """The relay leaves no jump the gadget cannot spell.

        The emission pass would raise on one, so this pins the property the
        raise defends rather than re-testing the raise: after routing, every
        distance is within a single ``DownAccLines``.
        """
        parity = "".join(str(bin(row).count("1") & 1) for row in range(32))
        items = _emit(parity, 5)
        for _ in range(_PASSES):
            _resolve(items)
            if not _relay(items):
                break
        starts, labels = _index(items)
        for item, start in zip(items, starts, strict=True):
            if isinstance(item, _Jump):
                distance = labels[item.label] - (start + item.width)
                assert 0 <= distance <= _REACH, f"{item.label} spans {distance}"


class TestJumpChecks:
    """The two guards that keep an over-long jump from being emitted."""

    def test_a_jump_past_the_reach_is_refused(self) -> None:
        with pytest.raises(ValueError, match="spans 300 lines"):
            _check("X", 300, 40)

    def test_a_jump_too_wide_for_its_slot_is_refused(self) -> None:
        """The fixed window is what this protects: it cannot grow."""
        with pytest.raises(ValueError, match="needs 10 lines, has 9"):
            _check("X", 36, 9)


class TestLoader:
    @pytest.mark.parametrize("value", [0, 1, 8, 10, 48, 49, 99, 255])
    def test_set_acc_lands_on_its_target(self, value: int) -> None:
        """Executed, not counted: the loader may count up or overshoot."""
        program = "\n".join([*_set_acc(value), "div"])
        assert run_interprogck8(program, []) == chr(value)

    def test_overshooting_is_taken_when_it_is_shorter(self) -> None:
        """8 costs four lines counting back, nine counting up."""
        assert len(_set_acc(8)) == 4


class TestTextGenerator:
    """The text side, executed: every byte reached by a shortest run."""

    @pytest.mark.parametrize(
        "text", ["a", "Hello World\n", "\x00\xff\n", "The quick brown fox."]
    )
    def test_round_trips(self, text: str) -> None:
        io = ScriptedIO("")
        run(gen.interprogck8(text).splitlines(), io)
        assert io.getvalue() == text

    def test_empty_text_is_an_empty_program(self) -> None:
        assert gen.interprogck8("") == ""

    def test_rejects_non_bytes(self) -> None:
        with pytest.raises(ValueError, match="bytes"):
            gen.interprogck8("\u0100")

    def test_beats_the_wiki_hand_written_hello_world(self) -> None:
        """53 lines against the wiki's 58, and it prints the same text.

        The gain is the *overshoot* spelling: counting down to a target
        with ``@nt`` is shorter than counting up wherever the units digit
        is above five, which the wiki's version never does.
        """
        program = gen.interprogck8("Hello World\n")
        assert len(program.splitlines()) == 53
        io = ScriptedIO("")
        run(program.splitlines(), io)
        assert io.getvalue() == "Hello World\n"
