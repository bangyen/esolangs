"""Circlefuck boolean generation, ordering and folding."""

import random

import pytest

from esolangs import tools as boolean
from tests.tools.boolean_runners import run_circlefuck


class TestCirclefuck:
    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("10", 1),  # NOT
            ("0110", 2),  # XOR
            ("0001", 2),  # AND
            ("11111110", 3),  # NAND3
            ("1111111111111111", 4),  # constant one
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        """Every input combination produces the truth-table result."""
        program = boolean.circlefuck(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_circlefuck(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

    @pytest.mark.parametrize(
        ("values", "n"),
        [
            ([0, 255], 1),
            ([48, 49, 50, 51], 2),
        ],
    )
    def test_byte_values(self, values: list[int], n: int) -> None:
        """The byte tree under the generator prints the leaf's byte."""
        from esolangs.tools.circlefuck import _best_byte_order

        program = _best_byte_order(values, n)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_circlefuck(program, [str(b) for b in bits])
            assert got == chr(values[combo]), f"inputs {bits}"

    def test_identity_and_greedy_are_the_only_candidates(self) -> None:
        """The two candidates are counted and the selected one is executed."""
        import importlib

        # The package re-exports the generator under the submodule's own
        # name, so import the module explicitly rather than by attribute.
        module = importlib.import_module("esolangs.tools.circlefuck")
        from esolangs.tools.circlefuck import _circlefuck_ordered

        table = "01" * 64  # alternating: the greedy pick is not the identity
        built = 0
        ordered = _circlefuck_ordered

        def counted(
            values: list[int],
            perm: tuple[int, ...],
            _build: object = ordered,
        ) -> str:
            nonlocal built
            built += 1
            return _build(values, perm)  # type: ignore[operator, no-any-return]

        with pytest.MonkeyPatch.context() as patch:
            patch.setattr(module, "_circlefuck_ordered", counted)
            program = boolean.circlefuck(table)
        assert built == 2, f"built {built} candidates, not identity plus greedy"

        for combo in range(128):
            bits = [(combo >> (6 - i)) & 1 for i in range(7)]
            got = run_circlefuck(program, [str(b) for b in bits])
            assert got == table[combo], f"inputs {bits}"

    def test_constant_subtrees_fold(self) -> None:
        """A constant slice prints its answer instead of branching further.

        Circlefuck branches on the cell the pointer is over, so the split
        axis used to be fixed to the last input and only tables constant
        along *that* axis folded -- ``11110000`` folded nothing and cost
        the same as a scattered table.  The tree now picks its order, so
        both single-dependency tables fold to one branch.

        Their layouts need not be equal because pointer walks are a real
        cost; both must still beat an unfolded table.
        """
        assert len(boolean.circlefuck("11111111")) < len(
            boolean.circlefuck("10101010"),
        )
        assert len(boolean.circlefuck("10101010")) < len(
            boolean.circlefuck("10010110"),
        )
        walked = len(boolean.circlefuck("11110000"))
        assert walked <= len(boolean.circlefuck("10010110"))

    def test_folded_leaf_clears_its_cell(self) -> None:
        """A folded leaf builds its value on a cleared cell.

        The ``[-]`` a full-depth leaf relies on is emitted inside each
        ``[`` on the way down, so a leaf that skips those levels has to
        clear the cell itself.  Without it the cell still holds the input
        bit and every one-valued input prints one too high -- which only
        shows on an input of ``1``, so it is worth pinning per input.
        """
        program = boolean.circlefuck("11111111")
        for combo in range(8):
            bits = [(combo >> (2 - i)) & 1 for i in range(3)]
            got = run_circlefuck(program, [str(b) for b in bits])
            assert got == "1", f"inputs {bits}"


def _constant_subtree_count(truth_table: list[int], n: int, prefix: list[int]) -> int:
    """The one-prefix scorer the greedy used to call once per candidate."""
    buckets: dict[int, set[int]] = {}
    for row in range(len(truth_table)):
        key = 0
        for i in prefix:
            key = (key << 1) | ((row >> (n - 1 - i)) & 1)
        buckets.setdefault(key, set()).add(truth_table[row])
    return sum(1 for values in buckets.values() if len(values) == 1)


@pytest.mark.parametrize("seed", range(40))
def test_circlefuck_scores_every_candidate_as_the_one_prefix_count(seed: int) -> None:
    """One pass scores all inputs exactly as scoring each prefix did.

    Byte tables, since the tree scores on bytes: the masks are
    kept per distinct value, not per bit.
    """
    from esolangs.tools.circlefuck import _constant_subtree_scores

    rng = random.Random(seed)
    n = rng.randint(1, 7)
    table = [rng.choice((48, 49, 7)) if rng.random() < 0.7 else 48 for _ in range(2**n)]
    prefix = rng.sample(range(n), rng.randint(0, n))
    keys = [0] * 2**n
    for i in prefix:
        keys = [(key << 1) | ((row >> (n - 1 - i)) & 1) for row, key in enumerate(keys)]
    scores = _constant_subtree_scores(table, n, keys)
    assert scores == [_constant_subtree_count(table, n, [*prefix, i]) for i in range(n)]


@pytest.mark.parametrize("seed", range(40))
def test_circlefuck_essential_inputs_are_the_ones_flipping_changes(seed: int) -> None:
    """The sibling-block scan finds exactly the inputs the table depends on."""
    from esolangs.tools.circlefuck import _essential_byte_inputs

    rng = random.Random(seed)
    n = rng.randint(1, 8)
    # A function of a random subset of the inputs, so most are inessential.
    subset = sorted(rng.sample(range(n), rng.randint(0, n)))
    values = [rng.choice((48, 49, 7)) for _ in range(2 ** len(subset))]
    table = []
    for row in range(2**n):
        index = 0
        for i in subset:
            index = (index << 1) | ((row >> (n - 1 - i)) & 1)
        table.append(values[index])
    expected = [
        i
        for i in range(n)
        if any(table[row] != table[row ^ (1 << (n - 1 - i))] for row in range(2**n))
    ]
    assert _essential_byte_inputs(table, n) == expected


def test_circlefuck_emits_the_permuted_tree_without_a_permuted_table() -> None:
    """Indexing the stream-order table per node equals building the permuted copy.

    The fold is settled bottom-up before emission, so this also pins that a
    node folds exactly when every row it reaches agrees.
    """
    from esolangs.tools.circlefuck import _circlefuck_ordered

    def permuted(table: list[int], perm: tuple[int, ...]) -> list[int]:
        n = len(perm)
        out = [0] * len(table)
        for row in range(len(table)):
            source = 0
            for i in range(n):
                source |= ((row >> (n - 1 - i)) & 1) << (n - 1 - perm[i])
            out[row] = table[source]
        return out

    def reference(table: list[int], perm: tuple[int, ...]) -> str:
        # The emitter as it was: a permuted copy, and each node scanning its
        # rows for agreement.
        n = len(perm)
        frame = permuted(table, perm)
        prog: list[str] = []
        for _ in range(n):
            prog.append(",")
            prog.extend("-" * 48)
            prog.append(">")
        prog.pop()

        def build(k: int, row: int, cell: int) -> None:
            if k < 0:
                if frame[row]:
                    prog.extend("+" * frame[row])
                prog.append(".")
                prog.append("@")
                return
            if len({frame[r] for r in range(row, len(frame), 2 ** (n - 1 - k))}) == 1:
                prog.append("[-]")
                build(-1, row, cell)
                return
            target = perm[k]
            step = ">" if target > cell else "<"
            prog.extend(step * abs(target - cell))
            prog.append("[")
            prog.append("[-]")
            build(k - 1, row + 2 ** (n - 1 - k), target)
            prog.append("]")
            build(k - 1, row, target)

        build(n - 1, 0, n - 1)
        return "".join(prog)

    rng = random.Random(7)
    for n in range(1, 8):
        for _ in range(6):
            table = [
                rng.choice((48, 49)) if rng.random() < 0.8 else 48 for _ in range(2**n)
            ]
            perm = list(range(n))
            rng.shuffle(perm)
            order = tuple(perm)
            assert _circlefuck_ordered(table, order) == reference(table, order)


def test_circlefuck_greedy_spends_a_fixed_number_of_passes() -> None:
    """The order is settled in at most ``_CIRCLEFUCK_PASSES + 1`` scoring passes.

    One pass is one walk over the rows, so this is the bound that makes the
    order O(T): the essential inputs past the last pass follow its scores,
    and every table with that many essential inputs or fewer gets the full
    greedy.
    """
    import importlib

    from esolangs.tools.circlefuck import (
        _CIRCLEFUCK_PASSES,
        _circlefuck_greedy,
        _constant_subtree_scores,
    )

    module = importlib.import_module("esolangs.tools.circlefuck")
    scorer = _constant_subtree_scores
    passes = 0

    def counted(table: list[int], n: int, keys: list[int]) -> list[int]:
        nonlocal passes
        passes += 1
        return scorer(table, n, keys)

    rng = random.Random(3)
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(module, "_constant_subtree_scores", counted)
        for n in (4, 8, 10, 12):
            table = [rng.choice((48, 49)) for _ in range(2**n)]
            passes = 0
            _circlefuck_greedy(table, n)
            assert passes == min(n, _CIRCLEFUCK_PASSES) + (n > _CIRCLEFUCK_PASSES)
    # and an inessential input never costs a pass
    table = [48 + ((row >> 9) & 1) for row in range(2**12)]  # depends on one input
    passes = 0
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(module, "_constant_subtree_scores", counted)
        program = _circlefuck_greedy(table, 12)
    assert passes == 1
    assert program.count("[") - program.count("[-]") == 1  # a single branch
