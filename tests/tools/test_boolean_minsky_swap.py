"""minsky_swap generator tests."""

from itertools import pairwise

import pytest

from tests.witness_tables import witnesses


class TestParameterizedMinskySwap:
    """Input-by-substitution boolean generator for the no-input language Minsky Swap."""

    def run_minsky_swap(self, prog: str) -> str:
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.register_based.minsky_swap import run

        io = ScriptedIO()
        run(prog, io)
        return io.getvalue().split()[1]

    def instantiate(self, tpl: str, bits: list[int]) -> str:
        """Fill the template the way a caller does, not the way this file did."""
        from tests.tools.fills import fill

        _fill_minsky_swap = fill("Minsky Swap")

        return _fill_minsky_swap(tpl, bits)

    @pytest.mark.parametrize("width", [1, 10, 15, 40, 80])
    def test_rmsn_templates_preserve_command_targets(self, width: int) -> None:
        """Public and example fills use the notation's one equal-width pair."""
        import esolangs
        from esolangs.tools.examples import BOOLEAN_EXAMPLES
        from esolangs.tools.minsky_swap import minsky_swap_setters

        example = BOOLEAN_EXAMPLES["minsky-swap"]
        assert example.fill is not None
        for n in (1, 2, 3, 5):
            table = "".join(str(row.bit_count() & 1) for row in range(1 << n))
            template = esolangs.generate("Minsky Swap", table, width=width)
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

        template = esolangs.generate("Minsky Swap", "0110", width=1)
        assert template.setters == (("decnz(2);", "inc();   "),) * 2
        assert max(map(len, template.splitlines())) == 9
        for bits in ([0, 0], [0, 1], [1, 0], [1, 1]):
            program = esolangs.instantiate("Minsky Swap", template, bits)
            assert max(map(len, program.splitlines())) == 9
            assert self.run_minsky_swap(program) == str(bits[0] ^ bits[1])

    @pytest.mark.parametrize("n", [1, 2])
    def test_single_digit_router_for_every_small_table(self, n: int) -> None:
        import esolangs

        for table in witnesses(n):
            for width in (1, 8, 9, 10, 15):
                tagged = esolangs.generate("Minsky Swap", table, width=width)
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

    @pytest.mark.parametrize("bits", [(0, 0), (0, 1), (1, 0), (1, 1)])
    def test_examples_fill_sets_either_bit_in_either_position(
        self, bits: tuple[int, int]
    ) -> None:
        """``_fill_minsky_swap`` spells a set bit above the LSB too."""
        from esolangs.tools import minsky_swap
        from esolangs.tools.examples import AND2
        from tests.tools.fills import fill

        _fill_minsky_swap = fill("Minsky Swap")

        program = _fill_minsky_swap(minsky_swap(AND2), list(bits))
        assert self.run_minsky_swap(program) == AND2[(bits[0] << 1) | bits[1]]
