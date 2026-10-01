"""Boolean-function generator for Fargo.

``@ i`` returns the ``i``th bit of the input number, so no routing is
needed and the construction is the **algebraic normal form**
``f(x) = c0 XOR (c1 & x0) XOR (c2 & x1) XOR (c3 & x0 & x1) XOR ...``,
coefficients from the Möbius transform (:func:`anf_coefficients`).
The emitter factors each variable as ``p = p0 ^ (x & p1)``, so every
coefficient appears at most once; identity order emits O(T) characters.
The emitter picks each node's arm locally (:func:`_arm_expression`).
Through five inputs, character-cost splits and an indexed selector also
compete; their difference recursion is bounded. The transform and arm rule
pack Theta(log T) coefficients per word, giving O(T) word-RAM build work.

The program is ``% 0 <expression>`` then ``$``, writing exactly ``0`` or
``1``; a constant table emits the literal.  The harness feeds one line
holding ``int(bits, 2)``, so input ``i`` (most-significant-first) is bit
``n - 1 - i`` of that number -- the only place the mapping appears.  The
interpreter reads that line before execution, so every program consumes
exactly one input line.  With no reads there is no read order: factoring
order only renames the ``@`` literals, and :func:`fargo` compares named orders.
"""

from collections.abc import Callable
from functools import cache

from esolangs.tools.helpers import (
    _validate_truth_table,
    anf_coefficients,
    permute_truth_table,
)

__all__ = ["fargo"]


def _word_width(n: int) -> int:
    """Return a power-of-two packing width, at least two and Theta(n)."""
    return max(2, 1 << (n.bit_length() - 1))


def _name(index: int) -> str:
    """Return a short lowercase Fargo definition name."""
    digits: list[str] = []
    while True:
        index, digit = divmod(index, 26)
        digits.append(chr(ord("a") + digit))
        if not index:
            return "".join(reversed(digits))
        index -= 1


def _factored(masks: list[int], constant: int, n: int) -> str:
    """Return the ANF as short nullary definitions and one output call."""
    lines: list[str] = []

    def define(expression: str) -> str:
        name = _name(len(lines))
        lines.append(f"{name} {expression}")
        return name

    used = {i for mask in masks for i in range(n) if mask >> i & 1}
    reads = {i: define(f"@ {i:b}") for i in sorted(used)}

    def combine(parts: list[str], op: str) -> str:
        while len(parts) > 1:
            joined: list[str] = []
            for i in range(0, len(parts) - 1, 2):
                joined.append(define(f"{op} {parts[i]} {parts[i + 1]}"))
            if len(parts) % 2:
                joined.append(parts[-1])
            parts = joined
        return parts[0]

    terms = [
        combine(
            [reads[i] for i in range(n) if mask >> i & 1],
            "&",
        )
        for mask in masks
    ]
    if constant:
        terms.insert(0, "1")
    # The all-zero table has no terms and no constant, so ``combine`` would
    # index an empty list.  It is the constant program, same as the compact
    # path; only the width check sent it here.
    result = combine(terms, "^") if terms else "0"
    return "\n".join([*lines, f"% 0 {result}", "$", ""])


class _SourceLimitError(Exception):
    """A candidate cannot beat the already-emitted source."""


class _Emission:
    """Append-only source with a character budget for reordered candidates."""

    def __init__(self, limit: int | None) -> None:
        self.limit = limit
        self.size = 0
        self.pieces: list[str] = []

    def append(self, text: str) -> None:
        self.size += len(text)
        if self.limit is not None and self.size >= self.limit:
            raise _SourceLimitError
        self.pieces.append(text)

    def render(self) -> str:
        return "".join(self.pieces)


def _arm_choice(
    w0: int,
    wd: int,
    w1: int,
    *,
    one_constant: bool,
    zero_implies_one: Callable[[], bool],
    one_implies_zero: Callable[[], bool],
) -> int:
    """Choose a Davio or monotone OR arm, preserving polarity ties."""
    if not w1:
        return 1
    if one_constant and w0:
        return 2
    options = [(w0 + wd, 0, 0), (w1 + wd, 1, 1)]
    # Keep implication checks lazy: the constant shortcuts need neither.
    if w0 and zero_implies_one():
        options.append((w0 + w1, 0, 2))
    if one_implies_zero():
        options.append((w0 + w1, 1, 3))
    return min(options)[2]


