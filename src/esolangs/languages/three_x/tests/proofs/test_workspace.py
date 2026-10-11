"""3x keys satisfy the ledger workspace bound."""

from esolangs.languages.three_x.generator import _level
from esolangs.languages.three_x.tests.formulas import _key
from scripts.benchmark import state_bits


def test_three_x_keys_fit_their_bound() -> None:
    """K(i) covers the 41 shortest constants, every key through n = 20."""
    keys: list = []
    length = 0
    while len(keys) < 41:
        length += 1
        keys.extend(_level(length))
    for i, value in enumerate(keys[:41], 1):
        assert state_bits(value, {}) <= _key(i), (i, value)
