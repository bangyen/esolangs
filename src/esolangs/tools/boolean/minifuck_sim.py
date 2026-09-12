r"""The Minifuck machine the boolean generator emits against."""

from collections.abc import Callable
from functools import lru_cache

# How an emitted string.
# count.
# ``walk`` fast path keeps a.
# .
# The law is the *function*,.
# -- :meth:`_Joint.emit` runs.
# be resolved by ``getattr``.
# 18-table build, where.
# hands the loop a callable.
# off the dispatch.
_Runs = list[tuple["Callable[[_Sim, int], None]", int]]


@lru_cache(maxsize=512)
def _runs(code: str) -> _Runs:
    r"""Parse ``code`` into maximal runs, one law application each."""
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
    r"""A Minifuck machine advanced by the four laws above."""

    __slots__ = ("dead", "length", "out", "ptr", "skip", "tape")

    def __init__(self, size: int) -> None:
        r"""Start with a zeroed tape of ``size`` cells at the origin."""
        self.tape = 0
        self.length = size
        self.ptr = 0
        self.out: list[str] = []
        self.dead = False
        self.skip = False

    def cell(self, index: int) -> int:
        r"""Return the bit in cell ``index``."""
        return (self.tape >> index) & 1

    def cells(self, stop: int) -> tuple[int, ...]:
        r"""Return cells ``0..stop-1``, the shape a column comparison wants."""
        return tuple((self.tape >> i) & 1 for i in range(stop))

    def copy(self) -> "_Sim":
        r"""Return an independent copy, for branching a derivation or a probe."""
        clone = _Sim.__new__(_Sim)
        clone.tape = self.tape
        clone.length = self.length
        clone.ptr = self.ptr
        clone.out = list(self.out)
        clone.dead = self.dead
        clone.skip = self.skip
        return clone

    def key(self) -> tuple[object, ...]:
        r"""Return the whole state, hashable, so a caller can dedup on it."""
        return (self.tape, self.length, self.ptr, tuple(self.out), self.dead, self.skip)

    def run_left(self, count: int) -> None:
        r"""Apply ``"<" * count``: the left law."""
        if self.dead or count <= 0:
            return
        if self.skip:
            self.skip = False
            count -= 1
        self.ptr = max(self.ptr - count, 0)

    def run_comment(self, count: int) -> None:
        r"""Apply a run of comment characters: the comment law."""
        if self.dead or count <= 0:
            return
        if self.skip:
            self.skip = False

    def run_walk(self, pairs: int) -> None:
        r"""Apply ``"[x" * pairs``: the walk law, in closed form."""
        if self.dead or pairs <= 0:
            return
        if self.skip:
            # The pending skip eats the.
            self.skip = False
            pairs -= 1
            if pairs == 0:
                return
        tape, ptr = self.tape, self.ptr
        low = ptr + 1
        mask = (1 << pairs) - 1
        # Prefix XOR of the window by.
        # holds the XOR of itself and.
        # spans compose to cover the.
        carries = (tape >> low) & mask
        span = 1
        while span < pairs:
            carries ^= (carries << span) & mask
            span <<= 1
        tape = (tape & ~(mask << low)) | ((carries ^ mask) << low)
        # The window's total parity is.
        # lands in the cell above --.
        tape ^= ((carries >> (pairs - 1)) & 1) << (low + pairs)
        ptr += pairs
        self.tape, self.ptr = tape, ptr
        self.length = max(self.length, ptr + 2)

    def run_brackets(self, count: int) -> None:
        r"""Apply ``"[" * count``: the bracket law."""
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
                # The crossing lands on 0, so.
                # above and owes a skip to.
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
        # e_j for j = 1..count: a run.
        # so the window never needs to.
        mask = (1 << count) - 1
        effective = (tape >> low) & mask
        span = 1
        while span < count:
            effective ^= (effective << span) & mask
            span <<= 1
        # The staircase inverse: T is.
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
            # Remainder 1: the next.
            # its skip pending for the.
            crossed += 1
            skip_out = True
        else:
            skip_out = False
        # Exhausted over every.
        # staircase inverse is never 0.
        # two arms above.
        if crossed == 0:  # pragma: no cover - see above
            return
        window = (1 << crossed) - 1
        effective &= window
        tape = (tape & ~(window << low)) | ((effective ^ window) << low)
        # The carry: the last.
        tape ^= ((effective >> (crossed - 1)) & 1) << (low + crossed)
        self.tape = tape
        self.ptr = ptr + crossed
        self.skip = skip_out
        self.length = max(self.length, self.ptr + 2)

    def run_weight(self, units: int) -> bool:
        r"""Apply ``("[x<[<" + "<") * (units - 1) + "[x<[<"`` in closed form."""
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
        r"""Apply the sculpting round ``"<" * count + "[x" * count + "x"``."""
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
        r"""Apply a sequence of sculpting rounds, fused over their window."""
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
        r"""Apply ``.``: the print law."""
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
        r"""Advance by an already-parsed emission, one law call per run."""
        for law, count in parsed:
            law(self, count)

    def exec(self, ins: str) -> None:
        r"""Execute one instruction, the single-character case of the laws."""
        if ins == "<":
            self.run_left(1)
        elif ins == "[":
            self.run_brackets(1)
        elif ins == ".":
            self.run_dot()
        else:
            self.run_comment(1)


