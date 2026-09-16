"""Boolean-function generator for Vandevelo.

The program reads the inputs, then hangs -- ``loop -> loop?`` evaluated
lazily never terminates -- exactly when the table entry is 1.  Every value
a Vandevelo program can bind is affine in the inputs (``==``/``!=`` are
XNOR/XOR over nil), and only ``::`` chains evaluate conditionally, so a
guard line hangs on an affine coset of inputs and a whole program hangs on
a union of cosets.  The generator therefore emits one guard line per coset
of an affine cover of the table's 1-set.

The cover is peeled: while 1-rows remain, an affine cube is grown inside
the remainder by iterated popular differences -- pick the direction ``v``
maximising ``|B & (B ^ v)|``, intersect, repeat while nonempty -- and its
rows are removed.  The counting behind that choice is Cohen--Shinkar's
(ECCC TR14-099): while the remainder has density ``eps``, a cube of
dimension ``log2(n) - log2(log2(1/eps)) - 2`` survives, so the peel ends in
``1 + 9 * 2**n / n`` clauses and the guard parts across all clauses total
``O(2**n)``.  Dense random tables measure a flat 8.1--8.9 characters per
entry at n=8..12 (9,397 at dense n=10 against the retired per-row
spelling's 36,829); the parity table is one hyperplane and collapses from
52,821 characters to 259.

A cube's guard needs one part per constraint.  Constraints come out of
Gaussian elimination in reduced form, so each is a parity of at most
``dim + 1`` inputs; single-input constraints test the input name directly
and wider ones live in strict register bindings (``A ~> a?``,
``A ~> A? != b?``) that later clauses morph one toggle at a time instead
of respelling.  Register upkeep is the one piece with no O(T) proof --
its worst case is O(T log log T) from the ``dim + 1`` width bound -- and
the measured upkeep share stays under half of the emitted text.
"""

from esolangs.tools.helpers import _validate_truth_table

__all__ = ["vandevelo"]


_ALPHABET = "abcdefghijkmnopqrstuvwxyzABCDEFGHJKLMOPQRSTUVWXYZ0123456789_&*$"
_RESERVED = {"Inp", "Nil", "l", "loop"}

# Direction candidates scored per growth round.  The peel is exact with any
# cap -- a missed direction only costs cover size -- and 48 keeps the
# popular-difference scan linear in the remainder instead of quadratic.
_CANDIDATE_CAP = 48


def _name(index: int) -> str:
    """Return the ``index``th shortest non-reserved Vandevelo name."""
    base = len(_ALPHABET)
    value = index + 1
    chars = []
    while value:
        value, digit = divmod(value - 1, base)
        chars.append(_ALPHABET[digit])
    return "".join(reversed(chars))


def _points(mask: int) -> list[int]:
    """Set bit positions of ``mask``, ascending."""
    out = []
    while mask:
        low = mask & -mask
        out.append(low.bit_length() - 1)
        mask ^= low
    return out


def _shift(mask: int, v: int, n: int) -> int:
    """Return the point-set ``mask`` with every point XORed by ``v``.

    One block swap per set bit of ``v``: bit ``b`` of the point index
    swaps adjacent 2**b-wide lanes of the 2**n-bit mask.
    """
    for b in range(n):
        if v >> b & 1:
            width = 1 << b
            lane = int(("0" * width + "1" * width) * (1 << (n - b - 1)), 2)
            mask = ((mask & lane) << width) | ((mask >> width) & lane)
    return mask


def _popularities(b_mask: int, n: int) -> list[int]:
    """``P[v] = |B & (B ^ v)|`` for every ``v``, one autocorrelation.

    Walsh--Hadamard transform of the indicator, squared pointwise, and
    transformed back: exact integers throughout, ``n * 2**n`` additions.
    """
    size = 1 << n
    vec = [b_mask >> x & 1 for x in range(size)]
    span = 1
    while span < size:
        for start in range(0, size, span * 2):
            for i in range(start, start + span):
                low, high = vec[i], vec[i + span]
                vec[i], vec[i + span] = low + high, low - high
        span *= 2
    vec = [value * value for value in vec]
    span = 1
    while span < size:
        for start in range(0, size, span * 2):
            for i in range(start, start + span):
                low, high = vec[i], vec[i + span]
                vec[i], vec[i + span] = low + high, low - high
        span *= 2
    return [value >> n for value in vec]


