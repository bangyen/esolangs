"""factor generator tests."""

import sys

import pytest

from esolangs import tools as boolean
from tests.tools.boolean_runners import (
    run_bf,
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

    def test_the_render_works_under_an_unlimited_global(self) -> None:
        """``sys.set_int_max_str_digits(0)`` means unlimited, not zero.

        Read as a ceiling, 0 sent every render over it and then asked for
        a limit below CPython's 640 floor, a ``ValueError`` on every table.
        """
        before = sys.get_int_max_str_digits()
        sys.set_int_max_str_digits(0)
        try:
            assert boolean.factor("0110").isdigit()
        finally:
            sys.set_int_max_str_digits(before)

    @pytest.mark.slow
    @pytest.mark.weekly
    @pytest.mark.cost_evidence("Factor's dense n=13 render stops beyond 500000 digits")
    def test_total_past_the_retired_digit_budget(self) -> None:
        """No digit budget: the 500000-digit refusal is gone (dense n=13).

        703447 digits, and the interpreter decodes it to the program the
        generator encoded.  That decode is the whole load cost (n=12
        parity's 460824 took 43s), so the rows run on
        the decoded machine -- the object ``_Machine.step`` drives --
        rather than through 8192 re-factorizations; ``weekly`` like the
        other high-arity probes.
        """
        from esolangs.interpreters.tape_based.factor import _parse, decode
        from esolangs.tools.factor import _encode
        from tests.tools.test_boolean_contract import _dense

        n = 13
        table = _dense(n)
        program = boolean.factor(table)
        assert len(program) > 500_000
        code = decode(_parse(program))
        # Re-encoding rather than comparing against brainfuck's program: the
        # construction Factor encodes is its own now, and the contract is the
        # round trip, which holds whatever it builds.  The digit limit guards
        # str -> int too, so it is raised here as the generator raises it for
        # its own render.
        limit = sys.get_int_max_str_digits()
        sys.set_int_max_str_digits(len(program) + 1)
        try:
            assert _encode(code) == int(program)
        finally:
            sys.set_int_max_str_digits(limit)
        for row in (0, 1, 2**12, 2**13 - 2, 2**13 - 1):
            bits = [str((row >> (n - 1 - i)) & 1) for i in range(n)]
            assert run_bf(code, bits) == table[row], row
