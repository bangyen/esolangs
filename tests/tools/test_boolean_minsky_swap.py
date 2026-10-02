"""minsky_swap generator tests."""

from itertools import pairwise

import pytest


class TestParameterizedMinskySwap:
    """Input-by-substitution boolean generator for the no-input language Minsky Swap.

    Minsky Swap prints the two registers at halt; the generator's answer is
    stored in ``reg[1]``, so it is the second number of the dump line.
    """

    def run_minsky_swap(self, prog: str) -> str:
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.register_based.minsky_swap import run

        io = ScriptedIO()
        run(prog, io)
        return io.getvalue().split()[1]

    def instantiate(self, tpl: str, bits: list[int]) -> str:
        """Fill the template the way a caller does, not the way this file did.

        This used to carry its own copy of the setter -- the same blocks,
        padded to ``2**n``.  A copy of a construction is free to drift from
        it, and this one did: when the generator shortened each block to its
        own bit's weight, the copy went on emitting full-length ones, so the
        template's jump targets addressed commands that were no longer
        there.  The program did not fail, it ran off into a loop, and the
        suite hung rather than reporting anything.

        The shipped filler is the thing under test here anyway: what this
        class pins is the truth table the instantiated program computes, and
        that is checked below either way.
        """
        from tests.tools.fills import _fill_minsky_swap

        return _fill_minsky_swap(tpl, bits)

    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("10", 1),  # NOT
            ("01", 1),  # identity
            ("00", 1),  # constant zero
            ("11", 1),  # constant one
            ("0001", 2),  # AND
            ("0110", 2),  # XOR
            ("0111", 2),  # OR
            ("1110", 2),  # NAND
            ("11111110", 3),  # NAND3
            ("01101001", 3),  # majority
            ("1111111100000000", 4),  # top half
        ],
    )
    @pytest.mark.medium
    def test_truth_table(self, table: str, n: int) -> None:
        """Every instantiated input produces the truth-table result."""
        from esolangs import tools as generators

        template = generators.minsky_swap(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = self.run_minsky_swap(self.instantiate(template, bits))
            assert got == str(int(table[combo])), f"inputs {bits}"

    @pytest.mark.parametrize("n", [1, 2, 3])
    @pytest.mark.medium
    def test_all_small_tables(self, n: int) -> None:
        """Every table up to three inputs produces the right result."""
        from esolangs import tools as generators

        for table_int in range(2 ** (2**n)):
            table = format(table_int, f"0{2**n}b")
            template = generators.minsky_swap(table)
            for combo in range(2**n):
                bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
                got = self.run_minsky_swap(self.instantiate(template, bits))
                assert got == str(int(table[combo])), f"{table} inputs {bits}"

    @pytest.mark.parametrize("width", [1, 9, 10, 15, 20, 40, 80])
    def test_rmsn_templates_preserve_command_targets(self, width: int) -> None:
        """Public and example fills use the notation's one equal-width pair."""
        import esolangs
        from esolangs.tools.examples import BOOLEAN_EXAMPLES
        from esolangs.tools.minsky_swap import minsky_swap_setters

        example = BOOLEAN_EXAMPLES["minsky-swap"]
        assert example.fill is not None
        for n in (1, 2, 3, 5):
            table = "".join(str(row.bit_count() & 1) for row in range(1 << n))
            template = esolangs.generate("Minsky Swap", table, width)
            pairs = minsky_swap_setters(template, n)
            assert len(set(pairs)) == 1
            assert len(pairs[0][0]) == len(pairs[0][1])
            assert max(map(len, template.splitlines())) <= max(
                width, 8 + len(str(2 ** (n + 1) + 7 * n + 6))
            )
            for row in range(1 << n):
                bits = list(map(int, f"{row:0{n}b}"))
                program = esolangs.instantiate("Minsky Swap", str(template), bits)
                assert self.run_minsky_swap(program) == table[row]
                assert self.run_minsky_swap(example.fill(template, bits)) == table[row]

    def test_short_rmsn_public_floor(self) -> None:
        import esolangs

        template = esolangs.generate("Minsky Swap", "0110", 1)
        assert template.setters == (("decnz(2);", "inc();   "),) * 2
        assert max(map(len, template.splitlines())) == 9
        for bits in ([0, 0], [0, 1], [1, 0], [1, 1]):
            program = esolangs.instantiate("Minsky Swap", template, bits)
            assert max(map(len, program.splitlines())) == 9
            assert self.run_minsky_swap(program) == str(bits[0] ^ bits[1])

    @pytest.mark.parametrize("n", [1, 2])
    def test_single_digit_router_for_every_small_table(self, n: int) -> None:
        import esolangs

        for value in range(1 << (1 << n)):
            table = format(value, f"0{1 << n}b")
            for width in (1, 8, 9, 10, 15):
                tagged = esolangs.generate("Minsky Swap", table, width)
                assert tagged.setters is not None
                assert len(tagged.setters) == n
                assert len(set(tagged.setters)) == 1
                assert len(tagged.setters[0][0]) == len(tagged.setters[0][1])
                for template in (tagged, str(tagged)):
                    for row in range(1 << n):
                        bits = list(map(int, f"{row:0{n}b}"))
                        program = esolangs.instantiate(
                            "Minsky Swap", template, bits, truth_table=table
                        )
                        assert self.run_minsky_swap(program) == table[row]
                    with pytest.raises(esolangs.TemplateError):
                        esolangs.instantiate(
                            "Minsky Swap",
                            template,
                            [0] * n,
                            truth_table="".join(
                                "1" if bit == "0" else "0" for bit in table
                            ),
                        )

    def test_rmsn_growth_remains_linear(self) -> None:
        from esolangs import tools as generators

        sizes = [
            len(generators.minsky_swap("01101001" * (2 ** (n - 3)), 1))
            for n in (7, 8, 9)
        ]
        assert all(b <= 2 * a for a, b in pairwise(sizes))

    def test_template_is_input_independent(self) -> None:
        """The template has input runs, not hardcoded bits.

        Every run is two wide, and the stage after each carries the weight:
        two ``+`` after the MSB, one after the LSB.  The jump targets count
        those stages, not the runs.  The five commands ahead of the first
        run are the shared leaves and the ``~`` that jumps over them.
        """
        from esolangs import tools as generators

        template = generators.minsky_swap("0110")
        assert "{X" not in template
        assert template.startswith("~ ~ + * ~ $$ ~ ~ * ++ * $$ ~ ~ * + * *")

    @pytest.mark.parametrize("bits", [(0, 0), (0, 1), (1, 0), (1, 1)])
    def test_examples_fill_sets_either_bit_in_either_position(
        self, bits: tuple[int, int]
    ) -> None:
        """``_fill_minsky_swap`` spells a set bit above the LSB too.

        The catalogue entry runs one fixed pair, ``(0, 1)``, which leaves
        the non-LSB always zero -- so its weighted ``"+" * weight`` block
        is never emitted there.  Each pair below is run, not merely built,
        because a wrong weight or pad would still produce a plausible
        string.
        """
        from esolangs.tools import minsky_swap
        from esolangs.tools.examples import AND2
        from tests.tools.fills import _fill_minsky_swap

        program = _fill_minsky_swap(minsky_swap(AND2), list(bits))
        assert self.run_minsky_swap(program) == AND2[(bits[0] << 1) | bits[1]]

    def test_examples_fill_is_one_pair_at_every_input(self) -> None:
        """A run is ``++`` or ``**`` at the MSB exactly as at the LSB.

        The weight is the template's: the ``+`` block after the run is as
        wide as the bit's weight, so the run itself never counts it.  A
        zero is two swaps, which is what keeps the pointer on ``reg[0]``
        for the stage's ``~`` -- an odd run would leave it on the
        accumulator.
        """
        from esolangs.tools import minsky_swap
        from esolangs.tools.examples import AND2
        from esolangs.tools.minsky_swap import MINSKY_SWAP_PAIR
        from tests.tools.fills import _fill_minsky_swap

        assert MINSKY_SWAP_PAIR == ("**", "++")
        template = minsky_swap(AND2)
        leaves = "~ ~ + * ~ "
        assert _fill_minsky_swap(template, [1, 1]).startswith(
            leaves + "++ ~ ~ * ++ * ++ ~ ~ * + *"
        )
        assert _fill_minsky_swap(template, [0, 1]).startswith(
            leaves + "** ~ ~ * ++ * ++ ~ ~ * + *"
        )
        assert _fill_minsky_swap(template, [1, 0]).startswith(
            leaves + "++ ~ ~ * ++ * ** ~ ~ * + *"
        )
