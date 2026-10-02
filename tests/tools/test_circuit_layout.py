"""Fast geometry tests for the shared wire-routing layout.

The Circuit Diagram construction tests are ``medium`` because they execute
programs.  These touch ``_RoutingLayout`` directly -- no interpreter, no
build -- so the interval runs and the junction/reservation indexes stay
covered by the fast band, which is the band the touched-file gate reads.
"""

# ruff: noqa: SLF001 - the layout's indexes are the observable here.
from __future__ import annotations

import pytest

from esolangs.tools.circuit_diagram.layout import _RoutingLayout


def test_reserve_replaces_the_owner_and_its_index_entries() -> None:
    """Re-reserving a cell moves it to the new signal's rows and columns."""
    layout = _RoutingLayout()
    layout.reserve((1, 2), 5)
    layout.reserve((1, 2), 5)  # same owner: a no-op
    layout.reserve((1, 2), 6)
    assert layout._reserved == {(1, 2): 6}
    assert layout._reserved_rows == {2: [(1, 6)]}
    assert layout._reserved_cols == {1: [(2, 6)]}


def test_release_keeps_the_other_signals_reservations() -> None:
    """Releasing one signal rebuilds the indexes from what remains."""
    layout = _RoutingLayout()
    layout.reserve((1, 2), 5)
    layout.reserve((3, 2), 6)
    layout.reserve((1, 4), 6)
    layout.release(6)
    assert layout._reserved == {(1, 2): 5}
    assert layout._reserved_rows == {2: [(1, 5)]}
    assert layout._reserved_cols == {1: [(2, 5)]}
    layout.release(5)
    assert not layout._reserved
    assert not layout._reserved_rows
    assert not layout._reserved_cols


def test_route_is_free_rejects_an_interior_wire_of_another_signal() -> None:
    """A run crossing the route's interior blocks it, cell by cell no more."""
    layout = _RoutingLayout()
    layout.run_horizontal(0, 2, 0, 2)
    assert not layout._route_is_free([(0, 0), (2, 0)], 1)


def test_route_is_free_rejects_an_interior_reservation() -> None:
    """A reservation of another signal inside the span blocks the route."""
    layout = _RoutingLayout()
    layout.reserve((1, 0), 2)
    assert not layout._route_is_free([(0, 0), (2, 0)], 1)


def test_route_is_free_rejects_an_interior_junction() -> None:
    """A junction of another signal past the endpoints' neighbourhoods."""
    layout = _RoutingLayout()
    layout.junction(2, 0, 3)
    assert not layout._route_is_free([(0, 0), (4, 0)], 1)


def test_route_is_free_rejects_an_interior_vertical_run() -> None:
    """The vertical span is checked against the vertical runs."""
    layout = _RoutingLayout()
    layout.run_vertical(0, 0, 4, 2)
    assert not layout._route_is_free([(0, 0), (0, 4)], 1)


def test_route_is_free_tolerates_the_same_signal_and_crossings() -> None:
    """A same-signal run or reservation, and a perpendicular crossing, pass."""
    layout = _RoutingLayout()
    layout.reserve((1, 0), 1)
    layout.run_vertical(1, -1, 1, 2)  # crosses the route's row
    assert layout._route_is_free([(0, 0), (2, 0)], 1)


def test_a_second_junction_at_one_cell_is_not_indexed_twice() -> None:
    """The same signal flanking the same cell keeps one index entry."""
    layout = _RoutingLayout()
    layout.junction(5, 5, 1)
    layout.junction(5, 5, 1)
    assert layout._junction_rows == {5: [(5, 1)]}
    assert layout._junction_cols == {5: [(5, 1)]}


def test_a_junction_over_another_signals_run_is_refused() -> None:
    """Coverage is read from the intervals, not a per-cell mirror."""
    layout = _RoutingLayout()
    layout.run_horizontal(0, 2, 0, 2)
    with pytest.raises(AssertionError, match="junction collision at"):
        layout.junction(1, 0, 1)
