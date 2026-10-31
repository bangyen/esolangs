"""Blindfolded Arithmetic Boolean program generator: shift the table by the row.

Straight-line code, run once.  ``b`` is built as the integer whose bit ``r``
is row ``r``'s answer in the table read at the essential inputs, by Horner's
rule in base 8 with the digit summed from registers holding 1, 2, 4 and 8.  The
input ``i`` is the row plus one, so ``i - 1`` is the row; each essential bit,
least significant first, divides ``b`` by ``1 + bit * (Q - 1)`` for
``Q = 2**2**m``, kept by squaring, and an ignored bit is dropped unused.
``i`` becomes ``b``'s low bit, and ``e = e / e`` on a zeroed ``e`` halts and
prints it.

Size:
    Theta(T) text, 9 or 10 instructions an essential input and at most two an
    ignored one; n=4 parity: 377 chars, n=10 parity: 5,777 chars.

Decisions:
    Base 8 is the widest Horner base whose digit registers (1, 2, 4), radix
    and accumulator fit beside ``i``; base 2 costs 9,851 chars at n=10
    parity.

    Each octal digit is added as ``v`` or as ``v - 8`` with a carry up,
    whichever totals fewer terms of +-1, +-2, +-4, +-8
    ([ablations.signed_digits]).

    The shorter of the table and its complement is built, the complement's
    answer negated by ``i = a - i``: or at n=10 8,849 -> 677 chars
    ([ablations.complement_table]).

    The reversed table read with negated inputs (divisor ``Q - bit * (Q - 1)``,
    same cost) is also tried: and at n=8 1,061 -> 551 ([ablations.mirror_lookup]).

    The divisor 2 is rebuilt into ``c`` every round: keeping it across
    rounds saved one 6-char instruction per firing — a fixed amount
    against a Theta(T) program ([ablations.register_reuse]).
"""

from esolangs.generation.helpers import (
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
    # ``best[carry]`` = (term count, digit terms, least significant first).
    best: dict[int, tuple[int, list[list[tuple[str, int]]]]] = {0: (0, [])}
    for digit in [*digits, 0]:
        step: dict[int, tuple[int, list[list[tuple[str, int]]]]] = {}
        for carry, (cost, plan) in best.items():
            for value, out in ((digit + carry, 0), (digit + carry - 8, 1)):
                terms = _terms(value)
                if out not in step or cost + len(terms) < step[out][0]:
                    step[out] = (cost + len(terms), [*plan, terms])
        best = step
    plan = best[0][1]
    while plan and not plan[-1]:
        plan.pop()
    for position, terms in enumerate(reversed(plan)):
        if position:
            code.append("b=b*e")
        code += [f"b=b{sign}{_REGISTER[size]}" for sign, size in terms]
    return code


def _lookup(n: int, essential: list[int], *, mirror: bool = False) -> list[str]:
    """Return the code shifting ``b`` right by the essential bits of ``i - 1``.

    An ignored input's bit is dropped from ``i`` unused; rounds stop at the
    most significant essential input.  Every divisor is 2 or
    ``1 + bit * (Q - 1)``, never 0, until the halt.  ``mirror`` divides by
    ``Q - bit * (Q - 1)`` instead, so every input reads negated.
    """
    code = ["i=i-a", "e=a+a"]
    left = len(essential)
    for k in range(n - 1, (essential or [n])[0] - 1, -1):
        code.append("c=a+a")
        if k not in essential:
            code.append("i=i/c")
            continue
        code += [
            "d=i/c",
            "d=d*c",
            "d=i-d",  # input k's bit
            "i=i/c",
            "c=e-a",
            "c=c*d",
            "c=e-c"
            if mirror
            else "c=c+a",  # 1 or Q = 2**2**m, by the bit or its negation
            "b=b/c",
        ]
        left -= 1
        if left:
            code.append("e=e*e")
    # ``e`` takes ``b // 2``: overwriting ``Q`` keeps the peak at 2T bits
    # where ``d`` held 2.5T (645 bits at n=8).
    return [*code, "c=a+a", "e=b/c", "e=e*c", "i=b-e", "e=e-e", "e=e/e"]


def blindfolded_arithmetic(truth_table: str) -> str:
    """Build a program printing ``truth_table[row]`` for input ``row + 1``."""
    n = _validate_truth_table(truth_table)
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
