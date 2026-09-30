"""Factor witness with fixed Delannoy-ball blocks and a binary rank decoder."""

from collections.abc import Callable
from functools import lru_cache
from math import comb

from esolangs.tools.helpers import _validate_truth_table
from tests.proofs._factor_counter import _Code, _counter, counter_program

_CELLS = 14
_BUDGET = 14
_BITS = 32
_BASE = 64
_TEMP = 14
_TIMES = 15
_GATE = 16
_WORK = 17
_GUARD = 18
_MAG = 19
_SIGN = 20
_B = 21
_INPUT = 22
_OUTPUT = 23
_INDEX = 24
_THRESH = 25
_ZERO = 26
_FLAGS = 32


def ball_count(cells: int, budget: int) -> int:
    """Count integer vectors of the given dimension and bounded L1 norm."""
    return sum(
        2**j * comb(cells, j) * comb(budget, j) for j in range(min(cells, budget) + 1)
    )


def unrank(value: int, cells: int = _CELLS, budget: int = _BUDGET) -> list[int]:
    """Unrank in coordinate order zero, positive one, negative one, and so on."""
    result = []
    for remaining in reversed(range(cells)):
        choices = [0] + [sign * d for d in range(1, budget + 1) for sign in (1, -1)]
        for digit in choices:
            count = ball_count(remaining, budget - abs(digit))
            if value < count:
                result.append(digit)
                budget -= abs(digit)
                break
            value -= count
        else:
            raise ValueError("rank exceeds the ball")
    if value:
        raise ValueError("rank exceeds the ball")
    return result


def rank(vector: list[int], budget: int = _BUDGET) -> int:
    """Rank an L1-bounded integer vector in the same coordinate order."""
    value = 0
    for remaining, digit in zip(reversed(range(len(vector))), vector, strict=True):
        if digit:
            value += ball_count(remaining, budget)
            value += 2 * sum(
                ball_count(remaining, budget - d) for d in range(1, abs(digit))
            )
            if digit < 0:
                value += ball_count(remaining, budget - abs(digit))
        budget -= abs(digit)
    return value


@lru_cache(maxsize=1)
def block_decoder() -> str:
    """Recover the rank's selected bit using fixed binary arithmetic."""
    code = _Code()
    for cell in range(_CELLS, _BASE + 6 * _BITS + 3):
        code.at(cell, "[-]")
    code.at(_B, "+" * _BUDGET)

    def copy(source: int, target: int) -> None:
        code.at(target, "[-]")
        code.at(source, "[-")
        code.at(target, "+")
        code.at(_TEMP, "+")
        code.at(source, "]")
        code.transfer(_TEMP, source)

    def nonzero(source: int, action: Callable[[], None]) -> None:
        copy(source, _GATE)
        code.at(_GATE, "[[-]")
        action()
        code.at(_GATE, "]")

    def switch(source: int, limit: int, action: Callable[[int], None]) -> None:
        def branch(value: int) -> None:
            if value == limit:
                action(value)
                return
            flag = _FLAGS + value
            code.at(flag, "+")
            code.at(source, "[-")
            code.at(flag, "-")
            branch(value + 1)
            code.at(source, "]")
            code.at(flag, "[-")
            action(value)
            code.at(flag, "]")

        branch(0)

    def add() -> None:
        for bit in range(_BITS):
            cell = _BASE + 6 * bit
            code.transfer(cell, cell + 3)
            code.transfer(cell + 2, cell + 3)
            code.at(cell + 1, "[-")
            code.at(cell + 3, "+")
            code.at(cell + 5, "+")
            code.at(cell + 1, "]")
            code.transfer(cell + 5, cell + 1)
            code.at(cell + 3, "[-")
            code.at(cell + 4, "+")
            code.at(cell, "[-")
            code.at(cell + 8, "+")
            code.at(cell + 4, "-")
            code.at(cell, "]")
            code.at(cell + 4, "[-")
            code.at(cell, "+")
            code.at(cell + 4, "]")
            code.at(cell + 3, "]")
        code.at(_BASE + 6 * _BITS + 2, "[-]")

    for coordinate in range(_CELLS):
        code.at(coordinate, "+" * _BUDGET)
        code.at(_MAG, "[-]" + "+" * _BUDGET)
        code.at(_SIGN, "[-]+")
        code.at(_THRESH, "[-]" + "+" * _BUDGET)
        code.at(coordinate, "[-")
        code.at(_ZERO, "[-]+")

        def below() -> None:
            code.at(_THRESH, "-")
            code.at(_MAG, "-")
            code.at(_ZERO, "-")

        nonzero(_THRESH, below)
        code.at(_ZERO, "[-")
        code.at(_SIGN, "[-]")
        code.at(_MAG, "+")
        code.at(_ZERO, "]")
        code.at(coordinate, "]")
        code.at(_TIMES, "[-]+")
        code.at(_GUARD, "[-]")
        nonzero(_MAG, lambda: code.at(_GUARD, "+"))
        code.at(_GUARD, "[")
        for bit in range(_BITS):
            code.at(_BASE + 6 * bit + 1, "[-]")
        copy(_B, _WORK)

        def count(value: int, coordinate: int = coordinate) -> None:
            number = ball_count(_CELLS - coordinate - 1, value)
            for bit in range(_BITS):
                if number & (1 << bit):
                    code.at(_BASE + 6 * bit + 1, "+")

        switch(_WORK, _BUDGET, count)
        code.at(_TIMES, "[-")
        add()
        code.at(_TIMES, "]")
        code.at(_GUARD, "[-]")

        def advance() -> None:
            code.at(_MAG, "-")
            code.at(_B, "-")
            code.at(_GUARD, "+")

        nonzero(_MAG, advance)
        code.at(_TIMES, "[-]++")
        code.at(_INPUT, "[-]+")
        nonzero(_MAG, lambda: code.at(_INPUT, "-"))
        code.at(_INPUT, "[-")
        copy(_SIGN, _TIMES)
        code.at(_INPUT, "]")
        code.at(_GUARD, "]")

    for _ in range(5):
        code.transfer(_INDEX, _WORK, "++")
        code.transfer(_WORK, _INDEX)
        code.at(_INPUT, "," + "-" * 48)
        code.transfer(_INPUT, _INDEX)

    def output(value: int) -> None:
        code.transfer(_BASE + 6 * (31 - value), _OUTPUT)

    switch(_INDEX, 31, output)
    code.at(_OUTPUT, "+" * 48 + ".")
    return code.render()


def block_program(truth_table: str) -> str:
    """Encode 32-bit chunks in fixed signed balls and address their ranks."""
    n = _validate_truth_table(truth_table)
    if n < 5:
        return counter_program(truth_table)
    vectors = [
        unrank(int(truth_table[i : i + 32], 2)) for i in range(0, len(truth_table), 32)
    ]
    blocks = [
        "".join(">" + ("+" if v >= 0 else "-") * abs(v) for v in vector)
        for vector in vectors
    ]
    data = ">".join(blocks) + "<" * _CELLS
    return data + _counter(n - 5, stride=15) + ">" + block_decoder()
