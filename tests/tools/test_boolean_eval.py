"""Covers :mod:`esolangs.tools.eval_lang`."""

import pytest

from esolangs import tools as boolean
from esolangs.tools.eval_lang import EVAL_ZERO
from esolangs.tools.helpers import TEMPLATE_CHAR

#: One input's run, as the template spells it.
_X = TEMPLATE_CHAR * len(EVAL_ZERO)


class TestEvalBoolean:
    """Input-by-substitution boolean generator for the no-input language Eval."""

    def run_eval(self, prog: str) -> str:
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.stack_based.eval import run

        io_ = ScriptedIO("")
        run(prog, io_)
        return io_.getvalue()

    def instantiate(self, tpl: str, bits: list[int]) -> str:
        """Fill the template the way the example harness does."""
        from tests.tools.fills import _fill_eval

        return _fill_eval(tpl, bits)

    def test_both_bits_embed_at_the_same_width(self) -> None:
        """The setter is two characters whichever bit it carries."""
        from tests.tools.fills import _fill_eval

        for n in (1, 2, 3):
            template = _X * n
            for i in range(n):
                zeros = [0] * n
                ones = list(zeros)
                ones[i] = 1
                assert len(_fill_eval(template, zeros)) == len(
                    _fill_eval(template, ones)
                ), f"n={n} input {i}"

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
            ("01101001", 3),  # XOR3
            ("1000000000000000", 4),  # AND4
            ("1111111100000000", 4),  # top half
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        """Every instantiated input produces the truth-table result."""
        from esolangs.tools import parameterized

        template = parameterized.eval(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = self.run_eval(self.instantiate(template, bits))
            assert got == str(int(table[combo])), f"inputs {bits}"

    @pytest.mark.parametrize("n", [1, 2, 3])
    def test_all_small_tables(self, n: int) -> None:
        """Every table up to three inputs produces the right result."""
        from esolangs.tools import parameterized

        for table_int in range(2 ** (2**n)):
            table = format(table_int, f"0{2**n}b")
            template = parameterized.eval(table)
            for combo in range(2**n):
                bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
                got = self.run_eval(self.instantiate(template, bits))
                assert got == str(int(table[combo])), f"{table} inputs {bits}"

    def test_ignored_inputs_shrink_the_lookup(self) -> None:
        """A constant table pushes one result and only drains its inputs."""
        from esolangs.tools import parameterized

        full = parameterized.eval("10010110")
        folded = parameterized.eval("11111111")
        assert len(folded) < len(full)
        assert folded == _X * 3 + "`~;~~;~~;~."

    def test_folding_keeps_both_bits_equal_width(self) -> None:
        """Folding shrinks the template, never one instantiation.

        The embedding's whole point is that ``len(program)`` cannot reveal
        the inputs.  A fold that depended on the bits would reintroduce
        exactly that leak, so this pins equal width on folded tables too.
        """
        from esolangs.tools import parameterized

        for table in ("11111111", "11110000", "11001100", "0001"):
            n = len(table).bit_length() - 1
            template = parameterized.eval(table)
            widths = {
                len(
                    self.instantiate(
                        template, [(c >> (n - 1 - i)) & 1 for i in range(n)]
                    )
                )
                for c in range(2**n)
            }
            assert len(widths) == 1, f"{table} leaks its inputs: {widths}"

    def test_template_is_input_independent(self) -> None:
        """The template has one run per input, not hardcoded bits."""
        from esolangs.tools import parameterized

        template = parameterized.eval("0110")
        assert "{X" not in template
        assert template.count(TEMPLATE_CHAR) == 2 * len(EVAL_ZERO)

    def test_linear_lookup_structure(self) -> None:
        """Each level shares one half-stack discard between both branches."""
        from esolangs.tools import parameterized

        template = parameterized.eval("0110")
        assert template.startswith(_X * 2)
        assert template.endswith(".")
        assert '"' not in template
        assert "!" not in template
        assert template.count("~^=~?*") == 2
        assert template.count("~=~?*") == 2
        assert template.removeprefix(_X * 2).startswith("0``0")
        assert template.count(";") == 3  # shared discards of 2 and 1

    def test_reordering_is_not_part_of_the_lookup(self) -> None:
        """The free staged order is always shortest for the linear lookup."""
        from esolangs.tools import parameterized
        from esolangs.tools.helpers import permute_truth_table
        from esolangs.tools.parameterized import _eval_ordered

        # Staging pushes X0 first, so the free arrangement's split order is
        # the reversal -- the no-ops build is not the identity permutation.
        free = tuple(reversed(range(3)))
        for value in range(256):
            table = format(value, "08b")
            dispatched = len(parameterized.eval(table))
            staged = len(_eval_ordered(permute_truth_table(table, free), ""))
            assert dispatched == staged, table

    def test_reorder_cost_selects_the_emitted_template(self) -> None:
        """The pricing model matches every candidate and picks the shortest."""
        from esolangs.tools.helpers import permute_truth_table
        from esolangs.tools.parameterized import (
            _eval_cost,
            _eval_ordered,
            _eval_stack_programs,
        )

        for n in (1, 2, 3):
            for value in range(2 ** (2**n)):
                table = format(value, f"0{2**n}b")
                costs = []
                for arrangement, ops in _eval_stack_programs(n).items():
                    permuted = permute_truth_table(table, tuple(reversed(arrangement)))
                    assert _eval_cost(permuted, ops) == len(
                        _eval_ordered(permuted, ops)
                    )
                    costs.append(_eval_cost(permuted, ops))
                assert len(boolean.eval(table)) == min(costs)

    def test_reorder_ops_run_outside_the_placeholders(self) -> None:
        """The rearrangement is emitted code, not a change to the fills.

        This is what makes it a reorder rather than a relabelling: the
        input runs keep their places and the harness fills them exactly
        as before, while the emitted program gains ops that rearrange the
        stack its nodes pop from.  Equal-width embedding therefore still
        holds, since nothing inside a run moved.
        """
        from esolangs.tools import parameterized
        from tests.tools.fills import _fill_eval

        # A table whose cheapest order is not the free one.
        table = "00001101"
        template = parameterized.eval(table)
        assert template.startswith(_X * 3)  # runs unmoved
        widths = {
            len(_fill_eval(template, [(c >> (2 - i)) & 1 for i in range(3)]))
            for c in range(8)
        }
        assert len(widths) == 1  # every fill the same length

    def test_stack_ops_reach_every_arrangement(self) -> None:
        """Two stacks with a reverse and a cross-move permute the bits.

        ``~`` switches stacks, ``*`` reverses the active one and ``=`` moves
        its top across; the pair is a spindle, so the three compose to reach
        every arrangement at n <= 4.  Unlike Forþ's ``o``, ``*`` is usable
        here because the staging leaves the bits alone on that stack.
        """
        from math import factorial

        from esolangs.tools.parameterized import _eval_stack_programs

        for n in (2, 3, 4):
            assert len(_eval_stack_programs(n)) == factorial(n)
        # The free arrangement is the one staging produces, and costs nothing.
        assert _eval_stack_programs(3)[(0, 1, 2)] == ""

    def test_reorder_catalog_invariants(self) -> None:
        """The built words are capped, deduplicated and (length, ~<*<=)-sorted.

        The sort order is required: ``_eval_stack_programs`` folds the
        words first-claim-wins, so cheapest-first is what makes every
        claimed string minimal, and the ``~`` < ``*`` < ``=`` tie order is
        what keeps the fold byte-identical to the search it replaced.
        """
        from esolangs.tools.parameterized import (
            _EVAL_MAX_OPS,
            _eval_reorders,
        )

        built = _eval_reorders()
        assert len(set(built)) == len(built)
        assert built[0] == ""
        assert all(len(ops) <= _EVAL_MAX_OPS for ops in built)
        rank = {"~": 0, "*": 1, "=": 2}
        keys = [(len(ops), [rank[op] for op in ops]) for ops in built]
        assert keys == sorted(keys)

    def test_reorder_words_are_the_capped_reachable_set(self) -> None:
        """Every built word replays, and the built set is exactly the cap's.

        The construction admits words the old catalog never listed -- longer
        spellings of arrangements a shorter word already claims -- so the
        pin is on what survives the fold, not on the raw word list.  The
        count that must hold is the arrangement count: 735 from ``n == 12``
        on, which is where the catalog froze.
        """
        from esolangs.tools.parameterized import _eval_stack_programs

        assert len(_eval_stack_programs(12)) == 735
        assert len(_eval_stack_programs(13)) == 735
        assert len(_eval_stack_programs(7)) == 620
        assert len(_eval_stack_programs(4)) == 24

    def test_reorder_catalog_matches_search(self) -> None:
        """The catalog fold reproduces the search it replaced, byte for byte.

        The breadth-first walk over (tree stack, input stack, active stack)
        that used to run inside ``_eval_stack_programs`` lives on here as
        the specification.  Equality is asserted on the item *lists*, not
        the dicts: the shipped fold must claim the same arrangements with
        the same op strings in the same order, because ``eval``'s stable
        sort breaks total-length ties by that order.
        """
        from collections import deque

        from esolangs.tools.parameterized import (
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
        from esolangs.tools import parameterized

        sizes = []
        for width in range(6, 13):
            parity = "".join(str(i.bit_count() & 1) for i in range(2**width))
            sizes.append(len(parameterized.eval(parity)) / len(parity))
        assert sizes == sorted(sizes, reverse=True)
        assert sizes[-1] < 2.1

        n = 6
        table = "".join("1" if bin(i).count("1") % 2 else "0" for i in range(2**n))
        template = parameterized.eval(table)
        # The template is the exact shape of every program it fills to.
        assert len(template) == len(self.instantiate(template, [0] * n)) == 206
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = self.run_eval(self.instantiate(template, bits))
            assert got == str(int(table[combo])), f"inputs {bits}"
