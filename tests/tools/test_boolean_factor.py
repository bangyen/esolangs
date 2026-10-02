"""factor generator tests."""

import sys

import pytest

from esolangs import tools as boolean
from tests.tools.boolean_runners import (
    run_bf,
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

    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("10", 1),  # NOT
            ("01", 1),  # identity
            ("0110", 2),  # XOR
            ("0001", 2),  # AND
            ("1110", 2),  # NAND
            ("11111110", 3),  # NAND3
        ],
    )
    @pytest.mark.medium
    def test_truth_table(self, table: str, n: int) -> None:
        """Every input combination produces the truth-table result."""
        program = boolean.factor(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_factor(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

    def test_factors_back_into_a_working_bf_program(self) -> None:
        """The integer's factorization is a brainfuck program for the table.

        This used to assert the stronger ``factor(t) ==
        _factor_encode(brainfuck(t))``, which pinned *which* brainfuck
        program was encoded.  Factor pays a prime per run rather than a
        character per command, so it builds for that objective instead and no
        longer emits brainfuck's shortest program; what has to hold is the
        encoding itself, which is what this decodes and runs.
        """
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
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            io = ScriptedIO("".join(f"{bit}" for bit in bits))
            run_bf(code, io)
            assert io.getvalue() == table[combo], f"inputs {bits}"

    def test_builds_above_the_greedy_order_cap(self) -> None:
        """Past ``_GREEDY_ORDER_MAX_ARITY`` only the identity order is built.

        The generator scores two input orders by digits and keeps the better;
        above the cap the greedy order is not searched at all, which is a path
        of its own.  AND11 takes it cheaply -- the tree folds to one leaf, so
        this is 1330 digits and a 2ms build rather than parity's 425ms.
        """
        from esolangs.tools.helpers import _GREEDY_ORDER_MAX_ARITY

        n = _GREEDY_ORDER_MAX_ARITY + 1
        table = "0" * (2**n - 1) + "1"
        program = boolean.factor(table)
        assert program.isdigit()
        assert run_factor(program, ["1"] * n) == "1"
        assert run_factor(program, ["0"] * n) == "0"

    def test_sparse_tables_stay_small_at_n_four(self) -> None:
        """Sparse tables (few one-rows) encode a short brainfuck program,
        so they stay well under the digit cap even at n == 4."""
        assert boolean.factor("0" * 16).isdigit()
        assert boolean.factor("1" * 16).isdigit()

    def test_a_table_past_cpythons_own_limit_still_renders(self) -> None:
        """XOR7 exceeds CPython's 4300-digit rendering guard.

        Terminal transfers brought XOR6 below it; use the next arity to
        keep exercising the temporary limit increase.
        """
        xor7 = "".join("1" if bin(i).count("1") % 2 else "0" for i in range(128))
        program = boolean.factor(xor7)
        assert program.isdigit()
        assert len(program) > sys.get_int_max_str_digits()

    def test_the_render_leaves_the_global_limit_alone(self) -> None:
        """The digit limit is process-global, so it is borrowed, not kept.

        A generator that raised it and walked away would silently disarm
        the guard for everything else in the process.
        """
        before = sys.get_int_max_str_digits()
        boolean.factor(
            "".join("1" if bin(i).count("1") % 2 else "0" for i in range(16))
        )
        assert sys.get_int_max_str_digits() == before

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
