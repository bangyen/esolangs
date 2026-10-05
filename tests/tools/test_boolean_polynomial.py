"""polynomial generator tests."""

import random

import pytest

from esolangs import tools as boolean
from esolangs.tools.polynomial import _polynomial_dag, _polynomial_states
from tests.tools.boolean_oracles import (
    _polynomial_tree,
)
from tests.tools.boolean_runners import (
    run_polynomial,
)


@pytest.mark.medium
class TestPolynomial:
    def test_uncapped_dag_has_matching_text_bound(self) -> None:
        """Pin and execute the construction matching the language lower bound.

        The public generator keeps its resource cap; composing the existing
        DAG emitter and assembler directly is the language-level witness.
        These are structural envelopes, not a fitted size ratio.
        """
        from esolangs.tools.polynomial import _polynomial_assemble
        from tests.tools.test_boolean_contract import _dense

        for n in range(4, 9):
            table = _dense(n)
            levels = _polynomial_states(table, n)
            ceilings = [2 ** min(k, 2 ** (n - k)) for k in range(n + 1)]
            states = sum(map(len, levels))
            assert all(
                len(level) <= ceiling
                for level, ceiling in zip(levels, ceilings, strict=True)
            )
            assert states <= sum(ceilings)
            assert sum(ceilings) * n <= 8 * 2**n

            instructions = _polynomial_dag(table)
            assert len(instructions) <= 6 * states
            assert all(
                (len(instruction) == 1 and instruction[0] <= 2)
                or (
                    len(instruction) == 2
                    and instruction[1] <= 4
                    and abs(instruction[0]) <= 50 * states + n + 3
                )
                for instruction in instructions
            )

        table = _dense(4)
        instructions = _polynomial_dag(table)
        program = _polynomial_assemble(instructions)
        m = len(instructions)
        operand = max(abs(instruction[0]) for instruction in instructions)
        # The m-th prime is below m**2.  This bounds every factor's l1 norm;
        # multiplying l1 norms bounds every expanded coefficient.
        factor_l1_bound = (operand + 1) ** 2 + m**16
        coefficient_digits = m * len(str(factor_l1_bound))
        rendered_bound = 7 + (2 * m + 1) * (coefficient_digits + len(str(2 * m)) + 6)
        assert len(program) <= rendered_bound
        for row in range(16):
            bits = [(row >> (3 - i)) & 1 for i in range(4)]
            assert run_polynomial(program, [str(bit) for bit in bits]) == table[row]

    def test_wide_table_rejected(self) -> None:
        """The gate is the instruction count, not the input count.

        Each instruction takes a fresh prime and becomes a polynomial
        factor, so what the interpreter cannot afford per row is
        instructions.  A scattered n == 11 table needs 2417 under its
        cheapest construction and is refused; the message names the count
        rather than ``n``.

        The witness has to be re-picked whenever the cap moves: the
        scattered n == 6 witness of the 138 era rendered under the 328 the
        peels bought, and the n == 8 witness of the 328 era renders under
        the 1934 the NTT screens bought, so a stale body silently stops
        exercising the gate.
        """
        random.seed(0)
        scattered = "".join(random.choice("01") for _ in range(2**11))
        with pytest.raises(ValueError, match="groups instructions onto primes"):
            boolean.polynomial(scattered)

    def test_polynomial_cap_admits_every_n10_table(self) -> None:
        """The cap is the analytic worst case over n == 10 tables.

        Level ``k`` of the machine holds at most ``min(2**k, 2**2**(10-k))``
        states -- reachability bounds it by doubling, the subtable width by
        counting -- at 5 instructions plus at most 2 transitions each, and
        the leaf level 5 each less the final endif.  So the cap admits all
        of n == 10 by construction, and the dense fixture sits under it
        with room that is measured, not assumed.
        """
        from esolangs.tools.polynomial import _POLYNOMIAL_MAX_INSTRS

        states = [min(2**k, 2 ** (2 ** (10 - k))) for k in range(11)]
        # Root level 3, every other level 6 per state, two leaves at 6.
        worst = 3 + 6 * (sum(states[:10]) - 1) + 6 * states[10]
        assert worst == 1659
        # The bound stays at the 1934 the previous builder's worst case set:
        # the interpreter was measured to afford it, and a cheaper spelling
        # per state is no reason to refuse a table that fit before.
        assert (
            worst <= _POLYNOMIAL_MAX_INSTRS == 7 * sum(states[:10]) + 5 * states[10] - 1
        )

    def test_state_machine_merges_what_the_tree_cannot(self) -> None:
        """A subtable that is not constant can still collapse to one state.

        ``10101010`` is NOT of the last input: the tree folds nothing and
        spends an internal node per level, while every prefix leaves the
        same residual subfunction, so the machine needs one state per level
        until the last.  This is the merge that makes the construction
        stronger than the fold, rather than another way to spell it.
        """
        table = "10101010"
        assert [len(level) for level in _polynomial_states(table, 3)] == [1, 1, 1, 2]
        assert len(_polynomial_dag(table)) < len(_polynomial_tree(table))
        program = boolean.polynomial(table)
        for combo in range(8):
            bits = [(combo >> (2 - i)) & 1 for i in range(3)]
            assert run_polynomial(program, [str(b) for b in bits]) == table[combo]

    @pytest.mark.slow
    def test_polynomial_screen_slack(self) -> None:
        """The screen's slack is a measurement, and it is arity-dependent.

        Selection is on rendered characters while the screen is on
        instructions, so the shortest render can sit above the cheapest
        candidate.  Every table at n <= 3 needs at most 1; a slack fitted
        there would emit the worse program at n == 4, where 2000 sampled
        tables reach 6.
        """
        from esolangs.tools.polynomial import (
            _POLYNOMIAL_SCREEN_SLACK,
            _polynomial_assemble,
            _polynomial_hybrid,
            _polynomial_hybrid_cost,
        )

        worst = 0
        for n in range(1, 4):
            for value in range(1 << (1 << n)):
                table = format(value, f"0{1 << n}b")
                built = [
                    (_polynomial_hybrid_cost(table, k), _polynomial_hybrid(table, k))
                    for k in range(n + 1)
                ]
                rendered = [
                    (len(_polynomial_assemble(instrs)), cost) for cost, instrs in built
                ]
                shortest = min(length for length, _ in rendered)
                needed = min(cost for length, cost in rendered if length == shortest)
                worst = max(worst, needed - min(cost for cost, _ in built))
        # Pure-``k`` candidates only.
        assert worst == 1
        assert worst <= _POLYNOMIAL_SCREEN_SLACK

    @pytest.mark.parametrize("table", ["00100000", "11011111", "00000010"])
    def test_machine_losing_on_characters_does_not_ship(self, table: str) -> None:
        """Fewer instructions is not fewer characters.

        These three are 35 instructions as a machine against the tree's 36
        and still render longer (4677 characters against 4614 for the
        first), because the machine spends a ``*=`` -- ``p**6`` against a
        ``+=``'s ``p**2`` -- where the tree spends only ``+=``.  The
        dispatch compares *rendered* programs, so they keep the tree's
        emission.  Found by sweeping the n == 3 corpus for tables whose
        fewest-instruction candidate is not the shortest render: five of
        256.
        """
        from esolangs.tools.polynomial import _polynomial_assemble, _polynomial_hybrid

        machine = _polynomial_assemble(_polynomial_hybrid(table, 0))
        tree = _polynomial_assemble(_polynomial_tree(table))
        assert len(_polynomial_hybrid(table, 0)) < len(_polynomial_tree(table))
        assert len(machine) > len(tree)
        assert boolean.polynomial(table) == tree
