"""Tests for the Vandevelo boolean generator."""

from itertools import product

from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.other.vandevelo import _Machine
from esolangs.tools.vandevelo import vandevelo
from esolangs.vm import run_until_halt_or_cycle


def _result(program: str, bits: tuple[int, ...]) -> str:
    io = ScriptedIO("".join(f"{bit}\n" for bit in bits))
    return "0" if run_until_halt_or_cycle(_Machine(program, io)) else "1"


def test_xor_executes_every_generated_row() -> None:
    program = vandevelo("0110")
    results = (_result(program, bits) for bits in product(range(2), repeat=2))
    assert "".join(results) == "0110"


def test_constant_still_reads_every_input() -> None:
    program = vandevelo("00000000")
    io = ScriptedIO("0\n1\n0\n")
    assert run_until_halt_or_cycle(_Machine(program, io))
    assert io.position() == 3


def test_one_rows_are_named_cubes() -> None:
    program = vandevelo("0001")
    assert program.splitlines()[-1] == "b? :: a? :: loop?"


def test_constant_one_needs_no_guards() -> None:
    program = vandevelo("11111111")
    assert program.splitlines()[-1] == "loop?"


def test_constant_subtree_is_one_coset() -> None:
    program = vandevelo("00001111")
    assert program.splitlines()[-1] == "a? :: loop?"


def test_parity_is_a_single_hyperplane() -> None:
    """The parity table's 1-set is one affine coset: one register, one guard."""
    parity = "".join("1" if bin(i).count("1") % 2 else "0" for i in range(2**8))
    lines = vandevelo(parity).splitlines()
    assert lines[-1] == "i? :: loop?"
    # 8 reads, the loop line, 8 register lines building the parity, 1 guard.
    assert len(lines) == 18


def test_the_exact_autocorrelation_improves_on_the_capped_scan() -> None:
    """The fallback that makes the clause bound a bound, not a heuristic.

    :data:`~esolangs.tools.vandevelo._CANDIDATE_CAP` scans only 48
    directions, so it can miss the pigeonhole-average one that
    Cohen--Shinkar's telescoping argument needs; while the remainder is
    dense the generator falls back to an exact Walsh--Hadamard
    autocorrelation.  That fallback runs on most tables but only
    *improves* on a minority -- 17 of 400 random tables at n=4..7 -- so
    this table is a found witness rather than a constructed one, and it
    is pinned because deleting the fallback would leave the docstring's
    bound unproven while every small table still passed.
    """
    table = "00111101101000111111101000100101"
    program = vandevelo(table)
    results = (_result(program, bits) for bits in product(range(2), repeat=5))
    assert "".join(results) == table


def test_registers_are_reused_and_morphed_on_a_wide_table() -> None:
    """Wide tables drive register reuse, morphing, and back-substitution.

    Below n=6 every constraint is one input wide or its cube is small
    enough that the bank never has a second live parity to reuse, so the
    three paths that make upkeep sublinear -- exact reuse, one-toggle
    morphing, and the reduced-elimination back-substitution behind the
    ``dim + 1`` width bound -- are unreachable.  This is the smallest
    shape that exercises all three.
    """
    table = "0011110011110111100001000000010001110110010000001111000111000111"
    program = vandevelo(table)
    lines = program.splitlines()
    morphs = [line for line in lines if "~>" in line and "!=" in line]
    assert morphs, "no register was built or morphed"
    results = (_result(program, bits) for bits in product(range(2), repeat=6))
    assert "".join(results) == table


def _spread_cube(n: int, dim: int) -> list[int]:
    """Directions whose columns run through every nonzero value of F2^dim.

    The worst shape for the echelon basis: each free coordinate's dual
    picks up about half the pivots, so the basis weighs ``n * dim / 2``.
    """
    return [
        sum(((j % (2**dim - 1) + 1) >> i & 1) << j for j in range(n))
        for i in range(dim)
    ]


def _check_basis(dirs: list[int], n: int) -> list[int]:
    from esolangs.tools.vandevelo import _constraints

    duals = [w for w, _ in _constraints(0, dirs, n)]
    assert len(duals) == n - len(dirs)
    assert all((w & v).bit_count() % 2 == 0 for w in duals for v in dirs)
    # independent: eliminate on leading bits
    rows: dict[int, int] = {}
    for w in duals:
        while w and (w.bit_length() - 1) in rows:
            w ^= rows[w.bit_length() - 1]
        assert w
        rows[w.bit_length() - 1] = w
    return duals


def test_constraints_weigh_four_per_input_plus_a_core() -> None:
    """The O(T) upkeep bound rests on the per-clause constraint weight.

    On a spread cube the echelon basis weighs ``n * dim / 2``; the short
    relation basis stays under ``4 * n + (dim + 1) * (1 + 2**((dim+1)/2))``
    with at most ``core - dim`` constraints wider than four inputs.
    """
    from esolangs.tools.vandevelo import _echelon

    n, dim = 16, 4
    dirs = _spread_cube(n, dim)
    duals = _check_basis(dirs, n)
    echelon = sum(w.bit_count() for w in _echelon(dirs, n))
    assert echelon >= n * dim // 2
    core = 1 + 2 ** ((dim + 1) / 2)
    assert sum(w.bit_count() for w in duals) < echelon
    assert sum(w.bit_count() for w in duals) <= 4 * n + (dim + 1) * core
    assert sum(w.bit_count() > 4 for w in duals) <= core - dim


def test_constraint_bound_holds_on_random_cubes() -> None:
    import random

    rng = random.Random(3)
    for n in range(2, 14):
        for dim in range(1, n):
            for _ in range(4):
                dirs: list[int] = []
                span = {0}
                while len(dirs) < dim:
                    v = rng.randrange(1, 1 << n)
                    if v not in span:
                        dirs.append(v)
                        span |= {s ^ v for s in span}
                duals = _check_basis(dirs, n)
                core = 1 + 2 ** ((dim + 1) / 2)
                assert sum(w.bit_count() for w in duals) <= 4 * n + (dim + 1) * core
                assert sum(w.bit_count() > 4 for w in duals) <= core - dim


def test_a_full_bank_respells_its_least_recently_used_register(monkeypatch) -> None:
    """The cap that keeps register names as short as input names.

    ``n**2`` never binds at sizes this suite builds, so the cap is forced
    down to ``n`` here: the bank must stay at ``n`` names, every clause
    must still find a free register, and the program must still compute
    the table.
    """
    import importlib

    module = importlib.import_module("esolangs.tools.vandevelo")
    monkeypatch.setattr(module, "_bank_cap", lambda n: n)
    table = "0011110011110111100001000000010001110110010000001111000111000111"
    program = vandevelo(table)
    lines = program.splitlines()
    registers = {
        line.split(" ~> ")[0] for line in lines if "~>" in line and "Inp" not in line
    }
    assert len(registers) == 6
    assert (
        sum("~>" in line and "!=" not in line and "Inp" not in line for line in lines)
        > 6
    )
    results = (_result(program, bits) for bits in product(range(2), repeat=6))
    assert "".join(results) == table


def test_short_names_are_unique_and_skip_builtins() -> None:
    """The compact namespace does not shadow input, nil, or the loop."""
    from esolangs.tools.vandevelo import _RESERVED, _name

    names = [_name(index) for index in range(500)]
    assert len(set(names)) == len(names)
    assert not set(names) & _RESERVED
