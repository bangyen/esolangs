"""Parse Flowchart diagrams and resolve the connections between nodes."""

from collections.abc import Mapping
from types import MappingProxyType
from typing import Literal

from esolangs.runtime.source_hints import syntax_error

# Headings, as (d_row, d_col) with rows growing downward.
_UP = (-1, 0)
_DOWN = (1, 0)
_LEFT = (0, -1)
_RIGHT = (0, 1)
_HEADINGS = (_RIGHT, _DOWN, _LEFT, _UP)

# The spellings, as a type.  ``_parse`` is the only writer of ``self.nodes``
# and it copies out of :data:`_NODES`, so every spelling the interpreter ever
# dispatches on is one of these -- which lets ``_execute`` end in an ``else``
# that mypy narrows to the last one, rather than a branch nothing can take.
# Adding a node means adding it here as well as to ``_NODES``, or the tuple
# stops type-checking.
_Spelling = Literal[
    "(( ))",
    "\\[ ]/",
    "/[ ]\\",
    "\\{ }/",
    "/{ }\\",
    "( )",
    "[ ]",
    "{ ]",
    "[ }",
    "{ }",
    "< >",
    "/ /",
    "\\ \\",
    "< ]",
    "[ >",
]

# Node spellings, longest first: ``\[ ]/`` contains ``[ ]``, and ``[ }``,
# ``[ >`` and ``[ ]`` share a prefix, so a shorter spelling must never be
# matched inside a longer one.
_NODES: tuple[_Spelling, ...] = (
    "(( ))",
    "\\[ ]/",
    "/[ ]\\",
    "\\{ }/",
    "/{ }\\",
    "( )",
    "[ ]",
    "{ ]",
    "[ }",
    "{ }",
    "< >",
    "/ /",
    "\\ \\",
    "< ]",
    "[ >",
)

# Characters that carry a pointer between nodes.  Every one of these is a
# plain conduit: the headings it permits are derived from its shape.
_EXITS = {
    "─": (_LEFT, _RIGHT),
    "│": (_UP, _DOWN),
    "┌": (_RIGHT, _DOWN),
    "┐": (_LEFT, _DOWN),
    "└": (_RIGHT, _UP),
    "┘": (_LEFT, _UP),
    "┬": (_LEFT, _RIGHT, _DOWN),
    "┴": (_LEFT, _RIGHT, _UP),
    "├": (_UP, _DOWN, _RIGHT),
    "┤": (_UP, _DOWN, _LEFT),
    "┼": (_LEFT, _RIGHT, _UP, _DOWN),
}


def _turn_left(d: tuple[int, int]) -> tuple[int, int]:
    """Return the heading 90 degrees to the left of ``d``."""
    d_row, d_col = d
    return (-d_col, d_row)


def _turn_right(d: tuple[int, int]) -> tuple[int, int]:
    """Return the heading 90 degrees to the right of ``d``."""
    d_row, d_col = d
    return (d_col, -d_row)


type _Exit = tuple[int, int, tuple[int, int]]
type _Image = tuple[
    tuple[str, ...],
    int,
    Mapping[tuple[int, int], tuple[_Spelling, int]],
    tuple[int, int],
    tuple[_Exit, ...],
]


