"""Boolean program generator for Interprogck8.

A decision tree whose long edges ride ``DownAccLines`` *flights*: a rung
jumps ``1 + acc`` lines and leaves the accumulator alone, so a flight
hops a fixed stride through rungs to the first other line on its residue,
its *stop*.

- **Read.**  One even line, ``{values/=u/=X/=X}`` with ``X`` 49 pips,
  leaves Q (81) on a ``1`` and T (84) on a ``0``.  From the odd rung after
  it, 81 flies stride 82 on the odd lines; 84 lands 85 below, an even
  line, which zeroes the accumulator and walks into the 0 subtree.  A rung
  under acc 0 is a fall-through, so walks cross live lanes freely.
- **Lanes.**  A read takes the first even line whose rung residue mod 82
  is not in the air.  The air holds one residue per ancestor whose 1 child
  is still unplaced, so it never exceeds ``n - 1`` of the 41 odd residues;
  the 1 child's stop is the first line on its residue past the 0 subtree.
- **Leaves.**  ``nNnN`` (65) flies stride 66 to one of two printers past
  the tree; a tree stop stays off their two residues mod 66.
- **Fill.**  A rung only where a flight hops or a walk crosses a live lane,
  ``x`` elsewhere: the wiki errors on blank lines, so none are emitted.

Size is O(T) at every arity: a node's read scan, dismount and stop scan
span at most 82, 85 and 3 * 82 lines, a leaf's scan 66, and no line
exceeds the 65-character read; a dense table measures 153 lines an entry
from ``n = 8`` to 17.  Rungs on live lanes make the characters per entry
creep with ``n`` (511 at ``n = 8``, 586 at 17), under the corridor that
fills every odd line, 1,207 at both.  Each flight is laid once and a
printer lane once from its earliest launch, so building is O(T); a run
visits each line at most once, since every jump is forward.

A read whose halves are equal (``subtree_ids``), a constant or an ignored
input, still consumes its digit: both arms converge, the 1 flight stopping
on the line the zeroed 0 walk passes through, onto one child.  Other repeats
are not shared: a stop sits on one lane, so two parents cannot land on one
child.  Forty-one lanes bound the arity at forty-one; past forty inputs the
table alone is a terabyte.
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

    def read(entry: int) -> int:
        """Place a read at the first even line off every live lane; return its rung."""
        line = entry + entry % 2
        while (line + 1) % _STRIDE in air or {line, line + 1} & layout.ops.keys():
            line += 2
        layout.walk(entry, line, air)
        layout.put(line, _READ)
        return line + 1

    def stop(start: int, lane: int) -> int:
        """Place a stop on ``lane``'s first free line past ``start``, off printers."""
        line = start + (lane - start) % _STRIDE
        while line % _PRINT_STRIDE in _PRINT_LANES or line in layout.ops:
            line += _STRIDE
        layout.put(line, "NnNn")
        return line

    def node(depth: int, block: int, entry: int) -> int:
        """Lay one subtree entered at ``entry`` under acc 0; return its frontier."""
        if depth == n:
            value = ids[n][block]
            line = entry + entry % 2
            while (line + 1) % _PRINT_STRIDE != _PRINT_LANE[
                value
            ] or line in layout.ops:
                line += 2
            layout.walk(entry, line, air)
            layout.put(line, "nNnN")
            layout.leaves.append((line + 1, value))
            return line + 2
        launch = read(entry)
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
        landing = stop(max(frontier, launch + 2), lane)
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
    code = one_stop + 1
    while any(
        (code + i) % 2 and (code + i) % _PRINT_STRIDE == _PRINT_LANE[0]
        for i in range(len(one_code) + 20)
    ):
        code += 1
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
    spell = ["@id"] * (distance // 10) + ["@nd"] * (distance % 10)
    if len(spell) > 19:
        raise AssertionError(f"printer escape spells {distance} in {len(spell)} lines")
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
