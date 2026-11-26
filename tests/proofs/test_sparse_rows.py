"""Execute named rows of tables too large for the all-row suites."""

import pytest

import esolangs
from esolangs.debugger import make_vm
from esolangs.registry import LANGUAGES
from tests.proofs._witnesses import SparseRows, band_marks, sparse_registrations
from tests.proofs.deep.execution import run_to_answer
from tests.support.witness_tables import row_bits

_REGISTRATIONS = sparse_registrations()


def _cases() -> list[object]:
    return [
        pytest.param(
            name,
            n,
            marks=band_marks(registration.bands[n], f"{name} named rows at n = {n}"),
        )
        for name, registration in sorted(_REGISTRATIONS.items())
        for n in registration.arities
    ]


def _check_row(name: str, program: esolangs.Artifact, table: str, row: int) -> None:
    """Check one named row on a fresh VM."""
    facts = esolangs.describe(name)
    halts = None
    if facts.answer_mode == "termination":
        halts = str(list(facts.answer_encoding).index("halts"))
        assert table[row] == halts, f"{name} row {row}: a diverging row has no answer"
    n = len(table).bit_length() - 1
    bits = row_bits(row, n)
    if facts.parameterized:
        source, stdin = esolangs.Language(name).instantiate(program, bits), ""
    else:
        source, stdin = program, esolangs.encode_inputs(name, bits, truth_table=table)
    machine = make_vm(name, source, stdin=stdin)
    assert run_to_answer(machine) is not None  # no cap
    if halts is None:
        answer = esolangs.read_answer(name, machine.output)
        assert answer == table[row], (
            f"{name} n={n} row {row}: answer {answer} != {table[row]}"
        )


def _specs(name: str, n: int) -> tuple[SparseRows, ...]:
    """Return the registration's witnesses at ``n`` (one or several)."""
    built = _REGISTRATIONS[name].build(n)
    return (built,) if isinstance(built, SparseRows) else built


@pytest.mark.parametrize(("name", "n"), _cases())
def test_sparse_execution_rows(name: str, n: int) -> None:
    """Every named row answers correctly."""
    for spec in _specs(name, n):
        program = esolangs.generate(name, spec.table)
        for row in spec.rows:
            _check_row(name, program, spec.table, row)


@pytest.mark.slow
def test_sparse_registrations_are_real() -> None:
    """Every registration names a generator, its arities and its witness."""
    for name, registration in _REGISTRATIONS.items():
        assert name in LANGUAGES, f"{name} is not a registered generator"
        for n in registration.arities:
            for spec in _specs(name, n):
                assert len(spec.table) == 1 << n
                assert spec.witness in spec.rows
                assert all(0 <= row < len(spec.table) for row in spec.rows)
