"""forbin generator tests."""

import itertools
import random

import pytest

import esolangs
from esolangs import tools as boolean
from tests.tools.boolean_runners import (
    run_forbin_boolean,
)
from tests.witness_tables import witnesses


class TestForbinBoolean:
    @pytest.mark.parametrize("width", [1, 4, 7, 13, 40, 80])
    def test_narrow_small_tables(self, width: int) -> None:
        """The witness tables execute with a four-column grammar floor."""
        for n in range(1, 4):
            for table in witnesses(n):
                program = esolangs.generate("Forbin", table, width=width)
                assert isinstance(program, str)
                assert max(map(len, program.splitlines())) <= max(width, 4)
                for row in range(2**n):
                    bits = list(format(row, f"0{n}b"))
                    assert run_forbin_boolean(program, bits) == table[row]

    @pytest.mark.parametrize("width", [1, 4, 13, 80])
    def test_narrow_block_guards(self, width: int) -> None:
        """Both block guards and constant spans emit exactly one answer."""
        rng = random.Random(20260930)
        for n in (8, 9):
            tables = [
                "0" * (2 ** (n - 1)) + "1" * (2 ** (n - 1)),
                "".join(str(row.bit_count() & 1) for row in range(2**n)),
                "".join(rng.choice("01") for _ in range(2**n)),
            ]
            for table in tables:
                program = esolangs.generate("Forbin", table, width=width)
                assert isinstance(program, str)
                assert max(map(len, program.splitlines())) <= max(width, 4)
                for row in [0, 2**n - 1, *rng.sample(range(2**n), 16)]:
                    bits = list(format(row, f"0{n}b"))
                    assert run_forbin_boolean(program, bits) == table[row]

    def test_a_fitting_program_keeps_its_source(self) -> None:
        program = boolean.forbin("01101001")
        width = max(map(len, program.splitlines()))
        assert boolean.forbin("01101001", width) == program

    def test_uses_the_lsb_of_each_input(self) -> None:
        """Each input is read as 8 bits and only the LSB is kept."""
        program = boolean.forbin("01")
        assert "e,e,e,e,e,e,e,a=(in 0);" in program

    def test_small_program_uses_one_character_variables(self) -> None:
        """The first 52 variables do not carry widening decimal suffixes."""
        targets = [
            line.split("=", 1)[0]
            for line in boolean.forbin("01101001").splitlines()
            if line.endswith("=(in 0);")
        ]
        assert targets
        assert all(len(name) == 1 for group in targets for name in group.split(","))

    def test_the_block_is_painted_as_a_literal_argument_list(self) -> None:
        """A table inside one block is emitted verbatim, two characters an entry."""
        program = boolean.forbin("01101001")
        assert "0,1,1,0,1,0,0,1)" in program

    def test_compact_variables_skip_keywords_without_duplicates(self) -> None:
        """Filtering a reserved word does not reuse its successor's name."""
        from esolangs.tools.forbin import _FORBIN_RESERVED, _forbin_name

        names = [_forbin_name(i) for i in range(600)]
        assert len(set(names)) == len(names)
        assert not set(names) & _FORBIN_RESERVED

    def test_constant_spans_fold_above_the_block(self) -> None:
        """A constant span of blocks calls a printer instead of painting."""
        from esolangs.tools.forbin import _BLOCK_BITS, _Names

        arity = _BLOCK_BITS + 2
        wide = 2**arity
        register = _Names(arity, 1 << _BLOCK_BITS).table + " "
        whole = boolean.forbin("1" * wide)
        assert whole.count("return(") == 1
        # The constant table paints no block, so defines no shift register.
        assert register not in whole
        # Two constant spans call printers beside the one painted quarter.
        parity = "".join(str(i.bit_count() & 1) for i in range(wide // 4))
        mixed = boolean.forbin("0" * (wide // 2) + "1" * (wide // 4) + parity)
        assert mixed.count("return(") == 3

    def test_full_tree_growth_is_linear(self) -> None:
        """Names and indentation add only a geometric cost to the tree."""
        sizes = []
        for n in range(11, 15):
            parity = "".join(str(i.bit_count() & 1) for i in range(2**n))
            sizes.append(len(boolean.forbin(parity)))
        assert all(later < 2 * earlier for earlier, later in itertools.pairwise(sizes))
