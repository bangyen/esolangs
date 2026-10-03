"""Execute eight row jumps after the complete seventeen-input setup."""

import itertools

from address_gadget import execute_state
from combined_helpers import _copy, place_chunks
from decoder_group import _setup
from dispatch3 import _readouts
from helper_consumer import helper_chunks, helper_values
from live_rows import build_live_rows
from planner import _Planner
from setup_consumer import check_setup_memory, control_inputs

from esolangs.tools.malbolge.core import _char_for, _g, _rot


def row_words() -> list[int]:
    """Return eight selectors in the three-cell-spaced free high region."""
    words = _readouts()
    for _ in range(7):
        words = list(map(_rot, words))
    assert min(words) == 58565
    assert max(words) == 58589
    assert len(set(words)) == 8
    assert len({value & 255 for value in words}) == 8
    return words


def build_row_routes(
    *, shared: bool = False
) -> tuple[str, tuple[tuple[int, int, int], ...], dict[str, int], tuple[_Planner, ...]]:
    """Emit eight row controls, optionally jumping to one shared continuation."""
    blocked: set[int] = set()
    source, groups, outputs, plan = build_live_rows(
        reserved=blocked,
        next_chunk=(
            [("*", 42, 29524), ("p", 19, None), ("p", 19, 29524)]
            if shared
            else [("*", 20, None)]
        ),
    )
    replaced_halt = plan.c
    blocked.remove(replaced_halt)
    words = row_words()
    stubs = {value + offset for value in words for offset in (1, 2)}
    assert not stubs & blocked
    assert not set(words) & set(plan.data)
    blocked.update(stubs)
    if shared:
        blocked.update(words)
    group = _setup(
        frozenset({142, 145, 139, 144}), external_pointer=True, runtime_base=True
    )
    protected = set(helper_values(group)) | {42, 147, 219, 142, 145, 139, 144, 20}
    chunks: list[list[tuple[str, int, int | None]]] = []
    common_entry = None
    if shared:
        protected.update({19, 21})
        candidates = []
        for seed, reach in group.reach.items():
            roots = [
                address
                for address, value in plan.mem.items()
                if 130 <= address < 420
                and address not in protected
                and value == _g(seed)
            ]
            if not roots:
                continue
            for value, recipe in reach.items():
                if (
                    6563 < value < 58248
                    and not set(range(value, value + 801)) & blocked
                ):
                    candidates.append((len(recipe), value, seed, min(roots)))
        assert candidates, "no shared continuation window"
        _, pointer, seed, root = min(candidates)
        common_entry = pointer + 1
        protected.add(root)
        blocked.update(range(pointer, pointer + 801))
        chunks.extend(
            helper_chunks(
                group,
                21,
                pointer,
                root,
                {"all1": 42, "all2": 147, "z0": 219},
                seed_cell=seed,
            )
        )
    chunks.extend([[("*", 20, None)] for _ in range(7)])
    # Reload the unknown row word if the placement jump changed the accumulator.
    chunks.extend(
        (
            [("*", 147, 59048), ("p", 20, None)],
            [("*", 147, 59048), ("p", 20, None), ("i", 20, None)],
        )
    )
    plan, emitted, routes = place_chunks(plan, chunks, blocked, protected)
    entries = []
    for row, value in enumerate(words):
        emitted[value + 1] = "i" if shared else "<"
        if not shared:
            emitted[value + 2] = "v"
        outputs[f"row_entry_{row}"] = value + 1
        outputs[f"row_value_{row}"] = value
        entry = _copy(plan, value + 1)
        assert entry.d == 21
        entry.mem[20] = value
        entries.append(entry)
    if common_entry is not None:
        emitted[common_entry] = "<"
        emitted[common_entry + 1] = "v"
        outputs["shared_entry"] = common_entry
        entry = _copy(plan, common_entry)
        entry.d = 22
        entry.mem[20] = None
        entries = [entry]
    rendered = list(source)
    for address, operation in emitted.items():
        rendered[address] = chr(_char_for(operation, address))
    outputs.update(
        dispatch_routes=routes,
        dispatch_code_cells=outputs["row_code_cells"] - 1 + len(emitted),
    )
    return "".join(rendered), groups, outputs, tuple(entries)


def main(*, shared: bool = False) -> None:
    """Run all eight actual jumps on every address-family control."""
    source, groups, outputs, _ = build_row_routes(shared=shared)
    group = _setup(
        frozenset({142, 145, 139, 144}), external_pointer=True, runtime_base=True
    )
    words = row_words()
    total = 0
    for prefix in control_inputs():
        for row, tail in enumerate(itertools.product((0, 1), repeat=3)):
            printed: list[int] = []
            state, memory = execute_state(source, prefix + tail, printed)
            halt = outputs["shared_entry"] + 1 if shared else words[row] + 2
            assert state[1] == halt, (prefix, row, state)
            if shared:
                assert memory[21] == outputs["shared_entry"] - 1
                assert state[2] == 23
            assert printed == [words[row] & 255]
            assert memory[20] == words[row]
            assert all(
                memory[cell] == wanted for cell, wanted in helper_values(group).items()
            )
            check_setup_memory(memory, groups, outputs, group, prefix)
            total += 1
    assert total == 256
    print(
        f"live row dispatch: {total} sources; "
        f"{'one shared entry' if shared else 'eight distinct executed stubs'}; "
        f"{outputs['dispatch_code_cells']} code cells"
    )


if __name__ == "__main__":
    main()
    main(shared=True)
