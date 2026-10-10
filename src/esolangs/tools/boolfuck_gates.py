"""Normalize two-input cofactors into shared AND/XOR bodies in O(T)."""

from typing import Literal

from esolangs.tools.helpers import (
    _validate_truth_table,
    constant_span_test,
    subtree_ids,
)
from esolangs.tools.shared_block import ContinuationCost as _Cost

type _Kind = Literal["and", "xor"]
type _Normal = tuple[_Kind | None, int, bool, bool, int | None]


def affine_stream(table: str) -> str | None:
    """Stream an affine truth table through one input and one accumulator."""
    n = _validate_truth_table(table)
    if n < 2:
        return None
    bias = int(table[0])
    coefficients = [int(table[1 << (n - i - 1)]) ^ bias for i in range(n)]
    expected = [bias]
    for coefficient in reversed(coefficients):
        expected += [value ^ coefficient for value in expected]
    if any(str(value) != bit for value, bit in zip(expected, table, strict=True)):
        return None
    # Selected bytes cost at most 17 commands, ignored ones 10, plus at
    # most 19 for bias/printing: 17*n+19 fits the existing bound for n>=2.
    # Cells -1/0/1 use at most four address bits; machine/cursor state
    # needs bl(L)+12+bl(n), below the existing workspace formula for n>=2.
    parts = [">+<" if bias else ""]
    for coefficient in coefficients:
        parts.append("," + ("[+>+<]" if coefficient else "") + "<,,,,,,,>")
    # Ignored reads can leave cell 0 set; clear it before the ASCII high bits.
    parts.append("[+]>;<;;;+;;+;;")
    return "".join(parts)


def _normal(word: str) -> _Normal:
    if word.count("1") in (0, 4):
        return None, int(word[0]), False, False, None
    if word[0] == word[3] and word[1] == word[2]:
        return "xor", int(word[0]), False, False, None
    if word.count("1") in (1, 3):
        bias = int(word.count("1") == 3)
        exceptional = next(i for i, bit in enumerate(word) if int(bit) != bias)
        return "and", bias, not exceptional & 2, not exceptional & 1, None
    return "and", int(word[0]), False, False, 1 if word[0] == word[1] else 0


def normal_gates(table: str) -> str | None:
    """Return shared normalized gates where both existing ledgers admit them."""
    n = _validate_truth_table(table)
    # Prefix forks cost at most 15 commands per input. The AND/XOR tails
    # give 2*n*n + 25*n + 26, at most the existing bound exactly when n>=9.
    # Native extreme paths attain it at n=9 (413) and n=16 (938).
    if n < 9:
        return None
    depth = n - 2
    x, y, result = 2 * depth, 2 * depth + 2, 2 * n
    kinds = {_normal(table[row : row + 4])[0] for row in range(0, len(table), 4)} - {
        None
    }
    gates = [kind for kind in ("and", "xor") if kind in kinds]
    flags = {kind: x + 1 + 2 * i for i, kind in enumerate(gates)}
    carrier = x + 1
    ids, constant = subtree_ids(table), constant_span_test(table)
    out: list[str] = []
    pos = 0
    count = 0

    def emit(code: str) -> None:
        nonlocal count
        out.append(code)
        count += len(code)

    def move(target: int) -> None:
        nonlocal pos
        emit(">" * (target - pos) if target >= pos else "<" * (pos - target))
        pos = target

    def clear(cell: int) -> None:
        move(cell)
        emit("[+]")

    def printer() -> None:
        move(result)
        emit(";")
        move(carrier)
        emit(";;;+;;+;;")

    for i in range(n):
        move(2 * i)
        emit(",")
        move(-1)
        emit("," * 7)
    header_cost = count

    # Let M be the sum of the original input-address widths and b=bl(2n).
    # Read scratch and transient flags need at most M+2 bits. After the
    # prefix, four gate cells need at most 4b<=M+2 for n>=9. Constant exits
    # clear x/y before setting R/carrier, adding at most two address bits.
    # State and input cursor need bl(L)+max(12,b+11)+bl(n), so the total
    # fits the existing workspace formula, including power-of-two lengths.
    def leaf(value: int) -> None:
        clear(x)
        clear(y)
        if value:
            move(result)
            emit("+")
        printer()

    def node(i: int, lo: int, hi: int) -> _Cost:
        start = count
        if constant(lo, hi):
            leaf(int(table[lo]))
            # Each clear executes at most four commands, one more than text.
            return _Cost(count - start + 2)
        if i == depth:
            kind, bias, flipx, flipy, forced = _normal(table[lo:hi])
            if kind is None:
                raise ValueError("constant cofactor reached a pending gate")
            if forced is not None:
                clear((x, y)[forced])
                emit("+")
            for cell, flip in ((x, flipx), (y, flipy)):
                if flip:
                    move(cell)
                    emit("+")
            if bias:
                move(result)
                emit("+")
            move(flags[kind])
            emit("+")
            return _Cost(count - start + int(forced is not None), target=flags[kind])
        mid = (lo + hi) // 2
        left, right = ids[i + 1][lo >> (n - i - 1)], ids[i + 1][mid >> (n - i - 1)]
        if left == right:
            clear(2 * i)
            prefix = count - start + 1
            return _Cost(prefix, (node(i + 1, lo, mid),))
        bit, flag = 2 * i, 2 * i + 1
        move(flag)
        emit("+")
        move(bit)
        zero_entry = count - start + 1
        emit("[+")
        move(flag)
        emit("+")
        one_entry = count - start
        one = node(i + 1, mid, hi)
        finish = count
        move(bit)
        emit("]")
        one_finish = count - finish + 1  # the closing bracket rechecks [
        zero_start = count
        move(flag)
        emit("[+")
        one_finish += count - zero_start - 1  # the zero arm skips its +
        zero_entry += count - zero_start
        zero = node(i + 1, lo, mid)
        finish = count
        move(flag)
        emit("]")
        zero_finish = count - finish + 1
        return _Cost(
            0,
            (
                _Cost(one_entry + one_finish, (one,)),
                _Cost(zero_entry + zero_finish, (zero,)),
            ),
        )

    prefix = node(0, 0, len(table))
    tails: dict[int | None, int] = dict.fromkeys((None, *flags.values()), 0)
    for kind in gates:
        pending = flags[kind]
        distance = abs(pending - pos)
        move(pending)
        emit("[+")
        start = count
        if kind == "and":
            move(x)
            emit("[+")
            move(y)
            emit("[+")
            move(result)
            emit("+")
            move(y)
            emit("]")
            move(x)
            emit("]")
            clear(y)
        else:
            for cell in (x, y):
                move(cell)
                emit("[+")
                move(result)
                emit("+")
                move(cell)
                emit("]")
        printer()
        move(pending)
        active = count - start + (2 if kind == "xor" else 0) + 4
        emit("]")
        for target in tails:
            tails[target] += distance + (active if target == pending else 1)
    commands = header_cost + prefix.evaluate(tails)
    if commands > 2 * n * n + 27 * n + 8:
        return None
    return "".join(out)
