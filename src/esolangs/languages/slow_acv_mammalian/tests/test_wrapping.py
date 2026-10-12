from esolangs.languages.slow_acv_mammalian.wrapping import (
    _balance_mammalian,
    _mammalian,
)
from esolangs.tools.wrap import balance_score


def test_equal_cells_reach_the_global_minimum() -> None:
    for count in range(1, 33):
        program = " ".join(["1111"] * count)
        balanced = _balance_mammalian(program)
        optimum = min(
            (_mammalian(program, width) for width in range(1, len(program) + 1)),
            key=balance_score,
        )
        assert balance_score(balanced) == balance_score(optimum)
