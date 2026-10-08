"""Boolean-function generator for Fargo.

``@ i`` returns the ``i``th bit of the input number, so no routing is
needed and the construction is the **algebraic normal form**
``f(x) = c0 XOR (c1 & x0) XOR (c2 & x1) XOR (c3 & x0 & x1) XOR ...``,
coefficients from the Möbius transform (:func:`anf_coefficients`).
The emitter factors each variable as ``p = p0 ^ (x & p1)``, so every
coefficient appears at most once; identity order emits O(T) characters.
A node keeps its 0-arm (Davio0) unless the 1-arm vanishes (1-arm kept) or is
the constant one (``f0 | x``); the free choice among Davio0, Davio1 and
monotone-OR arms (9.61% at n=8), rotated orders (0.25% at n=8) and
indexed-selector cost splits (7.61% at n=5) fall under the 10% bar and are
not built. The transform packs Theta(log T) coefficients per word, giving
O(T) word-RAM build work.

The program is ``% 0 <expression>`` then ``$``, writing exactly ``0`` or
``1``; a constant table emits the literal.  The harness feeds one line
holding ``int(bits, 2)``, so input ``i`` (most-significant-first) is bit
``n - 1 - i`` of that number -- the only place the mapping appears.  The
interpreter reads that line before execution, so every program consumes
exactly one input line.  With no reads there is no read order: factoring
order only renames the ``@`` literals, and :func:`fargo` uses the identity.
"""

from string import ascii_lowercase

from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Language
from esolangs.tools.helpers import (
    _validate_truth_table,
    anf_coefficients,
    short_name,
)
from esolangs.tools.wrap import balance_score

__all__ = ["fargo"]


def _word_width(n: int) -> int:
    """Return a power-of-two packing width, at least two and Theta(n)."""
    return max(2, 1 << (n.bit_length() - 1))


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
        w0, w1 = count(low), count(one)
        if not w1:
            choice = 1
        elif one == 1 and w0:
            choice = 2
        else:
            choice = 0
        d = f0 ^ f1
        kept, kept_anf, op, operand, operand_anf = (
            (f0, low, "^", d, high),
            (f1, one, "^", d, high),
            (f0, low, "|", f1, one),
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
        w0, w1 = weight(low), weight(one)
        if not w1:
            choice = 1
        elif w1 == 1 and one[0] & 1 and w0:
            choice = 2
        else:
            choice = 0
        d = [a ^ b for a, b in zip(f0, f1, strict=True)]
        kept, kept_anf, op, operand, operand_anf = (
            (f0, low, "^", d, high),
            (f1, one, "^", d, high),
            (f0, low, "|", f1, one),
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
    lits = max(n, 2)  # literal 1 is a node even with one input
    nodes: list[tuple[int, tuple[int, ...]]] = []
    heights = [0] * lits
    stack: list[int] = []
    for token in reversed(expression.split()):
        if token in arities:
            children = tuple(stack.pop() for _ in range(arities[token]))
            stack.append(lits + len(nodes))
            nodes.append((symbols.index(token), children))
            heights.append(1 + max(heights[child] for child in children))
        else:
            stack.append(int(token, 2))
    levels: list[list[int]] = [[] for _ in range(max(heights) + 1)]
    for node in range(lits, len(heights)):
        levels[heights[node]].append(node)
    canonical = list(range(lits)) + [0] * len(nodes)
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
            tag, children = nodes[node - lits]
            keys[node] = (
                tag,
                canonical[children[0]],
                canonical[children[1]] if len(children) == 2 else 0,
            )
        previous: tuple[int, int, int] | None = None
        named = lits - 1
        for node in ordered(group):
            key = keys[node]
            if key != previous:
                tag, zero, one = key
                unique.append((tag, (zero,) if tag == 0 else (zero, one)))
                named = lits + len(unique) - 1
                previous = key
            canonical[node] = named
    references = [f"{value:b}" for value in range(lits)]
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
    # Interns the folded Davio expression; the old ANF-per-mask form was 1.4-2.0x
    # larger at n=3-5 on random, constant-half and tiled tables.
    return _definition_program(expression, n)


def _balance(table: str, default: str) -> str:
    """Compare both order sets and the single definition/factored fallback."""
    # Width requests add orders; their shortest expression cannot grow.
    wide = fargo(table, len(default))
    return min(default, wide, fargo(table, 1), key=balance_score)


LANGUAGE = Language(
    "Fargo",
    "other.fargo",
    boolean=fargo,
    contract=BooleanContract(
        input_shape="row_index",
        note="Fargo reads one number whose bits are the inputs, so the "
        "committed input is the row index rather than a bit per line",
    ),
    balance=_balance,
    no_wrap="each physical line is one command; expressions have no continuation",
)
