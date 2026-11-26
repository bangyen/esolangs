"""Emit BrainIf spatial lookups with guarded walks along a strip."""

from collections.abc import Sequence

from esolangs.generation.helpers import _ASCII_ONE, _ASCII_ZERO, _validate_truth_table
from esolangs.languages.brainif._assembly import _climb, _Lines, _resolve


def _top_level(n: int) -> int:
    """Return the deepest level that loops, for an ``n``-input table.

    Cost model, in lines: adding level ``K`` (``K`` levels already looped)
    saves its walk, ``2**(n-K)`` guarded ``left`` lines, and costs a loop of
    about ``19 + 5K`` lines plus ``5 * 2**K - 2`` more marker-climb lines
    (rank ``r`` has ``2**r`` markers climbing ``3 + 2(K-1-r)`` extra each,
    summing to ``5 * 2**K - 2K - 5``).  Dropping the linear terms, it pays
    while ``2**(n-K) > 5 * 2**K``, i.e. ``K < (n - log2 5) / 2``, so the
    looped levels number ``(n - 1) // 2`` and the deepest is ``(n - 3) // 2``.
    Measured on seeded random tables the best top level is that at n=6, 8,
    10..14, and one lower at n=5, 7, 9, but by less than the 10% bar
    ([ablations.lookup_loops]).

    The cap also clears the pair condition: levels ``i < j`` share a marker
    position exactly when ``j - i == 2**(n-1-j)``, and ``m_i = 2**(n-1-i)``
    must be even for a two-cell loop iteration.  ``top <= (n-2)/2`` leaves
    ``2**(n-1-top) >= 2**(n/2)``, which outgrows ``top``, and ``(n-3)//2``
    stays under it.  ``n`` counts the essential inputs; :class:`_Strip`
    re-checks the pairs once ignored ones sit between the levels.
    """
    return max(0, (n - 3) // 2)


class _Strip:
    """The strip's cell values, and what a guard at a given class may see.

    A cell holds ``2 * (position % 2) + bit``; the parity keeps a two-line
    step from firing twice.  A *marker* cell holds its level's value plus the
    bit instead, which is what stops that level's loop.
    """

    def __init__(self, cells: str, weights: Sequence[int]) -> None:
        """Place the markers and fix the alphabet; ``weights[i]`` is ``m_i``.

        An ignored input weighs 0 and only steps the pointer.  Levels ``i < j``
        share a marker cell exactly when ``(j - i) % (2 * m_j) == m_j``; the
        looped levels are the widest ones up to the first such pair.
        """
        self.cells = cells
        size = len(cells)
        essential = [i for i, w in enumerate(weights) if w]
        self.levels: list[int] = []
        for i in essential[: _top_level(len(essential)) + 1]:
            if any((i - j) % (2 * weights[i]) == weights[i] for j in self.levels):
                break
            self.levels.append(i)
        #: ``2 * m_i``: the period of level ``i``'s marker class.
        self.period = {i: 2 * weights[i] for i in self.levels}
        #: Level ``i``'s walk starts at ``size - 2 - i`` (mod its period) and
        #: ends ``m_i`` cells left of it, which is where its marker goes.
        self.first = {
            i: (size - 2 - i - weights[i]) % self.period[i] for i in self.levels
        }
        # The deepest looped level has the most markers, so it takes the
        # cheapest value: a climb to v costs v lines, once per marker.
        top = len(self.levels) - 1
        self.value = {i: 4 + 2 * (top - rank) for rank, i in enumerate(self.levels)}
        self.level_at: dict[int, int] = {}
        for i in self.levels:
            for pos in range(self.first[i], size, self.period[i]):
                self.level_at[pos] = i
        self.alphabet: dict[int, set[int]] = {0: {0, 1}, 1: {2, 3}}
        for i in self.levels:
            self.alphabet[self.first[i] % 2] |= {self.value[i], self.value[i] + 1}

    def at(self, pos: int) -> int:
        """Return the value stored in cell ``pos``."""
        bit = int(self.cells[pos])
        level = self.level_at.get(pos)
        if level is None:
            return 2 * (pos % 2) + bit
        return self.value[level] + bit

    def seen(self, residue: int, modulus: int | None) -> list[int]:
        """Values a cell known only as ``residue`` mod ``modulus`` may hold.

        ``None`` means the position is exact -- the first read -- so the value
        is a compile-time constant.  Otherwise a level's markers are possible
        when the two classes can meet; an over-estimate costs a dead guard
        line, an under-estimate is a bug.
        """
        if modulus is None:
            return [self.at(residue)]
        if modulus == 1:
            # Past the weight-1 level an ignored read's parity is unknown.
            return sorted(self.alphabet[0] | self.alphabet[1])
        parity = residue % 2
        out = {2 * parity, 2 * parity + 1}
        for i in self.levels:
            if self.first[i] % 2 != parity:
                continue
            coarse = min(modulus, self.period[i])
            if self.first[i] % coarse == residue % coarse:
                out |= {self.value[i], self.value[i] + 1}
        return sorted(out)


def _emit_guarded(
    out: _Lines, strip: _Strip, residue: int, modulus: int | None, suffix: str
) -> None:
    """Emit one guarded line per value the named cell may hold."""
    out.extend(f"if {v} {suffix}" for v in strip.seen(residue, modulus))


def _emit_strip_cells(out: _Lines, strip: _Strip, size: int) -> None:
    """Emit the strip: the table, then one padding cell per input."""
    # Padding takes the cheaper bit; the last cell needs no ``right``,
    # since the walk starts there.
    for index in range(size):
        value = strip.at(index)
        out.extend(f"if {passed} increment" for passed in range(value))
        if index + 1 < size:
            out.add(f"if {value} move right")


def _emit_linear_read(
    out: _Lines, strip: _Strip, weights: Sequence[int], size: int, i: int
) -> None:
    """Emit input ``i``'s read and the walk its zero branch takes."""
    far, after = f"far_{i}", f"after_{i}"
    # Every higher bit moves the pointer a multiple of the smallest
    # higher weight, so the read cell's class is known modulo it.
    known = next((w for w in reversed(weights[:i]) if w), None)
    _emit_guarded(out, strip, size - 1 - i, known, "input")
    if not weights[i]:
        out.add(f"if {_ASCII_ZERO} move left")
        out.add(f"if {_ASCII_ONE} move left")
        return
    out.add(f"if {_ASCII_ZERO} goto @{far}")
    out.add(f"if {_ASCII_ONE} move left")
    _emit_guarded(out, strip, size - 2 - i, known, f"goto @{after}")
    out.mark(far)
    out.add(f"if {_ASCII_ZERO} move left")
    if i in strip.levels:
        _emit_loop(out.lines, strip, i, size)
    else:
        for k in range(weights[i]):
            _emit_guarded(out, strip, size - 2 - i - k, known, "move left")
    out.mark(after)


def _emit_linear_output(out: _Lines, strip: _Strip) -> None:
    """Emit the output tail for the selected cell the walk ends on."""
    # The selected cell's value is its bit in the low place -- every
    # marker value is even -- and the climbs converge, so neither the
    # branch nor the climb cares which class the cell came from.
    alphabet = strip.alphabet[0] | strip.alphabet[1]
    for value in sorted(v for v in alphabet if v % 2):
        out.add(f"if {value} goto @one_out")
    out.extend(_climb())
    out.add(f"if {_ASCII_ZERO} output")
    out.add(f"if {_ASCII_ZERO} goto @done")
    out.mark("one_out")
    for value in range(1, _ASCII_ONE):
        out.add(f"if {value} increment")
    out.add(f"if {_ASCII_ONE} output")
    out.mark("done")


def _brainif_linear(truth_table: str, weights: Sequence[int] | None = None) -> str:
    """Emit a linear spatial lookup for BrainIf.

    One cell an entry, carrying its bit *and* its parity -- ``{0, 1}`` even,
    ``{2, 3}`` odd -- so an emitted step left is two guarded moves, one per
    value the cell it leaves can hold.  The strip stores 0..3 rather than
    ``'0'``/``'1'`` because BrainIf cannot write a constant: a cell climbs by
    ``if v increment`` lines, so an ASCII digit an entry would be a 48-line climb an
    entry, and only the final ``output`` cares what the byte is.

    The build runs left to right and the selection right to left, reading the
    index in complement: a ``1`` stays put and a ``0`` walks its weight.  One
    padding cell an input keeps every read right of the answer cell.

    The top levels walk by *loop* rather than by emitted line.  Level ``i``
    ends ``m_i = 2**(n-1-i)`` cells left of a position fixed mod ``2*m_i``
    whatever the higher bits were, so a marker value planted on that whole
    residue class stops the loop exactly there: the class has period
    ``2*m_i`` and the window is ``m_i`` long, so the window holds one.  That
    trades ``2*m_i`` ``left`` lines for ``2**i`` marker climbs, which only the
    widest levels are worth (:func:`_top_level`) -- level 0 alone is half
    the crossings and costs one marker.  Commands use the published spellings.

    ``weights`` gives each input's row weight (see
    :func:`~esolangs.generation.projection.input_weights`); an ignored input, weight 0,
    is read and stepped past, and ``truth_table`` is then its projection.
    The default is every input essential.
    """
    n = len(weights) if weights else _validate_truth_table(truth_table)
    weights = weights or [1 << (n - 1 - i) for i in range(n)]
    cells = truth_table + "0" * n
    size = len(cells)
    strip = _Strip(cells, weights)
    out = _Lines()
    # Phase 1: lay out the strip cells the selection walk will cross.
    _emit_strip_cells(out, strip, size)
    # Phase 2: read each input and walk its weight on a zero.  A read
    # overwrites the cell it lands on, so its guard is every value that
    # cell's class admits; the first step off it is one line, not two,
    # because the byte just read says which branch is running.  The read
    # for level ``i`` sits at ``size - 1 - i`` mod ``2**(n-i)`` --
    # exactly, for level 0.
    for i in range(n):
        _emit_linear_read(out, strip, weights, size, i)
    # Phase 3: print the selected cell the walk ends on.
    _emit_linear_output(out, strip)
    return _resolve(out.lines)


def _emit_loop(lines: list[str], strip: _Strip, level: int, size: int) -> None:
    """Emit level ``level``'s walk as a loop that halts on its own marker.

    Three groups, entered and left on parity ``P``: cross one cell, cross a
    second, repeat unless the cell is the marker.  Two cells an iteration
    holds the parity, and ``m_i`` is even wherever a level may loop, so the
    walk lands on the marker rather than stepping over it.
    """
    name = f"loop_{level}"
    parity = (size - 2 - level) % 2
    own = {strip.value[level], strip.value[level] + 1}
    crossable = sorted(strip.alphabet[parity] - own)
    lines.append(f"@{name}")
    lines.extend(f"if {v} move left" for v in crossable)
    lines.extend(f"if {v} move left" for v in sorted(strip.alphabet[1 - parity]))
    lines.extend(f"if {v} goto @{name}" for v in crossable)