def _cube(rest: int, n: int, pool: list[int]) -> tuple[int, list[int]]:
    """Grow one affine cube inside the remainder set.

    Returns ``(base, dirs)`` with ``base ^ span(dirs)`` entirely inside
    ``rest``.  Directions are chosen by popular difference over a capped
    candidate list -- pooled directions from earlier cubes first, so
    consecutive clauses share constraint structure and the register bank
    below morphs instead of rebuilding.  While the working set is still
    dense (``|B| >= 2**n / n``), a capped scan that misses the pigeonhole
    average falls back to the exact autocorrelation, so every round in the
    regime Cohen--Shinkar's telescoping argument covers really does take a
    direction at least as popular as the average the argument needs.
    """
    b_mask = rest
    dirs: list[int] = []
    span = {0}
    while True:
        pivot = (b_mask & -b_mask).bit_length() - 1
        cands: list[int] = []
        seen = set(span)
        for v in pool:
            if v not in seen and v < (1 << n):
                cands.append(v)
                seen.add(v)
        diffs = sorted(
            (pivot ^ p for p in _points(b_mask) if pivot ^ p not in seen),
            key=lambda v: (v.bit_count(), v),
        )
        cands.extend(diffs[:_CANDIDATE_CAP])
        best_v, best_c = 0, 0
        for v in cands:
            count = (b_mask & _shift(b_mask, v, n)).bit_count()
            if count > best_c:
                best_v, best_c = v, count
        size = b_mask.bit_count()
        if size * n >= (1 << n) and best_c * (1 << n) < size * size:
            popular = _popularities(b_mask, n)
            for v in range(1, 1 << n):
                if popular[v] > best_c and v not in seen:
                    best_v, best_c = v, popular[v]
        if not best_c:
            break
        b_mask &= _shift(b_mask, best_v, n)
        dirs.append(best_v)
        span |= {s ^ best_v for s in span}
    base = (b_mask & -b_mask).bit_length() - 1
    return base, dirs


def _constraints(base: int, dirs: list[int], n: int) -> list[tuple[int, int]]:
    """Dual constraints pinning ``base + span(dirs)``: ``(parity, value)``.

    Reduced elimination keeps each dual to one free coordinate plus bits on
    the ``len(dirs)`` pivots, so no constraint is wider than ``dim + 1``.
    """
    pivots: dict[int, int] = {}
    for row in dirs:
        cur = row
        for bit, prow in pivots.items():
            if cur >> bit & 1:
                cur ^= prow
        if not cur:  # pragma: no cover - _cube only keeps independent dirs
            # A dependent direction would reduce to zero and take the pivot
            # key to -1, quietly corrupting the dual basis and so the guard.
            raise AssertionError("dependent direction reached elimination")
        hi = cur.bit_length() - 1
        for bit in pivots:
            if pivots[bit] >> hi & 1:
                pivots[bit] ^= cur
        pivots[hi] = cur
    duals = []
    for free in (b for b in range(n) if b not in pivots):
        w = 1 << free
        for bit, prow in pivots.items():
            if prow >> free & 1:
                w ^= 1 << bit
        duals.append(w)
    return [(w, (w & base).bit_count() % 2) for w in duals]


def vandevelo(truth_table: str, width: int | None = None) -> str:
    """Build a Vandevelo program computing ``truth_table`` by termination."""
    n = _validate_truth_table(truth_table)
    compact = width is not None
    names = [_name(index) for index in range(n)]
    lines = (
        [f"{names[index]}~>Inp?" for index in range(n)]
        if compact
        else [f"{names[index]} ~> Inp?" for index in range(n)]
    )
    lines.append("l->l?" if compact else "loop -> loop?")
    loop = "l?" if compact else "loop?"

    def ref(bit: int) -> str:
        # Index bit ``bit`` is the (n-1-bit)th input read: rows are spelled
        # most-significant-first, and the first read is the top bit.
        return names[n - 1 - bit]

    rest = 0
    for row, entry in enumerate(truth_table):
        if entry == "1":
            rest |= 1 << row

    pool: list[int] = []
    bank: dict[str, int] = {}
    next_register = n
    while rest:
        base, dirs = _cube(rest, n, pool)
        covered = 1 << base
        for v in dirs:
            covered |= _shift(covered, v, n)
        rest &= ~covered
        for v in dirs:
            if v in pool:
                pool.remove(v)
            pool.insert(0, v)
        del pool[24:]

        parts = []
        used: set[str] = set()
        for w, value in _constraints(base, dirs, n):
            if w.bit_count() == 1:
                part = ref(w.bit_length() - 1)
            else:
                exact = next(
                    (r for r, held in bank.items() if held == w and r not in used),
                    None,
                )
                if exact is not None:
                    register = exact
                else:
                    nearest: str | None = None
                    distance = w.bit_count()
                    for r, held in bank.items():
                        if r in used:
                            continue
                        d = (held ^ w).bit_count()
                        if d < distance:
                            nearest, distance = r, d
                    if nearest is None:
                        register = _name(next_register)
                        next_register += 1
                        bits = _points(w)
                        first, rest_bits = ref(bits[0]), bits[1:]
                        lines.append(
                            f"{register}~>{first}?"
                            if compact
                            else f"{register} ~> {first}?"
                        )
                        for b in rest_bits:
                            lines.append(
                                f"{register}~>{register}?!={ref(b)}?"
                                if compact
                                else f"{register} ~> {register}? != {ref(b)}?"
                            )
                    else:
                        register = nearest
                        for b in _points(bank[register] ^ w):
                            lines.append(
                                f"{register}~>{register}?!={ref(b)}?"
                                if compact
                                else f"{register} ~> {register}? != {ref(b)}?"
                            )
                    bank[register] = w
                used.add(register)
                part = register
            if value:
                parts.append(f"{part}?")
            else:
                parts.append(f"{part}?==Nil?" if compact else f"{part}? == Nil?")
        lines.append(
            "::".join([*parts, loop]) if compact else " :: ".join([*parts, loop])
        )
    return "\n".join(lines)
