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
Repeated expression nodes use shared definitions when shorter; the inline
form stays a candidate on every fitting path.
"""

from collections.abc import Callable
from string import ascii_lowercase

from esolangs.generation.helpers import (
    _validate_shape,
    _validate_truth_table,
    grid_width,
    short_name,
)
from esolangs.generation.wrap import balance_score
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Language

__all__ = ["fargo"]


class _Grain[T]:
    """One granularity of the Davio-choice recursion: scalar ints or word lists.

    The shared recursion (``davio`` inside :func:`_arm_expression`) runs
    unchanged on either grain; each grain supplies the scalar-int or
    packed-word-list version of every operation that touches the table or
    the ANF coefficients.
    """

    def __init__(
        self,
        *,
        initial_half: Callable[[T, int], int],
        split: Callable[[T, int], tuple[T, T]],
        is_zero: Callable[[T], bool],
        weight: Callable[[T], int],
        is_one: Callable[[T, int], bool],
        needs_weight: bool,
        xor: Callable[[T, T], T],
        child: Callable[[T, T, int], None],
        downgrade: Callable[[T, T, int], bool],
    ) -> None:
        self.initial_half = initial_half
        self.split = split
        self.is_zero = is_zero
        self.weight = weight
        self.is_one = is_one
        self.needs_weight = needs_weight
        self.xor = xor
        self.child = child
        self.downgrade = downgrade


def _arm[T](
    choice: int, f0: T, f1: T, low: T, one: T, high: T, d: T
) -> tuple[T, T, str, T, T]:
    """Return the kept arm, operator, and operand arm for a Davio choice.

    Choice 0 keeps the 0-arm and xors out the Davio difference; choice 1
    keeps the 1-arm when that difference vanishes; choice 2 keeps the 0-arm
    with a monotone OR when the 1-arm is the constant one.
    """
    if choice == 0:
        return f0, low, "^", d, high
    if choice == 1:
        return f1, one, "^", d, high
    return f0, low, "|", f1, one


def _word_width(n: int) -> int:
    """Return a power-of-two packing width, at least two and Theta(n)."""
    return max(2, 1 << (n.bit_length() - 1))


def _popcount_table(w: int) -> list[int]:
    """Return popcounts of all ``w // 2``-bit values."""
    counts = [0]
    for _ in range(w // 2):
        counts += [count + 1 for count in counts]
    return counts


class _ArmBuilder:
    """Emit the arm expression into ``pieces`` via the shared Davio recursion."""

    def __init__(self, w: int, at: tuple[int, ...]) -> None:
        self.halfword = w // 2
        self.countmask = (1 << self.halfword) - 1
        self.counts = _popcount_table(w)
        self.at = at
        self.pieces: list[str] = []
        self.scalar_grain = _Grain[int](
            initial_half=lambda _table, bit: 1 << bit,
            split=lambda value, half: (value & ((1 << half) - 1), value >> half),
            is_zero=lambda value: not value,
            weight=self.count,
            is_one=lambda value, _w: value == 1,
            needs_weight=False,
            xor=lambda a, b: a ^ b,
            child=self.scalar_leaf,
            downgrade=lambda _table, _anf, _bit: False,
        )
        self.word_grain = _Grain[list[int]](
            initial_half=lambda table, _bit: len(table) // 2,
            split=lambda value, half: (value[:half], value[half:]),
            is_zero=lambda value: not any(value),
            weight=self.weight,
            is_one=lambda value, w: w == 1 and (value[0] & 1) == 1,
            needs_weight=True,
            xor=lambda a, b: [x ^ y for x, y in zip(a, b, strict=True)],
            child=self.leaf,
            downgrade=self.word_downgrade,
        )

    def count(self, value: int) -> int:
        return self.counts[value & self.countmask] + self.counts[value >> self.halfword]

    def weight(self, words: list[int]) -> int:
        return sum(self.count(value) for value in words)

    def scalar_leaf(self, table: int, anf: int, bit: int) -> None:
        if anf == 1:
            self.pieces.append("1")
        else:
            self.davio(table, anf, bit, self.scalar_grain)

    def leaf(self, table: list[int], anf: list[int], bit: int) -> None:
        if len(anf) == 1:
            self.scalar_leaf(table[0], anf[0], bit)
        elif anf[0] == 1 and self.weight(anf) == 1:
            self.pieces.append("1")
        else:
            self.davio(table, anf, bit, self.word_grain)

    def word_downgrade(self, table: list[int], anf: list[int], bit: int) -> bool:
        # A single remaining word drops to the scalar recursion.
        if len(anf) == 1:
            self.scalar_leaf(table[0], anf[0], bit)
            return True
        return False

    def davio[T](self, table: T, anf: T, bit: int, grain: _Grain[T]) -> None:
        """Shared Davio-choice recursion; ``grain`` fixes int vs word granularity."""
        pieces = self.pieces
        half = grain.initial_half(table, bit)
        low, high = grain.split(anf, half)
        while grain.is_zero(high):
            table, anf, bit = grain.split(table, half)[0], low, bit - 1
            if grain.downgrade(table, anf, bit):
                return
            half //= 2
            low, high = grain.split(anf, half)
        f0, f1 = grain.split(table, half)
        one = grain.xor(low, high)
        w0, w1 = grain.weight(low), grain.weight(one)
        if not w1:
            choice = 1
        elif grain.is_one(one, w1) and w0:
            choice = 2
        else:
            choice = 0
        d = grain.xor(f0, f1)
        kept, kept_anf, op, operand, operand_anf = _arm(
            choice, f0, f1, low, one, high, d
        )
        literal = f"^ 1 @ {self.at[bit]:b}" if choice % 2 else f"@ {self.at[bit]:b}"
        if not grain.is_zero(kept_anf):
            pieces.append(f"{op} ")
            grain.child(kept, kept_anf, bit - 1)
            pieces.append(" ")
        # The scalar grain's is_one ignores the weight, so skip computing it.
        operand_weight = grain.weight(operand_anf) if grain.needs_weight else 0
        if grain.is_one(operand_anf, operand_weight):
            pieces.append(literal)
        else:
            pieces.append(f"& {literal} ")
            grain.child(operand, operand_anf, bit - 1)


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
    anf = [
        sum(value << bit for bit, value in enumerate(coeffs[start : start + w]))
        for start in range(0, len(table), w)
    ]
    values = [
        int(table[start : start + w][::-1], 2) for start in range(0, len(table), w)
    ]
    if not any(anf):
        return "0"
    builder = _ArmBuilder(w, at)
    builder.leaf(values, anf, n - 1)
    return "".join(builder.pieces)


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
    shared = _definition_program(expression, n)
    if width is None:
        return min(compact, shared, key=len)
    if grid_width(compact) <= width:
        return min(
            (program for program in (compact, shared) if grid_width(program) <= width),
            key=len,
        )
    return shared


def _balance(table: str, default: str) -> str:
    """Compare the default, the default-width fit and the width-one fit."""
    wide = fargo(table, len(default))
    return min(default, wide, fargo(table, 1), key=balance_score)


def anf_coefficients(truth_table: str) -> list[int]:
    """Return row-indexed ANF coefficients, allowing a nullary reduced table.

    Pack Theta(log T) coefficients per word for O(T) word-RAM work.
    """
    n = _validate_shape(truth_table)
    if n == 0:
        return [int(truth_table)]
    width = _word_width(n)
    words = [
        int(truth_table[start : start + width][::-1], 2)
        for start in range(0, len(truth_table), width)
    ]
    stride = 1
    while stride < width:
        high = int(("1" * stride + "0" * stride) * (width // (2 * stride)), 2)
        words = [value ^ ((value << stride) & high) for value in words]
        stride *= 2
    stride = 1
    while stride < len(words):
        for start in range(0, len(words), 2 * stride):
            for offset in range(start, start + stride):
                words[offset + stride] ^= words[offset]
        stride *= 2
    return [(value >> bit) & 1 for value in words for bit in range(width)]


LANGUAGE = Language(
    "Fargo",
    "fargo",
    category="other",
    boolean=fargo,
    contract=BooleanContract(
        input_shape="row_index",
        note="Fargo reads one number whose bits are the inputs, so the "
        "committed input is the row index rather than a bit per line",
    ),
    balance=_balance,
    no_wrap="each physical line is one command; expressions have no continuation",
    eof="the interpreter reads before the program starts",
    # Fargo reads one *number* before the program starts, not a bit per
    # line, and ``@ k`` indexes that number's bits.  The boolean
    # convention is therefore to feed the row index: the inputs
    # most-significant-first are its binary digits, so the 0,1 row of a
    # two-input table is the single line "1".
)
