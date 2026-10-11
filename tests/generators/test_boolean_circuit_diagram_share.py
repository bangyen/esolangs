"""Circuit Diagram's shared fold is area-smaller but not linear-area.

``circuit_diagram`` admits the cofactor-sharing bus fold only while its
distinct node count keeps the layout within ``nodes**2 <= 4*T``.  Past that it
falls back to the H-layout, a minterm lattice that is Theta(T) area but never
shares the repeated cofactors.  The gap is a layout, not a better fold: the
shared model is several times smaller for these tables, yet grows faster than
the linearity contract (x4.4, same-parity) allows.  These controls pin the
rejection, the growth, and the fallback that loses the sharing.
"""

from __future__ import annotations

import hashlib

from esolangs.tools.circuit_diagram import (
    _circuit_diagram_model,
    _dag,
    _linear_shared_layout,
    circuit_diagram,
)
from esolangs.tools.circuit_diagram.hlayout import _h_term_layout


def _dense(n: int) -> str:
    """The linearity test's sha256 stream table for ``n`` inputs."""
    digest = hashlib.sha256(f"dense:{n}".encode()).digest()
    bits: list[str] = []
    block = 0
    while len(bits) < 2**n:
        digest = hashlib.sha256(digest + bytes([block & 255])).digest()
        bits.extend(str(byte & 1) for byte in digest)
        block += 1
    return "".join(bits[: 2**n])


def _area(model) -> int:
    height, width = model.bounds()
    return height * width


class TestCircuitDiagramShareScope:
    """The wall: a smaller shared fold the node cutoff refuses to admit."""

    def test_shared_fold_is_smaller_but_rejected_by_the_node_cutoff(self) -> None:
        table = _dense(8)
        nodes = len(_dag(table, 8)[0])
        assert nodes**2 > 4 * len(table)  # over the admission cutoff
        assert _area(_circuit_diagram_model(table, None)) < _area(_h_term_layout(table))
        assert _linear_shared_layout(table, 8) is None

    def test_the_public_build_falls_back_to_the_unshared_h_layout(self) -> None:
        table = _dense(8)
        assert circuit_diagram(table) == _h_term_layout(table).render()

    def test_shared_fold_growth_exceeds_the_linear_contract(self) -> None:
        """Same-parity size difference n=8->10 against the x4.4 contract."""
        shared = _area(_circuit_diagram_model(_dense(10), None)) / _area(
            _circuit_diagram_model(_dense(8), None)
        )
        hlay = _area(_h_term_layout(_dense(10))) / _area(_h_term_layout(_dense(8)))
        assert round(shared, 3) == 4.926
        assert hlay <= 4.4 < shared
