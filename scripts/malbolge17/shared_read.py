"""Execute one read stream through selected cells and a common return."""

import argparse
import itertools

from address17 import ALL2, group_word
from address_gadget import build, execute_state
from parity_views import STORED_PARITY

from esolangs.interpreters.other.malbolge import (
    _advance,
    _crazy,
    _initial_memory,
)
from esolangs.tools.malbolge import _valid_chars
from esolangs.tools.malbolge.core import _WORDS, _char_for

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


def main(*, full: bool = False) -> None:
    """Check selected reads on a standalone source and the address source."""
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
    _address_handoff(full=full)


def _address_handoff(*, full: bool = False) -> None:
    """Read guarded result cells in real post-address memory with one stream."""
    outputs: dict[str, int] = {}
    address, groups, _, _ = build(
        None,
        dispatch_ab=True,
        parity=True,
        high_pointer=True,
        high_parity=True,
        guard_scratch=True,
        prepare_returns=True,
        result_first=True,
        slot_pointers=True,
        outputs=outputs,
    )
    source = list(address)
    for offset, op in enumerate("jpjjp<v"):
        source[_ENTRY + offset] = chr(_char_for(op, _ENTRY + offset))
    program = "".join(source)
    result_cells = [cell for group in groups[:5] for cell in group[1:]]
    slot_pointer = {
        groups[slot][1]: outputs[f"slot_pointer_{slot}"] for slot in range(3)
    }
    samples = (
        (0,) * 14,
        (1,) * 14,
        tuple(index % 2 for index in range(14)),
        tuple((index + 1) % 2 for index in range(14)),
        (0, 0) + (1,) * 12,
        (0, 1) + (1,) * 12,
        (1, 0) + (0,) * 12,
        (1, 1) + (0,) * 12,
    )
    cases = itertools.product(range(2), repeat=14) if full else samples
    checked = 0
    source_pointers = 0
    for bits in cases:
        _, folded = execute_state(program, bits)
        pointer = _crazy(ALL2 - 2, group_word(list(bits)))
        assert folded[outputs["pointer"]] == pointer
        assert tuple(folded[cell] for cell in groups[-1]) == tuple(
            STORED_PARITY[(pointer + 1 + offset) % 2] for offset in range(3)
        )
        assert folded[1] == 85
        assert all(folded[cell + 1] == 0 for cell in result_cells)
        selected = (
            (result_cells[sum(bits) % len(result_cells)],) if full else result_cells
        )
        if bits[:2] == (0, 0):
            selector = 2 * bits[11] + bits[12]
            slot = selector if selector < 3 else bits[13]
            special_cell = groups[slot][1 + bits[13]]
            assert special_cell <= 127
            selected = (*selected, special_cell)
        for cell in selected:
            memory = folded.copy()
            value = memory[cell]
            operand = memory[86]
            if cell <= 127:
                pointer_cell = slot_pointer.get(cell, 200 + ((69 - cell - 200) % 94))
                assert ord(program[pointer_cell]) == cell - 1
                assert memory[pointer_cell] == cell - 1
                source_pointers += 1
            else:
                pointer_cell = 419
                memory[pointer_cell] = cell - 1
            state = (0, _ENTRY, pointer_cell, False)
            result: list[int] = []
            for step in range(7):
                state, writes, effect = _advance(state, memory)
                for write_address, new_value in writes:
                    memory[write_address] = new_value
                if step == 3:
                    assert state[1:3] == (_ENTRY + 4, 86)
                if effect is not None:
                    result.append(effect)
            assert state[3]
            assert result == [_crazy(_crazy(0, value), operand) & 0xFF]
            checked += 1
    expected = 20_480 if full else 82
    assert checked == expected
    print(
        f"guarded address handoff: {checked} / {expected} executed reads, "
        f"{source_pointers} source-resident pointers"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--full", action="store_true", help="check all address paths")
    main(full=parser.parse_args().full)
