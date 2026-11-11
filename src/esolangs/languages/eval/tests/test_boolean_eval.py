"""Covers :mod:`esolangs.languages.eval.generator`."""

from collections import deque
from math import factorial
from unittest.mock import patch

import esolangs
from esolangs.generation.helpers import TEMPLATE_CHAR, permute_truth_table
from esolangs.languages.eval import generator as boolean
from esolangs.languages.eval.generator import PAIR, eval_setters
from esolangs.languages.eval.tests.eval_support import (
    _eval_ordered,
    _eval_stack_programs,
)
from esolangs.runtime.io import ScriptedIO
from scripts.docs.evidence import construction_boundaries
from tests.support.analysis_support import assert_analysis_complement
from tests.support.generator_support import assert_saved_rows, constant_artifacts
from tests.support.witness_tables import row_bits

#: One input's run, as the template spells it.
_X = TEMPLATE_CHAR * len(PAIR[0])


class TestEvalBoolean:
    """Input-by-substitution boolean generator for the no-input language Eval."""

    def run_eval(self, prog: str) -> str:
        from esolangs.languages.eval.interpreter import run

        io_ = ScriptedIO("")
        run(prog, io_)
        return io_.getvalue()

    def instantiate(self, tpl: esolangs.TemplateArtifact, bits: list[int]) -> str:
        """Fill the template the way the example harness does."""
        return esolangs.instantiate("Eval", tpl, bits).source

    def test_ignored_inputs_shrink_the_lookup(self) -> None:
        """A constant table pushes one result; its staged inputs never drain."""
        from tests.support.witness_tables import parity

        assert not {"_EVAL_TREE_STACK", "_EVAL_READ_STACK"} & vars(boolean).keys()
        assert_analysis_complement("Eval", "read_at")
        assert_analysis_complement("Eval", "read_at", parity(6))
        _check_constants()
        full = boolean.eval("10010110")
        folded = boolean.eval("11111111")
        assert len(folded) < len(full)
        assert folded == TEMPLATE_CHAR * 3 + "`."

    def test_folding_keeps_both_bits_equal_width(self) -> None:
        """Folding shrinks the template, never one instantiation."""
        for table in ("11111111", "11110000", "11001100", "0001"):
            n = len(table).bit_length() - 1
            template = esolangs.generate("Eval", table)
            widths = {
                len(self.instantiate(template, row_bits(c, n))) for c in range(2**n)
            }
            assert len(widths) == 1, f"{table} leaks its inputs: {widths}"

    def test_template_is_input_independent(self) -> None:
        """The template has one run per input, not hardcoded bits."""
        template = boolean.eval("0110")
        assert "{X" not in template
        assert template.count(TEMPLATE_CHAR) == 2 * len(PAIR[0])

    def test_reordering_is_not_part_of_the_lookup(self) -> None:
        """The free staged order is always shortest for the linear lookup."""
        from esolangs.languages.eval.tests.ablations import ablate

        # Staging pushes X0 first, so the free arrangement's split order is
        # the reversal -- the no-ops build is not the identity permutation.
        free = tuple(reversed(range(3)))
        for value in range(256):
            table = format(value, "08b")
            assert boolean.eval(table) == ablate(table, "default")
            dispatched = len(boolean.eval(table))
            staged = len(_eval_ordered(permute_truth_table(table, free), ""))
            assert dispatched == staged - (3 if len(set(table)) == 1 else 0), table

    def test_reorder_cost_selects_the_emitted_template(self) -> None:
        """The pricing model matches every candidate and picks the shortest."""
        for n in (1, 2, 3):
            for value in range(2 ** (2**n)):
                table = format(value, f"0{2**n}b")
                costs = []
                for arrangement, ops in _eval_stack_programs(n).items():
                    permuted = permute_truth_table(table, tuple(reversed(arrangement)))
                    costs.append(len(_eval_ordered(permuted, ops)))
                if len(set(table)) == 1:
                    costs.append(n + 2)
                assert len(boolean.eval(table)) == min(costs)

    def test_reorder_ops_run_outside_the_placeholders(self) -> None:
        """The rearrangement is emitted code, not a change to the fills."""
        # A table whose cheapest order is not the free one.
        table = "00001101"
        template = esolangs.generate("Eval", table)
        assert template.source.startswith(_X * 3)  # runs unmoved
        widths = {
            len(self.instantiate(template, [(c >> (2 - i)) & 1 for i in range(3)]))
            for c in range(8)
        }
        assert len(widths) == 1  # every fill the same length

    def test_stack_ops_reach_every_arrangement(self) -> None:
        """Two stacks with a reverse and a cross-move permute the bits."""
        for n in (2, 3, 4):
            assert len(_eval_stack_programs(n)) == factorial(n)
        # The free arrangement is the one staging produces, and costs nothing.
        assert _eval_stack_programs(3)[(0, 1, 2)] == ""

    def test_reorder_words_are_the_capped_reachable_set(self) -> None:
        """Every built word replays, and the built set is exactly the cap's."""
        assert len(_eval_stack_programs(12)) == 735
        assert len(_eval_stack_programs(13)) == 735
        assert len(_eval_stack_programs(7)) == 620
        assert len(_eval_stack_programs(4)) == 24

    def test_reorder_catalog_matches_search(self) -> None:
        """The catalog fold reproduces the search it replaced, byte for byte."""
        from esolangs.languages.eval.tests.eval_support import (
            _EVAL_MAX_OPS,
            _eval_stack_programs,
        )

        def searched(n: int) -> dict[tuple[int, ...], str]:
            start: tuple[tuple[int, ...], tuple[int, ...], int] = (
                (),
                tuple(range(n)),
                0,
            )
            seen = {start: ""}
            frontier = deque([start])
            reached: dict[tuple[int, ...], str] = {}
            while frontier:
                state = frontier.popleft()
                tree, read, active = state
                ops = seen[state]
                if active == 0 and not tree and read not in reached:
                    reached[read] = ops
                if len(ops) >= _EVAL_MAX_OPS:
                    continue
                stacks = {0: tree, 1: read}
                moves = [((tree, read, 1 - active), "~")]
                flipped = tuple(reversed(stacks[active]))
                moves.append(
                    ((flipped, read, active), "*")
                    if active == 0
                    else ((tree, flipped, active), "*")
                )
                if stacks[active]:
                    moved, rest = stacks[active][-1], stacks[active][:-1]
                    other = (*stacks[1 - active], moved)
                    moves.append(
                        ((rest, other, active), "=")
                        if active == 0
                        else ((other, rest, active), "=")
                    )
                for next_state, op in moves:
                    if next_state not in seen:
                        seen[next_state] = ops + op
                        frontier.append(next_state)
            return reached

        for n in range(6):
            assert list(_eval_stack_programs(n).items()) == list(searched(n).items())

    def test_scales_to_more_inputs(self) -> None:
        """Size stays linear and a wider generated program executes."""
        sizes = []
        for width in range(6, 13):
            parity = "".join(str(i.bit_count() & 1) for i in range(2**width))
            sizes.append(len(boolean.eval(parity)) / len(parity))
        assert sizes == sorted(sizes, reverse=True)
        assert sizes[-1] < 2.1

        n = 6
        table = "".join("1" if (i).bit_count() % 2 else "0" for i in range(2**n))
        template = esolangs.generate("Eval", table)
        # The template is the exact shape of every program it fills to.
        assert len(template.source) == len(self.instantiate(template, [0] * n)) == 167
        for combo in range(2**n):
            bits = row_bits(combo, n)
            got = self.run_eval(self.instantiate(template, bits))
            assert got == str(int(table[combo])), f"inputs {bits}"

    def test_two_stack_build_computes_its_table(self) -> None:
        """The new cutoff keeps one-stack n4/5 and two-stack n6/7 correct."""
        language = esolangs.Language("Eval")
        for witness in construction_boundaries(language.name)[
            "one_to_two_stack_lookup_cutoff"
        ]:
            n, table = witness.arity, witness.table()
            with patch.object(boolean, "_eval_dual", wraps=boolean._eval_dual) as dual:
                artifact = language.generate(table)
            assert dual.call_count == int(n == 6)
            assert artifact.source.count(TEMPLATE_CHAR) == (2 if n == 5 else 3) * n
            assert_saved_rows(language, artifact, table, range(len(table)))

        for table in (
            "".join("1" if (i).bit_count() % 2 else "0" for i in range(2**5)),
            "0" * 31 + "1",
            "0110100110010110",
            "".join(str(i.bit_count() % 2) for i in range(64)),
            "0" * 127 + "1",
        ):
            n = len(table).bit_length() - 1
            template = esolangs.generate("Eval", table)
            assert template.source.count(TEMPLATE_CHAR) == (3 if n >= 6 else 2) * n
            for combo in range(2**n):
                program = self.instantiate(template, row_bits(combo, n))
                assert self.run_eval(program) == table[combo], (table, combo)


def _check_constants() -> None:
    from esolangs.languages.eval.interpreter import run

    for n, bit, _options, template in constant_artifacts("Eval", range(1, 13)):
        assert template.source.count("$") == n
        assert eval_setters(template.source, n) == (("0", "`"),) * n
        for bits in ([0] * n, [1] * n):
            program = esolangs.instantiate("Eval", template, bits)
            io = ScriptedIO("7")
            run(program.source, io)
            assert io.getvalue() == bit
            assert io.reads == 0
            assert io.input_char() == ord("7")