def _arm_expression(
    table: str,
    coeffs: list[int],
    n: int,
    at: tuple[int, ...],
    *,
    limit: int | None = None,
) -> str:
    """Return the same local arm rule using packed coefficients and scalar leaves.

    Above word width, each level touches O(T/n) words. Below it, a node
    uses constant-size word arithmetic and a derived population-count table.
    """
    w = _word_width(n)
    halfword = w // 2
    countmask = (1 << halfword) - 1
    counts = [0]
    for _ in range(halfword):
        counts += [count + 1 for count in counts]

    def count(value: int) -> int:
        return counts[value & countmask] + counts[value >> halfword]

    pieces = _Emission(limit)

    def scalar_leaf(table: int, anf: int, bit: int) -> None:
        if anf == 1:
            pieces.append("1")
        else:
            scalar(table, anf, bit)

    def scalar(table: int, anf: int, bit: int) -> None:
        half = 1 << bit
        mask = (1 << half) - 1
        low, high = anf & mask, anf >> half
        while not high:
            table, anf, bit = table & mask, low, bit - 1
            half //= 2
            mask = (1 << half) - 1
            low, high = anf & mask, anf >> half
        f0, f1 = table & mask, table >> half
        one = low ^ high
        w0, wd, w1 = count(low), count(high), count(one)
        choice = _arm_choice(
            w0,
            wd,
            w1,
            one_constant=one == 1,
            zero_implies_one=lambda: not (f0 & ~f1),
            one_implies_zero=lambda: not (f1 & ~f0),
        )
        d = f0 ^ f1
        kept, kept_anf, op, operand, operand_anf = (
            (f0, low, "^", d, high),
            (f1, one, "^", d, high),
            (f0, low, "|", f1, one),
            (f1, one, "|", f0, low),
        )[choice]
        literal = f"^ 1 @ {at[bit]:b}" if choice % 2 else f"@ {at[bit]:b}"
        if kept_anf:
            pieces.append(f"{op} ")
            scalar_leaf(kept, kept_anf, bit - 1)
            pieces.append(" ")
        if operand_anf == 1:
            pieces.append(literal)
        else:
            pieces.append(f"& {literal} ")
            scalar_leaf(operand, operand_anf, bit - 1)

    def weight(words: list[int]) -> int:
        return sum(count(value) for value in words)

    def leaf(table: list[int], anf: list[int], bit: int) -> None:
        if len(anf) == 1:
            scalar_leaf(table[0], anf[0], bit)
        elif anf[0] == 1 and weight(anf) == 1:
            pieces.append("1")
        else:
            build(table, anf, bit)

    def build(table: list[int], anf: list[int], bit: int) -> None:
        half = len(table) // 2
        low, high = anf[:half], anf[half:]
        while not any(high):
            table, anf, bit = table[:half], low, bit - 1
            if len(anf) == 1:
                scalar_leaf(table[0], anf[0], bit)
                return
            half //= 2
            low, high = anf[:half], anf[half:]
        f0, f1 = table[:half], table[half:]
        one = [a ^ b for a, b in zip(low, high, strict=True)]
        w0, wd, w1 = weight(low), weight(high), weight(one)
        choice = _arm_choice(
            w0,
            wd,
            w1,
            one_constant=w1 == 1 and bool(one[0] & 1),
            zero_implies_one=lambda: all(
                not (a & ~b) for a, b in zip(f0, f1, strict=True)
            ),
            one_implies_zero=lambda: all(
                not (b & ~a) for a, b in zip(f0, f1, strict=True)
            ),
        )
        d = [a ^ b for a, b in zip(f0, f1, strict=True)]
        kept, kept_anf, op, operand, operand_anf = (
            (f0, low, "^", d, high),
            (f1, one, "^", d, high),
            (f0, low, "|", f1, one),
            (f1, one, "|", f0, low),
        )[choice]
        literal = f"^ 1 @ {at[bit]:b}" if choice % 2 else f"@ {at[bit]:b}"
        if any(kept_anf):
            pieces.append(f"{op} ")
            leaf(kept, kept_anf, bit - 1)
            pieces.append(" ")
        if weight(operand_anf) == 1 and operand_anf[0] & 1:
            pieces.append(literal)
        else:
            pieces.append(f"& {literal} ")
            leaf(operand, operand_anf, bit - 1)

    anf = [
        sum(value << bit for bit, value in enumerate(coeffs[start : start + w]))
        for start in range(0, len(table), w)
    ]
    values = [
        int(table[start : start + w][::-1], 2) for start in range(0, len(table), w)
    ]
    if not any(anf):
        return "0"
    leaf(values, anf, n - 1)
    return pieces.render()


