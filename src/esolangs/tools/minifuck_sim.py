"""The Minifuck machine the boolean generator emits against.

The generator decides what to emit next from what the program so far has
done, so :class:`_Sim` accepts emissions one at a time and :class:`_Joint`
runs one per truth-table row in lockstep.  The machine is four closed-form
laws, one per maximal run of the alphabet, not a stepper: the left law
(``"<" * k`` is ``ptr = max(ptr - k, 0)``), the comment law (only consumes
a pending skip), the bracket law (``"[" * k`` writes the complement of the
prefix-XOR over the cells crossed, costing the staircase
``T(m) = m + sum(e_1..e_m)``, the same one :class:`_Chain` walks), and the
print law (``.`` prints cells 0-7 as a byte, or on zero *reads*, which
marks the row ``dead``).  ``"[x" * k`` keeps its own spelling
(:meth:`_Sim.run_walk`).  The interpreter's ``_step`` stays the definition
and the tests pin every law to it differentially from arbitrary states
(the first cascade-less walk law matched fresh states and diverged on 877
of 3000 random ones; 40000 random ``(state, code)`` pairs at the
prototype).  What to emit lives in :mod:`esolangs.tools.minifuck`.
"""

from collections.abc import Callable
from functools import lru_cache

from esolangs.tools.helpers import TEMPLATE_CHAR

# How an emitted string decomposes: each entry is a law and its repeat
# count.  ``dot`` carries no count -- prints are emitted singly -- and the
# ``walk`` fast path keeps a pure ``[x`` run at one law call.
#
# The law is the *function*, not its name.  A parse is applied once per row
# -- :meth:`_Joint.emit` runs it across ``2**n`` machines -- so a name would
# be resolved by ``getattr`` once per row per run, 546195 times over an
# 18-table build, where resolving it once at parse time costs nothing and
# hands the loop a callable.  Measured on the real emission mix, that is 29%
# off the dispatch.
_Runs = list[tuple["Callable[[_Sim, int], None]", int]]


