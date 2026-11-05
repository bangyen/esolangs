"""REFRACTRAN Boolean generator: controlled swaps evaluate a reduced DAG.

A bit is one of two prime rails. Four fractions swap the rails under a product
of asserted controls, restoring those controls and three shared temporaries.
Each node computes z XOR (x AND z) XOR (x AND o) in up to three swaps;
constant controls disappear and a known-one first swap becomes initial state.
Parity and its negation share opposite residuals through signed rail references
([ablations.parity_complement]). Inputs are
ordered one-digit prime exponents; a final swap puts the answer in parity.
At depth d there are at most min(2**d, 2**2**(n-d)) distinct nodes, hence
O(T/log T) nodes. Their O(log T)-digit fractions and a linear sieve through
O((nodes+n) log(nodes+n)) give O(T) construction and text. Construction counts
O(log T)-bit word operations and expected constant-time interning lookups.
Constants omit gates and share prime 3 for their input exponents.
Each swap takes at most eight inspections. Gated builds have squarefree
rails; constants are at most 2*3**n. Both bound the integer to fewer than
4L bits. The cursor and flags fit bl(L)+16 more bits.

Size:
    O(T) characters; n=10 random 1847: 30,327 chars. Constants: 4n + 1 chars.
"""

from __future__ import annotations

from esolangs.generation.helpers import TEMPLATE_CHAR, _validate_truth_table
from esolangs.generation.token_balance import balanced_token_width
from esolangs.generation.wrap import balance_score, wrap_space_delimited


def _primes(count: int) -> list[int]:
    """Return the first count primes with Euler's linear sieve."""
    # p_k < k(log k + log log k) for k >= 6; this binary-log bound is larger.
    bound = 2 * max(6, count) * (max(6, count).bit_length() + 1)
    least = [0] * (bound + 1)
    primes: list[int] = []
    for value in range(2, bound + 1):
        if not least[value]:
            least[value] = value
            primes.append(value)
            if len(primes) == count:
                return primes
        for prime in primes:
            multiple = prime * value
            if multiple > bound:
                break
            least[multiple] = prime
            if prime == least[value]:
                break
    raise AssertionError("prime bound exhausted")


def _is_parity(table: str) -> bool:
    """Whether the table is parity or its negation over all inputs."""
    offset = int(table[0])
    return all(
        bit == "01"[(row.bit_count() & 1) ^ offset] for row, bit in enumerate(table)
    )


def _diagram(table: str, n: int) -> tuple[list[tuple[int, int, int]], int]:
    """Return dependency-ordered nodes and root; negative references select NOT."""
    nodes: list[tuple[int, int, int]] = []
    # [ablations.parity_complement]: one XOR chain, with polarity on the root.
    if _is_parity(table):
        if not n:
            return [], int(table[0])
        nodes.append((n - 1, 0, 1))
        nodes.extend(
            (depth, child, -child)
            for child, depth in enumerate(range(n - 2, -1, -1), 2)
        )
        root = n + 1
        return nodes, -root if table[0] == "1" else root
    seen: dict[tuple[int, int, int], int] = {}

    def walk(depth: int, lo: int, hi: int) -> int:
        if depth == n:
            return int(table[lo])
        mid = (lo + hi) // 2
        zero, one = walk(depth + 1, lo, mid), walk(depth + 1, mid, hi)
        # Canonical folds: [ablations.constant_fold], [ablations.ignored_input].
        if zero == one:
            return zero
        key = (depth, zero, one)
        # Repeated subfunctions share rails: [ablations.subtree_sharing].
        if key not in seen:
            seen[key] = len(nodes) + 2
            nodes.append(key)
        return seen[key]

    root = walk(0, 0, len(table))
    return nodes, root


def _swap(a: int, b: int, controls: tuple[int, ...]) -> list[str]:
    """Swap target rails a/b iff every control is present; scratch starts empty."""
    control = 1
    for prime in controls:
        control *= prime
    # 11/13/17 are the shared scratch rails. Every path restores them to zero.
    return [f"221/{denominator * control}" for denominator in (11, a, b, 11)]


def refractran(truth_table: str, width: int | None = None) -> str:
    """Return a template whose final integer is odd exactly for answer one."""
    n = _validate_truth_table(truth_table)
    nodes, root = _diagram(truth_table, n)
    if not nodes:
        # Ignored exponents may share an odd prime: only parity carries output.
        program = ("1" if root else "2") + f"*3^{TEMPLATE_CHAR}" * n
        return wrap_space_delimited(program, width) if width is not None else program
    # Leaf constants no longer need rails. Keep only output and scratch fixed.
    reserved = {2, 3, 11, 13, 17}
    free = [p for p in _primes(5 + n + 2 * len(nodes)) if p not in reserved]
    inputs = free[:n]
    rails = [(free[n + 2 * i], free[n + 2 * i + 1]) for i in range(len(nodes))]

    def asserted(reference: int) -> int:
        a, b = rails[abs(reference) - 2]
        return a if reference < 0 else b

    initial = ["2", *(f"{p}^{TEMPLATE_CHAR}" for p in inputs)]
    fractions: list[str] = []
    for target, (depth, zero, one) in enumerate(nodes):
        a, b = rails[target]
        x = inputs[depth]
        # Constant propagation: the known-one first swap is initial state;
        # false controls are dead, and true controls need no prime factor.
        initial.append(str(b if zero == 1 else a))
        if zero not in (0, 1):
            z = asserted(zero)
            fractions += _swap(a, b, (z,))
            fractions += _swap(a, b, (x, z))
        elif zero == 1:
            fractions += _swap(a, b, (x,))
        if one not in (0, 1):
            fractions += _swap(a, b, (x, asserted(one)))
        elif one == 1:
            fractions += _swap(a, b, (x,))
    fractions += _swap(2, 3, (asserted(root),))
    program = " ".join(["*".join(initial), *fractions])
    return wrap_space_delimited(program, width) if width is not None else program


def _balance(_table: str, default: str) -> str:
    """Return the better of the plain and closed-form wrapped layouts."""
    tokens = default.split()
    width = balanced_token_width(tokens, " ", minimum=max(map(len, tokens)))
    return min([default, wrap_space_delimited(default, width)], key=balance_score)
