"""The Minifuck machine the boolean generator emits against.

The generator cannot hand a whole program to the interpreter and read the
answer: it decides what to emit *next* from what the program built so far
has done, so it needs a machine it can feed one emission at a time and
inspect between them.  :class:`_Sim` is that machine, and :class:`_Joint`
runs one per truth-table row in lockstep, which is how a single emitted
template is checked against every row of the table at once.

**The machine is a set of laws, not an interpreter.**  This module used to
import the interpreter's ``_step`` and advance one character at a time --
the simulator the standing loop-less rule names.  What replaced it is four
closed-form laws, one per maximal run of the language's alphabet, so any
emitted string advances a row in as many law applications as it has runs
rather than characters:

* **The left law** (:meth:`_Sim.run_left`): ``<`` never writes and clamps
  at 0, so ``"<" * k`` is ``ptr = max(ptr - k, 0)``.
* **The comment law** (:meth:`_Sim.run_comment`): a comment character can
  only consume a pending skip.
* **The bracket law** (:meth:`_Sim.run_brackets`): ``"[" * k`` writes the
  complement of the running prefix-XOR over the cells it crosses, exactly
  like a walk, because a ``[``'s cascade flip folds into the next cell's
  effective value.  What the run *costs* is the staircase: crossing a cell
  whose effective value is 1 spends two instructions, its cascade's skip
  eating the next ``[``, so the extent is the inverse of
  ``T(m) = m + sum(e_1..e_m)`` -- the same staircase :class:`_Chain` walks
  for the staging index.  A run can end one instruction into a 2-cost
  crossing, which is the one way it leaves a skip pending.
* **The print law** (:meth:`_Sim.run_dot`): ``.`` advances, flips, and
  prints cells 0-7 as one byte -- or, on a zero byte, *reads*, which a
  parameterized program must never do; the row is marked ``dead`` and its
  state freezes where it stood, exactly as the emitter always treated it.

``"[x" * k`` keeps its own spelling (:meth:`_Sim.run_walk`) because the
parse below would otherwise pay two law calls per pair; it is the bracket
law with every skip eaten immediately, and the two share the prefix-XOR
carry derivation.

The laws are this module's own statement of the language, which is the
point -- the build path no longer drives an interpreter -- and it is also
the risk, so nothing rests on the derivation alone.  The interpreter's
``_step`` stays the single *definition* of Minifuck, and the tests pin the
laws to it differentially: every law against character-by-character
stepping from arbitrary states (fresh ones are exactly where a wrong model
still looks right -- the first cascade-less walk law matched fresh states
and diverged on 877 of 3000 random ones), and :meth:`_Sim.apply` against
stepping over random mixed streams.  At the prototype stage that
comparison ran 40000 random ``(state, code)`` pairs over the generator's
whole gadget vocabulary with no disagreement; the shipped tests keep the
same check.

This lives beside the generator rather than inside it because the two
answer different questions.  Everything here is *what Minifuck does* to a
row; the construction in :mod:`esolangs.tools.boolean.minifuck` is *what
to emit* -- embeds, stagings, separations, sculpting rounds and the
endgame, all of which consume this machine and none of which it knows
about.
"""

