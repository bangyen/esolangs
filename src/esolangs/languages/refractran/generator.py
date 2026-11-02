"""REFRACTRAN Boolean generator: controlled swaps evaluate a reduced DAG.

A bit is one of two prime rails. Four fractions swap the rails under a product
of asserted controls, restoring those controls and three shared temporaries.
Each node computes z XOR (x AND z) XOR (x AND o) in three swaps. Inputs are
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
    O(T) characters; n=10 random 1847: 32,137 chars. Constants: 4n + 1 chars.
"""

from __future__ import annotations

from esolangs.generation.helpers import TEMPLATE_CHAR, _validate_truth_table
from esolangs.generation.token_balance import balanced_token_width
from esolangs.generation.wrap import balance_score, wrap_space_delimited
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Example, Language

PAIR = ("0", "1")


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


def _diagram(table: str, n: int) -> tuple[list[tuple[int, int, int]], int]:
    """Return distinct unequal-halves nodes in dependency order and the root."""
    nodes: list[tuple[int, int, int]] = []
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
    primes = _primes(9 + n + 2 * len(nodes))
    inputs = primes[9 : 9 + n]
    initial = ["1" if root == 1 else "2"]
    initial += [f"{p}^{TEMPLATE_CHAR}" for p in inputs]
    fractions: list[str] = []
    if nodes:
        # Leaf constants have rails (5,7) and (19,23); output rails are (2,3).
        rails = [(5, 7), (19, 23)] + [
            (primes[9 + n + 2 * i], primes[10 + n + 2 * i]) for i in range(len(nodes))
        ]
        initial += ["5", "23", *(str(a) for a, _b in rails[2:])]
        for target, (depth, zero, one) in enumerate(nodes, 2):
            a, b = rails[target]
            x, z, o = inputs[depth], rails[zero][1], rails[one][1]
            fractions += _swap(a, b, (z,))
            fractions += _swap(a, b, (x, z))
            fractions += _swap(a, b, (x, o))
        fractions += _swap(2, 3, (rails[root][1],))
    program = " ".join(["*".join(initial), *fractions])
    return wrap_space_delimited(program, width) if width is not None else program


def _balance(_table: str, default: str) -> str:
    """Return the better of the plain and closed-form wrapped layouts."""
    tokens = default.split()
    width = balanced_token_width(tokens, " ", minimum=max(map(len, tokens)))
    return min([default, wrap_space_delimited(default, width)], key=balance_score)


LANGUAGE = Language(
    "REFRACTRAN",
    "refractran",
    category="register_based",
    boolean=refractran,
    contract=BooleanContract(
        answer_mode="dump",
        answer_pattern=r"([01])$",
        note="Inputs are ordered prime exponents in the initial integer; "
        "the final binary state ends in the answer bit.",
    ),
    wrap=wrap_space_delimited,
    balance=_balance,
    empty_program="REFRACTRAN needs an initial integer",
    example=Example(pair=PAIR, expected_compared=False),
)
