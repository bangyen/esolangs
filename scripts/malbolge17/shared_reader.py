"""Execute a parity-selected table read from the shared seventeen-input entry."""

import itertools

from decoder_group import _VIEW, _setup
from helper_consumer import helper_values
from row_routes import build_row_routes, row_words
from setup_consumer import check_setup_memory, control_inputs

from esolangs.interpreters.other.malbolge import _advance, _crazy, _initial_memory, _op
from esolangs.tools._malbolge_core import _char_for, _rot


def build_shared_reader() -> tuple[
    str, tuple[tuple[int, int, int], ...], dict[str, int]
]:
    """Return a live first-field read; its diagnostic halt has no return edge."""
    source, groups, outputs, entries = build_row_routes(shared=True)
    plan = entries[0]
    group = _setup(
        frozenset({142, 145, 139, 144}), external_pointer=True, runtime_base=True
    )
    view_cell = group.view_cells[0]
    plan.op("*", 145)
    plan.op("p", view_cell)
    plan.goto(142)
    plan.raw("j")
    # Only C is needed after the runtime jump; D is the live base, not group.base.
    plan.raw("p")
    plan.raw("<")
    halt = plan.c
    plan.raw("v")
    assert max(plan.code) < outputs["shared_entry"] + 800
    assert not plan.data
    rendered = list(source)
    for address, operation in plan.code.items():
        rendered[address] = chr(_char_for(operation, address))
    outputs.update(
        read_halt=halt,
        read_view_cell=view_cell,
        read_code_cells=outputs["dispatch_code_cells"] - 2 + len(plan.code),
    )
    return "".join(rendered), groups, outputs


def main() -> None:
    """Trace the actual read operand before mutation, without host injection."""
    source, groups, outputs = build_shared_reader()
    group = _setup(
        frozenset({142, 145, 139, 144}), external_pointer=True, runtime_base=True
    )
    total = 0
    for prefix in control_inputs():
        for row, tail in enumerate(itertools.product((0, 1), repeat=3)):
            memory = list(_initial_memory(source))
            state = (0, 0, 0, False)
            inputs = iter(48 + bit for bit in prefix + tail)
            printed = []
            expected = None
            for _ in range(100_000):
                if state[1] == outputs["shared_entry"]:
                    check_setup_memory(memory, groups, outputs, group, prefix)
                    base = memory[142] + 1
                    expected = _crazy(_VIEW[base % 2], memory[base])
                    parity = _rot(memory[145])
                char = next(inputs) if _op(memory[state[1]], state[1]) == "/" else None
                state, writes, effect = _advance(state, memory, char)
                for address, value in writes:
                    memory[address] = value
                if effect is not None:
                    printed.append(effect)
                if state[3]:
                    break
            assert expected is not None
            assert state[1] == outputs["read_halt"]
            assert state[2] == base + 2
            assert printed == [expected & 255]
            assert memory[base] == expected
            assert memory[20] == row_words()[row]
            assert memory[145] == parity
            helpers = helper_values(group)
            helpers[outputs["read_view_cell"]] = _VIEW[base % 2]
            assert all(memory[cell] == value for cell, value in helpers.items())
            total += 1
    print(
        f"shared live read: {total} executed controls; "
        f"{outputs['read_code_cells']} code cells"
    )


if __name__ == "__main__":
    main()
