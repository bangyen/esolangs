"""Interprogck8 Boolean program generator: a decision tree on ``DownAccLines`` flights.

A rung jumps ``1 + acc`` lines and leaves the accumulator alone, so a flight
hops a fixed stride through rungs to the first other line on its residue,
its *stop*.

- **Read.**  One even line, ``{values/=u/=X/=X}`` with ``X`` 49 pips,
  leaves Q (81) on a ``1`` and T (84) on a ``0``.  From the odd rung after
  it, 81 flies stride 82 on the odd lines; 84 lands 85 below, an even
  line, which zeroes the accumulator and walks into the 0 subtree.  A rung
  under acc 0 is a fall-through, so walks cross live lanes freely.
- **Lanes.**  Up to 15 inputs a read sits on the first even line after its
  entry: a 0 child's lane is its parent's + 6, a 1 child's + 2 (mod 82),
  which never meets an in-air ancestor's lane (see ``_ENTRY_LANES``).
  Beyond, a depth-``d`` read takes the first even line whose rung residue
  mod 82 is ``2d + 1``, so no two reads in the air share a lane (the air
  holds at most ``n - 1`` of the 41 odd residues).  The 1 child's stop is
  the first line on its residue past the 0 subtree and stays off the two
  printer residues mod 66.
- **Fill.**  A rung only where a flight hops or a walk crosses a live lane,
  ``x`` elsewhere: the wiki errors on blank lines, so none are emitted.

A read whose halves are equal (``subtree_ids``), a constant or an ignored
input, still consumes its digit: both arms converge, the 1 flight stopping
on the line the zeroed 0 walk passes through, onto one child.

Size:
    O(T) at every arity: a node's read gap, dismount and stop gap span at
    most 82, 85 and 2 * 82 lines, a leaf's scan 66, and no line exceeds the
    65-character read; a dense table is 210 lines an entry from ``n = 8`` to
    17.  Rungs on live lanes make characters per entry creep with ``n`` (550
    at ``n = 8``, 785 at 17), under the corridor filling every odd line,
    1,207 at both.  Each flight is laid once and a printer lane once from its
    earliest launch, so building is O(T); a run visits each line at most once,
    since every jump is forward.
    n=10 random 1847: 532,117 chars, n=10 parity: 586,697 chars,
    n=10 and: 26,904 chars.

Raises:
    GeneratorCapError: more than forty inputs; 41 lanes bound the arity.

Decisions:
    Other repeated subtrees are not shared: a stop sits on one lane, so two
    parents cannot land on one child.
"""

from esolangs.exceptions import GeneratorCapError
from esolangs.generation.helpers import _validate_truth_table, subtree_ids
from esolangs.registry._language import Language
from esolangs.runtime.source_hints import with_hint

#: The rung.  ``DownAccLines`` jumps to ``ip + 1 + acc``.
_RUNG = "DownAccLines"

#: Q (81) flies 82 a hop; T (84) lands 85 below the rung.
_STRIDE = 82
_DISMOUNT = 85
_PIPS_49 = ":" * 24 + "."
_READ = "{values/=u/=" + _PIPS_49 + "/=" + _PIPS_49 + "}"

#: ``nNnN`` loads 65: a leaf flies stride 66 to the printer for its value.
_PRINT_STRIDE = 66
_PRINT_LANE = {0: 33, 1: 1}
_PRINT_LANES = frozenset(_PRINT_LANE.values())

#: Up to this many inputs a read stays on the first even line after its
#: entry: a 0 child's lane is its parent's + 6, a 1 child's + 2 (mod 82), so
#: an in-air ancestor ``k`` levels up collides only when ``3a + b = 41 m``
#: with ``a + b = k``, ``a >= 1``, first at ``k = 15``, i.e. ``n = 16``.
_ENTRY_LANES = 15

#: The deepest read clears ``n - 1`` lanes in the air.
_MAX_INPUTS = 40


class _Layout:
    """The assembly state: placed lines and the printer flights' launches."""

    def __init__(self) -> None:
        self.ops: dict[int, str] = {}
        self.leaves: list[tuple[int, int]] = []

    def put(self, line: int, op: str) -> None:
        """Occupy ``line`` with ``op``; a collision is a planning bug."""
        if line in self.ops:
            raise AssertionError(f"line {line} holds {self.ops[line]!r}, wanted {op!r}")
        self.ops[line] = op

    def lay(self, launch: int, stride: int, stop: int) -> None:
        """Lay one flight's rungs from ``launch`` up to its ``stop``."""
        for line in range(launch, stop, stride):
            if self.ops.setdefault(line, _RUNG) != _RUNG:
                raise AssertionError(f"flight from {launch} hits {self.ops[line]!r}")
        if stop % stride != launch % stride:
            raise AssertionError(f"flight from {launch} steps over its stop {stop}")

    def walk(self, start: int, end: int, air: set[int]) -> None:
        """Mark the lines an acc-0 walk passes: a rung where a live lane crosses."""
        for line in range(start, end):
            live = line % 2 and (
                line % _STRIDE in air or line % _PRINT_STRIDE in _PRINT_LANES
            )
            self.ops.setdefault(line, _RUNG if live else "x")


