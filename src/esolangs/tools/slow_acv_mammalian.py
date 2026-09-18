"""Boolean-function generator for SLOW ACV MAMMALIAN.

A *chain* of ``n`` read nodes and one dispatch jump into a table of
256-token leaf slots: O(T) size and build, where the tree it replaced was
super-linear (``S(d) >= (2 + 1/255) S(d-1)``).  Two identities carry the
control flow, machine-verified end to end over every table through
``n == 3``:

``landing = start - 15``
    A read node is ``SEED*wrap EXCRETE SEED*j1 DIGEST SEED*16 DIGEST
    ACCEPT DIGEST LEAPFROG``; on :func:`_aim`'s class the 1-branch resumes
    15 tokens short and ``j1`` cancels (see :func:`_node`).

``target = nonhead + b``
    ``LEAPFROG`` targets ``acc - head - 1`` and a fresh ``DIGEST`` folds
    the head in, so an unconditional jump lands on the non-head sum plus
    its own appended byte.

A bit's whole effect is banked as ``2**(n-1-i) * 256`` on array 16's
non-head sum; both branches leave through trampolines aimed at one merge
address (so array 0's sums agree exactly), the 1-arm's tuning chunk
(:func:`_arm`) zeroes the even head residue at slope -2, and the weights
being multiples of 256 keep every downstream mod-256 solve blind to which
arms ran.  The 1-arm reaches array 16 with ``SPRINT``, appends its weight
in chunks of at most 15 ``SEED``s (head steps by 17, so a byte >= 239 is
within 15 steps), and returns the same way.

Everything is closed-form; the two bounded fixed points raise if they do
not settle, and the merge equalities are asserted on every build.
Executed evidence: every table through ``n == 3``, plus sampled rows of
dense tables through ``n == 12``.  All ``n`` inputs are read
unconditionally.
"""

from collections.abc import Sequence

from esolangs.tools.helpers import _ASCII_ZERO, _validate_truth_table

__all__ = ["slow_acv_mammalian"]

# The byte a stash chunk appends.  It is what raises the sum, and the sum is
# what puts a distant token index within a jump's reach, so the chunk buys
# the most reach per token by appending the largest byte there is.
_STASH_BYTE = 255

# The read node's second seed run.  The aim class fixes ``first & 48 == 16``,
# and XORing bits 4-5 from ``01`` to ``10`` is ``+16``, so this run is what
# lands the accumulator on the clean digit 48 -- it is not a free knob.
_J2 = 16

# The weight array.  It is one of the construction's free arrays, and SEED
# steps its head by 17 -- odd, so every residue is reachable -- while a head
# of 16 on array 0 SPRINTs the pointer there and a head of 7 SPRINTs it
# back (16 + 7 == 23).
_W = 16
_W_STEP = _W + 1
_W_INV = pow(_W_STEP, -1, 256)
_ROUTE_BACK = 23 - _W

# One leaf's fixed slot.  The weights are ``2**i`` multiples of it, so it
# must be a multiple of 256 for the mod-256 solves to stay blind to them,
# and the dispatch byte is chosen so every leaf body fits (see the solve in
# :func:`slow_acv_mammalian`).
_LEAF_SLOT = 256

#: A machine state as the generator tracks it: array 0 and the accumulator.
type _State = tuple[list[int], int]


def _seeded(array: Sequence[int], count: int) -> list[int]:
    """``array`` after ``count`` ``SEED``s, which only move the head."""
    out = list(array)
    out[0] = (out[0] + count) % 256
    return out


def _stash_chunk(array: list[int], acc: int) -> tuple[list[str], list[int], int]:
    """``SEED*k DIGEST EXCRETE``, appending exactly ``_STASH_BYTE``.

    The sum's low byte advances by one per ``SEED`` even across a head
    wrap, so the count solves in one step; from the third chunk on every
    count is 1, so a chunk is 3 tokens for 255 of reach.
    """
    count = (((acc % 256) ^ _STASH_BYTE) - sum(array)) % 256
    return (
        [*["SEED"] * count, "DIGEST", "EXCRETE"],
        [*_seeded(array, count), _STASH_BYTE],
        0,
    )


