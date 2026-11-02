"""Blindfolded Arithmetic Boolean program generator: shift the table by the row.

Straight-line code, run once.  ``b`` is built as the integer whose bit ``r``
is row ``r``'s answer in the table read at the essential inputs, by Horner's
rule in base 8 with the digit summed from registers holding 1, 2, 4 and 8.  The
input ``i`` is the row plus one, so ``i - 1`` is the row; each essential bit,
least significant first, divides ``b`` by ``1 + bit * (Q - 1)`` for
``Q = 2**2**m``, keeping Q-1 by squaring, and an ignored bit is dropped unused.
``i`` becomes ``b``'s low bit, and ``e = e / e`` on a zeroed ``e`` halts and
prints it.

Size:
    Theta(T) text, 8 or 9 instructions an essential input and one an
    ignored one; constants use 11 chars and two commands (workspace <= n+8 bits).
    n=4 parity: 323 chars, n=10 parity: 4,391 chars.

Decisions:
    Generic tables use base8 and digit registers 1,2,4; full-input parity
    from n=4 has only hex digits6/9, built as 6 or 6+3 beside radix16
    ([ablations.parity_radix16_trick]).

    Each octal digit is added as ``v`` or as ``v - 8`` with a carry up,
    whichever totals fewer terms of +-1, +-2, +-4, +-8
    ([ablations.signed_digits]).

    The shorter of the table and its complement is built, the complement's
    answer negated by ``i = a - i``: historical or at n=10
    8,849 -> 677 chars (2026-10-28)
    ([ablations.complement_table]).

    The reversed table read with negated inputs (divisor ``Q - bit * (Q - 1)``,
    same cost) is also tried: historical and at n=8 1,061 -> 551
    (2026-10-28; [ablations.mirror_lookup]).

    Counter and quotient alternate registers while ``c`` stays 2 and ``e``
    holds Q-1: (Q-1)(Q+1) updates it without a saved copy. The counter
    copies disappear ([ablations.alternating_counter_rounds_trick]).
"""

from esolangs.generation.helpers import (
    _parity_bias,
    _validate_truth_table,
    essential_inputs,
    read_at,
)
from esolangs.generation.wrap import wrap_tokens
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Language, Shape

#: One instruction and its separator; a break after ``;`` is whitespace.
_INSTRUCTION = r"[^;]*;?"
#: The registers holding 1, 2, 4 and 8 once the table integer starts.
_REGISTER = {1: "a", 2: "c", 4: "d", 8: "e"}


def _terms(value: int) -> list[tuple[str, int]]:
    """Return ``value`` (|value| <= 8) as at most two signed terms of 1, 2, 4, 8."""
    if not value:
        return []
    sign, other = ("+", "-") if value > 0 else ("-", "+")
    magnitude = abs(value)
    if magnitude in _REGISTER:
        return [(sign, magnitude)]
    big = 8 if magnitude == 7 else 4
    if magnitude in (3, 7):
        return [(sign, big), (other, big - magnitude)]
    return [(sign, big), (sign, magnitude - big)]


def _table_integer(truth_table: str) -> list[str]:
    """Return the code leaving ``b`` = the table, bit ``r`` = row ``r``.

    ``i`` is untouched; ``a``, ``c``, ``d``, ``e`` hold 1, 2, 4, 8 on exit.
    Each octal digit ``v`` (plus the carry in) is added as ``v`` or as
    ``v - 8`` carrying one up, whichever the cheaper rounds out over the
    whole table: two states, one pass.
    """
    code = ["a=i/i", "c=a+a", "d=c+c", "e=d+d"]
    digits = [int(char) for char in format(int(truth_table[::-1], 2), "o")][::-1]
    # Backpointers preserve the signed-digit tie order without copying every
    # prefix at each digit: two states per digit, O(T) total construction.
    best = {0: 0}
    layers: list[dict[int, tuple[int, list[tuple[str, int]]]]] = []
    for digit in [*digits, 0]:
        costs: dict[int, int] = {}
        layer: dict[int, tuple[int, list[tuple[str, int]]]] = {}
        for carry, cost in best.items():
            for value, out in ((digit + carry, 0), (digit + carry - 8, 1)):
                terms = _terms(value)
                if out not in costs or cost + len(terms) < costs[out]:
                    costs[out] = cost + len(terms)
                    layer[out] = (carry, terms)
        best = costs
        layers.append(layer)
    plan = []
    carry = 0
    for layer in reversed(layers):
        carry, terms = layer[carry]
        plan.append(terms)
    plan.reverse()
    while plan and not plan[-1]:
        plan.pop()
    for position, terms in enumerate(reversed(plan)):
        if position:
            code.append("b=b*e")
        code += [f"b=b{sign}{_REGISTER[size]}" for sign, size in terms]
    return code