class _Diagram:
    """Build and validate the grid before binding an execution port."""

    def __init__(self, code: list[str]) -> None:
        rows = [line.removesuffix("\r\n").rstrip("\n") for line in code]
        self.width = max((len(r) for r in rows), default=0)
        self.grid = tuple(r.ljust(self.width) for r in rows)

        # (row, col) -> (node spelling, col of the node's first character); every
        # cell a node covers maps to that node, so a pointer arriving at any
        # column of the box executes it.
        self.nodes: dict[tuple[int, int], tuple[_Spelling, int]] = {}
        self._parse()

    def _parse(self) -> None:
        """Record every node on the grid, longest spelling first."""
        for row, line in enumerate(self.grid):
            col = 0
            while col < len(line):
                for spelling in _NODES:
                    if line.startswith(spelling, col):
                        for i in range(len(spelling)):
                            self.nodes[(row, col + i)] = (spelling, col)
                        col += len(spelling)
                        break
                else:
                    c = line[col]
                    if c != " " and c not in _EXITS:
                        raise syntax_error(
                            f"unknown character {c!r} at ({col}, {row})",
                            (
                                "use Flowchart nodes and connected path glyphs; "
                                "keep other text outside the diagram"
                            ),
                        )
                    col += 1
        self._check_separation()
        self._check_alignment()

    def _check_separation(self) -> None:
        """Reject nodes touching side by side without a connecting path.

        Nodes may sit in adjacent rows: both wiki Hello Worlds stack their
        rows of ``{ ]``/``[ }`` boxes with no gap, and a box's exits are path
        cells, so a node above or below is simply not an exit.
        """
        for (row, col), node in self.nodes.items():
            neighbour = self.nodes.get((row, col + 1))
            if neighbour is not None and neighbour != node:
                raise syntax_error(
                    f"nodes touch without a path at ({col}, {row})",
                    "separate the nodes with a connecting path",
                )

    def _check_alignment(self) -> None:
        """Reject a vertical path that enters a node off its middle.

        Runs after the scan above, because a rail's node may be recorded
        after the rail itself.  Only vertical arms are checked: a node is a
        contiguous run of cells on one row, so a horizontal neighbour can
        only ever be at ``col0 - 1`` or ``col0 + len``, and the cell it enters is
        therefore always an end cell.  Horizontal entry cannot be drawn any
        other way, which is why the spec constrains only the vertical case.
        """
        for row, line in enumerate(self.grid):
            for col, c in enumerate(line):
                arms = _EXITS.get(c)
                if arms is None:
                    continue
                for arm in (_UP, _DOWN):
                    if arm not in arms:
                        continue
                    node = self.nodes.get((row + arm[0], col))
                    if node is None:
                        continue
                    spelling, col0 = node
                    middle = col0 + len(spelling) // 2
                    if col != middle:
                        raise syntax_error(
                            f"vertical path at ({col}, {row}) enters {spelling!r} at "
                            f"column {col}, but its middle is column {middle}",
                            "connect a vertical path at the middle column of the node",
                        )

    def start(self) -> tuple[int, int]:
        """Return the left-most, then top-most, ``( )`` node's first cell.

        The spec starts on "the left-most top-most node" -- column first,
        unlike its top-most-first pointer order -- and the wiki's
        eight-pointer Hello World needs exactly that: its start sits at the
        left edge below a higher ``( )`` that only forks.
        """
        for col in range(self.width):
            for row in range(len(self.grid)):
                node = self.nodes.get((row, col))
                if node and node[0] == "( )" and node[1] == col:
                    return (row, col)
        raise syntax_error(
            "Flowchart program has no '( )' start node",
            "add a ( ) start node and connect its exit",
        )

    def initial_exits(self, start: tuple[int, int]) -> tuple[_Exit, ...]:
        """Return the start node's attached paths.

        The start ``( )`` forks like any other, but there is no arriving
        heading to exclude, so every attached path gets a pointer, the
        pointer's own first.
        """
        exits = _forward_first(
            _exits_from_node(self.grid, self.nodes, self.width, *start, None),
            _RIGHT,
        )
        if not exits:
            raise syntax_error(
                "start node has no exit path", "connect a path leaving the start node"
            )
        return tuple(exits)


def _prepare_source(code: list[str]) -> _Image:
    diagram = _Diagram(code)
    start = diagram.start()
    return (
        diagram.grid,
        diagram.width,
        MappingProxyType(diagram.nodes),
        start,
        diagram.initial_exits(start),
    )


def _in_bounds(grid: tuple[str, ...], width: int, row: int, col: int) -> bool:
    """Whether ``(row, col)`` is on the grid."""
    return 0 <= row < len(grid) and 0 <= col < width


