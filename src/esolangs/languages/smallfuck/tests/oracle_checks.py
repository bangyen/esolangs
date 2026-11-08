"""Source-sized tape with an independent bracket-stack parser."""

from tests.interpreters.oracle_support import observed
from tests.interpreters.semantic_oracles import Observation, bracket_pairs
from tests.support.workspace_oracle import workspace_model, workspace_view

_WORKSPACE = workspace_model("smallfuck-v2", "instruction pointer tape dumped")


def _model(code, _stdin, cap=200):
    pairs = bracket_pairs(code)
    tape, pc, pointer, dumped, output = [0] * len(code), 0, 0, False, ""

    def view():
        return ((pc, pointer, tuple(tape), dumped), pc == len(code), output, 0, 0)

    trace = [view()]
    for _ in range(cap):
        if pc == len(code):
            break
        command = code[pc]
        if command == "*":
            tape[pointer] ^= 1
        elif command == "<" and pointer == 0:
            pc = len(code)
        elif command in "<>":
            pointer += 1 if command == ">" else -1
            if pointer == len(code):
                pc = len(code)
        elif command in "[]" and tape[pointer] == (command == "]"):
            pc = pairs[pc]
        if pc < len(code):
            pc += 1
        trace.append(view())
    if pc == len(code):
        dumped, output = True, str(tape[2] if len(tape) > 2 else 0)
        trace.extend([view()] * 3)
    return trace


def oracle(code, stdin, cap):
    """Retain the legacy terminal observation while the model exposes boundaries."""
    state, halted, output, consumed, _ = _model(code, stdin, cap)[-1]
    return Observation(output, state[2], state[0], consumed, halted)


def check(factory, code, stdin):
    try:
        trace = _model(code, stdin)
    except ValueError:
        trace = [(None, False, "", 0, 0)]
    checked = workspace_view(trace, _WORKSPACE, lambda row: row[0], lambda m: m.state)
    error = "syntax" if trace[0][0] is None else None
    assert observed(factory, code, stdin, checked, cap=200) == (error, trace)
    return trace
