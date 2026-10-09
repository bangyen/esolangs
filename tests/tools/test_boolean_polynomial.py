"""polynomial generator tests."""

import random

import pytest

import esolangs
from esolangs import generate
from esolangs import tools as boolean
from esolangs._evaluate import _evaluate
from esolangs.tools.polynomial import _polynomial_dag, _polynomial_states
from esolangs.tools.wrap import (
    DEFAULT_WIDTH,
    _polynomial,
    balance_score,
    wrap_program,
)
from tests.tools.boolean_oracles import (
    _polynomial_tree,
)
from tests.tools.boolean_runners import (
    run_polynomial,
    run_polynomial_from,
)


@pytest.mark.medium
class TestPolynomial:
    def test_uncapped_dag_has_matching_text_bound(self) -> None:
        """Pin and execute the construction matching the language lower bound."""
        from esolangs.tools.polynomial import _polynomial_assemble
        from tests.witness_tables import dense as _dense

        for n in range(4, 9):
            table = _dense(n)
            levels = _polynomial_states(table, n)
            ceilings = [2 ** min(k, 2 ** (n - k)) for k in range(n + 1)]
            states = sum(map(len, levels))
            assert all(
                len(level) <= ceiling
                for level, ceiling in zip(levels, ceilings, strict=True)
            )
            assert states <= sum(ceilings)
            assert sum(ceilings) * n <= 8 * 2**n

            instructions = _polynomial_dag(table)
            assert len(instructions) <= 6 * states
            assert all(
                (len(instruction) == 1 and instruction[0] <= 2)
                or (
                    len(instruction) == 2
                    and instruction[1] <= 4
                    and abs(instruction[0]) <= 50 * states + n + 3
                )
                for instruction in instructions
            )

        table = _dense(4)
        instructions = _polynomial_dag(table)
        program = _polynomial_assemble(instructions)
        m = len(instructions)
        operand = max(abs(instruction[0]) for instruction in instructions)
        # The m-th prime is below m**2.  This bounds every factor's l1 norm;
        # multiplying l1 norms bounds every expanded coefficient.
        factor_l1_bound = (operand + 1) ** 2 + m**16
        coefficient_digits = m * len(str(factor_l1_bound))
        rendered_bound = 7 + (2 * m + 1) * (coefficient_digits + len(str(2 * m)) + 6)
        assert len(program) <= rendered_bound
        for row in range(16):
            bits = [(row >> (3 - i)) & 1 for i in range(4)]
            assert run_polynomial(program, [str(bit) for bit in bits]) == table[row]

    def test_wide_table_rejected(self) -> None:
        """The gate is the instruction count, not the input count."""

        random.seed(0)
        scattered = "".join(random.choice("01") for _ in range(2**11))
        with pytest.raises(ValueError, match="groups instructions onto primes"):
            boolean.polynomial(scattered)

    def test_polynomial_cap_admits_every_n10_table(self) -> None:
        """The cap is the analytic worst case over n == 10 tables."""
        from esolangs.tools.polynomial import _POLYNOMIAL_MAX_INSTRS

        states = [min(2**k, 2 ** (2 ** (10 - k))) for k in range(11)]
        # Root level 3, every other level 6 per state, two leaves at 6.
        worst = 3 + 6 * (sum(states[:10]) - 1) + 6 * states[10]
        assert worst == 1659
        # The bound stays at the 1934 the previous builder's worst case set:
        # the interpreter was measured to afford it, and a cheaper spelling
        # per state is no reason to refuse a table that fit before.
        assert (
            worst <= _POLYNOMIAL_MAX_INSTRS == 7 * sum(states[:10]) + 5 * states[10] - 1
        )

    @pytest.mark.slow  # 4.5s: one NTT factorization, then 256 cached rows
    def test_a_dense_eight_input_table_runs_every_row(self) -> None:
        """The arity the old cap refused now builds, and every row answers."""
        from tests.witness_tables import dense as _dense

        table = _dense(8)
        program = boolean.polynomial(table)
        for row in range(256):
            bits = [(row >> (7 - i)) & 1 for i in range(8)]
            got = run_polynomial(program, [str(b) for b in bits])
            assert got == table[row], f"row {row}"

    @pytest.mark.slow  # 2.3s
    def test_state_machine_renders_past_the_old_input_gate(self) -> None:
        """Tables the ``n <= 4`` gate refused outright now render and run."""
        and5 = "0" * 31 + "1"
        program = boolean.polynomial(and5)
        assert program.startswith("f(x) = ")
        for combo in range(2**5):
            bits = [(combo >> (4 - i)) & 1 for i in range(5)]
            got = run_polynomial(program, [str(b) for b in bits])
            assert got == and5[combo], f"inputs {bits}"

        for n in (6, 8):
            parity = "".join(str(bin(row).count("1") % 2) for row in range(2**n))
            assert len(_polynomial_dag(parity)) == 11 * n + 3
            assert boolean.polynomial(parity).startswith("f(x) = ")

    def test_state_machine_merges_what_the_tree_cannot(self) -> None:
        """A subtable that is not constant can still collapse to one state."""
        table = "10101010"
        assert [len(level) for level in _polynomial_states(table, 3)] == [1, 1, 1, 2]
        assert len(_polynomial_dag(table)) < len(_polynomial_tree(table))
        program = boolean.polynomial(table)
        for combo in range(8):
            bits = [(combo >> (2 - i)) & 1 for i in range(3)]
            assert run_polynomial(program, [str(b) for b in bits]) == table[combo]

    def test_polynomial_hybrid_cost_mirrors_build(self) -> None:
        """The hybrid's cost function is a deliberate mirror of its emitter."""
        from esolangs.tools.polynomial import (
            _polynomial_hybrid,
            _polynomial_hybrid_cost,
        )

        for n in range(1, 4):
            for value in range(1 << (1 << n)):
                table = format(value, f"0{1 << n}b")
                for level in range(n + 1):
                    assert _polynomial_hybrid_cost(table, level) == len(
                        _polynomial_hybrid(table, level)
                    ), f"{table} k={level}"

    def test_hybrid_endpoints_are_the_two_old_constructions(self) -> None:
        """``k == n`` is the tree and ``k == 0`` is the machine."""
        from esolangs.tools.polynomial import _polynomial_hybrid

        for n in range(1, 4):
            for value in range(1 << (1 << n)):
                table = format(value, f"0{1 << n}b")
                assert _polynomial_hybrid(table, n) == _polynomial_tree(table), table
                machine = _polynomial_hybrid(table, 0)
                if len(set(table)) == 1:
                    assert len(machine) < len(_polynomial_dag(table)), table
                else:
                    assert machine == _polynomial_dag(table), table

    @pytest.mark.slow
    def test_polynomial_screen_slack(self) -> None:
        """The screen's slack is a measurement, and it is arity-dependent."""
        from esolangs.tools.polynomial import (
            _POLYNOMIAL_SCREEN_SLACK,
            _polynomial_assemble,
            _polynomial_hybrid,
            _polynomial_hybrid_cost,
        )

        worst = 0
        for n in range(1, 4):
            for value in range(1 << (1 << n)):
                table = format(value, f"0{1 << n}b")
                built = [
                    (_polynomial_hybrid_cost(table, k), _polynomial_hybrid(table, k))
                    for k in range(n + 1)
                ]
                rendered = [
                    (len(_polynomial_assemble(instrs)), cost) for cost, instrs in built
                ]
                shortest = min(length for length, _ in rendered)
                needed = min(cost for length, cost in rendered if length == shortest)
                worst = max(worst, needed - min(cost for cost, _ in built))
        # Pure-``k`` candidates only.
        assert worst == 1
        assert worst <= _POLYNOMIAL_SCREEN_SLACK

    @pytest.mark.parametrize(
        "table",
        ["00000101", "00001010", "01010000", "01011111", "10100000", "11111010"],
    )
    def test_hybrid_shortens_and_still_computes(self, table: str) -> None:
        """A split whose halves merge separately beats both parents."""
        from esolangs.tools.polynomial import _polynomial_hybrid

        assert len(_polynomial_hybrid(table, 1)) < len(_polynomial_tree(table))
        program = boolean.polynomial(table)
        for combo in range(8):
            bits = [(combo >> (2 - i)) & 1 for i in range(3)]
            assert run_polynomial(program, [str(b) for b in bits]) == table[combo]

    def test_drained_machine_survives_a_one_in_the_drained_bit(self) -> None:
        """The reduction reaches the machine, not just the tree."""
        table = "0000010100000101"  # ignores its first input
        program = boolean.polynomial(table)
        for combo in range(16):
            bits = [(combo >> (3 - i)) & 1 for i in range(4)]
            got = run_polynomial(program, [str(b) for b in bits])
            assert got == table[combo], f"inputs {bits}"

    @pytest.mark.parametrize("table", ["00100000", "11011111", "00000010"])
    def test_machine_losing_on_characters_does_not_ship(self, table: str) -> None:
        """Fewer instructions is not fewer characters."""
        from esolangs.tools.polynomial import _polynomial_assemble, _polynomial_hybrid

        machine = _polynomial_assemble(_polynomial_hybrid(table, 0))
        tree = _polynomial_assemble(_polynomial_tree(table))
        assert len(_polynomial_hybrid(table, 0)) < len(_polynomial_tree(table))
        assert len(machine) > len(tree)
        assert boolean.polynomial(table) == tree

    def test_every_path_reads_each_input_once(self) -> None:
        """Whichever construction wins, a run consumes exactly ``n`` inputs."""
        for table, n in (("0110", 2), ("10101010", 3), ("00001111", 3)):
            program = boolean.polynomial(table)
            for combo in range(2**n):
                bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
                feed = iter([str(b) for b in bits])
                got = run_polynomial_from(program, feed)
                assert got == table[combo], f"{table} inputs {bits}"
                assert not list(feed), f"{table} inputs {bits} left input unread"