def _set_bit(bit: int) -> str:
    r"""Return the ``{Xi}`` fill writing ``bit`` at ``ptr+1``."""
    return "[<" if bit else "xx"


class _Joint:
    r"""The ``2**n`` instantiations, advanced in lockstep as code is."""

    def __init__(self, n: int, size: int = 512) -> None:
        r"""Start one machine per row of the truth table."""
        self.n = n
        self.rows = [[(r >> (n - 1 - k)) & 1 for k in range(n)] for r in range(2**n)]
        self.ms = [_Sim(size) for _ in self.rows]
        self.parts: list[str] = []

    def emit(self, code: str) -> None:
        r"""Append code and run it on every row, keeping them in lockstep."""
        self.parts.append(code)
        if not code:
            return
        parsed = _runs(code)
        for m in self.ms:
            m.apply(parsed)

    def emit_setter(self, i: int) -> None:
        r"""Emit the ``{Xi}`` placeholder, simulating each row with its bit."""
        self.parts.append("{X" + str(i) + "}")
        one = _runs(_set_bit(1))
        zero = _runs(_set_bit(0))
        for bits, m in zip(self.rows, self.ms, strict=True):
            m.apply(one if bits[i] else zero)

    def emit_weight(self, code: str, units: int) -> None:
        r"""Append the weight gadget, advancing rows by its composed law."""
        self.parts.append(code)
        parsed: _Runs | None = None
        for m in self.ms:
            if not m.run_weight(units):
                if parsed is None:
                    parsed = _runs(code)
                m.apply(parsed)

    def fork(self) -> "_Joint":
        r"""Return a copy, for trying a continuation without committing."""
        clone = _Joint.__new__(_Joint)
        clone.n = self.n
        clone.rows = self.rows
        clone.ms = [m.copy() for m in self.ms]
        clone.parts = list(self.parts)
        return clone

    def col(self, cell: int) -> tuple[int, ...]:
        r"""Return ``cell``'s value across the rows -- the function it holds."""
        return tuple(m.cell(cell) for m in self.ms)

    def ptrs(self) -> tuple[int, ...]:
        r"""Return each row's pointer, so callers can see divergence."""
        return tuple(m.ptr for m in self.ms)

    def printed(self) -> list[str]:
        r"""Return what each row has printed so far."""
        return ["".join(m.out) for m in self.ms]

    def template(self) -> str:
        r"""Return the emitted template, ``{Xi}`` placeholders included."""
        return "".join(self.parts)


def _walk_to(j: _Joint, target: int) -> None:
    r"""Walk right to ``target`` with ``[x``, which is safe over any junk."""
    ptrs = set(j.ptrs())
    if len(ptrs) != 1:
        raise ValueError(f"walk needs a converged pointer, got {ptrs}")
    cur = ptrs.pop()
    if target < cur:
        raise ValueError(f"cannot walk left with [x ({cur} -> {target})")
    j.emit("[x" * (target - cur))


def _clamp(j: _Joint) -> None:
    r"""Clamp every row's pointer to 0."""
    j.emit("<" * (max(j.ptrs()) + 1))
