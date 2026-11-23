"""Executed command, character and bit bounds for the default dialect.

A nonconstant program doubles the prefix through its last read level and
adds 8194 tokens for the common print tail. The old prologue allowance
includes the removed print setup, so it still bounds the new prefix.
Ignored reads have zero weights and no pool; the full layout bounds them
with the same first window, prologue, and per-level arm budgets.

Each path visits each token at most once: dispatch enters the untouched
leaf window, then the leaf jumps past the dispatch. There is no FISSION,
so each visited token adds at most one eight-bit cell. The fixed allowance
covers the initial heads and fixed state; a sum of the cells, including
the accumulator's inputs to XOR, fits in the width of 512 times the token
count for nonconstant programs. The constant layout has a separate exact
peak after all input cells are read.
"""

_ROUTE_BACK, _EXACT = 58, 257
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


def _window(table: int) -> int:
    """Exact first-jump target (``_merge_address`` at rest 0)."""
    chunks = max(1, _cdiv(table + 6, 251))
    spent = 254 + 3 * chunks - 1 + (254 + chunks - 1) // 255
    chunks += table + spent + 7 > 254 * (chunks + 1)
    return 254 * (chunks + 1)


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


def scaling_terms(n: int, _: str) -> dict[str, int]:
    """Bound the initial window, prologue and complete read levels."""
    weights, pools, unit = _layout(n)
    table = sum(weights) + unit
    window = _window(table)
    # base = window - table <= 254 (ceil((table + 6) / 251) + 2) - table
    base = (3 * table + 1270) // 251 + 764
    free = min(n, 5)
    delta = [8 << k for k in range(1, free)]
    prologue = 2 * (28 + _EXACT + 2) + sum(_ROUTE_PRINT)
    prologue += sum(28 + 2 * _EXACT + 2 * d + _ROUTE_POOL for d in delta)
    prologue += 28 + _raise(base) + _ROUTE_BACK
    levels = 0
    for i, (w, pool) in enumerate(zip(weights, pools, strict=True)):
        chain = _chain(w, pool)
        if pool is not None:
            core, kb = 28 + 3 + _ROUTE_BACK, 0
        else:
            core = 28 + _raise(w) + _ROUTE_BACK
            kb = 0 if chain <= 12 else _cdiv(chain + 240, 251) + 1
        cs = core + _EXACT
        m = 0 if cs <= 514 else max(1, _cdiv(cs - 513, 251)) + 1
        if i == 0:
            spill = (3 * prologue + 254 * (240 + chain)) // 251
            levels += spill + 1269 + 254 * (m + 1)
        else:
            levels += 760 + 254 * (kb + m + 1)
    return {"W": window, "P": prologue, "Q": levels}


def token_terms(_: int, program: str) -> dict[str, int]:
    """Count emitted commands, including guards and padding."""
    return {"N": len(program.split())}


def workspace_terms(_: int, program: str) -> dict[str, int]:
    """Recognize the constant reader and count its final array head widths."""
    tokens = program.split()
    if "LEAPFROG" in tokens:
        return {"C": 0, "K": 0, "N": len(tokens), "S": 0}
    seeds = tokens.count("SEED")
    heads = sum((k * seeds).bit_length() for k in range(1, 24))
    return {"C": 1, "K": heads, "N": len(tokens), "S": seeds}
