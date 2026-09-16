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

A cube's guard needs one part per constraint, and any basis of the cube's
dual space will do.  :func:`_constraints` builds one from short relations:
all but at most ``1 + 2**((dim + 1) / 2)`` constraints are parities of at
most four inputs, the rest come from reduced elimination at most ``dim +
1`` wide, so a clause's constraints weigh at most ``4 * n + (dim + 1) * (1
+ 2**((dim + 1) / 2))`` inputs in total.  Single-input constraints test
the input name directly and wider ones live in strict register bindings
(``A ~> a?``, ``A ~> A? != b?``) that later clauses morph one toggle at a
time instead of respelling; a fresh register costs one line per input of
its parity and a morph strictly fewer, so upkeep never exceeds the total
constraint weight.  Summed over the peel, ``4 * n`` per clause is ``4 * n
+ 36 * 2**n`` by the clause bound, and the second term is at most ``4 *
2**dim`` per clause, hence ``4 * 2**n`` over the disjoint cubes.  Register
upkeep is therefore O(T) -- under ``40 * 2**n + 4 * n`` lines -- and its
measured share stays under half of the emitted text.  The bank holds at
most ``n**2`` registers (:func:`_bank_cap`), so a register name is never
longer than two input names and a full bank respells its least recently
used free register at the same cost as a fresh one.  The reduced-echelon
basis alone would not give this: on a cube whose columns spread over
``2**dim`` values it weighs ``n * dim / 2`` however the pivots are
chosen, which is ``Theta(T log log T)`` at the ``log2(n)`` dimensions the
peel produces.
"""

from esolangs.tools.helpers import _validate_truth_table

__all__ = ["vandevelo"]


_ALPHABET = "abcdefghijkmnopqrstuvwxyzABCDEFGHJKLMOPQRSTUVWXYZ0123456789_&*$"
_RESERVED = {"Inp", "Nil", "l", "loop"}

# Direction candidates scored per growth round.  The peel is exact with any
# cap -- a missed direction only costs cover size -- and 48 keeps the
# popular-difference scan linear in the remainder instead of quadratic.
_CANDIDATE_CAP = 48


def _bank_cap(n: int) -> int:
    """Live registers allowed for an ``n``-input table.

    Uncapped, the bank grows with the peel -- 7 registers at n=6 to 117 at
    n=13, about ``2**(n/2)`` -- and names for that many registers would put
    a factor of ``n`` on every reference.  ``n**2`` keeps a register name
    within twice an input name's length, always leaves a free register (a
    clause binds at most ``n - 1``), and never binds at measured sizes;
    ``n`` or ``2 * n`` would cost 40% and 23% at n=13 in forced respelling.
    """
    return n * n


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


def _echelon(dirs: list[int], n: int) -> list[int]:
    """Reduced-echelon basis of the constraint space of ``span(dirs)``.

    Reduced elimination keeps each dual to one free coordinate plus bits on
    the ``len(dirs)`` pivots, so no vector is wider than ``dim + 1``.  Only
    the completion step of :func:`_constraints` needs it.
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
    return duals


def _constraints(base: int, dirs: list[int], n: int) -> list[tuple[int, int]]:
    """Dual constraints pinning ``base + span(dirs)``: ``(parity, value)``.

    A constraint is a set of inputs whose ``dirs``-columns (the vector of
    the set's bits across the directions) sum to zero, and any basis of
    those sets pins the cube.  This one is built from short relations:
    inputs are scanned in order and kept in a *core* while no one-to-four
    of the core's columns sum to zero; every other input's column is, by
    maximality, a sum of at most three core columns, giving it a relation
    of weight at most four that no other relation shares its bit with.
    The core's pairwise column sums are distinct and nonzero in
    ``2**dim - 1`` values, so it holds at most ``1 + 2**((dim + 1) / 2)``
    inputs, and the ``|core| - dim`` relations still missing come from
    the reduced-echelon basis, each at most ``dim + 1`` wide.

    A cube's constraints therefore weigh at most
    ``4 * n + (dim + 1) * (1 + 2**((dim + 1) / 2))`` in total, against
    ``(n - dim) * (dim + 1)`` for the echelon basis alone, which is what
    the module docstring's O(T) upkeep bound sums.
    """
    dim = len(dirs)
    cols = [sum((v >> j & 1) << i for i, v in enumerate(dirs)) for j in range(n)]
    # Sums of one to three core columns, mapped to the set of inputs summed.
    sums: dict[int, int] = {}
    core: list[int] = []
    duals: list[int] = []
    for j, col in enumerate(cols):
        if col == 0:
            duals.append(1 << j)
        elif col in sums:
            duals.append(sums[col] | 1 << j)
        else:
            singles = [(cols[c], 1 << c) for c in core]
            pairs = [(a ^ b, x | y) for a, x in singles for b, y in singles if x < y]
            for value, inputs in [(col, 1 << j)] + [
                (col ^ a, 1 << j | x) for a, x in singles + pairs
            ]:
                sums.setdefault(value, inputs)
            core.append(j)
    # A short relation's leading bit is its own input -- the core inputs it
    # sums are all earlier -- so the relations are independent as they
    # stand.  Complete to a basis from the echelon duals, keeping each only
    # when it is independent of what came before.
    reduced = {w.bit_length() - 1: w for w in duals}
    for w in _echelon(dirs, n):
        cur = w
        while cur and (cur.bit_length() - 1) in reduced:
            cur ^= reduced[cur.bit_length() - 1]
        if cur:
            reduced[cur.bit_length() - 1] = cur
            duals.append(w)
    if len(duals) != n - dim:  # pragma: no cover - a basis has n - dim rows
        raise AssertionError("constraint basis has the wrong rank")
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
                    bank[register] = bank.pop(register)  # most recently used
                else:
                    nearest: str | None = None
                    distance = w.bit_count()
                    for r, held in bank.items():
                        if r in used:
                            continue
                        d = (held ^ w).bit_count()
                        if d < distance:
                            nearest, distance = r, d
                    if nearest is not None:
                        register = nearest
                        toggles = _points(bank.pop(register) ^ w)
                    elif len(bank) < _bank_cap(n):
                        register = _name(next_register)
                        next_register += 1
                        toggles = _points(w)
                    else:
                        # Bank full: respell the least recently used free
                        # register, which costs what a fresh one would.
                        register = next(r for r in bank if r not in used)
                        del bank[register]
                        toggles = _points(w)
                    if nearest is None:
                        first, toggles = ref(toggles[0]), toggles[1:]
                        lines.append(
                            f"{register}~>{first}?"
                            if compact
                            else f"{register} ~> {first}?"
                        )
                    for b in toggles:
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