def _tree(table: str, n: int, layout: _Layout) -> int:
    """Lay the tree from line 0; return the first line past it."""
    ids = subtree_ids(table)
    air: set[int] = set()

    def read(entry: int, depth: int) -> int:
        """Place a depth-``depth`` read on its own lane; return its rung.

        Lane ``2 * depth + 1`` is the depth's alone, and the air holds only
        shallower ancestors' lanes, so it is free by construction.  Every
        placed line lies before ``entry``, so the line is free too.
        """
        line = entry + entry % 2
        if n > _ENTRY_LANES:
            line += (2 * depth - line) % _STRIDE
        layout.walk(entry, line, air)
        layout.put(line, _READ)
        return line + 1

    def stop(start: int, lane: int) -> int:
        """Place a stop on ``lane``'s first free line past ``start``, off printers."""
        line = start + (lane - start) % _STRIDE
        # 82 = 16 mod 66 and the printer residues differ by 32: one hop clears.
        line += _STRIDE * (line % _PRINT_STRIDE in _PRINT_LANES)
        layout.put(line, "NnNn")
        return line

    def node(depth: int, block: int, entry: int) -> int:
        """Lay one subtree entered at ``entry`` under acc 0; return its frontier."""
        if depth == n:
            value = ids[n][block]
            line = entry + entry % 2
            line += (_PRINT_LANE[value] - 1 - line) % _PRINT_STRIDE
            layout.walk(entry, line, air)
            layout.put(line, "nNnN")
            layout.leaves.append((line + 1, value))
            return line + 2
        launch = read(entry, depth)
        lane = launch % _STRIDE
        arm = launch + _DISMOUNT
        layout.put(arm, "NnNn")
        air.add(lane)
        if ids[depth + 1][2 * block] == ids[depth + 1][2 * block + 1]:
            # Equal halves: the 0 walk runs on through the 1 flight's stop.
            landing = stop(arm + 1, lane)
            layout.walk(arm + 1, landing, air)
            air.discard(lane)
            layout.lay(launch, _STRIDE, landing)
            return node(depth + 1, 2 * block, landing + 1)
        frontier = node(depth + 1, 2 * block, arm + 1)
        air.discard(lane)
        landing = stop(frontier, lane)
        layout.lay(launch, _STRIDE, landing)
        return node(depth + 1, 2 * block + 1, landing + 1)

    return node(0, 0, 0)


def _printers(layout: _Layout, start: int) -> tuple[int, dict[int, int]]:
    """Lay both printers past ``start``; return the length and each value's stop.

    The 1 printer's stop and code come first, then a hop over the 0 side;
    0 flights cross that code, so its odd lines stay off their residue.
    """
    one_stop = start + (_PRINT_LANE[1] - start) % _PRINT_STRIDE
    layout.put(one_stop, "NnNn")
    one_code = ["@id"] * 4 + ["@nd"] * 9 + ["div", "NnNn"]
    # The 35-line window must start past the first odd 0-lane line.
    code = one_stop + 1 + (_PRINT_LANE[0] - _PRINT_LANE[1]) % _PRINT_STRIDE
    layout.walk(one_stop + 1, code, set())
    for i, op in enumerate(one_code):
        layout.put(code + i, op)
    hop = code + len(one_code)  # the adjusters and the rung of the escape
    zero_start = hop + 20
    zero_stop = zero_start + (_PRINT_LANE[0] - zero_start) % _PRINT_STRIDE
    layout.put(zero_stop, "NnNn")
    zero_code = ["@id"] * 4 + ["@nd"] * 8 + ["div"]
    for i, op in enumerate(zero_code):
        layout.put(zero_stop + 1 + i, op)
    end = zero_stop + 1 + len(zero_code)
    layout.put(end, "x")  # the escape lands here, never past the last line
    rung = hop + 19
    distance = end - rung - 1
    if distance != 44:  # the spacing and printer lanes fix it
        raise AssertionError(f"printer escape spans {distance} lines, not 44")
    spell = ["@id"] * 4 + ["@nd"] * 4
    for i, op in enumerate(spell):
        layout.put(hop + i, op)
    for line in range(hop + len(spell), rung):
        layout.put(line, "x")  # walked under the escape's acc: no rung
    layout.put(rung, _RUNG)
    layout.walk(rung + 1, zero_stop, set())
    return end + 1, {1: one_stop, 0: zero_stop}


def interprogck8(truth_table: str) -> str:
    """Build an Interprogck8 program printing ``truth_table[row]`` for the inputs.

    Reads ``n`` digits, one per line, and prints ``0`` or ``1``.
    """
    n = _validate_truth_table(truth_table)
    if n > _MAX_INPUTS:
        raise with_hint(
            GeneratorCapError(
                f"Interprogck8's 41 lanes route at most {_MAX_INPUTS} inputs, not {n}"
            ),
            "a table past forty inputs is a terabyte; no width enlarges the lanes",
        )
    layout = _Layout()
    start = _tree(truth_table, n, layout)
    length, stops = _printers(layout, start)
    # Every leaf of one value shares a lane, so the earliest launch's
    # flight lays every later one's rungs.
    earliest: dict[int, int] = {}
    for launch, value in layout.leaves:
        earliest[value] = min(earliest.get(value, launch), launch)
    for value, launch in earliest.items():
        layout.lay(launch, _PRINT_STRIDE, stops[value])
    return "\n".join(layout.ops.get(line, "x") for line in range(length))


LANGUAGE = Language(
    "Interprogck8",
    "interprogck8",
    category="register_based",
    generator_restrictions=(
        f"at most {_MAX_INPUTS} inputs, past any table that fits in memory"
    ),
    boolean=interprogck8,
    split=True,
    random=True,
    no_wrap="a newline adds a line and moves every DownAccLines landing",
)
