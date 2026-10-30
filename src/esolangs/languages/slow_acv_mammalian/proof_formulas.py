"""Executed command, character and bit bounds for the default dialect.

Cell modulus 256, I/O modulus 255.  A run executes whole emitted lists:
the first jump, the prologue, per level its prefix, node and either the
0-branch trampoline or the arm, then the dispatch and a leaf.  Each list's
length is bounded by the largest value its residues allow:

* a route (L1) takes at most 28 tokens out of array 0 and 58 into it, for
  every head; an exact append (L2) at most 255 SEEDs and two more;
* a node (L3) at most 115 aiming SEEDs and 21 more; the dispatch (L4) at
  most 155 SEEDs, the first count putting array 16's head on its class and
  both print heads at or past their digit's code (exhaustive over every
  head triple: 55 for the class alone);
* greedy chunks on array 16 (L5) are a deterministic walk on (head, sum mod
  255): one 495-chunk cycle of 1246 tokens and 121,890 bytes, so tokens
  <= 623 bytes / 60,945 + 23.5 for any start and any count; each appends
  238..254, so a raise of w loops on the bytes below w - 254, then two exact
  chunks close it;
* at a level start n0 = pos and h0 = (253 - pos) mod 255, so the prefix and
  node are at most 138 + 3k + ceil(k/255) tokens for k ballast chunks (L6);
  k is 0 while the chain bound is at most 12 and else at most
  ceil((chain + 240) / 251) + 1 (L7); both exhaustive over pos mod 16,320;
* the tuning byte is always 253, which leaves the closing trampoline's
  first residue at 3, so it costs 3m + 7 for m window chunks (L8).

Each level runs at most max(prefix + node + arm, landing - pos), the
0-branch fitting before the landing by construction.  The cells are
counted from the same lists.

Fewer essential inputs (m < n) never exceed the full bound: such a table is
the m-layout with weight 0 and no pool on the ignored inputs, and L1-L8 hold
for any weights.  ``_window``, ``_raise`` and ``_chain`` rise with the table
(at most 256, or 255 2^(m-5) - 31 for m > 5); pools are a prefix of the full
set.  A later level costs c_P with a pool, else c_R(w), whatever n and
position, rising in w with c_R(7) = c_R(8).  For m > 5 the non-pool weights
are termwise at most the full ones, also with the first node dropped.  For
m <= 5 inputs 0..m-1 dominate and gain one c_R(0) a level, the full layout
at least c_R(255), so the gap grows from n = 7, where it is >= 0.  At n <= 6
list sums exceed the full bound, so
every essential set was built with each leaf slot at its dearer value (slot
costs add; the emitted maximum over 211 random mixed tables): at most 8440
tokens and 44,870 characters at n = 6, against 13,972 and 104,508.
"""

from fractions import Fraction
from typing import NamedTuple

_ROUTE_OUT, _ROUTE_BACK, _EXACT, _NODE, _DISPATCH = 28, 58, 257, 136, 155
_ROUTE_PRINT, _ROUTE_POOL = (29, 40), 44