@pytest.mark.medium
@pytest.mark.parametrize(
    "table", ["01", "10", "0110", "0001", "10010110", "0110100110010110"]
)
def test_polynomial_balanced_folds_compute_the_table(table):
    from esolangs.tools.wrap import _polynomial_terms

    default = esolangs.generate("Polynomial", table)
    balanced = esolangs.generate("Polynomial", table, balance=True)
    layouts = [default] + [
        wrap_program(default, "polynomial", width)
        for width in range(1, max(map(len, _polynomial_terms(default))) + 1)
    ]
    assert balanced in layouts
    assert balance_score(balanced) == min(map(balance_score, layouts))
    assert (
        _evaluate("Polynomial", balanced, inputs=len(table).bit_length() - 1) == table
    )


def test_polynomial_never_strands_a_sign_on_its_own_line() -> None:
    """The raggedness this wrapper exists to fix: a line that is just a sign."""
    program = generate("Polynomial", "0110", width=DEFAULT_WIDTH)
    assert "\n" in program
    assert not [line for line in program.split("\n") if line.strip() in ("+", "-")]


def test_polynomial_starts_a_term_only_on_a_line_of_its_own() -> None:
    """The layout: a term starts a line, and only ever at the start of one."""
    program = generate("Polynomial", "0110", width=DEFAULT_WIDTH)
    lines = program.split("\n")
    # Line 1 is ``f(x) = <term>``: ``f(x)``, ``=`` and the unsigned term.
    assert lines[0].startswith("f(x) = ")
    assert len(lines[0].split()) == 3
    for line in lines[1:]:
        # Either a line that starts a term -- ``<sign> <term>`` -- or a row
        # carrying the previous one over, which is one unbroken run.
        assert len(line.split()) == (2 if line.startswith(("+ ", "- ")) else 1)