def _orders(n: int, *, compact: bool = False) -> list[tuple[int, ...]]:
    """Return two compact orders, or all four for width requests."""
    identity = tuple(range(n))
    if compact:
        return list(dict.fromkeys([identity, (*identity[1:], 0)]))
    orders = [identity, identity[::-1], (*identity[1:], 0), (n - 1, *identity[:-1])]
    return list(dict.fromkeys(orders))


def _expressions(
    truth_table: str, n: int, order: tuple[int, ...], *, limit: int | None = None
) -> list[str]:
    """Return the arm expression unless it cannot beat ``limit``."""
    table = permute_truth_table(truth_table, order)
    coeffs = anf_coefficients(table)
    at = tuple(n - 1 - order[n - 1 - bit] for bit in range(n))
    try:
        return [_arm_expression(table, coeffs, n, at, limit=limit)]
    except _SourceLimitError:
        return []


_SELECTOR_BODY = "^ y & @ x ^ y z"
_SELECTOR = f"M x y z {_SELECTOR_BODY}\n"


def _cost_key(source: str) -> tuple[int, int]:
    """Return characters and strict-evaluation token/frame cost."""
    tokens = source.removeprefix(_SELECTOR).split()
    # Each selector call evaluates its body and finishes one extra frame.
    return len(source), len(tokens) + tokens.count("M") * (
        len(_SELECTOR_BODY.split()) + 1
    )


def _cost_expression(truth_table: str, at: tuple[int, ...], *, selectors: bool) -> str:
    """Return a local character-cost split; callers cap the table at 32 rows."""

    # Distinct arms make product operands nonzero; input literals are nonconstant.
    def product(a: str, b: str) -> str:
        return a if b == "1" else f"& {a} {b}"

    def combine(a: str, b: str, op: str) -> str:
        if a == "0":
            return b
        if op == "^":
            if a == "1" and b.startswith("^ 1 "):
                return b[4:]
            if a.startswith("^ 1 ") and b.startswith("^ 1 "):
                return combine(a[4:], b[4:], "^")
        return f"{op} {a} {b}"

    @cache
    def build(values: str) -> str:
        n = len(values).bit_length() - 1
        if len(set(values)) == 1:
            return values[0]
        if n == 1:
            x = f"@ {at[0]:b}"
            return x if values == "01" else f"^ 1 {x}"
        half = len(values) // 2
        zero, one = values[:half], values[half:]
        if zero == one:
            return build(zero)
        difference = "".join(
            "0" if a == b else "1" for a, b in zip(zero, one, strict=True)
        )
        low, high, delta = build(zero), build(one), build(difference)
        x = f"@ {at[n - 1]:b}"
        notx = f"^ 1 {x}"
        candidates = [
            combine(low, product(x, delta), "^"),
            combine(high, product(notx, delta), "^"),
        ]
        if all(a <= b for a, b in zip(zero, one, strict=True)):
            candidates.append(combine(low, product(x, high), "|"))
        if all(b <= a for a, b in zip(zero, one, strict=True)):
            candidates.append(combine(high, product(notx, low), "|"))
        if selectors:
            candidates.append(f"M {at[n - 1]:b} {low} {high}")
        return min(candidates, key=_cost_key)

    return build(truth_table)


def _cost_programs(truth_table: str, n: int, order: tuple[int, ...]) -> list[str]:
    """Return plain and indexed-selector programs in the given input order."""
    table = permute_truth_table(truth_table, order)
    at = tuple(n - 1 - order[n - 1 - bit] for bit in range(n))
    programs = []
    for selectors in (False, True):
        expression = _cost_expression(table, at, selectors=selectors)
        header = _SELECTOR if "M" in expression.split() else ""
        programs.append(f"{header}% 0 {expression}\n$\n")
    return programs


