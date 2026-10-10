"""bitdeque generator tests."""

from itertools import pairwise

import pytest

from esolangs import tools as boolean
from esolangs.tools.bitdeque import _bitdeque_ordered
from tests.source_support import source_units
from tests.witness_tables import row_bits, witnesses


class TestParameterizedBitdeque:
    """Input-by-substitution boolean generator for the no-input language Bitdeque."""

    def run_bitdeque(self, prog: str) -> str:
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.queue_based.bitdeque import run

        io = ScriptedIO()
        run(prog, io)
        return io.getvalue().strip()

    def instantiate(self, tpl: str, bits: list[int]) -> str:
        # Deliberately the shipped fill rather than a copy of its rule: an
        # earlier duplicate here kept passing after the load order changed
        # under it, so the suite disagreed with the harness it is meant to
        # mirror.
        from tests.tools.fills import fill

        _fill_bitdeque = fill("Bitdeque")

        return _fill_bitdeque(tpl, bits)

    def test_template_is_input_independent(self) -> None:
        """The template has input runs, not hardcoded bits."""
        from esolangs import tools as generators
        from esolangs.tools.bitdeque import BITDEQUE_PAIR
        from esolangs.tools.helpers import runs

        for n in (2, 5):
            template = generators.bitdeque("0110" * 2 ** (n - 2))
            assert "{X" not in template
            setters = (BITDEQUE_PAIR,) * n
            spans = runs(template, "$", setters)
            assert [end - start for start, end in spans] == [11] * n

    def test_odd_inputs_are_pushed_complemented(self) -> None:
        """The load flips the register per block; the tree's table absorbs it."""
        from esolangs import tools as generators
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.queue_based.bitdeque import run

        template = generators.bitdeque("0101")
        prelude_and_load = " ".join(self.instantiate(template, [0, 1]).split()[:12])
        io = ScriptedIO()
        run(prelude_and_load, io)
        assert io.getvalue() == "0 0"  # input 1's one pushed as a zero
        for bits in ([0, 0], [0, 1], [1, 0], [1, 1]):
            assert self.run_bitdeque(self.instantiate(template, bits)) == str(bits[1])

    def test_linear_route_forces_the_register_between_inputs(self) -> None:
        """Both discard paths meet at a reset, and the last input skips it."""

        from esolangs.tools.bitdeque import _bitdeque_linear

        n = 5
        table = "".join(str(row.bit_count() & 1) for row in range(2**n))
        tokens = _bitdeque_linear(table).split()
        assert tokens[:3] == ["PUSH", "INVERT", "PUSH"]  # parity opens 0, 1
        assert tokens.count("POP") == 2**n - 1 + n  # the discards, the reads
        assert tokens.count("EJECT") == 2**n - 1
        assert " ".join(tokens).count("INVERT INVERT") == n - 1  # the resets
        assert tokens[-1] == "EJECT"  # the last input ends on its one block

    def test_ordered_route_rotates_a_nonhead_input_toward_the_head(self) -> None:
        """The private candidate builder covers the other shortest rotation."""

        template = _bitdeque_ordered("0110100110010110", (1, 0, 2, 3))
        assert "EJECT PUSH EJECT" in template

    def test_constant_table_is_a_leaf(self) -> None:
        """A constant table emits a drain-and-push leaf with no branching."""
        from esolangs import tools as generators

        template = generators.bitdeque("0000")
        assert "POP" in template
        assert "GOTO" in template

    def test_leaves_share_a_low_address_halt_trampoline(self) -> None:
        """Both leaves are emitted once, each returning through ``GOTO 1``."""
        from esolangs import tools as generators

        template = generators.bitdeque("01101001")
        assert template.startswith("GOTO 4 INVERT GOTO 5 GOTO ")
        assert f"{template} ".count("GOTO 1 ") == 2

    def test_linear_discard_executes_wide_rows(self) -> None:
        """Head/tail discards leave sampled six-input answers."""
        from esolangs.tools.bitdeque import _bitdeque_linear

        n = 6
        table = "".join(str(row.bit_count() & 1) for row in range(2**n))
        template = _bitdeque_linear(table)
        for row in (0, 1, 2, 7, 31, 32, 62, 63):
            bits = row_bits(row, n)
            assert self.run_bitdeque(self.instantiate(template, bits)) == table[row]

    def test_linear_discard_growth(self) -> None:
        """Wide templates and their fills scale with table size."""
        from esolangs.tools.bitdeque import _bitdeque_linear

        templates = []
        filled = []
        for n in range(11, 15):
            table = "".join(str(row.bit_count() & 1) for row in range(2**n))
            template = _bitdeque_linear(table)
            templates.append(len(template))
            filled.append(len(self.instantiate(template, [0] * n)))
        assert all(b <= 2 * a for a, b in pairwise(templates))
        assert all(b <= 2 * a for a, b in pairwise(filled))