@lru_cache(maxsize=512)
def _runs(code: str) -> _Runs:
    """Parse ``code`` into maximal runs, one law application each.

    ``[x`` is checked first, since walks are most of what is emitted.  Cached:
    an 18-table build makes 13911 parses of 90 distinct strings, and the
    returned list is never mutated.
    """
    parsed: _Runs = []
    i, n = 0, len(code)
    while i < n:
        ch = code[i]
        if ch == "[":
            j = i
            while j + 1 < n and code[j] == "[" and code[j + 1] == "x":
                j += 2
            if j > i:
                parsed.append((_Sim.run_walk, (j - i) // 2))
                i = j
                continue
            j = i
            while j < n and code[j] == "[":
                j += 1
            parsed.append((_Sim.run_brackets, j - i))
            i = j
        elif ch == "<":
            j = i
            while j < n and code[j] == "<":
                j += 1
            parsed.append((_Sim.run_left, j - i))
            i = j
        elif ch == ".":
            parsed.append((_Sim.run_dot, 1))
            i += 1
        else:
            j = i
            while j < n and code[j] not in "[<.":
                j += 1
            parsed.append((_Sim.run_comment, j - i))
            i = j
    return parsed


class _Sim:
    """A Minifuck machine advanced by the four laws above.

    Holds what an emitter branches on: tape, pointer, output, and two flags.
    ``dead`` marks a ``.`` on a zero pool (a read); ``skip`` holds the
    cascade's pending skip until the next emission arrives.
    """

    __slots__ = ("dead", "length", "out", "ptr", "skip", "tape")

    def __init__(self, size: int) -> None:
        """Start with a zeroed tape of ``size`` cells at the origin.

        The tape is an ``int`` bitvector, cell *i* at bit *i*, as the
        interpreter's ``_State``; a list would make an O(1) flip O(tape).
        """
        self.tape = 0
        self.length = size
        self.ptr = 0
        self.out: list[str] = []
        self.dead = False
        self.skip = False

    def cell(self, index: int) -> int:
        """Return the bit in cell ``index``."""
        return (self.tape >> index) & 1

    def cells(self, stop: int) -> tuple[int, ...]:
        """Return cells ``0..stop-1``, the shape a column comparison wants."""
        return tuple((self.tape >> i) & 1 for i in range(stop))

    def copy(self) -> "_Sim":
        """Return an independent copy, for branching a derivation or a probe."""
        clone = _Sim.__new__(_Sim)
        clone.tape = self.tape
        clone.length = self.length
        clone.ptr = self.ptr
        clone.out = list(self.out)
        clone.dead = self.dead
        clone.skip = self.skip
        return clone

    def key(self) -> tuple[object, ...]:
        """Return the whole state, hashable, so a caller can dedup on it."""
        return (self.tape, self.length, self.ptr, tuple(self.out), self.dead, self.skip)

    def run_left(self, count: int) -> None:
        """Apply ``"<" * count``: the left law.

        ``max(ptr - count, 0)``; a pending skip eats the first, a dead row stays.
        """
        if self.dead or count <= 0:
            return
        if self.skip:
            self.skip = False
            count -= 1
        self.ptr = max(self.ptr - count, 0)

    def run_comment(self, count: int) -> None:
        """Apply a run of comment characters: the comment law.

        Only a pending skip consumes one, which is why ``x`` absorbs the skip.
        """
        if self.dead or count <= 0:
            return
        if self.skip:
            self.skip = False

    def run_walk(self, pairs: int) -> None:
        """Apply ``"[x" * pairs``: the walk law, in closed form.

        Each pair advances and flips a cell; a flip to zero cascades into the
        next cell and sets the skip, which the ``x`` eats.  The cascade is a
        carry (checked on 5000 random states), so over a ``k``-cell window each
        bit becomes the complement of the prefix XOR up to it and the cell above
        takes the window's parity: ``O(log k)`` big-int doublings.  Without the
        cascade the model disagreed on 877 of 3000 states; this agrees on 4000 of 4000.
        """
        if self.dead or pairs <= 0:
            return
        if self.skip:
            # The pending skip eats the leading ``[``; its ``x`` is a comment.
            self.skip = False
            pairs -= 1
            if pairs == 0:
                return
        tape, ptr = self.tape, self.ptr
        low = ptr + 1
        mask = (1 << pairs) - 1
        # Prefix XOR of the window by doubling: after each step every bit
        # holds the XOR of itself and the ``span`` bits below it, so the
        # spans compose to cover the whole prefix in ``log2(pairs)`` steps.
        carries = (tape >> low) & mask
        span = 1
        while span < pairs:
            carries ^= (carries << span) & mask
            span <<= 1
        tape = (tape & ~(mask << low)) | ((carries ^ mask) << low)
        # The window's total parity is the carry out of its top cell, which
        # lands in the cell above -- the one the next emission steps onto.
        tape ^= ((carries >> (pairs - 1)) & 1) << (low + pairs)
        ptr += pairs
        self.tape, self.ptr = tape, ptr
        self.length = max(self.length, ptr + 2)

    def run_brackets(self, count: int) -> None:
        """Apply ``"[" * count``: the bracket law.

        Crossing cell *j* sees ``e_j = c_1 XOR ... XOR c_j`` and leaves
        ``NOT e_j``; a cascade's skip eats the next ``[``, so a cell with
        ``e_j == 1`` costs two, and the extent is the largest ``m`` with
        ``T(m) = m + sum(e_1..e_m) <= count``.  Remainder 1 means the next
        crossing has ``e == 1`` and its ``[`` fires with the skip left pending --
        the one way a run ends mid-cell.  The last cascade's carry lands above
        the window iff the window's parity is 1.  Inverted by binary search over
        popcounts, ``O(log k)``.  The single bracket (112877 of 182177 runs in a
        three-slice build) is spelled out: complement the crossed cell, and if it
        held 1 carry above and leave the skip pending (checked against the
        general arm over 23072 states).
        """
        if self.dead or count <= 0:
            return
        if self.skip:
            self.skip = False
            count -= 1
            if count == 0:
                return
        if count == 1:
            ptr = self.ptr + 1
            bit = 1 << ptr
            if self.tape & bit:
                # The crossing lands on 0, so the cascade flips the cell
                # above and owes a skip to whatever instruction follows.
                self.tape ^= bit | (bit << 1)
                self.skip = True
            else:
                self.tape |= bit
            self.ptr = ptr
            if ptr + 2 > self.length:
                self.length = ptr + 2
            return
        tape, ptr = self.tape, self.ptr
        low = ptr + 1
        # e_j for j = 1..count: a run of k brackets crosses at most k cells,
        # so the window never needs to be wider than the run.
        mask = (1 << count) - 1
        effective = (tape >> low) & mask
        span = 1
        while span < count:
            effective ^= (effective << span) & mask
            span <<= 1
        # The staircase inverse: T is nondecreasing, so binary-search the
        # largest m with T(m) <= count.
        lo, hi = 0, count
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if mid + (effective & ((1 << mid) - 1)).bit_count() <= count:
                lo = mid
            else:
                hi = mid - 1
        crossed = lo
        if crossed + (effective & ((1 << crossed) - 1)).bit_count() < count:
            # Remainder 1: the next crossing starts, cascades, and leaves
            # its skip pending for the instruction after the run.
            crossed += 1
            skip_out = True
        else:
            skip_out = False
        # Exhausted over every effective vector at counts 2..11: the
        # staircase inverse is never 0 there, and counts 0 and 1 are the
        # two arms above.
        if crossed == 0:  # pragma: no cover - see above
            return
        window = (1 << crossed) - 1
        effective &= window
        tape = (tape & ~(window << low)) | ((effective ^ window) << low)
        # The carry: the last crossing's cascade lands above the window.
        tape ^= ((effective >> (crossed - 1)) & 1) << (low + crossed)
        self.tape = tape
        self.ptr = ptr + crossed
        self.skip = skip_out
        self.length = max(self.length, self.ptr + 2)

    def run_weight(self, units: int) -> bool:
        """Apply ``("[x<[<" + "<") * (units - 1) + "[x<[<"`` in closed form.

        Each restoring read restores ``ptr + 1``, flips ``ptr + 2`` and moves
        the pointer down by the bit read, so the gadget is a march down
        consecutive 1-cells, stalling at a 0: cells ``ptr+3-m .. ptr+2``
        complemented, the stall cell flipped iff the remaining units are odd,
        pointer at ``ptr - m + 1``.  O(1) where the parsed runs cost ~4 calls per
        read.  Returns False untouched when a pending skip or a floor clamp
        applies (``test_the_weight_law_matches_the_parsed_runs``).
        """
        if units <= 0:
            return True
        if self.dead:
            return True
        if self.skip:
            return False
        p = self.ptr
        gaps = ~self.tape & ((1 << (p + 2)) - 1)
        run = p + 1 - (gaps.bit_length() - 1)
        marched = min(run, units)
        if marched > p + 1 or (marched < units and marched > p):
            return False
        tape = self.tape
        if marched:
            tape ^= ((1 << marched) - 1) << (p + 3 - marched)
        if (units - marched) & 1:
            tape ^= 1 << (p + 2 - marched)
        self.tape = tape
        self.ptr = p - marched + 1
        self.length = max(self.length, p + 3)
        return True

    def run_rewind(self, count: int) -> None:
        """Apply the sculpting round ``"<" * count + "[x" * count + "x"``.

        The walk law's prefix-XOR over the window ending at the pointer, the
        carry into ``ptr + 1``, pointer unchanged; one call where the runs cost
        three.  A pending skip or a pointer inside the window falls back
        (``test_the_rewind_law_matches_the_parsed_runs``).
        """
        if self.dead or count <= 0:
            if count <= 0 and not self.dead and self.skip:
                self.skip = False
            return
        if self.skip or self.ptr < count:
            self.run_left(count)
            self.run_walk(count)
            self.run_comment(1)
            return
        tape, ptr = self.tape, self.ptr
        low = ptr - count + 1
        mask = (1 << count) - 1
        carries = (tape >> low) & mask
        span = 1
        while span < count:
            carries ^= (carries << span) & mask
            span <<= 1
        tape = (tape & ~(mask << low)) | ((carries ^ mask) << low)
        tape ^= ((carries >> (count - 1)) & 1) << (low + count)
        self.tape = tape
        self.length = max(self.length, ptr + 2)

    def run_rewinds(self, widths: list[int]) -> None:
        """Apply a sequence of sculpting rounds, fused over their window.

        Every round touches only ``ptr - max(widths) + 1 .. ptr + 1``, so the
        window is extracted once and the sequence is arithmetic on integers the
        width of the deepest rewind, one write-back.  Falls back to
        :meth:`run_rewind` on a pending skip or a window off the tape.
        """
        if self.dead or not widths:
            return
        p = self.ptr
        top = max(widths)
        if self.skip or p < top:
            for width in widths:
                self.run_rewind(width)
            return
        shift = p - top + 1
        span_mask = (1 << (top + 1)) - 1
        window = (self.tape >> shift) & span_mask
        for width in widths:
            low = top - width
            mask = (1 << width) - 1
            bits = (window >> low) & mask
            carries = bits
            span = 1
            while span < width:
                carries ^= (carries << span) & mask
                span <<= 1
            window ^= ((bits ^ carries ^ mask) << low) | (
                ((carries >> (width - 1)) & 1) << top
            )
        self.tape = (self.tape & ~(span_mask << shift)) | (window << shift)
        self.length = max(self.length, p + 2)

    def run_dot(self, count: int = 1) -> None:
        """Apply ``.``: the print law.

        Advances, flips, reads cells 0-7 as a byte (cell 0 the MSB); zero
        *reads*, so the row is marked ``dead`` and frozen.
        """
        for _ in range(count):
            if self.dead:
                return
            if self.skip:
                self.skip = False
                continue
            ptr = self.ptr + 1
            tape = self.tape ^ (1 << ptr)
            window = tape & 0xFF
            if window == 0:
                self.dead = True
                return
            self.ptr = ptr
            self.tape = tape
            self.length = max(self.length, ptr + 2)
            self.out.append(chr(sum(((window >> i) & 1) << (7 - i) for i in range(8))))

    def apply(self, parsed: _Runs) -> None:
        """Advance by an already-parsed emission, one law call per run."""
        for law, count in parsed:
            law(self, count)

    def exec(self, ins: str) -> None:
        """Execute one instruction, the single-character case of the laws.

        For probes and tests; dispatches to the same four laws.
        """
        if ins == "<":
            self.run_left(1)
        elif ins == "[":
            self.run_brackets(1)
        elif ins == ".":
            self.run_dot()
        else:
            self.run_comment(1)


#: How each input is set, at ``ptr+1``: ``[<`` steps right, flips the cell
#: and steps back for a one; ``xx`` is two executed no-ops for a zero.  The
#: template spells each input as a run of :data:`TEMPLATE_CHAR` this wide.
MINIFUCK_ZERO, MINIFUCK_ONE = "xx", "[<"
_MINIFUCK_INPUT = TEMPLATE_CHAR * len(MINIFUCK_ZERO)


def _set_bit(bit: int) -> str:
    """Return the input fill writing ``bit`` at ``ptr+1``.

    Both spellings are two characters and leave the pointer, so the length
    does not leak the inputs.
    """
    return MINIFUCK_ONE if bit else MINIFUCK_ZERO


class _Joint:
    """The ``2**n`` instantiations, advanced in lockstep as code is emitted."""

    def __init__(self, n: int, size: int = 512) -> None:
        """Start one machine per row of the truth table."""
        self.n = n
        self.rows = [[(r >> (n - 1 - k)) & 1 for k in range(n)] for r in range(2**n)]
        self.ms = [_Sim(size) for _ in self.rows]
        self.parts: list[str] = []

    def emit(self, code: str) -> None:
        """Append code and run it on every row, keeping them in lockstep.

        Parsed once, one law call per run per row.  The template is appended
        before the rows advance, so the program never depends on the model.
        """
        self.parts.append(code)
        if not code:
            return
        parsed = _runs(code)
        for m in self.ms:
            m.apply(parsed)

    def emit_setter(self, i: int) -> None:
        """Emit input ``i``'s run, simulating each row with its bit."""
        self.parts.append(_MINIFUCK_INPUT)
        one = _runs(_set_bit(1))
        zero = _runs(_set_bit(0))
        for bits, m in zip(self.rows, self.ms, strict=True):
            m.apply(one if bits[i] else zero)

    def emit_weight(self, code: str, units: int) -> None:
        """Append the weight gadget, advancing rows by its composed law.

        ``code`` must spell exactly ``units`` restoring reads; a row the law
        refuses falls back to the parsed runs (~4 calls per read).
        """
        self.parts.append(code)
        parsed: _Runs | None = None
        for m in self.ms:
            if not m.run_weight(units):
                if parsed is None:
                    parsed = _runs(code)
                m.apply(parsed)

    def fork(self) -> "_Joint":
        """Return a copy, for trying a continuation without committing."""
        clone = _Joint.__new__(_Joint)
        clone.n = self.n
        clone.rows = self.rows
        clone.ms = [m.copy() for m in self.ms]
        clone.parts = list(self.parts)
        return clone

    def col(self, cell: int) -> tuple[int, ...]:
        """Return ``cell``'s value across the rows -- the function it holds."""
        return tuple(m.cell(cell) for m in self.ms)

    def ptrs(self) -> tuple[int, ...]:
        """Return each row's pointer, so callers can see divergence."""
        return tuple(m.ptr for m in self.ms)

    def printed(self) -> list[str]:
        """Return what each row has printed so far."""
        return ["".join(m.out) for m in self.ms]

    def template(self) -> str:
        """Return the emitted template, input runs included."""
        return "".join(self.parts)


def _walk_to(j: _Joint, target: int) -> None:
    """Walk right to ``target`` with ``[x``, which is safe over any junk."""
    ptrs = set(j.ptrs())
    if len(ptrs) != 1:
        raise ValueError(f"walk needs a converged pointer, got {ptrs}")
    cur = ptrs.pop()
    if target < cur:
        raise ValueError(f"cannot walk left with [x ({cur} -> {target})")
    j.emit("[x" * (target - cur))


def _clamp(j: _Joint) -> None:
    """Clamp every row's pointer to 0.  ``<`` never writes, so this is free."""
    j.emit("<" * (max(j.ptrs()) + 1))
