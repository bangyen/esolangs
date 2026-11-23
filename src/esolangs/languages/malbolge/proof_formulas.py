"""Execution and memory bounds for the main line and answer stub."""

from functools import cache

from esolangs.languages.malbolge.generator.core import _ENTRY, _hub_layout, _stub_builds
from esolangs.languages.malbolge.generator.digits import (
    _D_FLOOR,
    _SHORT_MAX,
    _full_layout,
    _hubs,
    _longest_stub,
)
from esolangs.languages.malbolge.interpreter import _advance, _initial_memory, _op


@cache
def _full_stub() -> int:
    longest = 0
    for weight_fold in (False, True):
        layout = _full_layout(weight_fold=weight_fold)
        hubs = _hubs(layout)
        _, stubs = _hub_layout(
            hubs, set(), _D_FLOOR, _stub_builds(hubs, layout.stubs), packed=True
        )
        start = 0
        for address, op in sorted(stubs.items()):
            if address - 1 not in stubs:
                start = address
            if op == "v":
                longest = max(longest, address + 1 - start)
    return longest


@cache
def _main(program: str) -> tuple[int, int, int]:
    """Count prefix steps and data writes through halt or stub dispatch."""
    memory = list(_initial_memory(program))
    state = 0, 0, 0, False
    total = writes = 0
    while total < len(program):
        _, c, d, _ = state
        op = _op(memory[c], c)
        total += 1
        if op == "v":
            return total, writes, 0
        if op == "i" and d >= _ENTRY:
            return total, writes, 1
        writes += int(op in ("p", "*"))
        state, changed, _ = _advance(state, memory, 48 if op == "/" else None)
        for address, value in changed:
            memory[address] = value
    raise AssertionError("generated main line did not halt or dispatch")


def execution_terms(n: int, program: str) -> dict[str, int]:
    """Measure the executed main prefix and bound the answer stub."""
    prefix, _, stub = _main(program)
    longest = _longest_stub(n) if n <= _SHORT_MAX else _full_stub()
    return {"E": prefix, "J": longest if stub else 0}


def workspace_terms(n: int, program: str) -> dict[str, int]:
    """Measure loaded memory and the main prefix's writes."""
    _, writes, stub = _main(program)
    return {
        "B": sum(word.bit_length() for word in _initial_memory(program)),
        **execution_terms(n, program),
        "W": writes,
        "F": stub,
    }
