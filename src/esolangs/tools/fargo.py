"""Boolean-function generator for Fargo.

``@ i`` returns the ``i``th bit of the input number, so no routing is
needed and the construction is the **algebraic normal form**
``f(x) = c0 XOR (c1 & x0) XOR (c2 & x1) XOR (c3 & x0 & x1) XOR ...``,
coefficients from the Möbius transform (:func:`anf_coefficients`).
The emitter factors each variable as ``p = p0 ^ (x & p1)``, so every
coefficient appears at most once; identity order emits O(T) characters.
The emitter picks each node's arm locally (:func:`_arm_expression`).
Rotated orders (0.25% at n=8) and character-cost splits with indexed
selectors (7.61% at n=5) fall under the 10% bar and are not built. The
transform and arm rule pack Theta(log T) coefficients per word, giving O(T)
word-RAM build work.

The program is ``% 0 <expression>`` then ``$``, writing exactly ``0`` or
``1``; a constant table emits the literal.  The harness feeds one line
holding ``int(bits, 2)``, so input ``i`` (most-significant-first) is bit
``n - 1 - i`` of that number -- the only place the mapping appears.  The
interpreter reads that line before execution, so every program consumes
exactly one input line.  With no reads there is no read order: factoring
order only renames the ``@`` literals, and :func:`fargo` uses the identity.
"""

from collections.abc import Callable
from string import ascii_lowercase

from esolangs.tools.helpers import (
    _validate_truth_table,
    anf_coefficients,
    short_name,
)

__all__ = ["fargo"]


def _word_width(n: int) -> int:
    """Return a power-of-two packing width, at least two and Theta(n)."""
    return max(2, 1 << (n.bit_length() - 1))


def _factored(coeffs: list[int], n: int) -> str:
    """Return the ANF as short nullary definitions and one output call."""
    masks = [mask for mask in range(1, 1 << n) if coeffs[mask]]
    lines: list[str] = []

    def define(expression: str) -> str:
        name = short_name(len(lines), ascii_lowercase)
        lines.append(f"{name} {expression}")
        return name

    used = {i for mask in masks for i in range(n) if mask >> i & 1}
    reads = {i: define(f"@ {i:b}") for i in sorted(used)}

    def fold(parts: list[str], op: str) -> str:
        while len(parts) > 1:
            joined: list[str] = []
            for i in range(0, len(parts) - 1, 2):
                joined.append(define(f"{op} {parts[i]} {parts[i + 1]}"))
            if len(parts) % 2:
                joined.append(parts[-1])
            parts = joined
        return parts[0]

    terms = [
        fold(
            [reads[i] for i in range(n) if mask >> i & 1],
            "&",
        )
        for mask in masks
    ]
    if coeffs[0]:
        terms.insert(0, "1")
    # The all-zero table has no terms and no constant, so ``fold`` would
    # index an empty list.  It is the constant program, same as the compact
    # path; only the width check sent it here.
    result = fold(terms, "^") if terms else "0"
    return "\n".join([*lines, f"% 0 {result}", "$", ""])


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

    pieces: list[str] = []

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
    return "".join(pieces)


def _expression(truth_table: str, n: int) -> str:
    """Return the arm expression in identity input order."""
    coeffs = anf_coefficients(truth_table)
    return _arm_expression(truth_table, coeffs, n, tuple(range(n)))


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
        name = short_name(len(lines), ascii_lowercase)
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
    expression = _expression(truth_table, n)
    compact = f"% 0 {expression}\n$\n"
    if width is None or max(map(len, compact.splitlines())) <= width:
        return compact
    if n > 5:
        return _definition_program(expression, n)
    return _factored(anf_coefficients(truth_table), n)
