"""Streetcode construction-time checks: street shape and drive-state graph.

Each shape check is a function returning a violation message or ``None``;
:func:`_reject` is the one place a message becomes a ``ValueError``.
:func:`validate_street` runs them in order and returns the drive-state graph.
"""

from collections import deque
from typing import Literal

from esolangs.languages.streetcode.interpreter.geometry import (
    _DELTA,
    _NO_LATCHES,
    _WALL_FORMS,
    _WALLS,
    _drive,
    _drives_on_the_right,
    _Grid,
    _initial_heading,
    _matches,
    _ReachableCell,
    _require,
    _State,
)
from esolangs.runtime.source_hints import syntax_error

# A state's successors, keyed by the two branch bits movement can read in
# one step: the arrival cell and the post-instruction cell, in that order.
type _Edges = dict[tuple[int, int], _State | Literal["halt"] | None]


def _reject(violation: str | None, hint: str) -> None:
    """Raise ``ValueError`` carrying ``violation`` and ``hint``, if there is one."""
    if violation is not None:
        raise syntax_error(violation, hint)


def validate_street(grid: _Grid, start: tuple[int, int]) -> dict[_State, _Edges] | None:
    """Reject a malformed street network; return its drive-state graph.

    :func:`validate_width` computes the reachable set every other check
    reads.  ``None`` means the grid is not a street (no walls, or an isolated
    ``C``), which has no graph and is driven by calling :func:`_drive`.
    """
    reachable = validate_width(grid, start)
    if reachable is None:
        return None
    _reject(
        enclosure_violation(grid, reachable),
        "enclose the street with walls before the grid border",
    )
    _reject(
        walls_violation(grid, reachable),
        "join wall segments using the supported straight, corner and junction shapes",
    )
    _reject(
        glyph_violation(grid),
        "join - and | wall segments through a + corner or junction",
    )
    _reject(
        connection_violation(grid, reachable),
        "connect all drawn geometry to the street containing C",
    )
    return validate_total(grid, start)


def drive_states(grid: _Grid, start: tuple[int, int]) -> dict[_State, _Edges]:
    """Explore every driving state the car can reach from ``start``.

    A state is position, heading and latches; geometry is static, so the BFS
    terminates.  Movement reads the tape at exactly two places, both testing
    ``== 0`` (:func:`_heading_from_merge_target` on the arrival cell,
    :func:`_heading_from_junction` on the current one), so probing all four
    bit combinations is exhaustive, not a sample.  A ``None`` successor is a
    state the car cannot leave.
    """
    origin = _State(*start, _initial_heading(grid, start), _NO_LATCHES)
    graph: dict[_State, _Edges] = {origin: {}}
    pending = [origin]
    while pending:
        state = pending.pop()
        edges = graph[state]
        for arrival in (0, 1):
            for current in (0, 1):
                successor = _drive(grid, state, arrival, current)
                edges[arrival, current] = successor
                if (
                    successor is not None
                    and successor != "halt"
                    and successor not in graph
                    and _drives_on_the_right(grid, successor)
                ):
                    graph[successor] = {}
                    pending.append(successor)
    return graph


def validate_total(grid: _Grid, start: tuple[int, int]) -> dict[_State, _Edges]:
    """Return the drive-state graph, rejecting a street the car cannot leave.

    Hugging is total by construction, so today this rejects only a
    reachable ``U`` with a walled opposite lane (``HaltError`` promoted
    to ``ValueError``); 137472 small walled grids found none only this
    check rejects.
    """
    graph = drive_states(grid, start)
    for state, edges in graph.items():
        _reject(
            wedge_violation(state, edges),
            "continue the road or place ; at the intended stop",
        )
        check_state_invariants(grid, state, edges)
    return graph


def wedge_violation(state: _State, edges: _Edges) -> str | None:
    """Name a drive state the car cannot leave, or ``None``.

    Only ``;`` halts a well-formed program, so a reachable state with
    no successor is a wedged street.  ``;`` reports ``"halt"`` rather
    than ``None``, so ``None`` means only the one thing.
    """
    if any(successor is None for successor in edges.values()):
        return (
            f"the car cannot drive out of {(state.row, state.col)} heading"
            f" {state.heading}: the street is a dead end with no ';'"
        )
    return None


