"""Interprogck8 Boolean program generator: short hops under flights that share rungs.

``DownAccLines`` skips ``1 + acc`` lines.  The program is cut into windows of
126 lines: 40 for code, then a zone of blank lines ending in a rung that every
flight in the air shares.

- **Read.**  ``{values/=u/=X/=X}`` with ``X`` 49 pips leaves Q (81) on a ``1``
  and T (84) on a ``0``.  ``IFT`` calls the slot ``<NnNn>`` on a 0, which
  zeroes the accumulator so the rung falls through onto the near child.  A 1
  keeps 81, or ``IFQ`` calls a body that rewrites it, and the rung lands on
  the far child: the slot is refilled after any other body.
- **Cluster.**  A subtree of at most 40 lines is laid whole, the far child
  as many lines past the rung as the near subtree is long.  A read over two
  leaves is two lines: the compare leaves Q or T and the rung's hop of 82 or
  85 lands the leaf's value on the tail's entry.
- **Flight.**  A larger subtree's read sets the accumulator to column
  ``40 + h - 2`` for ``h`` reads below it, so its rung lands in the zone and
  each window's closing rung hops it to the same column again.  Flights share
  that rung and differ by column; the stop, one ``NnNn`` at the flight's
  column in a later window, is reached by no other flight, since a deeper
  read has a lower column and finishes first.
- **Tail.**  The last window takes the printers at columns 82 and 85, above
  every flight's, and prints ``0`` or ``1``.

A read whose halves are equal (``subtree_ids``), a constant or an ignored
input, still consumes its digit: its child is laid straight after it.

Size:
    O(T) at every arity: a window is 126 lines and at most 1.3 T are opened,
    so a table takes under 420 T characters whatever ``n``.
    n=10 random 1847: 167,672 chars, n=10 parity: 197,134 chars,
    n=10 and: 8,206 chars.

Raises:
    GeneratorCapError: more than forty inputs; a flight's column must stay
        below the printers'.

Decisions:
    Other repeated subtrees are not shared: a stop sits on one column, so two
    parents cannot land on one child.
"""

from esolangs.exceptions import GeneratorCapError
from esolangs.generation.helpers import _validate_truth_table, subtree_ids
from esolangs.languages.interprogck8.proof_formulas import execution, workspace
from esolangs.registry._language import Language
from esolangs.runtime.source_hints import with_hint

#: The rung.  ``DownAccLines`` jumps to ``ip + 1 + acc``.
_RUNG = "DownAccLines"

#: The compare's pips: Q (81) when the digit is the ``0`` or ``1`` it names.
_PIPS = {0: ":" * 24, 1: ":" * 24 + "."}
#: A leaf's value as Q (81) or T (84) whatever the accumulator holds.
_VALUE = {0: "{values/=/=/=}", 1: "{values/=:/=./=}"}
#: The slot every read calls on a 0 to zero the accumulator.
_SLOT = ["<", "NnNn", ">"]

#: A window holds ``_FREE`` code lines, then a zone that must reach the
#: printers' entry at column 85 from the last code line.  The deepest of the
#: forty reads flies at column ``_FREE + 37``, under the printers' 82.
_FREE = 40
_ZONE = 86
_PERIOD = _FREE + _ZONE
_MAX_INPUTS = 40


def _read(bit: int) -> str:
    """The read leaving Q when the digit is ``bit``, else T."""
    return "{values/=u/=" + _PIPS[bit] + "/=" + _PIPS[bit] + "}"


def _arith(delta: int) -> list[str]:
    """The fewest ``@id``/``@nd``/``@dd``/``@nt`` lines adding ``delta`` mod 256."""
    delta = (delta + 128) % 256 - 128
    tens, ones = divmod(abs(delta), 10)
    big, near, far = ("@id", "@nd", "@nt") if delta >= 0 else ("@dd", "@nt", "@nd")
    exact = [big] * tens + [near] * ones
    over = [big] * (tens + 1) + [far] * (10 - ones)
    return min(exact, over, key=len) if ones else exact


def _block(target: int) -> list[str]:
    """A read whose 1 arm hops ``target`` lines and whose 0 arm falls through.

    ``IFQ`` calls a body rewriting Q to ``target``, then the slot is refilled.
    """
    body = min(_arith(target - 81), ["NnNn", *["@nd"] * target], key=len)
    return [_read(1), "IFT", "<", *body, ">", "IFQ", *_SLOT, _RUNG]


