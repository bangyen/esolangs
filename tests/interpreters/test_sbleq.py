"""Unit tests for the S*bleq interpreter."""

import io

import pytest

import esolangs
from esolangs.interpreters.io import IO, ScriptedIO
from esolangs.interpreters.tape_based.sbleq import _Machine, run
from esolangs.interpreters.tape_based.sbleq import _Machine as Sbleq
from esolangs.vm import run_until_halt_or_cycle


def run_bounded(program: str, stdin: str = "", store: str = "a") -> str:
    """Run ``program`` and return its output."""
    buffer = io.StringIO()

    class _IO(IO):
        def _read(self, _prompt: str) -> str:
            return stdin

        def _write(self, value: object) -> None:
            buffer.write(str(value))

    run(program, _IO(), store=store)
    return buffer.getvalue()


class TestCoreInstruction:
    """The single subtract-and-branch instruction."""

    def test_special_addresses_are_not_branch_operands(self) -> None:
        """``c`` is an address, not an operand port."""
        with pytest.raises(ValueError, match="invalid S\\*bleq branch address"):
            run_bounded("0 0 -1")


class TestSpecialAddresses:
    """The -1 (IP), -2 (input), and -3 (output) addresses."""

    @pytest.mark.parametrize(
        ("program", "stdin", "expected"),
        [
            # a=-3 outputs mem[6]=65; then 0-0=0 jumps to mem[5]=9 and halts.
            pytest.param(
                "-3 6 3 0 0 7 65 9", "", "A", id="output_via_a_negative_three"
            ),
            # b=-3 outputs the value at a, mem[6]=66.
            pytest.param(
                "6 -3 3 0 0 7 66 9", "", "B", id="output_via_b_negative_three"
            ),
            # a=-2 reads 'A'=65: 65 - (-2) = 67 > 0 falls through, then halts.
            pytest.param("-2 0 3 0 0 5 9", "A", "", id="input_reads_byte"),
            # Exhausted input reads as zero in the subtraction.
            pytest.param("-2 0 3 0 0 5 9", "", "", id="input_eof_reads_zero"),
            # b=-1 reads the ip (0): 2 - 0 = 2 > 0 falls through, then halts.
            pytest.param("2 -1 3 0 0 5 9", "", "", id="read_instruction_pointer"),
            # a=-1: ip(0) - mem[0](-1) = 1 is written to the ip and falls through.
            pytest.param("-1 0 3 6 0 0 0", "", "", id="write_instruction_pointer"),
            # Memory grows past the end; the negative target in mem[3] halts.
            pytest.param(
                "10 0 3 -1 0 0 0", "", "", id="write_past_end_extends_memory_and_breaks"
            ),
            # Storing to -1 moves the pointer, not the address 1.
            pytest.param(
                "-1 12 0  0 0 12  0 0 0  -3 13 0  -6 67",
                "",
                "C",
                id="a_write_to_the_pointer_redirects_the_fall_through",
            ),
        ],
    )
    def test_output(self, program: str, stdin: str, expected: str) -> None:
        assert run_bounded(program, stdin=stdin) == expected

    def test_invalid_address_rejected(self) -> None:
        """An address below -3 is an invalid operation."""
        with pytest.raises(ValueError, match="invalid address"):
            run_bounded("-4 0 3 0 0 5 9")

    def test_output_advances_past_its_own_instruction(self) -> None:
        """A ``-3`` instruction moves on three cells from where it stands."""
        assert run_bounded("0 0 9  -3 10 0  0 0 11  3 67 99") == "C"
        assert run_bounded("0 0 9  10 -3 0  0 0 11  3 67 99") == "C"


