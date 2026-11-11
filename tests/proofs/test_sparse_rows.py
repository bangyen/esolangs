"""Named-row evidence for exact cells the all-row suites cannot reach.

The execution and workspace suites step every row of every corpus table,
paying one parse a row; where that price explodes (What!? at n = 16
would spend ~14 hours parsing alone) their registrations stop, while
the clauses run to every n.  These suites step a fixed set of named rows
of each witness table instead, one fresh VM a row: every stepped row
must answer its table bit and stay under the bound, the witness row
must attain the formula exactly, and the workspace suite samples the
witness row alone.  Registrations live in each language's resource evidence.
A builder returns
one witness or a tuple of them, and a registration whose columns are
empty checks answers only, for a route with no bound yet.
"""

import pytest

import esolangs
from esolangs.debugger import make_vm
from esolangs.registry import LANGUAGES
from esolangs.vm import _capture_workspace
from scripts.benchmark import WrittenState
from tests.proofs._witnesses import SparseRows, band_marks, sparse_registrations
from tests.proofs.deep.execution import run_to_answer
from tests.proofs.execution import FORMULAS as EXECUTION_FORMULAS
from tests.proofs.workspace import FORMULAS as WORKSPACE_FORMULAS
from tests.support.witness_tables import row_bits

_REGISTRATIONS = sparse_registrations()


def _cases(column: str) -> list[object]:
    return [
        pytest.param(
            name,
            n,
            marks=band_marks(
                registration.bands[n], f"{name} {column} exact at n = {n}"
            ),
        )
        for name, registration in sorted(_REGISTRATIONS.items())
        if column == "execution" or column in registration.columns
        for n in registration.arities
    ]


def _step_row(
    name: str, program: esolangs.Artifact, table: str, row: int, *, written: bool
) -> tuple[int, int]:
    """Steps and written bits for one named row, on a freshly parsed VM."""
    facts = esolangs.describe(name)
    halts = None
    if facts["answer_mode"] == "termination":
        halts = str(list(facts["answer_encoding"]).index("halts"))
        assert table[row] == halts, f"{name} row {row}: a diverging row has no answer"
    n = len(table).bit_length() - 1
    bits = row_bits(row, n)
    if facts["parameterized"]:
        source, stdin = esolangs.instantiate(name, program, bits), ""
    else:
        source, stdin = program, esolangs.encode_inputs(name, bits, truth_table=table)
    machine = make_vm(name, source, stdin=stdin)
    state = WrittenState(_capture_workspace(machine)) if written else None
    steps = run_to_answer(machine, sample=state.sample if state is not None else None)
    assert steps is not None  # no cap
    if halts is None:
        answer = esolangs.read_answer(name, machine.output)
        assert answer == table[row], (
            f"{name} n={n} row {row}: answer {answer} != {table[row]}"
        )
    return steps, state.bits if state is not None else 0


def _specs(name: str, n: int) -> tuple[SparseRows, ...]:
    """Return the registration's witnesses at ``n`` (one or several)."""
    built = _REGISTRATIONS[name].build(n)
    return (built,) if isinstance(built, SparseRows) else built


@pytest.mark.parametrize(("name", "n"), _cases("execution"))
def test_sparse_execution_rows(name: str, n: int) -> None:
    """Named rows answer correctly; the witness row attains E exactly."""
    checked = "execution" in _REGISTRATIONS[name].columns
    for spec in _specs(name, n):
        program = esolangs.generate(name, spec.table)
        claim = EXECUTION_FORMULAS[name][0](n, program.source) if checked else None
        for row in spec.rows:
            steps, _ = _step_row(name, program, spec.table, row, written=False)
            if claim is not None:
                assert steps <= claim, f"{name} n={n} row {row}: {steps} > {claim}"
                if row == spec.witness:
                    assert steps == claim, f"{name} n={n} row {row}: {steps} != {claim}"


@pytest.mark.parametrize(("name", "n"), _cases("workspace"))
def test_sparse_workspace_rows(name: str, n: int) -> None:
    """The sampled witness row attains W exactly."""
    for spec in _specs(name, n):
        program = esolangs.generate(name, spec.table)
        claim = WORKSPACE_FORMULAS[name][0](n, program.source)
        row = spec.witness if spec.ws_witness is None else spec.ws_witness
        _, bits = _step_row(name, program, spec.table, row, written=True)
        assert bits == claim, f"{name} n={n}: {bits} != {claim}"


@pytest.mark.slow
def test_sparse_registrations_are_real() -> None:
    """Every registration names a generator, its arities and its witness."""
    for name, (build, arities, columns, _bands) in _REGISTRATIONS.items():
        assert name in LANGUAGES, f"{name} is not a registered generator"
        assert columns <= {"execution", "workspace"}
        if "execution" in columns:
            assert name in EXECUTION_FORMULAS
        if "workspace" in columns:
            assert name in WORKSPACE_FORMULAS
        for n in arities:
            built = build(n)
            for spec in (built,) if isinstance(built, SparseRows) else built:
                assert len(spec.table) == 1 << n
                assert spec.witness in spec.rows
                assert all(0 <= row < len(spec.table) for row in spec.rows)
