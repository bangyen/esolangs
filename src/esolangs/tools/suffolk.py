"""Boolean-function generator for Suffolk."""

from esolangs.tools.helpers import (
    _ASCII_ONE,
    _ASCII_ZERO,
    _validate_truth_table,
    essential_inputs,
    read_at,
)


def suffolk(truth_table: str) -> str:
    """Build Suffolk by a one-pass Shannon fold of reusable NOR muxes."""
    n = _validate_truth_table(truth_table)

    def const(cell: int, value: int) -> str:
        return (">" * cell + "!") * value

    if len(set(truth_table)) == 1:
        reads = "".join(
            const(2 + i, _ASCII_ZERO) + ">" * (2 + i) + ",!" for i in range(n)
        )
        return const(1, _ASCII_ONE + int(truth_table[0])) + reads + "><."

    used = essential_inputs(truth_table, n) or [0]
    reduced = truth_table if len(used) == n else read_at(truth_table, used, n)
    width = len(used)
    body = [const(1, 1)]  # pieces, joined once: O(T), not a copy per mux
    scratch = (2, 3)

    def cells(level: int) -> tuple[int, int, int, int]:
        base = 4 + 4 * level
        return base, base + 1, base + 2, base + 3

    selectors: list[tuple[int, int]] = []
    for original in range(n):
        level = n - 1 - original
        raw, negated, _, _ = cells(level)
        body.append(const(negated, _ASCII_ZERO) + ">" * negated + ",!")
        body.append(">" * negated + "<" + ">" * raw + "!")
        if original in used:
            selectors.append((raw, negated))

    def read(cell: int) -> str:
        return ">" * cell + "<"

    def nor(target: int, left: int, right: int) -> None:
        body.append(read(target) + read(left) + read(right) + ">" * target + "!")

    stack: list[tuple[int, int]] = []
    for index, bit in enumerate(reduced):
        signal, level = int(bit), 0
        while stack and stack[-1][1] == level:
            zero, _ = stack.pop()
            selector, negated = selectors[width - 1 - level]
            if zero == 0 and signal == 1:
                signal = selector
            elif zero == 1 and signal == 0:
                signal = negated
            elif zero != signal:
                _, _, first, second = cells(level)
                target = (first, second)[(index >> (level + 1)) & 1]
                nor(scratch[0], zero, selector)
                nor(scratch[1], signal, negated)
                nor(target, scratch[0], scratch[1])
                signal = target
            level += 1
        stack.append((signal, level))
    [(result, _)] = stack
    body.append(const(1, _ASCII_ZERO) + read(1) + read(result) + ".")
    return "".join(body)