class _Plan:
    """The windows of one program: placed lines, the cursor and the last cluster."""

    def __init__(self, table: str, n: int) -> None:
        self.n = n
        self.ids = subtree_ids(table)
        self.ops: dict[int, str] = dict(enumerate(_SLOT, 1))
        self.cursor = len(_SLOT) + 1
        self.window = 0
        self.sizes: dict[tuple[int, int], int] = {}

    def halves(self, depth: int, block: int) -> tuple[int, int]:
        """The ids of ``block``'s two child subtrees (leaf values at the bottom)."""
        return self.ids[depth + 1][2 * block], self.ids[depth + 1][2 * block + 1]

    def size(self, depth: int, block: int) -> int:
        """Lines of the cluster at ``block``, or ``_FREE + 1`` if it is longer."""
        key = (depth, block)
        if key not in self.sizes:
            low, high = self.halves(depth, block)
            if depth == self.n - 1:
                total = 3 if low == high else 2
            elif low == high:
                total = 1 + self.size(depth + 1, 2 * block)
            else:
                near = self.size(depth + 1, 2 * block)
                far = self.size(depth + 1, 2 * block + 1) if near <= _FREE else near
                total = len(_block(near)) + near + far
            self.sizes[key] = min(total, _FREE + 1)
        return self.sizes[key]

    def cluster(self, depth: int, block: int) -> list[str]:
        """The lines of the cluster at ``block``: every arm a short hop."""
        low, high = self.halves(depth, block)
        if depth == self.n - 1:
            if low == high:
                return [_read(1), _VALUE[low], _RUNG]
            return [_read(low), _RUNG]  # Q prints the 0, T the 1
        if low == high:
            return [_read(1), *self.cluster(depth + 1, 2 * block)]
        near = self.cluster(depth + 1, 2 * block)
        return [*_block(len(near)), *near, *self.cluster(depth + 1, 2 * block + 1)]

    def place(self, lines: list[str], reach: int) -> int:
        """Lay ``lines`` in the first window with room, ending within ``reach``.

        Returns the last line.  A window's code ends at ``_FREE``; ``reach`` is
        how far into it a rung may sit and still land in the zone.
        """
        line, room = self.cursor, min(_FREE, reach) - len(lines) + 1
        while not 1 <= line % _PERIOD <= room:
            line = (line // _PERIOD + 1) * _PERIOD + 1
        self.ops.update(enumerate(lines, line))
        self.cursor = line + len(lines)
        return self.cursor - 1

    def lay(self, depth: int, block: int) -> None:
        """Lay the subtree at ``block`` from the cursor, flights above clusters."""
        low, high = self.halves(depth, block)
        if self.size(depth, block) <= _FREE:
            end = self.place(self.cluster(depth, block), _FREE)
            self.window = end // _PERIOD
        elif low == high:
            self.place([_read(1), "NnNn"], _PERIOD)
            self.lay(depth + 1, 2 * block)
        else:
            column = _FREE + self.n - 3 - depth  # a read of height n - 1 - depth
            rung = self.place(_block(column), _PERIOD - 2 - column)
            self.lay(depth + 1, 2 * block)
            first = max(self.cursor, (rung // _PERIOD + 1) * _PERIOD)
            stop = first + (column + 1 - first) % _PERIOD
            self.ops[stop] = "NnNn"
            self.cursor = stop + 1
            self.lay(depth + 1, 2 * block + 1)

    def text(self) -> str:
        """Close the windows with their rungs and the printers' tail."""
        last = self.window + 1
        for window in range(last + 1):
            self.ops.setdefault(window * _PERIOD, _RUNG)
        tail = ["@nd", "@nd", "x", *_arith(-35), "div"]  # 81 -> 48, 84 -> 49
        end = last * _PERIOD + 82 + len(tail)
        self.ops.update(enumerate(tail, last * _PERIOD + 82))
        return "\n".join(self.ops.get(i, "x") for i in range(end))


def interprogck8(truth_table: str) -> str:
    """Build an Interprogck8 program printing ``truth_table[row]`` for the inputs.

    Reads ``n`` digits, one per line, and prints ``0`` or ``1``.
    """
    n = _validate_truth_table(truth_table)
    if n > _MAX_INPUTS:
        raise with_hint(
            GeneratorCapError(
                f"Interprogck8 keeps its flights under the printers for at most "
                f"{_MAX_INPUTS} inputs, not {n}"
            ),
            "a table past forty inputs is a terabyte; no width enlarges the columns",
        )
    plan = _Plan(truth_table, n)
    plan.lay(0, 0)
    return plan.text()


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
    proof_execution=(execution, False, (3, 4, 5, 6, 7)),
    proof_workspace=(workspace, False, (3, 4, 5, 6)),
)