def _parity_integer(table: str) -> list[str]:
    """Build full-input parity as hexadecimal digits 6 or 9, without search."""
    code = ["a=i/i", "c=a+a", "c=c+a", "d=c+c", "e=d+d", "e=e+c", "e=e+a"]
    # Four consecutive parity bits are 0110 or 1001: reversed, hex6 or9.
    # Half the groups are each kind, hence 5T/8+6 table instructions.
    for start in range(len(table) - 4, -1, -4):
        if start != len(table) - 4:
            code.append("b=b*e")
        code.append("b=b+d")
        if table[start] == "1":
            code.append("b=b+c")
    return code


def _lookup(n: int, essential: list[int], *, mirror: bool = False) -> list[str]:
    """Return the code shifting ``b`` right by the essential bits of ``i - 1``.

    ``c`` stays 2; ``e`` holds Q-1 and squares by (Q-1)(Q+1).
    The counter alternates with its quotient scratch, removing copies.
    An ignored input's bit is dropped from the counter unused; rounds stop at the
    most significant essential input.  Every divisor is 2 or
    ``1 + bit * (Q - 1)``, never 0, until the halt.  ``mirror`` divides by
    ``Q - bit * (Q - 1)`` instead, so every input reads negated.
    """
    code = ["i=i-a", "c=a+a", "e=a*a"]
    counter, scratch = "i", "d"
    left = len(essential)
    for k in range(n - 1, (essential or [n])[0] - 1, -1):
        if k not in essential:
            code.append(f"{counter}={counter}/c")
            continue
        code += [
            f"{scratch}={counter}/c",
            f"{counter}={counter}-{scratch}",
            f"{counter}={counter}-{scratch}",
            f"{counter}={counter}*e",
        ]
        if mirror:
            code.append(f"{counter}=e-{counter}")
        code += [f"{counter}={counter}+a", f"b=b/{counter}"]
        left -= 1
        if left:
            code += [f"{counter}=e+c", f"e=e*{counter}"]
        counter, scratch = scratch, counter
    # A retained divisor Q means b was divided by Q already; otherwise it
    # is only 1. Its overlap with the even table copy stays within 2T bits.
    return [
        *code,
        "e=b/c",
        "e=e*c",
        "i=b-e",
        "e=e-e",
        "e=e/e",
    ]


def blindfolded_arithmetic(truth_table: str) -> str:
    """Build a program printing ``truth_table[row]`` for input ``row + 1``."""
    n = _validate_truth_table(truth_table)
    if len(set(truth_table)) == 1:
        return "i=i-i;i=i/a" if truth_table[0] == "0" else "i=i/i;i=i/a"
    # At n=3 the larger constant setup grows parity by one instruction;
    # n=4 ties, and the independently judged saving tends to 25%.
    if n >= 4 and _parity_bias(truth_table) is not None:
        return ";".join(_parity_integer(truth_table) + _lookup(n, list(range(n))))
    essential = essential_inputs(truth_table, n)
    projected = read_at(truth_table, essential, n)
    # A set bit costs an instruction: the complement or reversal may be shorter.
    candidates = []
    for mirror in (False, True):
        table = projected[::-1] if mirror else projected
        for flip in (False, True):
            bits = table.translate(str.maketrans("01", "10")) if flip else table
            code = _table_integer(bits) + _lookup(n, essential, mirror=mirror)
            if flip:
                code.insert(-2, "i=a-i")
            candidates.append(code)
    return ";".join(min(candidates, key=lambda code: len(";".join(code))))


def _wrap(program: str, width: int) -> str:
    return wrap_tokens(program, width, _INSTRUCTION)


LANGUAGE = Language(
    "Blindfolded Arithmetic",
    "blindfolded_arithmetic",
    category="register_based",
    boolean=blindfolded_arithmetic,
    contract=BooleanContract(
        input_shape="row_number",
        note="the input must be a positive integer, so the committed input is "
        "the row index plus one",
    ),
    wrap=_wrap,
    empty_program="a Blindfolded Arithmetic program needs at least one instruction",
    # No flow control: the table is data, indexed by arithmetic, not a tree.
    shape=Shape.LOOKUP,
)
