"""Circuit Diagram's H-tree layout: the side length in closed form."""

from esolangs.tools.circuit_diagram.hlayout import _LATTICE, _h_size


def test_h_side_closed_form() -> None:
    for k in range(64):
        assert _h_size(2 * k) == _LATTICE * (12 * 2**k - 4 * k - 10)
        assert _h_size(2 * k + 1) == _LATTICE * (14 * 2**k - 4 * k - 12)
        assert _h_size(2 * k) ** 2 < 144 * _LATTICE**2 * 2 ** (2 * k)
        assert _h_size(2 * k + 1) ** 2 < 144 * _LATTICE**2 * 2 ** (2 * k + 1)
