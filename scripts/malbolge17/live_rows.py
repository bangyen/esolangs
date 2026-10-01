"""Execute the final three-input row fold after the live decoder setup."""

import itertools

from address_gadget import execute_state
from combined_helpers import _Chunk, _copy, build_combined_helpers, place_chunks
from decoder_group import _setup
from dispatch3 import _readouts
from helper_consumer import helper_values
from planner import _Planner
from setup_consumer import check_setup_memory, control_inputs

from esolangs.tools._malbolge_core import _char_for
from esolangs.tools._malbolge_digits import _D_INITS, _GADGET


def build_live_rows(
    *, reserved: set[int] | None = None, next_chunk: _Chunk | None = None
) -> tuple[str, tuple[tuple[int, int, int], ...], dict[str, int], _Planner]:
    """Return a source reading all 17 inputs and retaining the row selector."""
    blocked: set[int] = set()
    source, groups, outputs, plan = build_combined_helpers(reserved=blocked)
    replaced_halt = plan.c
    blocked.remove(replaced_halt)
    group = _setup(
        frozenset({142, 145, 139, 144}), external_pointer=True, runtime_base=True
    )
    protected = set(helper_values(group)) | {42, 147, 219, 142, 145, 139, 144, 19, 20}
    cells = []
    for initial in _D_INITS[0]:
        cell = next(
            a
            for a, value in plan.mem.items()
            if 130 <= a < 420 and a not in protected and value == initial
        )
        cells.append(cell)
        protected.add(cell)
    constants = {"K0": (219, 0), "K1": (42, 29524), "K2": (147, 59048)}
    chunks: list[list[tuple[str, int, int | None]]] = [
        [("*", 42, 29524), ("p", cell, None), ("p", cell, 29524)] for cell in (19, 20)
    ]
    for operation in _GADGET:
        if operation == "/":
            chunks.append([("/", 19, 29524)])
        elif operation.startswith("K"):
            cell, value = constants[operation]
            chunks.append([("*", cell, value)])
        else:
            chunks[-1].append(("p", cells[int(operation)], None))
    chunks[-1].extend(
        (
            ("p", 19, None),
            ("*", 19, None),
            ("p", cells[1], None),
            ("*", cells[1], None),
            ("p", 20, None),
        )
    )
    plan, emitted, routes = place_chunks(
        plan, chunks, blocked, protected, continuation=next_chunk
    )
    exit_plan = _copy(plan)
    halt = plan.c
    plan.raw("v")
    assert halt not in blocked
    emitted[halt] = "v"
    if reserved is not None:
        reserved.update(blocked)
        reserved.add(halt)
    assert plan.data == exit_plan.data
    rendered = list(source)
    for address, operation in emitted.items():
        rendered[address] = chr(_char_for(operation, address))
    outputs.update(
        row_halt=halt,
        row_word=20,
        row_routes=routes,
        row_code_cells=outputs["helper_code_cells"] - 1 + len(emitted),
    )
    return "".join(rendered), groups, outputs, exit_plan


def main() -> None:
    """Run eight row selections across all 32 address-family controls."""
    source, groups, outputs, _ = build_live_rows()
    group = _setup(
        frozenset({142, 145, 139, 144}), external_pointer=True, runtime_base=True
    )
    expected = _readouts()
    assert len(set(expected)) == 8
    total = 0
    for prefix in control_inputs():
        for row, tail in enumerate(itertools.product((0, 1), repeat=3)):
            printed: list[int] = []
            state, memory = execute_state(source, prefix + tail, printed)
            assert state[1] == outputs["row_halt"]
            assert not printed
            assert memory[outputs["row_word"]] == expected[row], (prefix, row)
            assert all(
                memory[cell] == wanted for cell, wanted in helper_values(group).items()
            )
            check_setup_memory(memory, groups, outputs, group, prefix)
            total += 1
    assert total == 256
    print(
        f"live row fold: {total} sources; {outputs['row_routes']} routes; "
        f"{outputs['row_code_cells']} code cells; eight distinct row words"
    )


if __name__ == "__main__":
    main()
