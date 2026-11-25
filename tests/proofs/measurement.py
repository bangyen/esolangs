"""Run resource witnesses and measure native commands and written state."""

import esolangs
from esolangs.vm import _capture_workspace, complete_vm, make_vm
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


def measure(
    name: str,
    table: str,
    *,
    written: bool = False,
    program: esolangs.ProgramSource | None = None,
) -> tuple[int, int]:
    """Most commands and optional written-state bits over halting rows."""
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
        steps = run_to_answer(
            machine, sample=state.sample if state is not None else None
        )
        assert steps is not None  # no cap
        worst_steps = max(worst_steps, steps)
        if state is not None:
            if machine.dumps_on_the_post_halt_step:
                complete_vm(machine, max_steps=0)
                state.sample(_capture_workspace(machine))
            worst_bits = max(worst_bits, state.bits)
    return worst_steps, worst_bits