def _aim(start: int) -> int:
    """Return the seed count putting ``start + j1`` on the aim class.

    Even values whose bits 4-5 are ``01``: 16 residues per 256, at most 49
    apart, so the head stays far under the 255 a mid-run wrap needs.
    """
    offset = (start - _J2) % 64
    if offset <= 14:
        # Inside a class block; an odd ``start`` steps to the next even.
        return start % 2
    return 64 - offset


def _node(array: list[int], acc: int) -> tuple[list[str], _State, _State, int]:
    """One read node: tokens, the 0-exit, the 1-exit, and the landing.

    The 0-branch falls through with ``acc == first``; the 1-branch jumps
    to ``start - 15`` with ``acc == first + 1``.  Neither exit depends on
    ``j1``, so the landing commits before the arm and merge exist.
    """
    wrap = (256 - array[0]) % 256
    opened = [*_seeded(array, wrap), acc % 256]
    start = sum(opened)
    j1 = _aim(start)
    first = start + j1
    tokens = [
        *["SEED"] * wrap,
        "EXCRETE",
        *["SEED"] * j1,
        "DIGEST",
        *["SEED"] * _J2,
        "DIGEST",
        "ACCEPT",
        "DIGEST",
        "LEAPFROG",
    ]
    loaded = _seeded(opened, j1 + _J2)
    return tokens, ([*loaded, 0], first), ([*loaded, 1], first + 1), start - 15


def _trampoline(
    array: list[int], acc: int, target: int
) -> tuple[list[str], list[int], int]:
    """Build an unconditional jump to token ``target``, plus its exit state.

    Chunks raise the non-head sum by 255 each until ``target`` is within a
    byte, then ``u`` is solved so the ``EXCRETE`` appends the closing
    ``b``.  ``b >= 1`` keeps the ``LEAPFROG`` firing; callers always aim
    past the sum they enter with.  ``rest_sum`` is ``sum(cur) - cur[0]``
    carried incrementally: each chunk appends exactly one new element
    (``_STASH_BYTE``) and touches no other, so re-summing the growing
    list every iteration -- as a naive read of the loop condition would
    -- costs O(chunks**2) for no reason.
    """
    cur, val, tokens = list(array), acc, []
    rest_sum = sum(cur[1:])
    while rest_sum < target - 255:
        chunk, cur, val = _stash_chunk(cur, val)
        rest_sum += _STASH_BYTE
        tokens += chunk
    hop = target - rest_sum
    if not 1 <= hop <= 255:  # pragma: no cover - the window solve is exact
        raise AssertionError(f"trampoline byte {hop} escaped 1..255")
    count = (((val % 256) ^ hop) - (cur[0] + rest_sum)) % 256
    tokens += [*["SEED"] * count, "DIGEST", "EXCRETE", "DIGEST", "LEAPFROG"]
    out = [(cur[0] + count) % 256, *cur[1:], hop]
    return tokens, out, sum(out)


