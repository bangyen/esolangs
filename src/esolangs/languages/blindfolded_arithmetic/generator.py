"""Blindfolded Arithmetic Boolean program generator: shift the table by the row.

Straight-line code, run once.  ``b`` is built as the integer whose bit ``r``
is row ``r``'s answer in the table read at the essential inputs, by Horner's
rule in base 8 with the digit summed from registers holding 1, 2 and 4.  The
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


def _table_integer(truth_table: str) -> list[str]:
    """Return the code leaving ``b`` = the table, bit ``r`` = row ``r``.

    ``i`` is untouched; ``a``, ``c``, ``d`` hold 1, 2, 4 and ``e`` 8 on exit.
    """
    code = ["a=i/i", "c=a+a", "d=c+c", "e=d+d"]
    digits = format(int(truth_table[::-1], 2), "o")
    for position, digit in enumerate(int(char) for char in digits):
        if position:
            code.append("b=b*e")
        code += [
            f"b=b+{reg}" for bit, reg in ((1, "a"), (2, "c"), (4, "d")) if digit & bit
        ]
    return code


def _lookup(n: int, essential: list[int]) -> list[str]:
    """Return the code shifting ``b`` right by the essential bits of ``i - 1``.

    An ignored input's bit is dropped from ``i`` unused; rounds stop at the
    most significant essential input.  Every divisor is 2 or
    ``1 + bit * (Q - 1)``, never 0, until the halt.
    """
    code = ["i=i-a", "e=a+a"]
    left = len(essential)
    two = False  # whether ``c`` already holds 2
    for k in range(n - 1, (essential or [n])[0] - 1, -1):
        if not two:
            code.append("c=a+a")
        if k not in essential:
            code.append("i=i/c")
            two = True
            continue
        code += [
            "d=i/c",
            "d=d*c",
            "d=i-d",  # input k's bit
            "i=i/c",
            "c=e-a",
            "c=c*d",
            "c=c+a",  # 1, or Q = 2**2**m for the mth essential input up
            "b=b/c",
        ]
        two = False
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
    return ";".join([*_table_integer(projected), *_lookup(n, essential)])


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
