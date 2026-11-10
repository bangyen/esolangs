"""Tests for the Freestajlo interpreter."""

import pytest

from esolangs.languages.freestajlo.interpreter import run
from tests.interpreters.runner import native_runner

_out = native_runner(run)


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        ("1 2 3 1&::::", "2321"),  # & copies the item that deep, 0 the top
        ("5 6 7 9 2~::::", "7695"),  # ~ inserts 9 two items down
        ("1 2|:::", "221"),
        ("3 4`:", "-8"),
        ("7_3%: 7 3_%: 7_2/:", "2-2-3"),  # % takes a's sign, / truncates
        ("2 10^: 2 1_^:", "10240"),
        ('"ab":::', "97980"),  # the first character ends on top, 0 under
        ("1!5 0!(:1!$)0!(:", "05"),
        ("f{'a.}ff", "aa"),
    ],
)
def test_arithmetic_and_stack_commands(code: str, expected: str) -> None:
    assert _out(code) == expected


def test_signed_quotient_and_remainder(monkeypatch) -> None:
    from esolangs.languages.freestajlo import interpreter
    from tests.support.prepared_support import check_image_reuse

    check_image_reuse(
        "Freestajlo", "f{,.} 1!0! f [tail]", interpreter, "_parse", monkeypatch
    )
    for dividend in [-(2**55 + 1), -13, -6, -1, 0, 1, 6, 13, 2**55 + 1]:
        for divisor in [-4, -3, 3, 4]:
            left = str(abs(dividend)) + "_" * (dividend < 0)
            right = str(abs(divisor)) + "_" * (divisor < 0)
            quotient = abs(dividend) // abs(divisor)
            if (dividend < 0) != (divisor < 0):
                quotient = -quotient
            assert _out(f"{left} {right}/:") == str(quotient)
            assert _out(f"{left} {right}%:") == str(dividend % divisor)