def _definition_program(expression: str, n: int) -> str:
    """Return shared definitions with deterministic linear-time prefix interning."""
    symbols = "@&|^"
    arities = {"@": 1, "&": 2, "|": 2, "^": 2}
    nodes: list[tuple[int, tuple[int, ...]]] = []
    heights = [0] * n
    stack: list[int] = []
    for token in reversed(expression.split()):
        if token in arities:
            children = tuple(stack.pop() for _ in range(arities[token]))
            stack.append(n + len(nodes))
            nodes.append((symbols.index(token), children))
            heights.append(1 + max(heights[child] for child in children))
        else:
            stack.append(int(token, 2))
    levels: list[list[int]] = [[] for _ in range(max(heights) + 1)]
    for node in range(n, len(heights)):
        levels[heights[node]].append(node)
    canonical = list(range(n)) + [0] * len(nodes)
    keys = [(0, 0, 0)] * len(heights)
    unique: list[tuple[int, tuple[int, ...]]] = []
    digit_bits = (n + 1) // 2
    radix = 1 << digit_bits
    mask = radix - 1
    key_bits = len(heights).bit_length()

    def ordered(group: list[int]) -> list[int]:
        # O(group + sqrt(T)) per height; prefix height is O(n).
        order = group
        for field in (2, 1, 0):
            for shift in range(0, key_bits, digit_bits):
                positions = [0] * radix
                for node in order:
                    positions[(keys[node][field] >> shift) & mask] += 1
                offset = 0
                for digit, count in enumerate(positions):
                    positions[digit] = offset
                    offset += count
                result = [0] * len(order)
                for node in order:
                    digit = (keys[node][field] >> shift) & mask
                    result[positions[digit]] = node
                    positions[digit] += 1
                order = result
        return order

    for group in levels[1:]:
        for node in group:
            tag, children = nodes[node - n]
            keys[node] = (
                tag,
                canonical[children[0]],
                canonical[children[1]] if len(children) == 2 else 0,
            )
        previous: tuple[int, int, int] | None = None
        named = n - 1
        for node in ordered(group):
            key = keys[node]
            if key != previous:
                tag, zero, one = key
                unique.append((tag, (zero,) if tag == 0 else (zero, one)))
                named = n + len(unique) - 1
                previous = key
            canonical[node] = named
    references = [f"{value:b}" for value in range(n)]
    lines: list[str] = []
    for tag, children in unique:
        name = _name(len(lines))
        arguments = " ".join(references[child] for child in children)
        lines.append(f"{name} {symbols[tag]} {arguments}")
        references.append(name)
    return "\n".join([*lines, f"% 0 {references[canonical[stack[0]]]}", "$", ""])


def fargo(truth_table: str, width: int | None = None) -> str:
    """Build a Fargo program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first).  Emits a Boolean expression (see the module
    docstring); a constant table emits ``% 0 0`` or ``% 0 1``, sound because
    the interpreter consumes the input line either way.
    """
    n = _validate_truth_table(truth_table)
    orders = _orders(n, compact=width is None)
    # Identity has linear text. Stop other orders at that budget: repeating
    # a high bit index at the leaves would otherwise cost Theta(T log n).
    expression = ""
    for order in orders:
        for candidate in _expressions(
            truth_table, n, order, limit=len(expression) if expression else None
        ):
            if not expression or len(candidate) < len(expression):
                expression = candidate
    compact = f"% 0 {expression}\n$\n"
    if n <= 5:
        # Index selectors save 7.43% on 200 seeded five-input tables. Difference
        # recursion stays capped, contributing only constant-size build work.
        compact = min(
            [
                compact,
                *[
                    program
                    for order in orders
                    for program in _cost_programs(truth_table, n, order)
                ],
            ],
            key=_cost_key,
        )
    if width is None or max(map(len, compact.splitlines())) <= width:
        return compact
    if n > 5:
        return _definition_program(expression, n)
    coeffs = anf_coefficients(truth_table)
    masks = [mask for mask in range(1 << n) if coeffs[mask] and mask]
    return _factored(masks, coeffs[0], n)
