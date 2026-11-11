"""Exact dependency detection, including late witnesses and fallback."""

import random
from itertools import product

from esolangs.generation import helpers
from esolangs.generation.algebraic import AffineForm, affine_form, parity_bias
from esolangs.generation.decision import decision_layers, reduced_diagram
from esolangs.generation.lookup import binary_weights
from tests.support.witness_tables import witnesses


def _oracle(table: str, n: int) -> list[int]:
    return [
        i
        for i in range(n)
        if any(
            table[row] != table[row ^ (1 << (n - 1 - i))] for row in range(len(table))
        )
    ]


def test_dependencies_exhaustive() -> None:
    assert not hasattr(helpers, "_parity_bias")
    assert parity_bias("0") == 0
    assert parity_bias("1") == 1
    for n in range(1, 5):
        perm = tuple(reversed(range(n)))
        forms = {
            "".join(
                str(
                    bias
                    ^ (sum(c * b for c, b in zip(coefficients, row, strict=True)) % 2)
                )
                for row in product((0, 1), repeat=n)
            ): AffineForm(bias, coefficients)
            for bias in (0, 1)
            for coefficients in product((0, 1), repeat=n)
        }
        tables = list(forms) + witnesses(n)
        if n <= 3:
            tables += ["".join(bits) for bits in product("01", repeat=1 << n)]
        for table in tables:
            dependencies = _oracle(table, n)
            assert helpers.essential_inputs(table, n) == dependencies
            assert helpers.stored_inputs(table, perm) == {perm[i] for i in dependencies}
            form = forms.get(table)
            assert affine_form(table, n) == form
            assert parity_bias(table) == (
                form.bias if form is not None and all(form.coefficients) else None
            )
            layers = decision_layers(table)
            nodes, root = reduced_diagram(table, n)
            assert len(layers.children) == n
            lookup = helpers.input_weights(table, n)
            assert isinstance(lookup, helpers.WeightedLookup)
            assert (
                tuple(binary_weights([i in dependencies for i in range(n)]))
                == lookup.weights
            )
            for row, bit in zip(product((0, 1), repeat=n), table, strict=True):
                layered, reduced = layers.root, root
                for level, selector in enumerate(row):
                    layered = layers.children[level][layered][selector]
                while reduced > 1:
                    node = nodes[reduced]
                    reduced = node.one if row[node.level] else node.zero
                assert str(layered) == str(reduced) == bit
                assert (
                    lookup.table[
                        sum(w * b for w, b in zip(lookup.weights, row, strict=True))
                    ]
                    == bit
                )
            symmetric = helpers.symmetric_weights(table, n)
            counts: dict[int, set[str]] = {}
            for row, bit in zip(product((0, 1), repeat=n), table, strict=True):
                counts.setdefault(sum(row[i] for i in dependencies), set()).add(bit)
            expected = len(dependencies) >= 2 and all(
                len(v) == 1 for v in counts.values()
            )
            assert (symmetric is not None) == expected
            if symmetric is not None:
                assert isinstance(symmetric, helpers.WeightedLookup)
                assert isinstance(symmetric.weights, tuple)
                for row, bit in zip(product((0, 1), repeat=n), table, strict=True):
                    index = sum(
                        w * b for w, b in zip(symmetric.weights, row, strict=True)
                    )
                    assert symmetric.table[index] == bit


def test_dependencies_late_witnesses_and_ignored_inputs() -> None:
    for n in (11, 12, 16):
        for bias in (0, 1):
            parity = "".join(str((row.bit_count() & 1) ^ bias) for row in range(1 << n))
            assert parity_bias(parity) == bias
            for row in (0, 1, 1023, 1024, 1025, 1 << (n - 1), (1 << n) - 1):
                corrupted = parity[:row] + str(1 - int(parity[row])) + parity[row + 1 :]
                assert parity_bias(corrupted) is None
    rng = random.Random(929)
    for n in range(5, 11):
        for bias in (0, 1):
            parity = "".join(
                str((sum(bits) + bias) % 2) for bits in product((0, 1), repeat=n)
            )
            assert parity_bias(parity) == bias
            late_fault = parity[:-1] + str(1 - int(parity[-1]))
            assert parity_bias(late_fault) is None
        tables = ["0" * (1 << n), "0" * ((1 << n) - 1) + "1"]
        tables += [
            "".join(str((row >> bit) & 1) for row in range(1 << n)) for bit in range(n)
        ]
        tables += ["".join(rng.choice("01") for _ in range(1 << n)) for _ in range(10)]
        for table in tables:
            assert helpers.essential_inputs(table, n) == _oracle(table, n)


def test_dependency_fallback_has_positive_control(monkeypatch) -> None:
    original = helpers._residual_ids
    calls = []

    def record(table, n):
        calls.append(n)
        return original(table, n)

    monkeypatch.setattr(helpers, "_residual_ids", record)
    assert helpers.essential_inputs("01" * 128, 8) == [7]
    assert calls == [8]
    calls.clear()
    parity = "".join(str(row.bit_count() % 2) for row in range(256))
    assert helpers.essential_inputs(parity, 8) == list(range(8))
    assert calls == []


def test_dependency_scan_has_linear_character_budget() -> None:
    class Metered(str):
        scanned = 0

        def __getitem__(self, index):
            value = super().__getitem__(index)
            if isinstance(index, slice):
                self.scanned += len(value)
            return value

    for n in (8, 10, 12):
        table = Metered("01" * (1 << (n - 1)))
        assert helpers.essential_inputs(table, n) == [n - 1]
        assert table.scanned <= 4 * len(table)
        table.scanned = 0
        assert helpers.stored_inputs(table, tuple(reversed(range(n)))) == {0}
        assert table.scanned <= 4 * len(table)