def _cells_of(
    nodes: Mapping[tuple[int, int], tuple[_Spelling, int]], row: int, col: int
) -> list[tuple[int, int]]:
    """Return every cell covered by the node at ``(row, col)``."""
    spelling, col0 = nodes[(row, col)]
    return [(row, col0 + i) for i in range(len(spelling))]


def _accepts(
    grid: tuple[str, ...],
    nodes: Mapping[tuple[int, int], tuple[_Spelling, int]],
    width: int,
    row: int,
    col: int,
    d: tuple[int, int],
) -> bool:
    """Whether a pointer may enter ``(row, col)`` travelling on ``d``.

    A line character connects only in the directions its shape draws, so
    it can be entered exactly when one of those arms points back at the
    cell the pointer is coming from -- a ``┐`` reached travelling right
    is entered through its left arm and then turns down.
    """
    if not _in_bounds(grid, width, row, col):
        return False
    if (row, col) in nodes:
        return True
    c = grid[row][col]
    return c in _EXITS and (-d[0], -d[1]) in _EXITS[c]


def _anchor(
    nodes: Mapping[tuple[int, int], tuple[_Spelling, int]], row: int, col: int
) -> tuple[int, int]:
    """Return the key a cell's re-entry memory is stored under.

    A node is several cells wide and a rail may re-enter it at any of
    them, so every cell of a box shares its first cell's key; a bare
    path character is its own anchor.
    """
    node = nodes.get((row, col))
    return (row, node[1]) if node else (row, col)


def _reading_order(
    exits: list[tuple[int, int, tuple[int, int]]],
) -> list[tuple[int, int, tuple[int, int]]]:
    """Sort a fork's exits top-most first, then left-most."""
    return sorted(exits, key=lambda step: (step[0], step[1]))


def _forward_first(
    exits: list[tuple[int, int, tuple[int, int]]], d: tuple[int, int]
) -> list[tuple[int, int, tuple[int, int]]]:
    """Order a fork's exits: the pointer's own first, then reading order.

    "A pointer will always choose to go forward on a node if given
    multiple exit paths, followed by clockwise, then counterclockwise"
    names only ``< >`` as the exception, so the forking pointer keeps
    that exit and the new pointers take the rest in reading order.
    """
    exits = _reading_order(exits)
    order = (d, _turn_right(d), _turn_left(d), (-d[0], -d[1]))
    own = min(exits, key=lambda step: order.index(step[2]), default=None)
    return [] if own is None else [own, *(e for e in exits if e != own)]


def _exits_from_node(
    grid: tuple[str, ...],
    nodes: Mapping[tuple[int, int], tuple[_Spelling, int]],
    width: int,
    row: int,
    col: int,
    came_from: tuple[int, int] | None,
) -> list[tuple[int, int, tuple[int, int]]]:
    """Return the ``(row, col, heading)`` steps leaving the node at ``(row, col)``.

    A node's exits are the path cells touching any cell of its box, minus
    the cell the pointer entered from -- excluding by *cell* rather than
    by heading matters because a box is several cells wide, so a pointer
    can enter one cell of it from the north and still find that same
    northern cell offered again from a different column.  ``came_from`` is
    ``None`` at the start, where nothing is excluded.
    """
    out: list[tuple[int, int, tuple[int, int]]] = []
    for c_row, c_col in _cells_of(nodes, row, col):
        for d in _HEADINGS:
            n_row, n_col = c_row + d[0], c_col + d[1]
            # A neighbouring node is never an exit: the only nodes that may
            # touch are stacked in adjacent rows, with no path between.
            if (n_row, n_col) in nodes or not _in_bounds(grid, width, n_row, n_col):
                continue
            if (n_row, n_col) == came_from:
                continue
            if not _accepts(grid, nodes, width, n_row, n_col, d):
                continue
            out.append((n_row, n_col, d))
    return out