@pytest.mark.parametrize("width", [1, 7, 9, 10, 11, 40, 80])
def test_bitdeque_short_load_witness_tables(width: int) -> None:
    import esolangs

    for n in range(1, 4):
        for table in witnesses(n):
            template = esolangs.generate("Bitdeque", table, width=width)
            for row, expected in enumerate(table):
                bits = list(map(int, format(row, f"0{n}b")))
                program = esolangs.instantiate("Bitdeque", template, bits)
                assert esolangs.run("Bitdeque", program) == expected


def test_bitdeque_short_load_floor_and_rendered_total() -> None:
    import esolangs

    template = esolangs.generate("Bitdeque", "0110", width=1)
    assert max(map(len, template.splitlines())) == 7
    for row in range(4):
        program = esolangs.instantiate("Bitdeque", template, [row // 2, row % 2])
        assert max(map(len, program.splitlines())) == 7
    assert (
        sum(
            len(esolangs.generate("Bitdeque", format(value, "08b"), width=1))
            for value in range(256)
        )
        == 117472
    )


@pytest.mark.parametrize("width", [1, 9, 40, 80])
def test_bitdeque_short_load_saved_source_and_large_tables(width: int) -> None:
    import esolangs

    for n in range(4, 7):
        table = "".join(str(row.bit_count() % 2) for row in range(2**n))
        template = str(esolangs.generate("Bitdeque", table, width=width))
        for row in [0, 1, 2**n // 3, 2**n - 1]:
            bits = list(map(int, format(row, f"0{n}b")))
            program = esolangs.instantiate(
                "Bitdeque", template, bits, truth_table=table
            )
            assert esolangs.run("Bitdeque", program) == table[row]


def test_bitdeque_short_load_rejects_changed_prefix() -> None:
    from esolangs.tools.bitdeque import bitdeque, bitdeque_setters

    template = bitdeque("0110", 1)
    pair = bitdeque_setters(template, 2)
    assert pair == (("POP  ", "EJECT"),) * 2
    with pytest.raises(ValueError, match="shorter than"):
        bitdeque_setters(template.replace("GOTO 17", "GOTO 18"), 2)


def test_bitdeque_short_load_rejects_wrong_table_provenance() -> None:
    import esolangs

    template = str(esolangs.generate("Bitdeque", "0110", width=9))
    with pytest.raises(esolangs.TemplateError, match="not the template"):
        esolangs.instantiate("Bitdeque", template, [0, 1], truth_table="0001")


def test_reordering_never_grows_a_program() -> None:
    """Choosing the input order can only shrink the emitted program."""
    for n in (1, 2, 3):
        for value in range(2 ** (2**n)):
            table = bin(value)[2:].zfill(2**n)
            baseline = _bitdeque_ordered(table, tuple(range(n)))
            # An order the search cannot place has no baseline to beat.
            if not baseline:
                continue
            assert source_units(boolean.bitdeque(table)) <= len(baseline), table


def test_reordering_shrinks_the_tables_it_should() -> None:
    """A table only one input order folds well is emitted from that order."""
    table = "10101010"
    assert source_units(boolean.bitdeque(table)) < len(
        _bitdeque_ordered(table, (0, 1, 2))
    )