def test_polynomial_carries_a_term_over_without_inventing_a_sign() -> None:
    """A row continuing a term is bare: the sign belongs to the term's start."""
    # Four-input parity: XOR's coefficients no longer reach the width now
    # that the generator spells itself on the cheap opcodes.
    program = generate("Polynomial", "0110100110010110", width=DEFAULT_WIDTH)
    carried = [
        line for line in program.split("\n")[1:] if not line.startswith(("+ ", "- "))
    ]
    assert carried, "the table is too small to fold a term -- pick a wider one"
    assert all(line.strip() and " " not in line for line in carried)


def test_polynomial_keeps_the_header_with_the_first_term() -> None:
    """``f(x)`` and ``=`` are not terms and do not get lines of their own."""
    assert _polynomial("f(x) = x^2 - 3x + 7", 80).split("\n")[0] == "f(x) = x^2"


def test_polynomial_meets_the_width_it_is_given() -> None:
    """Every row fits, at every width -- the coefficients fold too."""
    program = generate("Polynomial", "0110")
    for width in (13, 40, 80, 200):
        for line in _polynomial(program, width).split("\n"):
            assert len(line) <= width


def test_polynomial_keeps_an_oversized_term_with_its_sign() -> None:
    """A term wider than the width keeps its sign rather than shedding it."""
    wrapped = _polynomial("f(x) = x^2 - 123456789x + 7", 12)
    assert "- 123456789x" in wrapped.split("\n")


def test_polynomial_leaves_a_trailing_sign_alone() -> None:
    """A sign with no term after it is kept rather than dropped."""
    assert _polynomial("f(x) = x +", 80) == "f(x) = x\n+"


def test_polynomial_keeps_a_sign_with_no_term_to_attach_to() -> None:
    """Two signs in a row: the first has no term, and is kept as a line."""
    assert _polynomial("f(x) = x + - 7", 80) == "f(x) = x\n+\n- 7"


def test_polynomial_leaves_a_program_too_short_to_have_a_header() -> None:
    """The ``f(x) =`` header is three terms; a shorter program has none."""
    assert _polynomial("1", 10) == "1"