def check_state_invariants(grid: _Grid, state: _State, edges: _Edges) -> None:
    """Assert what must hold of a drive state under any reading of the spec.

    A car inside a wall, or one that teleports, is wrong under every
    reading (a junction firing a cell early once drove the car inside
    the wall).  :class:`AssertionError`, not ``ValueError``: a breach is
    the movement rules disagreeing with the grid.
    """
    if not grid.open_at(state.row, state.col):
        raise AssertionError(
            f"the car occupies {(state.row, state.col)}, which is not"
            f" open floor: {grid[state.row, state.col]!r}"
        )
    for successor in edges.values():
        if successor is None or successor == "halt":
            continue
        # A step drives one cell along one axis.  Anything else is the
        # car teleporting, which no movement rule is allowed to do.
        steps = abs(successor.row - state.row) + abs(successor.col - state.col)
        if steps != 1:
            raise AssertionError(
                f"the car moved from {(state.row, state.col)} to"
                f" {(successor.row, successor.col)}, which is not one"
                " orthogonal step"
            )
        if not grid.open_at(successor.row, successor.col):
            raise AssertionError(
                f"the car drove from {(state.row, state.col)} into"
                f" {(successor.row, successor.col)}, which is not open"
                f" floor: {grid[successor.row, successor.col]!r}"
            )
    _check_merge_latch(grid, state)


def _check_merge_latch(grid: _Grid, state: _State) -> None:
    """Assert a live merge latch drives to open floor straight ahead."""
    merge = state.latches.merge
    # A latch whose heading no longer matches is abandoned on the next
    # step, so its target is stale and describes no geometry.
    if merge is None or state.heading != merge.latched_heading:
        return
    if not grid.open_at(merge.target_row, merge.target_col):
        raise AssertionError(
            f"the merge latched at {(state.row, state.col)} is driving to"
            f" {merge.target}, which is not open floor:"
            f" {grid[merge.target_row, merge.target_col]!r}"
        )
    # The approach does not change lane, so the target sits straight
    # ahead along the latched heading -- never to one side, never
    # behind a car that can only drive forwards onto it.
    d_row, d_col = _DELTA[merge.latched_heading]
    off_row, off_col = merge.target_row - state.row, merge.target_col - state.col
    if off_row * d_col - off_col * d_row != 0:
        raise AssertionError(
            f"the merge latched at {(state.row, state.col)} heading"
            f" {merge.latched_heading} is driving to {merge.target}, which"
            " is off the axis it is travelling along"
        )
    if off_row * d_row + off_col * d_col < 0:
        raise AssertionError(
            f"the merge latched at {(state.row, state.col)} heading"
            f" {merge.latched_heading} is driving to {merge.target}, which"
            " is behind it"
        )


def validate_width(grid: _Grid, start: tuple[int, int]) -> set[_ReachableCell] | None:
    """Validate that every street is two characters wide.

    A corridor cell with open neighbours directly opposite, or a dead
    end, must have an open perpendicular neighbour; isolated cells and
    wall-free grids are exempt, and a blank row is a lane.  The upper
    bound is a fully open 3x3 block, which a two-wide network never
    contains (a cross-section run through a crossing reports the other
    street's length).  A 3x2 room passes, deliberately.
    """
    # No walls → not a street network (e.g. ["C","U"] or ["C"])
    if not any(ch in _WALLS for row in grid for ch in row):
        return None
    # BFS reachable open cells from C (open = not a wall)
    sr, sc = start
    visited: set[_ReachableCell] = set()
    q: deque[_ReachableCell] = deque([_ReachableCell((sr, sc))])
    visited.add(_ReachableCell((sr, sc)))
    while q:
        r, c = q.popleft()
        for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            nr, nc = r + dr, c + dc
            # No bounds test: off the grid is not open, so the fill
            # cannot walk out of the drawing.
            if grid.open_at(nr, nc) and (nr, nc) not in visited:
                visited.add(_ReachableCell((nr, nc)))
                q.append(_ReachableCell((nr, nc)))
    # Isolated single cell is not a street
    if len(visited) <= 1:
        return None
    _reject(width_violation(grid, visited), "keep the reachable street two cells wide")
    return visited


def width_violation(grid: _Grid, reachable: set[_ReachableCell]) -> str | None:
    """Name a cell breaking the two-wide rule, or ``None`` if none does.

    The rule as a value, so it can be asked without a second implementation.
    """
    for r, c in reachable:
        n = grid.open_at(r - 1, c)
        s = grid.open_at(r + 1, c)
        e = grid.open_at(r, c + 1)
        w2 = grid.open_at(r, c - 1)
        cnt = sum((n, s, e, w2))
        if cnt == 1:
            return f"not two-wide at {(r, c)} (dead end)"
        if n and s and not (e or w2):
            return f"not two-wide at {(r, c)} (vertical)"
        if e and w2 and not (n or s):
            return f"not two-wide at {(r, c)} (horizontal)"
        if all(grid.open_at(r + dr, c + dc) for dr in (0, 1, 2) for dc in (0, 1, 2)):
            return f"not two-wide at {(r, c)} (wider than two)"
    return None