class TestMemoryState:
    """Assertions on the memory a program leaves behind."""

    def final(
        self, program: str, stdin: str = "", steps: int = 200
    ) -> tuple[list[int], int]:
        """Run at most ``steps`` instructions; S*bleq programs may not halt."""
        machine = _Machine(program, ScriptedIO(stdin))
        for _ in range(steps):
            if machine.halted:
                break
            machine.step()
        return list(machine.mem), machine.ip

    def test_writing_past_the_end_pads_with_zeros(self) -> None:
        """Memory grows to reach the address, and the new cells hold 0."""
        assert self.final("5 5 9") == ([5, 5, 9, 0, 0, 0], 0)

    def test_address_zero_is_an_ordinary_cell(self) -> None:
        """Address 0 is written like any other, not treated as special."""
        assert self.final("0 1 3 7") == ([-1, 1, 3, 7], 7)

    def test_falling_through_advances_by_one_instruction(self) -> None:
        """A positive result moves on three cells, it does not reset there."""
        assert self.final("9 10 2 9 11 2 0 0 2") == (
            [9, 10, -7, 9, 11, 2, 0, 0, 2, 0],
            9,
        )

    def test_input_takes_the_first_byte_of_the_line(self) -> None:
        """``-2`` supplies one byte, and it is the first one."""
        assert self.final("0 -2 3 -3 0 6 9", stdin="A")[0][0] == -65
        assert self.final("0 -2 3 -3 0 6 9", stdin="AB")[0][0] == -65

    def test_exhausted_input_reads_as_zero(self) -> None:
        """With no input left the subtraction uses 0, which leaves the cell
        unchanged rather than shifting it by one.
        """
        assert self.final("0 -2 3 -3 0 6 9", stdin="")[0][0] == 0

    def test_a_zero_difference_takes_the_jump(self) -> None:
        """The branch is on ``<= 0``: an exactly zero result jumps too."""
        assert self.final("1 1 0 0 0 0") == ([0, 0, 0, 0, 0, 0], 0)


class TestVariants:
    """The store-target variants (S*bl*q stores in a and b; Subl*q in b)."""

    def test_each_variant_writes_where_it_says(self) -> None:
        """Which cell receives the difference, which ``== ""`` cannot show."""
        program = "6 7 3 0 0 5 9 5 3"
        assert self.mem(program, "a")[6:8] == [4, 5]
        assert self.mem(program, "ab")[6:8] == [4, 4]
        # Wiki rev 188944: "Subl*q ... result of subtraction is stored in b".
        assert self.mem(program, "b")[6:8] == [9, 4]

    @pytest.mark.parametrize(("store", "ip"), [("a", 3), ("ab", 9), ("b", 9)])
    def test_a_b_store_to_minus_one_moves_the_pointer(
        self, store: str, ip: int
    ) -> None:
        """Pins b=-1 writes: ``5 -1 0`` stores 6-0 into the IP, then +3 -> 9."""
        machine = _Machine("5 -1 0 0 0 6", ScriptedIO(""), store=store)
        machine.step()
        assert machine.ip == ip

    def test_a_huge_invalid_address_is_reported_in_full(self) -> None:
        """Pins format_integer: a 5001-digit operand past CPython's 4300 cap."""
        big = "1" + "0" * 5000
        with pytest.raises(ValueError, match=f"invalid address -{big}(?!\\d)"):
            run_bounded(f"-{big} 0 3 0 0 5 9")

    def test_the_variant_reaches_run_and_shows_in_the_output(self) -> None:
        """``run`` forwards ``store``, and the choice is visible in print."""
        program = "9 10 3  -3 10 6  0 0 11  5 3 99"
        assert run_bounded(program, store="a") == "\x03"
        assert run_bounded(program, store="b") == "\x02"
        assert run_bounded(program, store="ab") == "\x02"

    def test_a_variant_stores_into_address_zero(self) -> None:
        """``b`` is an address, and address 0 is one of them."""
        program = "5 0 8 0 0 0 0 0 9 3"
        assert self.mem(program, "a")[0] == 5
        assert self.mem(program, "b")[0] == -5
        assert self.mem(program, "ab")[0] == -5

    def mem(self, program: str, store: str = "a", steps: int = 200) -> list[int]:
        """Return the memory ``program`` leaves under the ``store`` variant."""
        machine = _Machine(program, ScriptedIO(""), store=store)
        for _ in range(steps):
            if machine.halted:
                break
            machine.step()
        return list(machine.mem)

    @pytest.mark.parametrize("store", ["a", "ab", "b"])
    def test_documented_store_targets_are_accepted(self, store: str) -> None:
        """The three wiki variants stay constructible."""
        assert _Machine("0 0 0", ScriptedIO(""), store=store).store == store

    def test_runs_own_default_is_the_base_language(self) -> None:
        """``run`` called with no ``store`` runs base S*bleq."""
        buffer = io.StringIO()

        class _IO(IO):
            def _read(self, _prompt: str) -> str:
                return ""

            def _write(self, value: object) -> None:
                buffer.write(str(value))

        run("9 10 3  -3 10 6  0 0 11  5 3 99", _IO())
        assert buffer.getvalue() == "\x03"

    @pytest.mark.parametrize(
        "store",
        [
            # 5 - 3 = 2 is stored in both a and b, falls through, then halts.
            pytest.param("ab", id="sblq_stores_in_both"),
            # The same program writes only mem[7], leaving mem[6]=9.
            pytest.param("b", id="subleq_store_in_b"),
        ],
    )
    def test_store_variant_runs_silently(self, store: str) -> None:
        assert run_bounded("6 7 3 0 0 5 9 5 3", store=store) == ""

    def test_the_default_variant_stores_in_a(self) -> None:
        """``run`` defaults to the base language, which writes to a alone."""
        program = "6 7 3 0 0 5 9 5 3"
        assert self.mem(program) == self.mem(program, "a")
        assert self.mem(program) != self.mem(program, "b")

    @pytest.mark.parametrize("store", ["A", "AB", "B", "c", "", "bb", "abc"])
    def test_unknown_store_target_is_rejected(self, store: str) -> None:
        """A store outside the three variants raises rather than running."""
        with pytest.raises(ValueError, match="unknown store target"):
            _Machine("0 0 0", ScriptedIO(""), store=store)


