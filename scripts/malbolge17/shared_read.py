"""Execute one read stream through three selected cells and a common return."""

from esolangs.interpreters.other.malbolge import (
    _advance,
    _crazy,
    _initial_memory,
)
from esolangs.tools._malbolge_core import _WORDS, _char_for
from esolangs.tools.malbolge import _valid_chars

_ENTRY = 420
_POINTERS = (60, 61, 62)
_CELLS = (5000, 5100, 5200)
_RETURN = 128


def _source() -> str:
    """Return the shared six-instruction read and print stream."""
    source = [_char_for("o", a) for a in range(_WORDS)]
    for offset, op in enumerate("jpjp<v"):
        source[_ENTRY + offset] = _char_for(op, _ENTRY + offset)
    return "".join(chr(char) for char in source)


def _run(source: str, pointer: int, char: int) -> tuple[int, tuple[int, int]]:
    """Return the output and post-read state with selected data supplied at entry."""
    memory = list(_initial_memory(source))
    cell = _CELLS[_POINTERS.index(pointer)]
    memory[pointer] = cell - 1
    memory[cell] = char
    memory[cell + 1] = _RETURN - 1
    state = (0, _ENTRY, pointer, False)
    output: list[int] = []
    after_read = (-1, -1)
    for step in range(6):
        state, writes, effect = _advance(state, memory)
        for address, value in writes:
            memory[address] = value
        if step == 2:
            after_read = state[1:3]
        if effect is not None:
            output.append(effect)
    assert state[3]
    assert len(output) == 1
    return output[0], after_read


def main() -> None:
    """Check all admissible characters at all three selected cells."""
    source = _source()
    operand = _initial_memory(source)[_RETURN]
    cases = 0
    outputs: set[int] = set()
    for pointer, cell in zip(_POINTERS, _CELLS, strict=True):
        for char in _valid_chars(cell):
            got, after_read = _run(source, pointer, char)
            assert after_read == (_ENTRY + 3, _RETURN)
            assert got == _crazy(_crazy(0, char), operand) & 0xFF
            outputs.add(got)
            cases += 1
    assert len(outputs) > 1
    print(f"shared read: {cases} / {cases} source cases, one code stream")


if __name__ == "__main__":
    main()
