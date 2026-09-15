"""Boolean-function generator for SLOW ACV MAMMALIAN.

The program is a *chain* of ``n`` read nodes followed by one dispatch jump
into a flat table of fixed 256-token leaf slots, so both the emitted size
and the build are O(T) for a table of length ``T = 2**n``: the tree this
replaced re-emitted both subtrees under every node and its slot recurrence
made it super-linear (``S(d) >= (2 + 1/255) S(d-1)``).

Two identities carry the control flow, both machine-verified by the tests
and end to end over every table through ``n == 3``:

``landing = start - 15``
    A read node is ``SEED*wrap EXCRETE SEED*j1 DIGEST SEED*16 DIGEST
    ACCEPT DIGEST LEAPFROG``; on the aim class :func:`_aim` picks, the
    1-branch resumes exactly 15 tokens short of the array sum and ``j1``
    cancels (see :func:`_node`).

``target = nonhead + b``
    ``LEAPFROG``'s target is ``acc - head - 1`` and a fresh ``DIGEST``
    folds the head in, so the head cancels and an unconditional jump lands
    on the non-head sum plus the byte its own ``EXCRETE`` appended.

What makes a *chain* possible where the tree forked is that a bit's whole
effect is banked as an exact binary weight ``2**(n-1-i) * 256`` on array
16's non-head sum and every other divergence between the two branch paths
is cancelled before they merge:

* Both branches leave through a trampoline aimed at the same merge
  address, and ``target = nonhead + b`` makes the post-jump non-head sum
  *equal the target*, so array 0's non-head sums agree exactly -- the
  next node's landing is path-independent.
* Both trampolines' final solves leave ``head0 == 2*hop - target``, so
  the branch paths' SEED counts differ by an even residue; the 1-arm's
  tuning chunk (:func:`_arm`) moves that residue at slope -2 and zeroes
  it, which equalizes every head (a SEED moves them all in lockstep).
* The weights are multiples of 256, so every mod-256 solve downstream is
  blind to which arms ran; only the dispatch jump, whose target is the
  full non-head sum, sees them -- and lands ``leaf_base + row * 256``.

The 1-arm reaches array 16 with ``SPRINT`` (head set to 16, ``acc == 0``
after an ``EXCRETE``), appends its weight in chunks of at most 15 ``SEED``s
each (array 16's head steps by 17, so a byte at least 239 is always within
15 steps), and returns the same way.  ``ACCEPT`` appends to array 0
whatever the pointer holds, so the reads themselves never route.

Everything is a closed form; the two bounded fixed points (the arm slot
and the tuning byte) settle in a few steps and raise if they do not.  The
merge equalities are asserted on every build, so a drifted identity aborts
the generation rather than emitting a mis-aimed program.  Executed
evidence: every table through ``n == 3``, every row, plus sampled rows of
dense tables through ``n == 12``.

The chain reads all ``n`` inputs unconditionally -- the reads are the
interface, so a constant table still consumes every input.
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

    ``SEED`` advances the sum by one per token, and a head wrap drops it by
    256, so the sum's *low byte* advances by exactly one either way.  Only
    the low byte is spent -- ``EXCRETE`` appends ``acc % 256`` -- so the
    count solves in one step instead of a scan.  After the first chunk the
    accumulator is 0 and the sum's low byte settles, so from the third
    chunk on every count is 1: a chunk is then 3 tokens for 255 of reach.
    """
    count = (((acc % 256) ^ _STASH_BYTE) - sum(array)) % 256
    return (
        [*["SEED"] * count, "DIGEST", "EXCRETE"],
        [*_seeded(array, count), _STASH_BYTE],
        0,
    )


def _aim(start: int) -> int:
    """Return the seed count putting ``start + j1`` on the aim class.

    The class is even values whose bits 4-5 are ``01`` -- 16 residues out
    of every 256, at most 49 apart, so the count never exceeds 49 and the
    node's head stays far under the 255 a mid-run wrap would need.
    """
    offset = (start - _J2) % 64
    if offset <= 14:
        # Inside a class block; an odd ``start`` steps to the next even.
        return start % 2
    return 64 - offset


def _node(array: list[int], acc: int) -> tuple[list[str], _State, _State, int]:
    """One read node: tokens, the 0-exit, the 1-exit, and the landing.

    All four are arithmetic in the entering state.  The 0-branch falls
    through with ``acc == first`` and the bit 0 appended; the 1-branch
    jumps to ``start - 15`` with ``acc == first + 1`` and the bit 1
    appended.  Nothing about the exits depends on which ``j1`` the aim
    picked, which is what lets the landing be committed before the arm
    and the merge exist.
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

    Chunks raise the non-head sum by exactly 255 each until ``target`` is
    within a byte's reach, and ``u`` is solved so the ``EXCRETE`` appends
    the one ``b`` that closes the rest: the final ``DIGEST`` folds the
    whole array into the cleared accumulator, so the jump resumes at the
    non-head sum plus ``b``, with the head cancelling out of
    ``acc - head - 1`` entirely.  ``b >= 1`` keeps the ``LEAPFROG`` firing
    (it is the array's last element), and the callers guarantee it by
    always aiming past the sum they enter with.
    """
    cur, val, tokens = list(array), acc, []
    while sum(cur) - cur[0] < target - 255:
        chunk, cur, val = _stash_chunk(cur, val)
        tokens += chunk
    hop = target - (sum(cur) - cur[0])
    if not 1 <= hop <= 255:  # pragma: no cover - the window solve is exact
        raise AssertionError(f"trampoline byte {hop} escaped 1..255")
    count = (((val % 256) ^ hop) - sum(cur)) % 256
    tokens += [*["SEED"] * count, "DIGEST", "EXCRETE", "DIGEST", "LEAPFROG"]
    out = [(cur[0] + count) % 256, *cur[1:], hop]
    return tokens, out, sum(out)


