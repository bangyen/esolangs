"""Run resource witnesses and measure native commands and written state."""

import esolangs
from esolangs.vm import VM, _capture_workspace, _DelegatingVM, complete_vm, make_vm
from scripts.benchmark import WrittenState
from scripts.docs.resource_evidence import resource_corpus, resource_witnesses
from tests.proofs._witnesses import (
    _seeded,
)
from tests.proofs.deep.execution import run_to_answer
from tests.support.witness_tables import parity as _parity
from tests.support.witness_tables import row_bits


def tables(name: str, n: int) -> tuple[str, ...]:
    """Combine the common corpus with the language's named resource witnesses."""
    corpus = resource_corpus(name, n)
    if corpus is not None:
        return corpus
    width = 1 << n
    tables = (
        _parity(n),
        _seeded(n, 1),
        "0" * width,
        "1" * width,
        "0" * (width - 1) + "1",
        "10" * (width // 2),
        "1" * (width - 1) + "0",
        "1" + "0" * (width - 2) + "1",
        "01" * (width // 2),
    )
    return tuple(dict.fromkeys((*tables, *resource_witnesses(name, n))))


def _measured_steps(
    machine: VM, state: WrittenState | None, *, check_answer: bool
) -> int:
    if check_answer and not machine.steppable_to_answer:
        # The periodic driver renders the answer from this same execution.
        assert isinstance(machine, _DelegatingVM)

        def step() -> None:
            machine.step()
            if state is not None:
                state.sample(_capture_workspace(machine))

        report = machine._complete_repeating(step)
        assert report is not None
        assert report.cycle is not None
        return report.cycle.repeat_pass * report.cycle.commands_per_pass
    steps = run_to_answer(machine, sample=state.sample if state is not None else None)
    assert steps is not None  # no cap
    return steps


def _check_answer(name: str, table: str, row: int, output: str) -> None:
    subject = f"{name} [{table}] row {row}"
    try:
        actual = esolangs.read_answer(name, output)
    except esolangs.ProgramError as error:
        raise esolangs.ProgramError(f"{subject}: {error}") from error
    if actual != table[row]:
        raise esolangs.ProgramError(f"{subject}: expected {table[row]}, got {actual}")


def measure(
    name: str,
    table: str,
    *,
    written: bool = False,
    program: esolangs.ProgramSource | None = None,
    check_answers: bool = False,
) -> tuple[int, int]:
    """Measure command and workspace maxima, optionally checking answers."""
    facts = esolangs.describe(name)
    halts = None
    if facts.answer_mode == "termination":
        halts = str(list(facts.answer_encoding).index("halts"))
    n = len(table).bit_length() - 1
    if program is None:
        program = esolangs.generate(name, table)
    worst_steps = worst_bits = 0
    for row in range(len(table)):
        if halts is not None and table[row] != halts:
            continue
        bits = row_bits(row, n)
        if facts.parameterized:
            source, stdin = esolangs.instantiate(name, program, bits), ""
        else:
            source, stdin = (
                program,
                esolangs.encode_inputs(name, bits, truth_table=table),
            )
        machine = make_vm(name, source, stdin=stdin)
        state = WrittenState(_capture_workspace(machine)) if written else None
        steps = _measured_steps(machine, state, check_answer=check_answers)
        worst_steps = max(worst_steps, steps)
        if (state is not None or check_answers) and machine.dumps_on_the_post_halt_step:
            complete_vm(machine, max_steps=0)
            if state is not None:
                state.sample(_capture_workspace(machine))
        if check_answers and halts is None:
            _check_answer(name, table, row, machine.output)
        if state is not None:
            worst_bits = max(worst_bits, state.bits)
    return worst_steps, worst_bits