from collections.abc import Callable
from functools import lru_cache

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

    The alphabet splits four ways -- ``<``, ``[``, ``.``, and everything
    else, which is a comment -- so the parse is a single scan.  A ``[`` is
    checked for the ``[x`` walk pattern first: the walk law covers ``k``
    pairs in one call where the bracket and comment laws would take two per
    pair, and walks are most of what the construction emits.

    Cached because the construction emits from a small fixed vocabulary:
    an 18-table build makes 13911 parses of 90 distinct strings, and the
    widest of them (a full-width ``[x`` walk) is re-parsed thousands of
    times.  The cache is safe because the returned list is never mutated --
    every caller hands it straight to :meth:`_Sim.apply`, which only
    iterates -- and bounded because the vocabulary is the gadget set plus
    the rewind lengths, which the pointer range caps.
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

    An emitter cannot hand a whole program over and read the answer: it must
    advance a machine and branch on where that left it.  So this accepts
    emissions one at a time, and holds the state an emitter branches on --
    the tape as cells, the pointer, what has printed, and the two flags
    below.

    ``dead`` marks the one transition a parameterized program must never
    take: a ``.`` on a zero pool reads a byte of input.  ``skip`` is the
    cascade's pending skip, which the interpreter spells by advancing past
    the next instruction inside one program; an emitter is handed code in
    pieces and has no next instruction yet, so the skip is held here and
    consumed when that instruction arrives.
    """

    __slots__ = ("dead", "length", "out", "ptr", "skip", "tape")

    def __init__(self, size: int) -> None:
        """Start with a zeroed tape of ``size`` cells at the origin.

        The tape is an ``int`` bitvector, cell *i* at bit *i* -- the same
        spelling the interpreter's ``_State`` uses, so the laws and the
        differential tests read the same object.  Holding it as a list of
        cells instead would make an O(1) flip cost O(tape).
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

        ``<`` is the language's cheapest instruction -- ``ptr - 1 if ptr
        else ptr``, with no tape write, no print and no skip -- so a run of
        them is exactly ``max(ptr - count, 0)``.  A pending skip still eats
        the first one, and a dead row does not move.
        """
        if self.dead or count <= 0:
            return
        if self.skip:
            self.skip = False
            count -= 1
        self.ptr = max(self.ptr - count, 0)

    def run_comment(self, count: int) -> None:
        """Apply a run of comment characters: the comment law.

        A comment moves only the interpreter's cursor, which an emitter does
        not model -- except that a pending skip consumes the first one, which
        is why ``x`` is the construction's "absorb the skip" instruction.
        """
        if self.dead or count <= 0:
            return
        if self.skip:
            self.skip = False

    def run_walk(self, pairs: int) -> None:
        """Apply ``"[x" * pairs``: the walk law, in closed form.

        Each pair advances one cell and flips it; when that flip leaves the
        cell zero the ``[`` cascades into the cell beyond it and sets the
        skip, which the pair's own ``x`` -- a comment -- then consumes.  So
        the pair always ends with the skip clear.

        **The cascade is a carry, and the run is a prefix parity.**  A ``[``
        adds one to the two-bit little-endian field above the pointer, and
        the skip it sets is exactly that addition's carry out -- checked
        against stepping on 5000 random states.  A pair's ``x`` eats the
        skip, so the next pair starts clean one cell higher, and the carry
        into position *j* is the XOR of every window bit below it.  So over
        a window of ``k`` cells the whole run is:

        * each window bit becomes the complement of the prefix XOR up to it,
        * the cell just above the window takes the window's total parity,

        which is ``O(log k)`` big-integer doublings rather than ``k`` steps.
        The cascade is the part a naive closed form gets wrong: a model
        without it disagreed with stepping on 877 of 3000 random states, and
        this form agrees on 4000 of 4000.
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

        What a bare bracket run writes is the walk law again.  Crossing cell
        *j* (counting up from the pointer) sees the effective value
        ``e_j = c_1 XOR ... XOR c_j`` -- each cascade flip folds into the
        next cell's effective value, which is what makes ``e`` the prefix
        XOR -- and leaves ``NOT e_j`` behind.  What differs is the *cost*:
        a cascade's skip eats the next ``[`` of the run itself, so crossing
        a cell with ``e_j == 1`` spends two instructions, and the run's
        extent is the largest ``m`` with

            T(m) = m + sum(e_1..e_m) <= count

        -- the bracket staircase the staging index's :class:`_Chain` walks,
        inverted.  The remainder ``count - T(m)`` is 0 or 1 by maximality:
        a full remainder would mean another crossing fit.  At remainder 1
        the next crossing has ``e == 1`` (a 1-cost crossing would also have
        fit), and its ``[`` executes -- writes its cell, fires the cascade
        -- with the skip left *pending* for whatever instruction follows the
        run.  That partial crossing is the one way a bracket run ends
        mid-cell, and the one way it hands a skip to the next emission.

        The last crossing's cascade flip is the walk law's carry: it lands
        on the first cell above the window, iff ``e`` over the whole window
        is 1.  Every earlier cascade landed on a cell the run then crossed
        and rewrote, which is why no other flip survives.

        The staircase is inverted by binary search over popcounts rather
        than walked: the prefix-XOR vector is one doubling pass, and
        ``T(m)`` is ``m`` plus a masked ``bit_count``, so the whole run is
        ``O(log k)`` big-integer operations like the walk it generalises.

        **The single bracket is spelled out.**  A run of one is 112877 of
        the 182177 bracket runs a three-slice build makes -- the sculpting
        rewind's ``[<`` pairs and the separators are almost all singletons
        -- and at ``count == 1`` every step above collapses: the window is
        one cell, so the doubling pass is a no-op, ``T(1) = 1 + e`` makes
        the search's answer ``crossed == 1`` either way, and the remainder
        is 1 exactly when ``e`` is.  So the whole law is *complement the
        crossed cell, and if it held 1 carry into the cell above and leave
        the skip pending*.  That is the arm below, checked against the
        general one over 23072 states (every ``(ptr, low six cells, skip,
        dead)`` plus 20000 random wide tapes) with no disagreement, on top
        of the differential tests that pin the law itself to ``_step``.
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

        The weight gadget is ``units`` restoring reads, and each read (with
        its separating ``<``) composes the laws above into one net effect:
        it restores the cell it reads at ``ptr + 1``, flips the cell at
        ``ptr + 2``, and moves the pointer down by the bit it read.  So the
        whole gadget is a march: the pointer walks down through consecutive
        1-cells, each step zeroing the cell read two steps earlier (restored
        to 1, then hit by a later step's flip), until it reads a 0 and
        stalls there for the remaining units, whose flips land on one cell
        and cancel in pairs.  With ``m`` the march length that is

        * cells ``ptr+3-m .. ptr+2`` complemented (one XOR mask),
        * the stall cell ``ptr+2-m`` flipped iff the remaining unit count is
          odd,
        * the pointer left at ``ptr - m + 1``,

        an O(1) application where the parsed runs cost ~4 law calls per
        read.  Flips only ever land on cells already read, so the march
        length is decided by the *entering* tape alone.

        Returns False without touching the row when the summary does not
        apply -- a pending skip re-times the first ``[``, and a march
        reaching the tape floor would clamp -- so the caller can fall back
        to the parsed runs.  ``test_the_weight_law_matches_the_parsed_runs``
        pins both outcomes to ``apply(_runs(code))`` from arbitrary states.
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

        The left law then the walk law retrace the same ``count`` cells, so
        the round is the walk law's prefix-XOR over the window ending at the
        pointer -- each window bit complemented into the running carry, the
        carry out flipped into ``ptr + 1`` -- with the pointer back where it
        started and the trailing ``x`` a no-op (a walk never ends mid-skip).
        One law call where the parsed runs cost three per row, which is what
        the round-heavy replay of a spelled build pays for.

        A pending skip re-times the first ``<`` and a pointer inside the
        window would clamp, so both fall back to the laws themselves; the
        sculpt's rewind guard keeps every emitted round on the fast path.
        ``test_the_rewind_law_matches_the_parsed_runs`` pins both paths.
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

        Every round starts and ends at the same pointer, so a sequence only
        ever touches cells ``ptr - max(widths) + 1 .. ptr + 1`` -- each
        round rewrites the ``width`` cells below the pointer and flips the
        carry into ``ptr + 1``.  Extracting that window once turns the
        whole sequence into arithmetic on integers the width of the deepest
        rewind rather than of the tape, with one write-back; a row a
        sculpt's rounds cost ``O(rounds)`` big-tape operations costs one.

        The frame needs a clear skip and the window on the tape, so either
        falls back to :meth:`run_rewind` round by round; the sculpt's
        rewind guard keeps every emitted sequence on the fused path.
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

        ``.`` advances one cell, flips it, and reads cells 0-7 as one byte,
        cell 0 the most significant bit.  A non-zero byte prints; a zero one
        *reads*, which a parameterized program must never do -- the row is
        marked ``dead``, and its state freezes where it stood, because the
        emitter stops modelling a row the moment it leaves the contract.

        ``count`` exists only so every law shares the parse's shape; prints
        are emitted singly.
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
        """Advance by an already-parsed emission, one law call per run.

        The parse carries each law as a function rather than a name, so this
        is the call and nothing else -- see :data:`_Runs` for why the name
        lookup does not belong in a loop that runs once per row.
        """
        for law, count in parsed:
            law(self, count)

    def exec(self, ins: str) -> None:
        """Execute one instruction, the single-character case of the laws.

        Kept because probes and tests drive a machine instruction by
        instruction.  It dispatches to the same four laws as :meth:`apply`,
        so there is one spelling of each law however the code arrives.
        """
        if ins == "<":
            self.run_left(1)
        elif ins == "[":
            self.run_brackets(1)
        elif ins == ".":
            self.run_dot()
        else:
            self.run_comment(1)


def _set_bit(bit: int) -> str:
    """Return the ``{Xi}`` fill writing ``bit`` at ``ptr+1``.

    Both spellings are two characters and leave the pointer where they found
    it, so every instantiation has the same length -- without that, the
    program's length would leak the inputs it is meant to be evaluating.
    """
    return "[<" if bit else "xx"


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

        The code is parsed once and each row advances by the laws, so an
        emission costs one law call per run per row however long its runs
        are.  The effect-carrying dedup that used to live here -- step one
        row per distinct window key, apply the delta to the rest -- was an
        optimization over per-character stepping, and went with the
        stepping: the laws are already arithmetic, so there is no per-
        character cost to share.

        The template is appended before the rows advance either way, so the
        program this builds never depends on how the rows are modelled.
        """
        self.parts.append(code)
        if not code:
            return
        parsed = _runs(code)
        for m in self.ms:
            m.apply(parsed)

    def emit_setter(self, i: int) -> None:
        """Emit the ``{Xi}`` placeholder, simulating each row with its bit."""
        self.parts.append("{X" + str(i) + "}")
        one = _runs(_set_bit(1))
        zero = _runs(_set_bit(0))
        for bits, m in zip(self.rows, self.ms, strict=True):
            m.apply(one if bits[i] else zero)

    def emit_weight(self, code: str, units: int) -> None:
        """Append the weight gadget, advancing rows by its composed law.

        ``code`` must spell exactly ``units`` restoring reads -- the
        differential test pins the pair -- and the template is appended
        before any row advances, as in :meth:`emit`.  A row the law refuses
        falls back to the parsed runs, so the fast path never changes what
        a row becomes, only what it costs: the gadgets are most of a
        separation's law calls, ~4 per read per row.
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
        """Return the emitted template, ``{Xi}`` placeholders included."""
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