class TestSnapshot:
    def test_snapshot_is_hashable_and_tracks_progress(self) -> None:
        machine = _Machine("3 4 6 1 1 0 0 0 0", ScriptedIO(""))
        before = machine.snapshot()
        hash(before)  # must not raise
        machine.step()
        assert machine.snapshot() != before


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
        """Step one: mem[5] - mem[6] = 7 > 0, kept at cell 5; step two:
        mem[7] - mem[3] = -5, kept at cell 7, then a jump to mem[7] < 0 halts."""
        machine = _Machine("3 4 8 5 6 10 3 0 9", ScriptedIO(""), indirect=True)
        while not machine.halted:
            machine.step()
        assert machine.mem[5] == 7
        assert machine.mem[7] == -5

    def test_an_indirect_operand_may_name_the_output_address(self) -> None:
        """``*a`` is -3, so the instruction prints the cell ``*b`` names."""
        out = ScriptedIO("")
        run("4 3 72 2 -3", out, indirect=True)
        assert out.getvalue() == "H"

    def test_a_negative_operand_names_no_cell_to_read_through(self) -> None:
        with pytest.raises(ValueError, match="names no cell"):
            run("-1 0 0", ScriptedIO(""), indirect=True)


def test_sbleq_looping_run_is_detected_as_a_cycle() -> None:
    # a=0 b=0 c=2: diff is always 0, so it jumps to mem[2] (address 0) forever
    machine = Sbleq("0 0 0", ScriptedIO(), store="a")
    assert run_until_halt_or_cycle(machine) is False


def test_a_huge_address_is_refused_before_allocating() -> None:
    """A store grown to whatever the program named thrashed the machine."""
    with pytest.raises(esolangs.InterpreterLimitError, match="grow its store"):
        esolangs.run("S*bleq", "100000000000000000000 0 0", stdin="", timeout=2)
    with pytest.raises(esolangs.InterpreterLimitError, match="grow its store"):
        esolangs.run("S*bleq", "1000000000000000000 0 0", stdin="", timeout=2)
    assert esolangs.run("S*bleq", "20 0 0", stdin="", timeout=5) == ""
