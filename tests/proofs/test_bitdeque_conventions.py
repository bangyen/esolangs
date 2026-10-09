"""Bitdeque's linear route, which the equal-width test misses."""

import itertools

from tests.proofs.test_conventions import _embedding, _tables


def test_bitdeque_linear_route_is_one_width() -> None:
    """The route the equal-width test misses stays at one length."""
    example = _embedding()["Bitdeque"]
    assert example.fill is not None
    for n in (4, 5):
        template = example.generator(_tables(n)[0])
        lengths = {
            len(example.fill(template, list(bits)))
            for bits in itertools.product((0, 1), repeat=n)
        }
        assert len(lengths) == 1, (n, sorted(lengths))
