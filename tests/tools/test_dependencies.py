"""Exact dependency detection, including late witnesses and fallback."""

import random

from esolangs.tools import helpers


def _oracle(table: str, n: int) -> list[int]:
    return [
        i
        for i in range(n)
        if any(
            table[row] != table[row ^ (1 << (n - 1 - i))] for row in range(len(table))
        )
    ]


def test_dependencies_exhaustive() -> None:
    for n in range(5):
        for value in range(1 << (1 << n)):
            table = format(value, f"0{1 << n}b")
            assert helpers.essential_inputs(table, n) == _oracle(table, n)


def test_dependencies_late_witnesses_and_ignored_inputs() -> None:
    rng = random.Random(929)
    for n in range(5, 11):
        tables = ["0" * (1 << n), "0" * ((1 << n) - 1) + "1"]
        tables += [
            "".join(str((row >> bit) & 1) for row in range(1 << n)) for bit in range(n)
        ]
        tables += ["".join(rng.choice("01") for _ in range(1 << n)) for _ in range(10)]
        for table in tables:
            assert helpers.essential_inputs(table, n) == _oracle(table, n)


def test_dependency_fallback_has_positive_control(monkeypatch) -> None:
    original = helpers._residual_ids  # noqa: SLF001 -- Instrument the fallback positive control.
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
