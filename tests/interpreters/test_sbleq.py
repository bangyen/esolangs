"""Unit tests for the S*bleq interpreter."""

import pytest

from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.tape_based.sbleq import _Machine, run
from esolangs.interpreters.tape_based.sbleq import _Machine as Sbleq
from esolangs.vm import run_until_halt_or_cycle
from tests.interpreters.contract import SnapshotContract


def run_bounded(program: str, stdin: str = "", store: str = "a") -> str:
    """Run ``program`` to its halt and return its output."""
    io = ScriptedIO(stdin)
    run(program, io, store=store)
    return io.getvalue()


def stepped(
    program: str, stdin: str = "", store: str = "a", steps: int = 200
) -> _Machine:
    """Step ``program`` at most ``steps`` times; S*bleq may not halt."""
    machine = _Machine(program, ScriptedIO(stdin), store=store)
    for _ in range(steps):
        if machine.halted:
            break
        machine.step()
    return machine


class TestSpecialAddresses:
    """The -1 (IP), -2 (input) and -3 (output) addresses, and branch operands."""

    def test_a_branch_address_is_never_negative(self) -> None:
        """``c`` is an address, not an operand port."""
        with pytest.raises(ValueError, match=r"invalid S\*bleq branch address"):
            run_bounded("0 0 -1")

    @pytest.mark.parametrize(
        ("program", "stdin", "expected"),
        [
            # a=-3 outputs mem[6]=65, then 0-0 jumps to mem[5]=9 and halts.
            pytest.param("-3 6 3 0 0 7 65 9", "", "A", id="output_via_a"),
            pytest.param("6 -3 3 0 0 7 66 9", "", "B", id="output_via_b"),
            pytest.param("-2 0 3 0 0 5 9", "A", "", id="input_reads_one_byte"),
            pytest.param("2 -1 3 0 0 5 9", "", "", id="read_instruction_pointer"),
            pytest.param("-1 0 3 6 0 0 0", "", "", id="write_instruction_pointer"),
            pytest.param(
                "-1 12 0  0 0 12  0 0 0  -3 13 0  -6 67",
                "",
                "C",
                id="pointer_write_redirects_fall_through",
            ),
            # Memory grows past the end; the negative target halts.
            pytest.param("10 0 3 -1 0 0 0", "", "", id="write_past_end_extends_memory"),
        ],
    )
    def test_output(self, program: str, stdin: str, expected: str) -> None:
        assert run_bounded(program, stdin=stdin) == expected

    def test_invalid_address_rejected(self) -> None:
        """An address below -3 is an invalid operation."""
        with pytest.raises(ValueError, match="invalid address"):
            run_bounded("-4 0 3 0 0 5 9")


class TestMemoryState:
    """Assertions on the memory a program leaves behind."""

    @pytest.mark.parametrize(("stdin", "first"), [("AB", -65), ("", 0)])
    def test_input_is_the_first_byte_or_zero_at_eof(self, stdin, first) -> None:
        assert stepped("0 -2 3 -3 0 6 9", stdin=stdin).mem[0] == first


class TestVariants:
    """The store-target variants (S*bl*q stores in a and b; Subl*q in b)."""

    def test_each_variant_writes_where_it_says(self) -> None:
        program = "6 7 3 0 0 5 9 5 3"
        assert list(stepped(program).mem)[6:8] == [4, 5]
        assert list(stepped(program, store="ab").mem)[6:8] == [4, 4]
        # Wiki rev 188944: "Subl*q ... result of subtraction is stored in b".
        assert list(stepped(program, store="b").mem)[6:8] == [9, 4]
        # Address 0 is ordinary: the b variants store the difference there too.
        zero = "5 0 8 0 0 0 0 0 9 3"
        assert stepped(zero).mem[0] == 5
        assert stepped(zero, store="b").mem[0] == -5
        assert stepped(zero, store="ab").mem[0] == -5

    @pytest.mark.parametrize(("store", "ip"), [("a", 3), ("ab", 9), ("b", 9)])
    def test_a_b_store_to_minus_one_moves_the_pointer(self, store, ip) -> None:
        machine = _Machine("5 -1 0 0 0 6", ScriptedIO(""), store=store)
        machine.step()
        assert machine.ip == ip

    def test_run_forwards_the_store_variant(self) -> None:
        """``run``'s store reaches the machine and shows in the output."""
        program = "9 10 3  -3 10 6  0 0 11  5 3 99"
        assert run_bounded(program) == "\x03"
        assert run_bounded(program, store="b") == "\x02"

    @pytest.mark.parametrize("store", ["A", "AB", "B", "c", "", "bb", "abc"])
    def test_unknown_store_target_is_rejected(self, store: str) -> None:
        """A store outside the three variants raises rather than running."""
        with pytest.raises(ValueError, match="unknown store target"):
            _Machine("0 0 0", ScriptedIO(""), store=store)


class TestProgramText:
    """Comments and whitespace, via the shared ``parse_int_memory``."""

    @pytest.mark.parametrize(
        ("program", "expected"),
        [
            # ``#`` starts a comment that runs to the end of its line.
            pytest.param(
                "-3 6 3 # print, then halt\n0 0 7 65 9", "A", id="comment_is_ignored"
            ),
            pytest.param(
                "# nothing but a comment", "", id="comment_only_program_is_empty"
            ),
        ],
    )
    def test_output(self, program: str, expected: str) -> None:
        assert run_bounded(program) == expected

    def test_malformed_token_raises_package_error(self) -> None:
        """A non-integer token is a ``ValueError`` naming the token."""
        with pytest.raises(ValueError, match="malformed memory token: 'x'"):
            run_bounded("0 0 x")


class TestIndirectFamily:
    """S**bleq and kin: ``a`` and ``b`` become ``*a`` and ``*b``."""

    def test_s_star_star_bleq_subtracts_through_the_named_cells(self) -> None:
        machine = _Machine("3 4 8 5 6 10 3 0 9", ScriptedIO(""), indirect=True)
        while not machine.halted:
            machine.step()
        assert machine.mem[5] == 7
        assert machine.mem[7] == -5

    def test_an_indirect_operand_may_name_the_output_address(self) -> None:
        """``*a`` is -3, so the instruction prints the cell ``*b`` names."""
        io = ScriptedIO("")
        run("4 3 72 2 -3", io, indirect=True)
        assert io.getvalue() == "H"

    def test_a_negative_operand_names_no_cell_to_read_through(self) -> None:
        with pytest.raises(ValueError, match="names no cell"):
            run("-1 0 0", ScriptedIO(""), indirect=True)


def test_sbleq_looping_run_is_detected_as_a_cycle() -> None:
    # a=0 b=0 c=2: diff is always 0, so it jumps to mem[2] (address 0) forever
    machine = Sbleq("0 0 0", ScriptedIO(), store="a")
    assert run_until_halt_or_cycle(machine) is False


class TestContract(SnapshotContract):
    machine = staticmethod(lambda code: _Machine(code, ScriptedIO("")))
    stepping_program = "3 4 6 1 1 0 0 0 0"