def _trampoline_len(array: list[int], acc: int, target: int) -> int:
    """Token count :func:`_trampoline` would emit reaching ``target``, O(1).

    The first two chunks solve a residue from ``acc``; every chunk after
    that always spends exactly one ``SEED`` (verified against
    :func:`_stash_chunk` directly), so the tail is closed by division
    instead of walked -- what lets the per-node retry search check a
    candidate landing without paying for the trampoline it would build.
    """
    cur, val = list(array), acc
    tokens = 0
    rest_sum = sum(cur[1:])
    for _ in range(2):
        if rest_sum >= target - 255:
            break
        chunk, cur, val = _stash_chunk(cur, val)
        rest_sum += _STASH_BYTE
        tokens += len(chunk)
    if rest_sum < target - 255:
        more = -(-(target - 255 - rest_sum) // _STASH_BYTE)
        tokens += 3 * more
        rest_sum += _STASH_BYTE * more
        cur = [(cur[0] + more) % 256, *cur[1:]]
    hop = target - rest_sum
    count = (((val % 256) ^ hop) - (cur[0] + rest_sum)) % 256
    return tokens + count + 4


def _chunk_run(chunks: int) -> int:
    """Bound from above what ``chunks`` stash chunks cost in tokens."""
    return 257 * min(chunks, 2) + 3 * max(0, chunks - 2)


def _tramp_bound(distance: int) -> int:
    """Upper bound on a trampoline's tokens for a raise of ``distance``."""
    chunks = max(0, -(-(distance - 255) // 255))
    return _chunk_run(chunks) + 255 + 4 + 8


class _Sums:
    """Build-time machine state: heads and non-head sums of arrays 0 and 16.

    Cells are never indexed (no ``CONSUME``/``FISSION``; ``SPRINT`` reads
    only ``curr[0]``), so the sums, heads, accumulator and pointer are the
    whole state.
    """

    __slots__ = ("acc", "h0", "hw", "n0", "nw", "ptr")

    def __init__(self) -> None:
        self.h0 = self.n0 = self.hw = self.nw = self.acc = self.ptr = 0

    def clone(self) -> "_Sums":
        out = _Sums.__new__(_Sums)
        for field in _Sums.__slots__:
            setattr(out, field, getattr(self, field))
        return out

    def arr0(self) -> list[int]:
        """Array 0 as the two-cell stand-in the sum arithmetic works on."""
        return [self.h0, self.n0]


def _replay(st: _Sums, tokens: Sequence[str], bit: int = 0) -> None:
    """Apply a token run to ``st``.  ``LEAPFROG`` moves only the cursor."""
    for tok in tokens:
        if tok == "SEED":
            st.h0 = (st.h0 + 1) % 256
            st.hw = (st.hw + _W_STEP) % 256
        elif tok == "DIGEST":
            st.acc ^= (st.h0 + st.n0) if st.ptr == 0 else (st.hw + st.nw)
        elif tok == "EXCRETE":
            if st.ptr == 0:
                st.n0 += st.acc % 256
            else:
                st.nw += st.acc % 256
            st.acc = 0
        elif tok == "ACCEPT":
            if st.acc % 256 != 48:
                raise AssertionError(f"ACCEPT entered with acc % 256 == {st.acc % 256}")
            st.n0 += bit
        elif tok == "SPRINT":
            if st.acc != 0:
                raise AssertionError("SPRINT with a nonzero accumulator")
            st.ptr = (st.ptr + (st.h0 if st.ptr == 0 else st.hw)) % 23


def _route_to_w(st: _Sums) -> list[str]:
    """Move the pointer 0 -> 16: launder acc to 0, set head 16, ``SPRINT``."""
    tokens = ["DIGEST", "EXCRETE"]
    _replay(st, tokens)
    run = [*["SEED"] * ((_W - st.h0) % 256), "SPRINT"]
    _replay(st, run)
    return tokens + run


def _route_to_0(st: _Sums) -> list[str]:
    """Move the pointer 16 -> 0.  The accumulator is already 0."""
    tokens = [*["SEED"] * (((_ROUTE_BACK - st.hw) * _W_INV) % 256), "SPRINT"]
    _replay(st, tokens)
    return tokens


def _w_exact_chunk(st: _Sums, value: int) -> list[str]:
    """Append exactly ``value`` (1..255) to array 16's non-head sum."""
    count = ((value - st.hw - st.nw) * _W_INV) % 256
    tokens = [*["SEED"] * count, "DIGEST", "EXCRETE"]
    before = st.nw
    _replay(st, tokens)
    if st.nw - before != value:  # pragma: no cover - the inverse is exact
        raise AssertionError(f"chunk appended {st.nw - before}, wanted {value}")
    return tokens


def _w_greedy_chunk(st: _Sums) -> list[str]:
    """Append a byte of at least 239 for at most 15 ``SEED``s.

    Head steps by 17, so 16 counts always hit the 17-wide window [239, 255].
    """
    for count in range(16):
        if (st.hw + st.nw + _W_STEP * count) % 256 >= 239:
            tokens = [*["SEED"] * count, "DIGEST", "EXCRETE"]
            _replay(st, tokens)
            return tokens
    raise AssertionError("no 17-step residue in [239, 255]")  # pragma: no cover


def _w_raise(st: _Sums, amount: int) -> list[str]:
    """Raise array 16's non-head sum by exactly ``amount >= 0``.

    Greedy chunks close all but the last 510, two exact chunks finish:
    about a token per 14 of weight, never overshot.
    """
    tokens: list[str] = []
    end = st.nw + amount
    while end - st.nw > 510:
        tokens += _w_greedy_chunk(st)
    if end - st.nw > 255:
        tokens += _w_exact_chunk(st, end - st.nw - 255)
    if end - st.nw:
        tokens += _w_exact_chunk(st, end - st.nw)
    return tokens


def _greedy_step_table() -> tuple[tuple[int, int], ...]:
    """For each residue ``r``, the greedy chunk's ``(seed count, added byte)``.

    Derived directly from :func:`_w_greedy_chunk`'s own search, not fit to
    any table of programs -- 256 residues, once, at import time.
    """
    table = []
    for r in range(256):
        for count in range(16):
            added = (r + _W_STEP * count) % 256
            if added >= 239:
                table.append((count, added))
                break
        else:  # pragma: no cover - argued in _w_greedy_chunk's docstring
            raise AssertionError(f"no 17-step residue in [239, 255] from {r}")
    return tuple(table)


_GREEDY_STEP = _greedy_step_table()


def _greedy_advance(r: int, target: int) -> tuple[int, int, int, int]:
    """Fast-forward the greedy phase: total SEEDs and advance past ``target``.

    A chunk's added byte depends only on the residue ``r = (hw + nw) %
    256`` (:func:`_greedy_step_table`), and the next residue is always
    ``2 * added % 256`` -- multiply out ``r' = (r + 17*count + added) %
    256`` where ``added = (r + 17*count) % 256`` and the ``17*count``
    terms cancel mod 256.  That orbit lives in 256 states, so simulating
    it must repeat a residue within 256 steps; once it does, the repeat's
    span is a cycle whose whole-multiples are skipped by multiplication
    instead of being walked, which is what makes this O(1) in ``target``
    rather than O(target / 247) like :func:`_w_raise`'s direct loop.
    Returns ``(seed count, chunk count, byte advance, final residue)``.
    """
    if target <= 0:
        return 0, 0, 0, r
    seen: dict[int, tuple[int, int, int]] = {}
    steps = seed_count = advance = 0
    while advance < target:
        if r in seen:
            prev_steps, prev_seeds, prev_advance = seen[r]
            cyc_steps = steps - prev_steps
            cyc_seeds = seed_count - prev_seeds
            cyc_advance = advance - prev_advance
            full = (target - advance - 1) // cyc_advance
            if full > 0:
                steps += full * cyc_steps
                seed_count += full * cyc_seeds
                advance += full * cyc_advance
            seen = {}  # landed back on the same r; walk the remainder plainly
            continue
        seen[r] = (steps, seed_count, advance)
        count, added = _GREEDY_STEP[r]
        seed_count += count
        steps += 1
        advance += added
        r = (2 * added) % 256
    return seed_count, steps, advance, r


def _route_to_0_len(hw: int) -> int:
    """Token count :func:`_route_to_0` would emit from head ``hw``."""
    return ((_ROUTE_BACK - hw) * _W_INV) % 256 + 1


def _w_raise_len(hw: int, nw: int, amount: int) -> tuple[int, int]:
    """``(token count, final hw)`` for :func:`_w_raise`'s effect, in O(1).

    Mirrors ``_w_raise`` exactly -- same chunk boundaries, same byte
    values -- but the greedy phase is closed by :func:`_greedy_advance`
    instead of walked chunk by chunk.  Sizing an arm's slot only needs
    this length and the resulting head (:func:`_route_to_0_len` needs
    nothing else), never the token text itself.
    """
    r = (hw + nw) % 256
    target = max(0, amount - 510)
    total_seeds, chunks, greedy_advance_amt, r = _greedy_advance(r, target)
    remaining = amount - greedy_advance_amt
    if remaining > 255:
        value = remaining - 255
        count = ((value - r) * _W_INV) % 256
        total_seeds += count
        chunks += 1
        r = (2 * value) % 256
        remaining = 255
    if remaining:
        value = remaining
        count = ((value - r) * _W_INV) % 256
        total_seeds += count
        chunks += 1
    tokens = total_seeds + 2 * chunks
    final_hw = (hw + _W_STEP * total_seeds) % 256
    return tokens, final_hw


def _jump(st: _Sums, target: int) -> list[str]:
    """Emit an array-0 trampoline to ``target`` and replay it onto ``st``."""
    tokens, out_arr, out_acc = _trampoline(st.arr0(), st.acc, target)
    _replay(st, tokens)
    if (st.h0, st.n0, st.acc) != (out_arr[0], sum(out_arr[1:]), out_acc):
        raise AssertionError("sum replay diverged from the trampoline model")
    return tokens


def _arm(one: _Sums, weight: int, beta: int, cont: int) -> tuple[list[str], _Sums]:
    """Build the 1-branch: bank ``weight`` on array 16 and merge at ``cont``.

    The tuning chunk's ``beta`` shifts this path's SEED count at slope -2,
    the knob that matches the 0-path's heads.
    """
    st = one.clone()
    tokens = _route_to_w(st)
    tokens += _w_raise(st, weight)
    tokens += _route_to_0(st)
    run = [*["SEED"] * ((beta - st.h0 - st.n0) % 256), "DIGEST", "EXCRETE"]
    _replay(st, run)
    tokens += run
    tokens += _jump(st, cont)
    return tokens, st


def _dispatch(st: _Sums, base: int) -> tuple[list[str], _Sums, list[int]]:
    """Build the jump into the leaf table, byte 1, plus the leaf counts.

    The exit residue is pinned even at ``sum % 256 == 2b``, so the worst
    leaf count is 240 of the slot's 252; the byte is the least that fires.
    """
    b = 1
    d = st.clone()
    tokens = _w_raise(d, base - b - st.nw)
    u = ((b - d.hw - d.nw) * _W_INV) % 256
    tail = [*["SEED"] * u, "DIGEST", "EXCRETE", "DIGEST", "LEAPFROG"]
    _replay(d, tail)
    tokens += tail
    s_mod = d.acc % 256
    c_of = [
        (((s_mod ^ (_ASCII_ZERO + digit)) - d.hw - d.nw) * _W_INV) % 256
        for digit in (0, 1)
    ]
    if s_mod != 2 * b or d.nw != base:  # pragma: no cover - the solves are exact
        raise AssertionError("the dispatch missed the leaf base")
    if max(c_of) + 4 > _LEAF_SLOT:  # pragma: no cover - worst count is 240
        raise AssertionError("a leaf overflowed its slot")
    return tokens, d, c_of


def slow_acv_mammalian(truth_table: str) -> str:
    """Build a SLOW ACV MAMMALIAN program evaluating ``truth_table``.

    One read node per input (``ACCEPT``), one dispatch jump, one 256-token
    leaf slot per entry: O(T) text.
    """
    n = _validate_truth_table(truth_table)
    st = _Sums()
    tokens: list[str] = []
    pos = 0

    for i in range(n):
        weight = _LEAF_SLOT * (1 << (n - 1 - i))
        # The node, with prefix ballast until the landing clears the
        # 0-branch trampoline exactly.  Every piece is rebuilt per chunk
        # because the chunk moves every solve.
        while True:
            node_toks, _, _, landing = _node(st.arr0(), st.acc)
            node_end = pos + len(node_toks)
            zero = st.clone()
            _replay(zero, node_toks, bit=0)
            one = st.clone()
            _replay(one, node_toks, bit=1)
            # Size the arm's slot from an exact length, not a dry build:
            # the slot only has to hold the tuning chunk and merge
            # trampoline too, and everything past them before ``cont`` is
            # dead.  ``_w_raise`` alone is O(weight) to simulate, and this
            # retry loop can run several times per level, so a level's
            # sizing cost was O(weight) per retry -- ``_w_raise_len``
            # closes it to O(1) without changing which attempt succeeds.
            core = one.clone()
            route_w_toks = _route_to_w(core)
            w_len, w_final_hw = _w_raise_len(core.hw, core.nw, weight)
            core_len = len(route_w_toks) + w_len + _route_to_0_len(w_final_hw)
            arm_slot = core_len + 257 + _tramp_bound(600)
            for _ in range(8):
                need = core_len + 257 + _tramp_bound(arm_slot)
                if need <= arm_slot:
                    break
                arm_slot = need
            else:  # pragma: no cover - the bound grows ~3/255 per token
                raise AssertionError("the arm slot did not settle")
            cont = landing + arm_slot
            # Only the landing check needs the trampoline's length, and
            # most retries fail it: building the real jump here re-paid
            # its O(distance) cost on every retry, on top of the ones
            # that fail.  ``_trampoline_len`` answers the check in O(1);
            # the real jump is built once below, for whichever attempt
            # the loop settles on.
            t0_len = _trampoline_len(zero.arr0(), zero.acc, cont)
            if landing >= node_end + t0_len:
                break
            chunk, _, _ = _stash_chunk(st.arr0(), st.acc)
            _replay(st, chunk)
            tokens += chunk
            pos += len(chunk)

        z = zero.clone()
        t0 = _jump(z, cont)
        if len(t0) != t0_len:  # pragma: no cover - the fast length is exact
            raise AssertionError(
                f"trampoline length mismatch: fast {t0_len}, real {len(t0)}"
            )

        tokens += node_toks
        tokens += t0
        tokens += ["SEED"] * (landing - node_end - len(t0))
        pos = landing

        # The arm at the landing, beta-tuned until the heads merge.  The
        # delta is always even (both paths' final solves leave
        # ``head0 == 2*hop - cont``) and beta moves it at slope -2; a
        # chunk-count boundary can shift the structure under the solve,
        # which the loop absorbs.
        beta = _STASH_BYTE
        for _ in range(8):
            arm_toks, merged = _arm(one, weight, beta, cont)
            delta = (merged.h0 - z.h0) % 256
            if delta == 0:
                break
            if delta % 2:  # pragma: no cover - see the evenness argument
                raise AssertionError(f"odd head delta {delta} at level {i}")
            beta = (beta + delta // 2) % 256
        else:  # pragma: no cover - one boundary shift per rebuild at most
            raise AssertionError("the tuning byte did not settle")
        if (merged.hw, merged.acc, merged.n0) != (z.hw, z.acc, z.n0):
            raise AssertionError(f"the branch paths did not merge at level {i}")
        if merged.nw - z.nw != weight or merged.ptr or z.ptr:
            raise AssertionError(f"the banked weight drifted at level {i}")
        if len(arm_toks) > arm_slot:
            raise AssertionError(
                f"the arm of {len(arm_toks)} tokens overflowed its slot"
            )
        tokens += arm_toks
        tokens += ["SEED"] * (arm_slot - len(arm_toks))
        pos = cont
        st = z

    # The dispatch: one trampoline on array 16.  Its target is the full
    # non-head sum plus a byte, and the banked weights shifted that sum by
    # ``row * 256``, so the fixed code lands each run on its own leaf.
    route = _route_to_w(st)
    tokens += route
    pos += len(route)
    base = pos
    for _ in range(8):
        need = pos + 17 * -(-(base - st.nw) // 239) + 2 * 257 + 259 + 64
        if need <= base:
            break
        base = need
    else:  # pragma: no cover - the bound grows ~17/239 per token
        raise AssertionError("the leaf base did not settle")

    dispatch, _, c_of = _dispatch(st, base)
    tokens += dispatch
    tokens += ["SEED"] * (base - pos - len(dispatch))

    for entry in truth_table:
        count = c_of[int(entry)]
        tokens += [*["SEED"] * count, "DIGEST", "PRONOUNCE", "EXCRETE", "LEAPFROG"]
        tokens += ["SEED"] * (_LEAF_SLOT - count - 4)
    return " ".join(tokens)
