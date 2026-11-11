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
Balanced layouts may instead follow the DAG with a program-counter prime.
Visited-node markers prevent reverse transfers through unrelated parents;
only the inputs and counter are initialized, keeping that token O(n log n).
Each swap takes at most eight inspections. Gated builds have squarefree
rails; constants are at most 2*3**n. Both bound the integer to fewer than
4L bits. The cursor and flags fit bl(L)+16 more bits.

Size:
    O(T) characters; n=10 random 1847: 30,327 chars. Constants: 4n + 1 chars.
"""

from __future__ import annotations

from esolangs.generation.algebraic import parity_bias
from esolangs.generation.decision import reduced_diagram
from esolangs.generation.fraction_templates import fraction_template, wrap_fractions
from esolangs.generation.helpers import _validate_truth_table
from esolangs.generation.requests import BalanceRequest, GenerationRequest
from esolangs.generation.template import TemplateLayout
from esolangs.generation.token_balance import balanced_token_width
from esolangs.generation.wrap import balance_score


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
    """Return dependency-ordered nodes and root; negative references select NOT."""
    nodes: list[tuple[int, int, int]] = []
    # [ablations.parity_complement]: one XOR chain, with polarity on the root.
    if parity_bias(table) is not None:
        if not n:
            return [], int(table[0])
        nodes.append((n - 1, 0, 1))
        nodes.extend(
            (depth, child, -child)
            for child, depth in enumerate(range(n - 2, -1, -1), 2)
        )
        root = n + 1
        return nodes, -root if table[0] == "1" else root
    diagram, root = reduced_diagram(table, n)
    rails = {0: 0, 1: 1}

    def place(reference: int) -> int:
        found = rails.get(reference)
        if found is not None:
            return found
        depth, zero, one = diagram[reference]
        zero, one = place(zero), place(one)
        # Rail primes depend on zero-first postorder, not analysis node ids.
        rails[reference] = placed = len(nodes) + 2
        nodes.append((depth, zero, one))
        return placed

    root = place(root)
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
    return _layout(truth_table, width).source


def _layout(truth_table: str, width: int | None) -> TemplateLayout:
    n = _validate_truth_table(truth_table)
    nodes, root = _diagram(truth_table, n)
    if not nodes:
        # Ignored exponents may share an odd prime: only parity carries output.
        layout = fraction_template([3] * n, [], root="1" if root else "2")
        return wrap_fractions(layout, width)
    # Leaf constants no longer need rails. Keep only output and scratch fixed.
    reserved = {2, 3, 11, 13, 17}
    free = [p for p in _primes(5 + n + 2 * len(nodes)) if p not in reserved]
    inputs = free[:n]
    rails = [(free[n + 2 * i], free[n + 2 * i + 1]) for i in range(len(nodes))]

    def asserted(reference: int) -> int:
        a, b = rails[abs(reference) - 2]
        return a if reference < 0 else b

    initial: list[str] = []
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
    layout = fraction_template(inputs, fractions, root="2", factors=initial)
    return wrap_fractions(layout, width)


def _path_program(table: str) -> TemplateLayout | None:
    """Return root-first transfers with an O(n log n) initial token."""
    n = len(table).bit_length() - 1
    diagram, root = reduced_diagram(table, n)
    if root < 2:
        return None
    needed: set[int] = set()

    def visit(reference: int) -> None:
        if reference < 2 or reference in needed:
            return
        needed.add(reference)
        visit(diagram[reference].zero)
        visit(diagram[reference].one)

    visit(root)
    references = sorted(needed, reverse=True)
    free = [
        prime
        for prime in _primes(5 + n + 2 * len(references))
        if prime not in {2, 3, 11, 13, 17}
    ]
    inputs = free[:n]
    counters = {0: 2, 1: 3} | {
        reference: free[n + 2 * i] for i, reference in enumerate(references)
    }
    fractions: list[str] = []
    for i, reference in enumerate(references):
        level, zero, one = diagram[reference]
        marker = free[n + 2 * i + 1]
        # A child counter alone cannot trigger an unvisited parent's inverse.
        fractions += _swap(
            counters[reference], counters[one] * marker, (inputs[level],)
        )
        fractions += _swap(counters[reference], counters[zero] * marker, ())
    return fraction_template(inputs, fractions, root=str(counters[root]))


def refractran_request(request: GenerationRequest) -> TemplateLayout:
    """Emit source through the declared generation request interface."""
    return _layout(request.table, request.width)


def refractran_balance_request(request: BalanceRequest) -> TemplateLayout:
    """Return the best plain, rail-circuit or marked-path layout."""
    default = request.source
    if not isinstance(default, TemplateLayout):
        raise TypeError("balancing needs a rendered template with slots")
    candidates = [default]
    for layout in (default, _path_program(request.table)):
        if layout is not None:
            tokens = layout.source.split()
            width = balanced_token_width(tokens, " ", minimum=max(map(len, tokens)))
            candidates.append(wrap_fractions(layout, width))
    return min(candidates, key=lambda candidate: balance_score(candidate.source))
