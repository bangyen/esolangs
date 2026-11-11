"""Executed command and snapshot-bit bounds.

Eight-row endpoint cells have at most two codes from n=7: at most
16 decoder lines, half as many table cells, code values at most 8, and a
constant closure contained in the four-row envelope. Their extra selector
replaces one address bit; each snapshot part stays below that envelope.

Hosting only removes chain lines, and its array bases move earlier. The
envelope includes the two superseded bootstrap lines. Affine streams use
n+5m+13+bias lines and at most 273+bl(n+5m+15)+bl(2n-1) bits, dominated by
the same bounds for n>=3; m<=n counts selected inputs.
"""


def _constants(n: int) -> set[int]:
    """The closure of 48, 4c (0 < c < m) and the weights 2^j under _cm_plan."""
    m = min(16, 1 << (n - 2))
    weights = (1 << j for j in range(n - 2))
    todo = [k for k in (*(4 * c for c in range(1, m)), 48, 49, *weights) if k > 2]
    seen: set[int] = set()
    while todo:
        k = todo.pop()
        if k not in seen:
            seen.add(k)
            c = (k - 2) % 4
            todo += [v for v in ((k - c) // 2, c) if v > 2]
    return seen


def _constant(program: str) -> bool:
    return program.startswith("r=z x+input,NOT PRINT.")


def execution_terms(n: int, program: str) -> dict[str, int]:
    """Identify constant readers and count the constants in the table layout."""
    constant = _constant(program)
    return {"C": int(constant), "K": 0 if constant else len(_constants(n))}


def workspace_terms(n: int, program: str) -> dict[str, int]:
    """Count the registers and arrays of the all-ones snapshot."""
    if _constant(program):
        return {"C": 1, "K": 0, "R": 0, "A": 0, "D": 0}
    bl = int.bit_length
    cells, high = 1 << (n - 2), n - 2
    m = min(16, cells)
    consts = _constants(n)
    cap_d = 2 * len(consts) + 5  # the decoder's capture line
    cap_s = cap_d + 4 * m + 2  # the cells' capture line
    regs = sum(8 * (1 + len(str(k))) + bl(k) for k in consts | {1, 2})
    regs += 90 + 9 + 14 + 16 + bl(cap_s + cells) + bl(cap_d + 4 * m)
    regs += sum(8 * (1 + len(str(i))) for i in range(n))
    regs += (high * (high + 1) // 2 - 1 if high >= 2 else 0) + 6
    a = 8 + sum(bl(cap_s + 1 + i) for i in range(1, cells))
    a += (cells - 1) * bl(4 * (m - 1))
    pops = sorted(range(16), key=lambda v: (v.bit_count(), v))[16 - m :]
    d = 8 + sum(v.bit_count() * (bl(cap_d + 4 * c + 4) + 1) for c, v in enumerate(pops))
    return {"C": 0, "K": len(consts), "R": regs, "A": a, "D": d}
