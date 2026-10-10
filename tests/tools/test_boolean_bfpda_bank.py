"""Native controls for BF-PDA residual words and correlated admission prices."""

import random

import pytest

from esolangs.tools.bfpda import _bfpda_tree, _prepare, _reflected, bfpda
from esolangs.tools.bfpda._bank import _body_metrics, _price, best_bank
from tests.tools.test_boolean_bfpda import _execute_bank


def _fixture(words, pattern, core_bits):
    depth = (len(pattern)).bit_length() - 1
    ignored = 16 - depth - core_bits
    blocks = tuple(word * (1 << ignored) for word in words)
    table = _reflected("".join(blocks[int(label)] for label in pattern), 16)
    context = _prepare(table)
    states = tuple(dict.fromkeys(context.ids[depth]))
    metric = _price(context, depth, states, _body_metrics(context))
    candidate, _ = _bfpda_tree(table, classes=blocks, class_depth=depth)
    assert len(candidate) == metric.size
    return table, candidate, metric, depth, ignored


def _rows(start, stop, depth, core_bits, ignored):
    def reflected(row, padding):
        value = (row >> core_bits) << (16 - depth)
        value |= (padding << core_bits) | (row & ((1 << core_bits) - 1))
        return int(f"{value:016b}"[::-1], 2)

    return [
        reflected(row, padding)
        for row in range(start, stop)
        for padding in (0, (1 << ignored) - 1)
    ]


@pytest.mark.medium
@pytest.mark.parametrize(
    ("words", "pattern"),
    [
        (("0000", "0110", "0001"), "01221012"),
        (tuple(f"{word:04b}" for word in range(1, 9)), "0123456776543210"),
    ],
)
def test_non_power_of_two_words_and_three_bit_words_cover_all_paths(words, pattern):
    table, candidate, metric, depth, ignored = _fixture(words, pattern, 2)
    assert metric.commands <= 162
    assert len(bfpda(table)) <= len(candidate)
    maximum = _execute_bank(
        table, candidate, _rows(0, 1 << (depth + 2), depth, 2, ignored)
    )
    assert maximum == metric.commands


@pytest.mark.medium
@pytest.mark.parametrize("seed", [73031, 73032, 73033])
@pytest.mark.parametrize("start", range(0, 512, 64))
def test_four_class_cap_bank_covers_every_essential_row(seed, start):
    rng = random.Random(seed)
    words = tuple("".join(str(rng.randrange(2)) for _ in range(64)) for _ in range(4))
    table, candidate, metric, depth, ignored = _fixture(words, "01233021", 6)
    assert metric.commands <= 162
    program = bfpda(table)
    assert len(program) <= len(candidate)
    plain, _ = _bfpda_tree(table)
    assert len(program) < len(plain)
    rows = _rows(start, start + 64, depth, 6, ignored)
    assert _execute_bank(table, candidate, rows) <= metric.commands
    _execute_bank(table, program, rows)


@pytest.mark.parametrize("classes", [("0001",), ("0001", "0001")])
def test_invalid_labels_abort(classes):
    with pytest.raises(ValueError, match="distinct residuals"):
        _bfpda_tree("0001" * 8, classes=classes, class_depth=3)


def test_word_must_fit_the_retired_stack():
    classes = ("0001", "0110", "0011", "0101")
    with pytest.raises(ValueError, match="retired stack"):
        _bfpda_tree(_reflected("".join(classes), 4), classes=classes)


def test_bank_keeps_existing_paths_when_no_candidate_is_admissible():
    table = _reflected("0001011000110101", 4)
    context = _prepare(table)
    assert best_bank(table, context, 42, 10000) is None
    assert best_bank(table, context, 10000, 0) is None


def test_emitter_drift_aborts(monkeypatch):
    from importlib import import_module

    module = import_module("esolangs.tools.bfpda")
    words = tuple(f"{word:04b}" for word in range(1, 9))
    table, _, _, _, _ = _fixture(words, "0123456776543210", 2)
    monkeypatch.setattr(module, "_bfpda_tree", lambda *_args, **_kwargs: (".", 1))
    with pytest.raises(ValueError, match="disagrees with its price"):
        best_bank(table, _prepare(table), 162, 10000)