def _chunk_run(chunks: int) -> int:
    """Bound from above what ``chunks`` stash chunks cost in tokens.

    The first two counts are whatever the entering residues force (at most
    255 each); every later chunk is the settled 3-token form.
    """
    return 257 * min(chunks, 2) + 3 * max(0, chunks - 2)


def _tramp_bound(distance: int) -> int:
    """Upper bound on a trampoline's tokens for a raise of ``distance``."""
    chunks = max(0, -(-(distance - 255) // 255))
    return _chunk_run(chunks) + 255 + 4 + 8


class _Sums:
    """Build-time machine state: heads and non-head sums of arrays 0 and 16.

    Cells are never indexed -- the construction uses no ``CONSUME`` or
    ``FISSION``, ``SPRINT`` only ever reads ``curr[0]``, and every
    ``LEAPFROG``'s firing cell is appended by its own code -- so the two
    sums, the two heads, the accumulator and the pointer are the whole
    state.
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

    Array 16's head steps by 17, so 16 consecutive counts place the
    appended byte on a lattice of gap 17 -- some point always falls in the
    17-wide window [239, 255].
    """
    for count in range(16):
        if (st.hw + st.nw + _W_STEP * count) % 256 >= 239:
            tokens = [*["SEED"] * count, "DIGEST", "EXCRETE"]
            _replay(st, tokens)
            return tokens
    raise AssertionError("no 17-step residue in [239, 255]")  # pragma: no cover


def _w_raise(st: _Sums, amount: int) -> list[str]:
    """Raise array 16's non-head sum by exactly ``amount >= 0``.

    Greedy high-byte chunks close all but the last 510, which two exact
    chunks (each 1..255) finish -- so the cost is about a token per 14 of
    weight and the total is hit exactly, never overshot.
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


def _jump(st: _Sums, target: int) -> list[str]:
    """Emit an array-0 trampoline to ``target`` and replay it onto ``st``."""
    tokens, out_arr, out_acc = _trampoline(st.arr0(), st.acc, target)
    _replay(st, tokens)
    if (st.h0, st.n0, st.acc) != (out_arr[0], sum(out_arr[1:]), out_acc):
        raise AssertionError("sum replay diverged from the trampoline model")
    return tokens


def _arm(one: _Sums, weight: int, beta: int, cont: int) -> tuple[list[str], _Sums]:
    """Build the 1-branch: bank ``weight`` on array 16 and merge at ``cont``.

    The tuning chunk appends ``beta`` to array 0; the merge trampoline's
    solves re-anchor on top of it, so ``beta`` shifts this path's total
    SEED count at slope -2 -- the knob that matches the 0-path's heads.
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

    The leaves always fit their slots, whatever byte the dispatch appends:
    its ``u`` run is solved so the appended byte is ``b``, which pins the
    exit residue at ``sum % 256 == 2b`` -- even, so XORing in a digit moves
    it by ``+1 +-16 +-32`` and the worst leaf count is ``241 * (-16) ==
    240`` of the slot's 252.  So the byte is simply the least that fires.
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

    The program reads ``n`` digits with ``ACCEPT`` and prints the table
    entry for the combination it was given.  One read node per input, one
    dispatch jump, one 256-token leaf slot per table entry: O(T) text.
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
            # Size the arm's slot from an exact dry build of its core; the
            # slot only has to hold the tuning chunk and merge trampoline
            # too, and everything past them before ``cont`` is dead.
            core = one.clone()
            core_len = len(_route_to_w(core)) + len(_w_raise(core, weight))
            core_len += len(_route_to_0(core))
            arm_slot = core_len + 257 + _tramp_bound(600)
            for _ in range(8):
                need = core_len + 257 + _tramp_bound(arm_slot)
                if need <= arm_slot:
                    break
                arm_slot = need
            else:  # pragma: no cover - the bound grows ~3/255 per token
                raise AssertionError("the arm slot did not settle")
            cont = landing + arm_slot
            z = zero.clone()
            t0 = _jump(z, cont)
            if landing >= node_end + len(t0):
                break
            chunk, _, _ = _stash_chunk(st.arr0(), st.acc)
            _replay(st, chunk)
            tokens += chunk
            pos += len(chunk)

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