def _cdiv(a: int, b: int) -> int:
    return -(-a // b)


def _layout(n: int) -> tuple[list[int], list[int | None], int]:
    """Weights, pools and leaf unit of the all-essential build."""
    free = min(n, 5)
    unit, stride = (7, 255) if n > 5 else (8, 256)
    weights = [stride << (n - free - 1 - i) for i in range(n - free)]
    weights += [unit << k for k in range(free)]
    pools: list[int | None] = [None] * (n - free + 1) + [2, 4, 6, 8][: free - 1]
    return weights, pools, unit


def _window(table: int) -> tuple[int, int]:
    """Exact first-jump target and chunk count (``_merge_address`` at rest 0)."""
    chunks = max(1, _cdiv(table + 6, 251))
    spent = 254 + 3 * chunks - 1 + (254 + chunks - 1) // 255
    chunks += table + spent + 7 > 254 * (chunks + 1)
    return 254 * (chunks + 1), chunks


def _raise(w: int) -> int:
    """Tokens of a raise of array 16 by ``w`` from any state."""
    if w <= 0:
        return 0
    greedy = (623 * (w - 254)) // 60945 + 24 if w > 508 else 0
    return greedy + (2 if w > 254 else 1) * _EXACT


def _chain(w: int, pool: int | None) -> int:
    """``_chain_bound``: the generator's own sizing of the 0-branch chain."""
    body = 3 if pool is not None else 17 * _cdiv(max(0, w - 508), 238) + 514
    start = 47 + body + 256 + 257 - 63 - 254
    if start + 8 <= 254:
        return 0
    chunks = _cdiv(start + 9 - 254, 251)
    return 3 * (chunks + 1) + _cdiv(chunks + 2, 255)


class _Plan(NamedTuple):
    """The bound pieces: table, first-jump window and tokens, prologue, base, levels."""

    table: int
    window: int
    jump: int
    prologue: int
    base: int
    levels: list[dict[str, int]]
    weights: list[int]


def _plan(n: int) -> _Plan:
    """The all-essential build's list bounds."""
    weights, pools, unit = _layout(n)
    table = sum(weights) + unit
    window, chunks = _window(table)
    jump = 3 * chunks + 259 + ((chunks - 2) // 255 + 1 if chunks >= 2 else 0)
    # base = window - table <= 254 (ceil((table + 6) / 251) + 2) - table
    base = (3 * table + 1270) // 251 + 764
    free = min(n, 5)
    delta = [8 << k for k in range(1, free)]
    prologue = 2 * (28 + _EXACT + 2) + sum(_ROUTE_PRINT)
    prologue += sum(28 + 2 * _EXACT + 2 * d + _ROUTE_POOL for d in delta)
    prologue += 28 + _raise(base) + _ROUTE_BACK
    levels = []
    for i, (w, pool) in enumerate(zip(weights, pools, strict=True)):
        chain = _chain(w, pool)
        if pool is not None:
            core, kb = 28 + 3 + _ROUTE_BACK, 0
        else:
            core = 28 + _raise(w) + _ROUTE_BACK
            kb = 0 if chain <= 12 else _cdiv(chain + 240, 251) + 1
        cs = core + _EXACT
        m = 0 if cs <= 514 else max(1, _cdiv(cs - 513, 251)) + 1
        arm = cs + 3 * m + 8 + m // 255
        if i == 0:
            kb = _cdiv(prologue - 253 + 14 + 255 + 225 + chain, 251) + 1
            pn = 1 + _EXACT + 3 * (kb - 1) + _cdiv(kb, 255) + _NODE
            spill = Fraction(3 * prologue, 251) + Fraction(254 * (240 + chain), 251)
            z = int(spill + 746) + 1
            length = int(spill + 1268 + 254 * (m + 1)) + 1
        else:
            pn = 138 + 3 * kb + _cdiv(kb, 255)
            z = 238 + 254 * kb
            length = 760 + 254 * (kb + m + 1)
        levels.append(
            {"pn": pn, "arm": arm, "z": z, "len": length, "lvl": max(pn + arm, z)}
        )
    return _Plan(table, window, jump, prologue, base, levels, weights)


def execution(n: int, _: str) -> int:
    """E: first jump, prologue, per-level lists on the all-ones path, tail."""
    plan = _plan(n)
    levels = sum(r["lvl"] for r in plan.levels)
    return plan.jump + plan.prologue + levels + _ROUTE_OUT + _DISPATCH + 9


def _tokens(n: int) -> int:
    """Program tokens: the first window, prologue, levels and tail."""
    plan = _plan(n)
    levels = sum(r["len"] for r in plan.levels)
    return plan.window + plan.prologue + levels + _ROUTE_OUT + _DISPATCH + 2


def characters(n: int, _: str) -> int:
    """V: leaf slots and gaps exactly, every other token at its list bound.

    A slot is 5 unit + 19 characters (a guard SPRINT ends it; another replaces
    a gap SEED at each block start) and the rest of the table SEEDs, so the
    table is at most 20 T + 5 table; the jump, prologue and levels count 5 per
    token plus 4 more for each non-SEED one.
    """
    plan = _plan(n)
    pools = min(n, 5) - 1
    delta = sum(8 << k for k in range(1, pools + 1))
    chunks = _window(plan.table)[1]
    head = 5 * (plan.window - plan.table) + 4 * (2 * chunks + 4)
    non_seed = 2 * delta + 2 * (6 + 2 * pools) + 3 * (6 + 2 * pools)
    non_seed += _raise(plan.base)
    body = 5 * plan.prologue + 4 * non_seed
    for r in plan.levels:
        body += 5 * r["len"] + 4 * (r["pn"] + r["arm"] + r["z"])
    tail = 9 * (_ROUTE_OUT + _DISPATCH + 2)
    return head + 20 * (1 << n) + 5 * plan.table + body + tail


def workspace(n: int, _: str) -> int:
    """B: 8 bits a cell on arrays 0 and 16, the pools' zeros, heads, counters.

    Array 0 ends holding its sum over 254 plus four small cells a level (the
    plant, the input bit, the launder, the tuning byte) and one more; array 16
    its sum over 238 plus two a level and four; both only grow.
    """
    plan = _plan(n)
    length = _tokens(n)
    banked = plan.base + sum(plan.weights)
    cells = length // 254 + 4 * n + 1 + banked // 238 + 2 * n + 4
    pools = sum(2 * (8 << k) + 16 for k in range(1, min(n, 5)))
    bl = int.bit_length
    return 8 * 23 + 8 * cells + pools + 16 + bl(length) + bl(length + 256) + 6 + bl(n)
