"""Project the live row word onto eight low indirect-pointer slots."""

import itertools

from address_gadget import execute_state
from combined_helpers import _copy, place_chunks
from decoder_group import _setup
from helper_consumer import helper_values
from live_rows import build_live_rows
from planner import _Planner
from row_routes import row_words
from setup_consumer import check_setup_memory, control_inputs

from esolangs.interpreters.other.malbolge import _crazy
from esolangs.tools.malbolge.core import _char_for


def pointer_slots() -> list[int]:
    """Return distinct slots after twice applying the same low-trit projection."""
    words = row_words()
    for _ in range(2):
        words = [_crazy(29537, _crazy(59048, word)) for word in words]
    slots = [word + 1 for word in words]
    assert slots == [27, 24, 18, 15, 3, 6, 21, 12]
    return slots


def build_row_projection() -> tuple[
    str, tuple[tuple[int, int, int], ...], dict[str, int], _Planner
]:
    """Emit the low selector without replacing labels or injecting memory."""
    blocked: set[int] = set()
    source, groups, outputs, plan = build_live_rows(
        reserved=blocked, next_chunk=[("*", 20, None)]
    )
    blocked.remove(plan.c)
    group = _setup(
        frozenset({142, 145, 139, 144}), external_pointer=True, runtime_base=True
    )
    protected = set(helper_values(group)) | {42, 147, 219, 142, 145, 139, 144, 19, 20}
    mask = next(
        cell
        for cell, value in plan.mem.items()
        if 128 <= cell < 420 and cell not in protected and value == 53
    )
    protected.add(mask)
    chunks: list[list[tuple[str, int, int | None]]] = [
        [("*", 20, None)] for _ in range(7)
    ]
    chunks.append([("*", 219, 0), ("p", mask, 29537)])
    # The first pass leaves a fixed trit 5; the second clears it.
    for _ in range(2):
        chunks.extend(
            (
                [("*", 147, 59048), ("p", 20, None)],
                [("*", 147, 59048), ("p", mask, _crazy(59048, 29537))],
                [("*", 147, 59048), ("p", mask, 29537), ("p", 20, None)],
            )
        )
    chunks[-1].append(("<", 21, None))
    plan, emitted, routes = place_chunks(plan, chunks, blocked, protected)
    entry = _copy(plan)
    assert plan.c not in blocked
    emitted[plan.c] = "v"
    outputs.update(
        projection_halt=plan.c,
        projection_mask=mask,
        projection_routes=routes,
        projection_code_cells=outputs["row_code_cells"] - 1 + len(emitted),
    )
    rendered = list(source)
    for address, operation in emitted.items():
        rendered[address] = chr(_char_for(operation, address))
    return "".join(rendered), groups, outputs, entry


def main() -> None:
    """Execute all eight selectors on every address-family control."""
    source, groups, outputs, _ = build_row_projection()
    group = _setup(
        frozenset({142, 145, 139, 144}), external_pointer=True, runtime_base=True
    )
    total = 0
    for prefix in control_inputs():
        for row, tail in enumerate(itertools.product((0, 1), repeat=3)):
            printed: list[int] = []
            state, memory = execute_state(source, prefix + tail, printed)
            assert state[1] == outputs["projection_halt"]
            assert printed == [pointer_slots()[row] - 1]
            assert memory[20] == pointer_slots()[row] - 1
            assert memory[outputs["projection_mask"]] == 29537
            assert all(
                memory[cell] == wanted for cell, wanted in helper_values(group).items()
            )
            check_setup_memory(memory, groups, outputs, group, prefix)
            total += 1
    print(
        f"live row projection: {total} controls; "
        f"{outputs['projection_code_cells']} code cells"
    )


if __name__ == "__main__":
    main()
