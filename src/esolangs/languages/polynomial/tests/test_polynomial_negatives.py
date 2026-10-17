"""Executed counterexamples for the expanded-source model of the scaling bound."""

from __future__ import annotations

import pytest

from esolangs.languages.polynomial.generator import polynomial
from esolangs.languages.polynomial.generator.algebra import format_coeffs, multiply
from esolangs.languages.polynomial.interpreter import (
    _parse_program,
    run,
    sanitize,
)
from esolangs.runtime.io import ScriptedIO

# --------------------------------------------------------------------------
# Polynomial cannot ship a factored program
# --------------------------------------------------------------------------
#
# the archived scaling proof prices Polynomial's text as the *expanded*
# polynomial's coefficient digits.  The obvious escape is to ship the product
# form instead -- m factors, each O(log) characters, so O(m log m) text and no
# expansion at all.  The document rules that out on the parser's behaviour,
# and a silent misparse is what makes it a dead end rather than a feature
# request: the program still runs, just as a different program.


class TestFactoredProgramsAreMisread:
    """``f(x) = (x-2)(x-3)`` parses, and parses *wrong*."""

    def test_only_the_last_term_of_each_degree_survives(self) -> None:
        # Accepted, not rejected, and read as the last term of each degree:
        # ``_sanitize`` sums ``c*x^d`` monomials and never multiplies out.
        # ``*`` is stripped by the character filter.
        assert sanitize("f(x) = (x-2)(x-3)") == [1, -3]
        assert sanitize("f(x) = (x-2)*(x-3)") == [1, -3]
        assert sanitize("f(x) = (x-2)(x-3)(x-5)") == [1, -5]


class TestRepeatedRealRootsDecodeToRepeatedInstructions:
    """``(x-2)^3`` is a legal program decoding to three copies of ``[1]``."""

    def test_a_cubed_root_decodes_to_three_instructions(self) -> None:
        assert _parse_program("f(x) = x^3-6x^2+12x-8") == ((1,), (1,), (1,))


# --------------------------------------------------------------------------
# Polynomial multiples cannot change what a program does
# --------------------------------------------------------------------------
#
# the archived scaling proof says extra roots that do not match an instruction
# code "may multiply the mandatory root product without changing execution".
# That premise carries the whole sparse-multiple frontier, so it is executed
# rather than asserted: built here, decoded here, and run here.

#: ``reg += 70 ; reg -= 5 ; output`` -- prints "A" (primes 2, 3, 5).
_A_PRINTER_FACTORS = (
    [1, -140, 70 * 70 + 4],  # (x-70)^2 + 2^2
    [1, 10, 25 + 9],  # (x+5)^2 + 3^2, a negative operand
    [1, 0, 25],  # x^2 + 5^2
)
_A_PRINTER_DECODED = [[70, 1], [-5, 1], [0, 1]]


def _a_printer() -> list[int]:
    base = [1]
    for factor in _A_PRINTER_FACTORS:
        base = multiply(base, factor)
    return base


class TestIgnoredRootMultiplesPreserveExecution:
    """Multiplying by a root that is not an instruction code changes nothing."""

    @pytest.mark.parametrize(
        ("name", "cofactor"),
        [
            ("x^2 + x + 1, irreducible and the wrong quadratic shape", [1, 1, 1]),
            ("x - 6, linear with a root that is not a prime power", [1, -6]),
        ],
    )
    def test_a_shape_dodging_cofactor_leaves_the_program_alone(
        self, name: str, cofactor: list[int]
    ) -> None:
        code = format_coeffs(multiply(_a_printer(), cofactor))
        assert [list(d) for d in _parse_program(code)] == _A_PRINTER_DECODED, name
        io = ScriptedIO("")
        run(code, io)
        assert io.getvalue() == "A", name

    def test_the_control_changes_the_decode(self) -> None:
        # x - 2: the root 2 = 2^1 IS an instruction code, so this one must
        # decode differently.  Without it the tests above would pass on an
        # implementation that ignored cofactors entirely.
        code = format_coeffs(multiply(_a_printer(), [1, -2]))
        assert [list(d) for d in _parse_program(code)] != _A_PRINTER_DECODED

    def test_a_real_generator_artifact_survives_being_multiplied(self) -> None:
        table = "0110"
        program = polynomial(table)
        lifted = format_coeffs(multiply(sanitize(program), [1, 1, 1]))

        def rows(code: str) -> str:
            out = []
            for row in range(1 << 2):
                io = ScriptedIO("".join(f"{b}" for b in f"{row:02b}"))
                run(code, io)
                out.append(io.getvalue())
            return "".join(out)

        assert rows(program) == table
        assert rows(lifted) == table
