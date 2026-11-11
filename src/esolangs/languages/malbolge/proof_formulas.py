"""Source and memory facts for the straight-line main and stub."""

from esolangs.languages.malbolge.generator.digits import _SHORT_MAX, _longest_stub
from esolangs.languages.malbolge.interpreter import _initial_memory, _op


def _stub(n: int) -> int:
    """Count the longest short stub, or the full layout's 199 commands."""
    return _longest_stub(n) if n <= _SHORT_MAX else 199


def _main(program: str) -> tuple[int, int]:
    """Find the main prefix and its closing instruction, if present."""
    for address, char in enumerate(program):
        if _op(ord(char), address) == "i":
            return address + 1, 1
    return len(program), 0


def execution_terms(n: int, program: str) -> dict[str, int]:
    """Measure the straight-line main before the stub."""
    prefix, closed = _main(program)
    return {"E": prefix, "J": _stub(n) if closed else 0}


def workspace_terms(n: int, program: str) -> dict[str, int]:
    """Measure loaded memory and the main prefix's writes."""
    prefix, closed = _main(program)
    writes = sum(
        _op(ord(char), address) in ("*", "p")
        for address, char in enumerate(program[:prefix])
    )
    return {
        "B": sum(word.bit_length() for word in _initial_memory(program)),
        "E": prefix,
        "W": writes,
        "J": _stub(n) if closed else 0,
        "F": int(prefix < len(program)),
    }