def block(grid: _Grid, cell: _ReachableCell) -> tuple[str, ...]:
    """Return the three-by-three neighbourhood around a reachable cell.

    Not bounds-checked: the enclosure check has rejected any
    road touching the border, and the precondition states that.
    """
    row, col = cell
    _require(
        condition=0 < row < grid.height - 1 and 0 < col < grid.width - 1,
        message=(
            f"{cell} is on the border of the grid, so its neighbourhood"
            " runs off it: the enclosure check did not establish what"
            " this read depends on"
        ),
    )
    return tuple(
        grid[row + d_row, col + d_col] for d_row in (-1, 0, 1) for d_col in (-1, 0, 1)
    )


def walls_violation(grid: _Grid, reachable: set[_ReachableCell]) -> str | None:
    """Name a cell whose wall neighbourhood matches no legal form.

    Width misses a one-cell hole (``-- --``); each reachable cell's 3x3
    must match ``_WALL_FORMS`` up to rotation.  The forms let a wall
    simply stop and admit any wall character at a corner -- whether a
    divider must end in ``+`` is unsettled, and
    the hello fixture leaves its ends bare.
    Must run after the enclosure check: :func:`block` does not
    bounds-check.  Returns ``None`` when every cell is fine.
    """
    for cell in reachable:
        r, c = cell
        cells = block(grid, cell)
        # A street is two cells wide, so every reachable cell has a
        # wall within one; a wall-free neighbourhood is an interior
        # wider than two, already rejected by the width check.
        if not any(ch in _WALLS for ch in cells):  # pragma: no cover
            continue
        # The two-wide check runs first and rejects every malformed
        # shape found so far; this stands as the independent check the
        # forms were written to be.
        if not any(  # pragma: no cover - the width check rejects these first
            _matches(cells, form) for form in _WALL_FORMS
        ):
            shape = " ".join(
                "".join("." if ch not in _WALLS else ch for ch in cells[i : i + 3])
                for i in (0, 3, 6)
            )
            return f"malformed wall at {(r, c)} ({shape})"
    return None


def enclosure_violation(grid: _Grid, reachable: set[_ReachableCell]) -> str | None:
    """Name a road cell on the grid's border, or ``None`` if none is.

    A flood fill from ``C`` reaching the border has escaped through a
    hole.  This is what catches a two-wide hole, which is legal-width
    passage the width check cannot see.
    """
    for r, c in reachable:
        if r in (0, grid.height - 1) or c in (0, grid.width - 1):
            return (
                f"street reaches the edge of the grid at {(r, c)}:"
                " the road is not enclosed by walls"
            )
    return None


def glyph_violation(grid: _Grid) -> str | None:
    """Name a ``-`` drawn beside a ``|``, or ``None`` if none is.

    A wall changing direction without its ``+``.  About glyph choice,
    not wall placement, so the forms in :func:`walls_violation` cannot
    see it.
    """
    for r in range(grid.height):
        for c in range(grid.width):
            char = grid[r, c]
            if char == "-":
                neighbours = ((r, c - 1), (r, c + 1))
                other = "|"
            elif char == "|":
                neighbours = ((r - 1, c), (r + 1, c))
                other = "-"
            else:
                continue
            for nr, nc in neighbours:
                if grid[nr, nc] == other:
                    return (
                        f"wall turns without a corner at {(r, c)}:"
                        f" {char!r} beside {other!r} at {(nr, nc)}"
                    )
    return None


def connection_violation(grid: _Grid, reachable: set[_ReachableCell]) -> str | None:
    """Name drawn geometry off the street, or ``None`` if none is.

    Grows the reachable open cells by one so the region takes in its
    walls; anything still drawn belongs to no street.  A one-thick
    island is taken in whole; only a block with an interior falls
    outside.  Blank cells are ignored (``ljust`` padding, the boolean
    example's margins).  Strict: any character off the street, not
    only walls -- stray marks are likelier a slip than a comment.
    """
    grown = {
        (r + dr, c + dc) for r, c in reachable for dr in (-1, 0, 1) for dc in (-1, 0, 1)
    }
    for r in range(grid.height):
        for c in range(grid.width):
            char = grid[r, c]
            if char == " " or (r, c) in grown:
                continue
            return f"geometry not connected to the street at {(r, c)} ({char!r})"
    return None
