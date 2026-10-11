"""factor generator tests."""

import sys

import pytest

from esolangs import tools as boolean
from tests.support.witness_tables import row_bits
from tests.tools.boolean_runners import (
    run_factor,
)


class TestFactor:
    def test_prime_search_is_exact_across_segments(self) -> None:
        """The uncapped encoder uses an arbitrary-precision exact sieve."""
        import sympy

        from esolangs.factor_primes import prime_segments

        segments = prime_segments(40)
        first = next(segments)
        second = next(segments)
        assert first == (2, 42, list(sympy.primerange(2, 42)))
        assert second == (42, 82, list(sympy.primerange(42, 82)))

    def test_factors_back_into_a_working_bf_program(self) -> None:
        """The integer's factorization is a brainfuck program for the table."""
        import sympy

        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.brainfuck import run as run_bf
        from esolangs.tools.factor import _BF_RESIDUE

        table = "0110"
        n = 2
        command = {residue: char for char, residue in _BF_RESIDUE.items()}
        factors = sorted(sympy.factorint(int(boolean.factor(table))).items())
        code = "".join(command[prime % 11] * power for prime, power in factors)

        for combo in range(2**n):
            bits = row_bits(combo, n)
            io = ScriptedIO("".join(f"{bit}" for bit in bits))
            run_bf(code, io)
            assert io.getvalue() == table[combo], f"inputs {bits}"

    def test_builds_above_the_greedy_order_cap(self) -> None:
        """Past ``_GREEDY_ORDER_MAX_ARITY`` only the identity order is built."""
        from esolangs.tools.helpers import _GREEDY_ORDER_MAX_ARITY

        n = _GREEDY_ORDER_MAX_ARITY + 1
        table = "0" * (2**n - 1) + "1"
        program = boolean.factor(table)
        assert program.isdigit()
        assert run_factor(program, ["1"] * n) == "1"
        assert run_factor(program, ["0"] * n) == "0"

    def test_a_table_past_cpythons_own_limit_still_renders(self) -> None:
        """XOR7 exceeds CPython's 4300-digit rendering guard."""
        xor7 = "".join("1" if bin(i).count("1") % 2 else "0" for i in range(128))
        program = boolean.factor(xor7)
        assert program.isdigit()
        assert len(program) > sys.get_int_max_str_digits()

    def test_the_render_works_under_an_unlimited_global(self) -> None:
        """``sys.set_int_max_str_digits(0)`` means unlimited, not zero."""
        before = sys.get_int_max_str_digits()
        sys.set_int_max_str_digits(0)
        try:
            assert boolean.factor("0110").isdigit()
        finally:
            sys.set_int_max_str_digits(before)


@pytest.mark.medium
def test_shared_residual_measures_encoded_size_and_executes_within_ledger() -> None:
    from esolangs.tools.factor import _encode, _program
    from tests.support.generator_support import assert_shared_program

    zero = "0001011101101001" * 4
    one = "0110100100010111" * 4
    table = zero + one + one + zero
    plain = str(_encode(_program(table)))
    assert_shared_program(
        "Factor",
        table,
        plain,
        265 * 8 + 231,
        lambda _: (
            7 * 8
            + 12
            + (2 * 8 + 1).bit_length()
            + (8).bit_length()
            + (51 * 2 ** (8 - 2) + 16 * 8 + 14).bit_length()
        ),
    )


@pytest.mark.parametrize(("bit", "expected"), [(0, "1"), (1, "0")])
def test_one_input_not_stays_within_the_command_ledger(bit, expected) -> None:
    from esolangs.debugger import make_vm
    from esolangs.tools.factor import factor

    program = factor("10")
    assert len(program) == 142
    machine = make_vm("Factor", program, stdin=str(bit))
    for _ in range(496):
        if machine.halted:
            break
        machine.step()
    assert machine.halted
    assert machine.output == expected


@pytest.mark.medium
def test_multiple_residuals_reduce_encoded_size_within_ledger():
    from esolangs._digits import digit_limit_for
    from esolangs.tools.factor import _encode, _program
    from tests.support.generator_support import assert_shared_program

    n = 10
    residual = "".join(str(row.bit_count() & 1) for row in range(1 << (n - 4)))
    table = "0" * (15 * len(residual)) + residual
    previous = []
    for shared in (False, True):
        number = _encode(_program(table, shared=shared, multiple=False))
        with digit_limit_for(int(number.bit_length() * 0.30103) + 1):
            previous.append(str(number))
    assert_shared_program(
        "Factor",
        table,
        min(previous, key=len),
        265 * n + 231,
        lambda _: (
            7 * n
            + 12
            + (2 * n + 1).bit_length()
            + n.bit_length()
            + (51 * 2 ** (n - 2) + 16 * n + 14).bit_length()
        ),
        rows=[
            *range(15 * len(residual), len(table)),
            *[prefix * len(residual) + len(residual) - 1 for prefix in range(15)],
        ],
    )


@pytest.mark.medium
@pytest.mark.parametrize("bit", ["0", "1"])
def test_constant_projection_skips_ascii_normalization(bit):
    from esolangs.tools.factor import _factor
    from tests.support.generator_support import assert_shared_program

    n = 8
    assert_shared_program(
        "Factor",
        bit * (1 << n),
        _factor(bit * (1 << n), keep_constant_input=True),
        265 * n + 231,
        lambda _program: (
            7 * n
            + 12
            + (2 * n + 1).bit_length()
            + n.bit_length()
            + (51 * 2 ** (n - 2) + 16 * n + 14).bit_length()
        ),
    )


@pytest.mark.parametrize("n", [1, 2, 3, 5, 8])
@pytest.mark.parametrize("bit", ["0", "1"])
def test_constant_projection_retains_balanced_encoding(n, bit):
    from esolangs.tools.factor import _factor
    from tests.support.generator_support import assert_constant_balanced_shape

    table = bit * (1 << n)
    assert_constant_balanced_shape(
        "Factor", "factor", table, _factor(table, keep_constant_input=True)
    )


@pytest.mark.medium
def test_factor_bank_compares_decimal_encodings_and_executes_within_ledger():
    from esolangs.tools.factor import _encode, _program
    from tests.support.generator_support import assert_shared_program

    n = 8
    a, b = "00010111" * 4, "01101001" * 4
    table = a + b + b + a + a + b + a + b
    previous = min(
        (
            str(_encode(code))
            for code in (
                _program(table),
                _program(table, shared=True, multiple=False),
                _program(table, shared=True, bank=False),
            )
        ),
        key=len,
    )
    assert_shared_program(
        "Factor",
        table,
        previous,
        265 * n + 231,
        lambda _: (
            7 * n
            + 12
            + (2 * n + 1).bit_length()
            + n.bit_length()
            + (51 * 2 ** (n - 2) + 16 * n + 14).bit_length()
        ),
    )
