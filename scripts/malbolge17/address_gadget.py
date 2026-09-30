"""Emit and execute the ordinary B path of the seventeen-input address fold."""

import itertools

from address17 import ALL1, ALL2, LOW, PIN, group_word
from address_parity import parity_operand
from parity_views import STORED_PARITY

from esolangs.interpreters.other.malbolge import (
    _XLAT2,
    _advance,
    _crazy,
    _initial_memory,
    _op,
)
from esolangs.tools._malbolge_core import (
    _ENTRY,
    _WORDS,
    _build_constants,
    _char_for,
    _g,
    _rot,
)
from esolangs.tools._malbolge_digits import _GADGET
from esolangs.tools.malbolge import (
    _T_HELPERS,
    _chain,
    _emit_chain,
    _Planner,
    _valid_chars,
)

# Seed 33 collides at C5468 after reserving the V route; 78 lands at 51395/50666.
_V_HANDOFF_SELECTOR_SEED = 78


def _branch_targets(seed: int, rotations: int) -> tuple[int, int]:
    """Return the two instruction cells selected by an input bit."""
    targets = []
    for bit in range(2):
        target = _crazy(48 + bit, seed)
        for _ in range(rotations):
            target = _rot(target)
        targets.append(target + 1)
    return targets[0], targets[1]


def build(
    z: int | None = 0,
    selected: int | None = None,
    *,
    dispatch_ab: bool = False,
    parity: bool = False,
    occupied: set[int] | None = None,
    outputs: dict[str, int] | None = None,
    continuation: str = "v",
    high_pointer: bool = False,
    high_parity: bool = False,
    group_read: bool = False,
    part_cells: list[tuple[str, set[int]]] | None = None,
    guard_scratch: bool = False,
    prepare_returns: bool = False,
    result_first: bool = False,
    slot_pointers: bool = False,
    shared_special_read: bool = False,
    shared_special_copy: bool = False,
    shared_v_handoff: bool = False,
    shared_exact_copy: bool = False,
    shared_special_fold: bool = False,
    normalize_labels: bool = False,
    restore_labels: bool = False,
    decoder_constants: bool = False,
    decoder_plans: list[_Planner] | None = None,
) -> tuple[str, tuple[tuple[int, int, int], ...], int, int]:
    """Return an address path; ``z=None`` dispatches A's two variants."""
    restore_labels |= decoder_constants
    normalize_labels |= restore_labels
    if decoder_plans is not None and not decoder_constants:
        raise ValueError("decoder plan requires prepared constants")
    if z not in (None, 0, 1, 2):
        raise ValueError(z)
    if z is None and selected is not None:
        raise ValueError(selected)
    if dispatch_ab and z is not None:
        raise ValueError(z)
    if parity and not dispatch_ab:
        raise ValueError("parity requires the combined dispatcher")
    if high_pointer and not parity:
        raise ValueError("high pointer requires the parity build")
    if high_parity and not parity:
        raise ValueError("high parity requires the parity build")
    if continuation != "v" and not parity:
        raise ValueError("continuation requires the parity build")
    if group_read and (not parity or continuation != "v"):
        raise ValueError(
            "group read requires the parity build and default continuation"
        )
    if any(op not in "ji*p</vo" for op in continuation):
        raise ValueError(continuation)
    if selected not in (None, 0, 1, 2):
        raise ValueError(selected)
    if prepare_returns and (not guard_scratch or not dispatch_ab or not parity):
        raise ValueError("return setup requires guarded parity dispatcher")
    if result_first and not guard_scratch:
        raise ValueError("result-first allocation requires guarded scratch")
    if slot_pointers and not result_first:
        raise ValueError("slot pointers require result-first scratch")
    if shared_special_read and (not slot_pointers or not prepare_returns):
        raise ValueError("shared special read requires prepared slot pointers")
    if shared_special_copy and not shared_special_read:
        raise ValueError("shared copy requires shared special read")
    if shared_v_handoff and not shared_special_copy:
        raise ValueError("V handoff requires shared copy")
    if shared_exact_copy and (not shared_special_copy or shared_v_handoff):
        raise ValueError("exact copy requires U copy without V handoff")
    if shared_special_fold and (
        not prepare_returns or not result_first or shared_special_read
    ):
        raise ValueError("shared fold requires prepared results without read probe")
    if normalize_labels and (not parity or group_read or continuation != "v"):
        raise ValueError("label normalization requires the halted parity build")
    startup = {10: "j", 11: "*", 12: "j", 13: "p", 14: "j", 15: "*", 16: "j", 17: "i"}
    raw = {125: 103, 126: 124}
    used = {*range(18), 125, 126}
    if restore_labels:
        # Startup jumps away at C17; these non-label seeds survive the fold.
        raw.update({18: 81, 25: 108})
        used.update((18, 25))
    if shared_special_read:
        raw.update({60: 96, 75: 59, 109: 84, 121: 54, 224: 120})
        used.update((60, 75, 109, 121, 224))
    if shared_v_handoff:
        raw.update({50: 106, 74: 59, 95: 97, 102: 73, 107: 120})
        used.update((50, 74, 95, 102, 107))
    copy_scratch = (85, 202, 92) if shared_special_copy else ()
    for slot, cell in enumerate(copy_scratch):
        used.update((cell, cell + 1, cell + 2))
        raw[cell + 2] = (47, 65, 99)[slot]
        if shared_exact_copy:
            used.add(cell + 3)

    def walked(
        value: int, *, high: bool = False, avoid: frozenset[int] = frozenset()
    ) -> int:
        cell = next(
            a
            for a in range(130 if high else 34, _ENTRY)
            if a not in used and a not in avoid and value in _valid_chars(a)
        )
        used.add(cell)
        raw[cell] = value
        return cell

    def walked_inert(value: int, *, high: bool = False) -> int:
        cell = next(
            a
            for a in range(130 if high else 34, _ENTRY)
            if a not in used and _char_for("o", a) == value
        )
        used.add(cell)
        raw[cell] = value
        return cell

    def scratch(value: int, *, result: bool) -> int:
        if not (guard_scratch and result):
            return walked(value)
        cell = next(
            a
            for a in range(34, _ENTRY - 1)
            if a not in used and a + 1 not in used and value in _valid_chars(a)
        )
        used.update((cell, cell + 1))
        raw[cell] = value
        return cell

    def scratch_group(values: tuple[int, int, int]) -> tuple[int, int, int]:
        if result_first:
            u = scratch(values[1], result=True)
            v = scratch(values[2], result=True)
            return scratch(values[0], result=False), u, v
        return (
            scratch(values[0], result=False),
            scratch(values[1], result=True),
            scratch(values[2], result=True),
        )

    reset = walked(33), walked(46), walked(81)
    helper = {"all1": walked(_g(128)), "all2": walked(_g(129))}
    for name, value in _T_HELPERS.items():
        helper[name] = walked(value, high=high_pointer and name == "a1")
    mask_specs = (
        tuple(
            (walked(seed), "rot rot rot rot K1 K2")
            for seed in (_g(170), _g(185), _g(197))
        )
        if parity
        else ()
    )
    parity_specs: tuple[tuple[int, str], ...] = (
        (
            (walked(_g(141), high=high_parity), "rot rot rot rot K2 K0 K2"),
            (walked(_g(165), high=high_parity), "rot rot rot rot K2 K0 K2"),
            (walked(_g(147), high=high_parity), "rot K0 K2"),
        )
        if parity
        else ()
    )
    normal_count = 4 if selected is None else 3
    normal = tuple(scratch_group(LOW) for _ in range(normal_count))
    if shared_special_read:
        assert tuple(group[1:] for group in normal[:3]) == (
            (48, 55),
            (66, 78),
            (100, 97),
        )
        raw.update(
            {49: 84, 67: 67, 101: 91} if shared_special_copy else {67: 108, 101: 74}
        )
        if shared_v_handoff:
            raw[98] = 77
    pin = None if selected is None else scratch_group(PIN)
    cells = normal if pin is None else (*normal, pin)
    twos = tuple(walked(38) for _ in range(5))
    z_load = walked(45) if z == 2 else None
    z_inputs: tuple[int, ...] | None
    branch_cell: int | None
    join_cell: int | None
    if z is None:
        z_inputs = (
            (walked(48), walked(45), walked(51))
            if dispatch_ab
            else (walked(45), walked(51))
        )
        z_cell = walked(34)
        branch_cell = walked(33)
        join_cell = walked(37)
        inner_branch = walked(33) if dispatch_ab else None
        ordinary_branch = walked(42) if dispatch_ab else None
    else:
        z_inputs = None
        z_cell = walked(56 if z == 2 else 47 if z == 0 else 45)
        branch_cell = join_cell = None
        inner_branch = ordinary_branch = None
    tail_cell = walked(38)
    if dispatch_ab:
        pin = scratch_group(PIN)
        cells = (*normal, pin)
    parity_all1 = reset[1] if parity else None
    parity_reunion = walked_inert(82) if parity else None
    tail_reunion = walked_inert(55) if parity else None
    selected_pointers = (
        tuple(walked(group[1] - 1) for group in normal[:3]) if slot_pointers else ()
    )
    if shared_v_handoff:
        assert selected_pointers[1] == 68
        raw[68] = 94
    assert all(cell < 128 for cell in selected_pointers)
    if outputs is not None:
        for slot, cell in enumerate(selected_pointers):
            if not (shared_v_handoff and slot == 1):
                outputs[f"slot_pointer_{slot}"] = cell
    shared_reunion = (127, 221, 315) if shared_special_read else ()
    for slot, cell in enumerate(shared_reunion):
        assert cell not in used
        assert cell + 1 not in used
        used.update((cell, cell + 1))
        raw[cell] = 35
        raw[cell + 1] = normal[slot][1] - 1
        assert raw[cell] in _valid_chars(cell)
        assert raw[cell + 1] in _valid_chars(cell + 1)
    fold_reunion = walked_inert(35) if shared_special_fold else None
    if fold_reunion is not None:
        assert fold_reunion + 1 not in used
        used.add(fold_reunion + 1)
        raw[fold_reunion + 1] = _char_for("o", fold_reunion + 1)
    if normalize_labels:
        # The old reducer at C731 hit C2190 before the extra handoff fit.
        parity_reunion = walked_inert(45 if restore_labels else 46)
    # A single assignment block crossed C53581; rotate seeds into separate gaps.
    label_jumps = (
        tuple(
            (walked_inert(value, high=True), value, turns)
            for value, turns in ((92, 5), (92, 4), (98, 4), (49, 3))
        )
        if restore_labels
        else ()
    )
    decoder_constant_cells = (
        (
            # Decoder view B3 needs 131; keep its constant source elsewhere.
            walked(80, high=True, avoid=frozenset({131})),
            walked(78, high=True),
            walked_inert(37, high=True),
        )
        if decoder_constants
        else None
    )
    boot = [_char_for("o", a) for a in range(_ENTRY)]
    for address, operation in startup.items():
        boot[address] = _char_for(operation, address)
    for address, value in raw.items():
        boot[address] = value
    boot_memory = list(_initial_memory("".join(chr(value) for value in boot)))
    state = (0, 0, 0, False)
    for _ in range(18):
        state, writes, _ = _advance(state, boot_memory)
        for address, value in writes:
            boot_memory[address] = value
    assert state[1:] == (3272, 126, False)
    memory: dict[int, int | None] = {a: boot_memory[a] for a in range(_ENTRY)}
    if parity:
        assert pin is not None
        for cell in pin:
            memory[cell] = None
    path = _Planner(3272, 126, memory, {})
    path.op("*", reset[0])
    path.op("p", reset[1])
    path.op("p", reset[2])
    _build_constants(path, helper)
    extra_all1 = () if parity_all1 is None else (parity_all1, helper["a1"], reset[0])
    for cell in (helper["all1"], helper["all2"], *extra_all1):
        path.op("p", cell)
        path.op("p", cell)
    path.op("*", helper["w"])
    path.op("p", helper["all2"])
    if fold_reunion is not None:
        _emit_chain(path, fold_reunion, "rot", helper)
        path.mem[fold_reunion] = 39377
        _emit_chain(path, fold_reunion + 1, "K1 K2 K1", helper)
        path.mem[fold_reunion + 1] = 0
    if parity:
        for cell, chain in sorted((*mask_specs, *parity_specs)):
            _emit_chain(path, cell, chain, helper)
        assert parity_reunion is not None
        _emit_chain(path, parity_reunion, "rot rot rot rot", helper)
        parity_entry = raw[parity_reunion]
        for _ in range(4):
            parity_entry = _rot(parity_entry)
        parity_entry += 1
    else:
        parity_entry = None
    if parity:
        assert tail_reunion is not None
        _emit_chain(path, tail_reunion, "rot rot rot", helper)
        tail_entry = raw[tail_reunion]
        for _ in range(3):
            tail_entry = _rot(tail_entry)
        tail_entry += 1
    else:
        tail_entry = None
    constants = {"K0": helper["z0"], "K1": helper["all1"], "K2": helper["all2"]}
    return_cells = sorted({result + 1 for group in cells for result in group[1:]})

    def emit_return_setup(plan: _Planner, *, special: bool = False) -> None:
        if prepare_returns:
            for cell in return_cells:
                if special and shared_special_read and cell in (49, 67, 101):
                    if shared_special_copy:
                        if cell == 67:
                            chain = " ".join(("rot",) * 9)
                            assert _chain(boot_memory[cell], chain) == 201
                            _emit_chain(plan, cell, chain, helper)
                    elif cell == 49:
                        assert _chain(boot_memory[cell], "K2") == 223
                        _emit_chain(plan, cell, "K2", helper)
                    continue
                if special and shared_v_handoff and cell == 98:
                    continue
                start = boot_memory[cell]
                chain = "K1" if _crazy(29524, start) == 0 else "K1 K2 K1"
                assert _chain(start, chain) == 0
                _emit_chain(plan, cell, chain, helper)

    parts: list[dict[int, str]] = []

    def record_part(name: str, code: dict[int, str]) -> None:
        parts.append(code)
        if part_cells is not None:
            part_cells.append((name, set(code)))

    def emit_suffix(
        suffix: _Planner,
        slots: tuple[tuple[int, int, int], ...],
        top: tuple[int, int, int],
    ) -> None:
        swap_cells = slots[0][1], slots[1][1], slots[2][2], top[1], top[2]
        for cell, two in zip(swap_cells, twos, strict=True):
            suffix.op("*", helper["all1"])
            suffix.op("p", two)
            suffix.op("p", cell)
        for group in (*slots, top):
            suffix.op("*", helper["all2"])
            suffix.op("p", group[2])
        suffix.op("*", helper["w"])
        for group in slots:
            suffix.op("p", group[2])
            suffix.op("*", group[2])
            suffix.op("p", group[1])
            suffix.op("*", group[1])
        suffix.op("p", z_cell)
        suffix.op("*", z_cell)
        suffix.op("p", top[2])
        suffix.op("*", top[2])
        suffix.op("*", helper["all2"])
        suffix.op("p", top[1])
        suffix.op("p", top[2])
        suffix.op("*", top[2])
        if parity:
            assert tail_reunion is not None
            suffix.goto(tail_reunion)
            suffix.raw("i")
            return
        suffix.op("p", helper["all1"])
        suffix.op("*", helper["all2"])
        suffix.op("p", helper["all1"])
        suffix.op("p", tail_cell)
        suffix.raw("v")

    pending_special: tuple[int, int, dict[int, int | None]] | None = None
    if z is None:
        assert z_inputs is not None
        assert branch_cell is not None
        assert join_cell is not None
        _emit_chain(path, join_cell, "rot", helper)
        path.raw("/")
        path.op("p", branch_cell)
        path.op("*", branch_cell)
        path.goto(branch_cell)
        path.raw("i")
        record_part("entry", path.code)
        common = _rot(37) + 1
        entries = tuple(_rot(_crazy(48 + bit, 33)) + 1 for bit in range(2))

        def z_block(entry: int, d: int, z_index: int) -> None:
            branch_memory = dict(path.mem)
            for cell in (branch_cell, inner_branch, ordinary_branch):
                if cell is not None:
                    branch_memory[cell] = None
            branch = _Planner(entry, d, branch_memory, {})
            _emit_chain(branch, z_inputs[z_index], "rot", helper)
            branch.op("p", z_cell)
            branch.mem[join_cell] = common - 1
            branch.goto(join_cell)
            branch.raw("i")
            record_part(f"z{z_index}", branch.code)

        if dispatch_ab:
            assert inner_branch is not None
            assert ordinary_branch is not None
            nested = []
            for entry, dispatch_cell, seed in (
                (entries[1], inner_branch, 33),
                (entries[0], ordinary_branch, 42),
            ):
                branch = _Planner(entry, branch_cell + 1, dict(path.mem), {})
                branch.raw("/")
                branch.op("p", dispatch_cell)
                for _ in range(3):
                    branch.op("*", dispatch_cell)
                branch.goto(dispatch_cell)
                branch.raw("i")
                record_part(f"dispatch-{seed}", branch.code)
                targets = []
                for bit in range(2):
                    target = _crazy(48 + bit, seed)
                    for _ in range(3):
                        target = _rot(target)
                    targets.append(target + 1)
                nested.append(tuple(targets))
            z_block(nested[0][0], inner_branch + 1, 1)
            z_block(nested[0][1], inner_branch + 1, 2)
            special_memory = dict(path.mem)
            for changed_cell in (branch_cell, ordinary_branch):
                special_memory[changed_cell] = None
            pending_special = nested[1][0], ordinary_branch + 1, special_memory
            z_block(nested[1][1], ordinary_branch + 1, 0)
        else:
            for bit, entry in enumerate(entries):
                z_block(entry, branch_cell + 1, bit)
        common_memory = dict(path.mem)
        common_memory[z_cell] = None
        for cell in z_inputs:
            common_memory[cell] = None
        for maybe_changed in (branch_cell, inner_branch, ordinary_branch):
            if maybe_changed is not None:
                common_memory[maybe_changed] = None
        common_memory[join_cell] = common - 1
        path = _Planner(common, join_cell + 1, common_memory, {})
    elif z == 2:
        assert z_load is not None
        _emit_chain(path, z_load, "K2", helper)
        path.op("p", z_cell)
    else:
        _emit_chain(path, z_cell, "K0 K2 K1 K2", helper)
    emit_return_setup(path)
    _emit_chain(path, tail_cell, "K0", helper)
    for group in normal:
        for operation in _GADGET:
            if operation == "/":
                path.raw("/")
            elif operation[0] == "K":
                path.op("*", constants[operation])
            else:
                path.op("p", group[int(operation)])
    if selected is not None:
        assert pin is not None
        for _ in range(3):
            path.raw("/")
        for operation in _GADGET:
            if operation == "/":
                path.op("*", helper["z0"])
            elif operation[0] == "K":
                path.op("*", constants[operation])
            else:
                path.op("p", pin[int(operation)])
    slots = list(normal[:3])
    top = normal[3] if selected is None else normal[selected]
    if selected is not None:
        assert pin is not None
        slots[selected] = pin
    emit_suffix(path, tuple(slots), top)
    record_part("common", path.code)
    if pending_special is not None:
        assert pin is not None
        if parity:
            cells = (
                *cells,
                (parity_specs[0][0], parity_specs[2][0], parity_specs[1][0]),
            )
        selector_cells = tuple(
            walked_inert(seed)
            for seed in (
                36,
                _V_HANDOFF_SELECTOR_SEED
                if shared_v_handoff or shared_exact_copy
                else 33,
                45,
                42,
                51,
                60,
                72,
            )
        )
        reunion_cells = (
            shared_reunion
            if shared_special_read
            else tuple(walked_inert(seed) for seed in (69, 41, 40))
        )
        selector_relocation = walked_inert(60 if high_parity else 50)
        copy_relocation = walked_inert(41) if shared_exact_copy else None
        entry, d, special_memory = pending_special
        for cell in (*pin, *selector_cells, *reunion_cells, selector_relocation):
            special_memory[cell] = raw[cell]
        special = _Planner(entry, d, special_memory, {})
        if copy_relocation is not None:
            # Exact-copy setup exceeded 59049 here; rotate 41 twice into C32810.
            special.mem[copy_relocation] = raw[copy_relocation]
            _emit_chain(special, copy_relocation, "rot rot", helper)
            special.goto(copy_relocation)
            special.raw("i")
            record_part("copy-setup-relocation", special.code)
            entry = _rot(_rot(raw[copy_relocation])) + 1
            special = _Planner(entry, copy_relocation + 1, dict(special.mem), {})
        emit_return_setup(special, special=True)
        for cell in copy_scratch:
            chain = "K2 K0" if cell == 202 else "K1 K2 K0"
            assert _chain(boot_memory[cell], chain) == ALL1
            _emit_chain(special, cell, chain, helper)
            chain = "K1 K2 K0 K2"
            assert _chain(boot_memory[cell + 1], chain) == ALL2
            _emit_chain(special, cell + 1, chain, helper)
            if shared_exact_copy:
                chain = "K1 K2 K0"
                assert _chain(boot_memory[cell + 3], chain) == ALL1
                _emit_chain(special, cell + 3, chain, helper)
        _emit_chain(special, tail_cell, "K0", helper)
        for group in normal[:3]:
            for operation in _GADGET:
                if operation == "/":
                    special.raw("/")
                elif operation[0] == "K":
                    special.op("*", constants[operation])
                else:
                    special.op("p", group[int(operation)])
        for operation in _GADGET:
            if operation == "/":
                special.op("*", helper["z0"])
            elif operation[0] == "K":
                special.op("*", constants[operation])
            else:
                special.op("p", pin[int(operation)])
        if fold_reunion is not None:
            for cell in (pin[0], *normal[3][1:]):
                special.op("*", helper["all1"])
                special.mem[helper["all1"]] = ALL1
                special.op("p", cell)
                special.op("p", cell)
                special.mem[cell] = ALL1
        reunion_rotations = (1, 1, 1) if shared_special_read else (6, 3, 2)
        reunion_targets = []
        for cell, rotations in zip(reunion_cells, reunion_rotations, strict=True):
            _emit_chain(special, cell, " ".join(["rot"] * rotations), helper)
            target = raw[cell]
            for _ in range(rotations):
                target = _rot(target)
            reunion_targets.append(target + 1)
        relocated_selector_entry = raw[selector_relocation]
        for _ in range(6):
            relocated_selector_entry = _rot(relocated_selector_entry)
        relocated_selector_entry += 1

        def selector_node(
            branch: _Planner, cell: int, rotations: int
        ) -> tuple[tuple[int, int], dict[int, int | None]]:
            branch.raw("/")
            branch.op("p", cell)
            for _ in range(rotations):
                branch.op("*", cell)
            branch.goto(cell)
            branch.raw("i")
            record_part("selector", branch.code)
            seed = raw[cell]
            return _branch_targets(seed, rotations), dict(branch.mem)

        first, first_memory = selector_node(special, selector_cells[0], 3)
        second: list[tuple[int, int, dict[int, int | None]]] = []
        for branch_index, (selector_entry, cell) in enumerate(
            zip(first, selector_cells[1:3], strict=True)
        ):
            if branch_index == 0:
                trampoline = _Planner(
                    selector_entry,
                    selector_cells[0] + 1,
                    first_memory,
                    {},
                )
                for _ in range(6):
                    trampoline.op("*", selector_relocation)
                trampoline.goto(selector_relocation)
                trampoline.raw("i")
                record_part("selector-relocation", trampoline.code)
                branch = _Planner(
                    relocated_selector_entry,
                    selector_relocation + 1,
                    dict(trampoline.mem),
                    {},
                )
            else:
                branch = _Planner(
                    selector_entry,
                    selector_cells[0] + 1,
                    first_memory,
                    {},
                )
            selector_targets, branch_memory = selector_node(branch, cell, 4)
            second.extend(
                (target, cell + 1, branch_memory) for target in selector_targets
            )
        leaves: list[tuple[int, int, dict[int, int | None]]] = []
        for (selector_entry, selector_d, branch_memory), cell in zip(
            second, selector_cells[3:], strict=True
        ):
            branch = _Planner(selector_entry, selector_d, branch_memory, {})
            selector_targets, leaf_memory = selector_node(branch, cell, 4)
            leaves.extend(
                (target, cell + 1, leaf_memory) for target in selector_targets
            )
        configurations = (
            (0, 1),
            (0, 2),
            (1, 1),
            (1, 2),
            (2, 1),
            (2, 2),
            (0, 0),
            (1, 0),
        )
        assert z_inputs is not None
        for (leaf, leaf_d, leaf_memory), (selected_slot, special_z) in zip(
            leaves, configurations, strict=True
        ):
            branch = _Planner(leaf, leaf_d, leaf_memory, {})
            _emit_chain(branch, z_inputs[special_z], "rot", helper)
            branch.op("p", z_cell)
            if shared_special_copy:
                branch.op("*", helper["all2"])
            branch.goto(reunion_cells[selected_slot])
            branch.raw("i")
            record_part("selected-leaf", branch.code)
        suffix_memory = dict(special.mem)
        for cell in (
            *z_inputs,
            z_cell,
            *selector_cells,
            *reunion_cells,
            selector_relocation,
        ):
            suffix_memory[cell] = None
        if shared_special_read:
            assert reunion_targets == [39378] * 3
            branch = _Planner(39378, 0, dict(suffix_memory), {})
            # ALL2 restores U; two fresh ALL1 cells then copy its exact value.
            stream = (
                "jpjo*jpjpoop<v"
                if shared_exact_copy
                else "jpjp*jppjjjp<v"
                if shared_v_handoff
                else "jpjp*jp<v"
                if shared_special_copy
                else "jpjjjp<v"
            )
            for op in stream:
                branch.raw(op)
            record_part("shared-selected-read", branch.code)
            if outputs is not None:
                outputs["shared_read_entry"] = 39378
        elif shared_special_fold:
            assert fold_reunion is not None

            def load_constant(plan: _Planner, name: str, value: int) -> None:
                plan.op("*", helper[name])
                plan.mem[helper[name]] = value

            def reset_copy_cell(plan: _Planner, cell: int) -> None:
                load_constant(plan, "all1", ALL1)
                plan.op("p", cell)
                plan.op("p", cell)
                plan.mem[cell] = ALL1

            def copy_cell(plan: _Planner, source_cell: int, target_cell: int) -> None:
                load_constant(plan, "all2", ALL2)
                plan.op("p", source_cell)
                load_constant(plan, "all2", ALL2)
                plan.op("p", source_cell)
                plan.op("p", pin[0])
                plan.op("p", target_cell)

            for slot, (target, reunion) in enumerate(
                zip(reunion_targets, reunion_cells, strict=True)
            ):
                branch = _Planner(target, reunion + 1, dict(suffix_memory), {})
                copy_cell(branch, normal[slot][1], normal[3][1])
                reset_copy_cell(branch, pin[0])
                copy_cell(branch, normal[slot][2], normal[3][2])
                reset_copy_cell(branch, pin[0])
                reset_copy_cell(branch, normal[slot][1])
                copy_cell(branch, pin[1], normal[slot][1])
                _emit_chain(branch, normal[slot][2], "K1 K2 K0 K2", helper)
                branch.goto(fold_reunion)
                branch.raw("i")
                record_part(f"copy-selected-{slot}", branch.code)
            branch = _Planner(39378, fold_reunion + 1, dict(suffix_memory), {})
            branch.raw("j")
            branch.d = 1
            for group in normal:
                for cell in group:
                    branch.mem[cell] = None
            emit_suffix(branch, normal[:3], normal[3])
            record_part("shared-special-fold", branch.code)
        else:
            for selected_slot, (target, reunion) in enumerate(
                zip(reunion_targets, reunion_cells, strict=True)
            ):
                branch = _Planner(target, reunion + 1, dict(suffix_memory), {})
                special_slots = list(normal[:3])
                special_slots[selected_slot] = pin
                emit_suffix(branch, tuple(special_slots), normal[selected_slot])
                record_part(f"suffix-{selected_slot}", branch.code)
    if parity:
        assert tail_entry is not None
        assert tail_reunion is not None
        tail_memory = dict(memory)
        for cell in used:
            tail_memory[cell] = None
        if fold_reunion is not None:
            tail_memory[fold_reunion] = 39377
            tail_memory[fold_reunion + 1] = 0
        if shared_special_read:
            for cell in shared_reunion:
                tail_memory[cell] = raw[cell]
                tail_memory[cell + 1] = raw[cell + 1]
        tail = _Planner(tail_entry, tail_reunion + 1, tail_memory, {})
        tail.op("p", helper["all1"])
        tail.op("*", helper["all2"])
        tail.op("p", helper["all1"])
        tail.op("p", tail_cell)
        assert parity_reunion is not None
        tail.goto(parity_reunion)
        tail.raw("i")
        record_part("tail", tail.code)
    if parity:
        assert parity_entry is not None
        assert parity_reunion is not None
        assert parity_all1 is not None
        reducer_memory = dict(memory)
        for cell in used:
            reducer_memory[cell] = None
        if fold_reunion is not None:
            reducer_memory[fold_reunion] = 39377
            reducer_memory[fold_reunion + 1] = 0
        if shared_special_read:
            for cell in shared_reunion:
                reducer_memory[cell] = raw[cell]
                reducer_memory[cell + 1] = raw[cell + 1]
        reducer = _Planner(parity_entry, parity_reunion + 1, reducer_memory, {})
        seed_all1, map_all1 = parity_all1, reset[0]
        reducer.op("p", helper["z1"])
        reducer.op("p", helper["a1"])
        for _ in range(6):
            reducer.op("*", mask_specs[0][0])
        reducer.op("p", seed_all1)
        reducer.op("*", helper["all2"])
        reducer.op("p", seed_all1)
        reducer.op("p", tail_cell)
        reducer.op("*", helper["all2"])
        reducer.op("p", seed_all1)
        reducer.op("*", helper["all2"])
        reducer.op("p", seed_all1)
        reducer.op("p", helper["a1"])
        for _ in range(4):
            reducer.op("*", mask_specs[0][0])
        reducer.op("*", helper["all2"])
        reducer.op("p", tail_cell)
        reducer.op("*", map_all1)
        reducer.op("p", tail_cell)
        for _ in range(10):
            reducer.op("*", tail_cell)
            reducer.op("p", helper["w"])
        reducer.op("p", mask_specs[0][0])
        reducer.op("p", parity_specs[0][0])
        reducer.op("p", mask_specs[1][0])
        reducer.op("p", parity_specs[1][0])
        reducer.op("p", mask_specs[2][0])
        reducer.op("p", parity_specs[2][0])
        if outputs is not None:
            outputs["continuation_c"] = reducer.c
            outputs["continuation_d"] = reducer.d
        if normalize_labels:
            for jump_cell, value, turns in label_jumps:
                for _ in range(turns):
                    reducer.op("*", jump_cell)
                reducer.mem[jump_cell] = _chain(value, " ".join(("rot",) * turns))
            entry_seed, entry_turns = (50, 4) if restore_labels else (49, 3)
            seed = next(
                cell
                for cell, value in reducer.mem.items()
                if cell >= 130 and value == entry_seed
            )
            for _ in range(entry_turns):
                reducer.op("*", seed)
            entry_word = _chain(entry_seed, " ".join(("rot",) * entry_turns))
            reducer.mem[seed] = entry_word
            reducer.goto(seed)
            reducer.raw("i")
            normalizer = _Planner(entry_word + 1, reducer.d, dict(reducer.mem), {})
            if decoder_constant_cells is not None:
                from setup_constants import preserve

                preserve(
                    normalizer,
                    map_all1,
                    helper["all2"],
                    decoder_constant_cells[0],
                    decoder_constant_cells[2],
                )
            from setup_constants import reset_labels

            if restore_labels:
                from decoder_group import _LABELS, _setup

                decoder_group = _setup(
                    frozenset({142, 145, 139, 144}),
                    external_pointer=True,
                    runtime_base=True,
                )
                label_targets = {
                    cell: decoder_group.hub_values[_LABELS.get(cell, "N")][0]
                    for cell in range(34, 128)
                }
                assert label_targets[42] == 29524
                assert label_targets[107] == 20776
                from setup_constants import prepare_labels

                prepare_labels(normalizer, map_all1, label_targets)

                for seed_cell, initial, turns in (
                    (18, 81, 8),
                    (107, 729, 9),
                    (107, 2187, 9),
                    (25, 108, 6),
                ):
                    jump_index = {81: 0, 729: 1, 2187: 2, 108: 3}.get(initial)
                    if jump_index is not None:
                        jump_cell, value, jump_turns = label_jumps[jump_index]
                        normalizer.goto(jump_cell)
                        normalizer.raw("i")
                        record_part(f"label-setup-before-{initial}", normalizer.code)
                        destination = _chain(value, " ".join(("rot",) * jump_turns)) + 1
                        normalizer = _Planner(
                            destination,
                            normalizer.d,
                            dict(normalizer.mem),
                            normalizer.data,
                        )
                    if outputs is not None:
                        outputs[f"labels_phase_{initial}"] = normalizer.c
                    if seed_cell == 25:
                        normalizer.op("*", 42)
                        normalizer.mem[42] = 29524
                        normalizer.op("p", 107)
                        normalizer.op("p", 107)
                        normalizer.mem[107] = 29524
                    seed_value = normalizer.mem[107] if seed_cell == 107 else initial
                    assert seed_value is not None
                    value = seed_value
                    for _ in range(turns):
                        normalizer.op("*", seed_cell)
                        value = _rot(value)
                        normalizer.mem[seed_cell] = value
                    if seed_cell != 107:
                        normalizer.op("p", 107)
                        value = _crazy(value, 29524)
                        normalizer.mem[107] = value
                    hub = value
                    assert hub == 29524 - _chain(initial, " ".join(("rot",) * turns))
                    for cell, target in label_targets.items():
                        if target == hub and cell != 107:
                            normalizer.op("p", cell)
                            normalizer.op("p", cell)
                            normalizer.mem[cell] = hub
                normalizer.mem[107] = label_targets[107]
                if outputs is not None:
                    outputs["labels_done"] = normalizer.c
            else:
                reset_labels(normalizer, map_all1)
            if decoder_constant_cells is not None:
                all2_cell, _v_cell, zero_cell = decoder_constant_cells
                assert normalizer.mem[42] == ALL1
                assert normalizer.mem[zero_cell] == 0
                assert normalizer.mem[all2_cell] == ALL2
                if outputs is not None:
                    outputs["decoder_all1"] = 42
                    outputs["decoder_all2"] = all2_cell
                    outputs["decoder_zero"] = zero_cell
                    outputs["decoder_continuation_c"] = normalizer.c
                    outputs["decoder_continuation_d"] = normalizer.d
                if decoder_plans is not None:
                    decoder_plans.append(
                        _Planner(
                            normalizer.c,
                            normalizer.d,
                            dict(normalizer.mem),
                            dict(normalizer.data),
                        )
                    )
            normalizer.raw("v")
            if not restore_labels:
                assert not normalizer.data
            record_part(
                "label-restoration-final" if restore_labels else "label-normalizer",
                normalizer.code,
            )
            if outputs is not None:
                outputs["label_entry"] = entry_word + 1
                outputs["label_halt"] = normalizer.c - 1
        elif group_read:
            reducer.goto(helper["a1"])
            reducer.raw("j")
            for op in "ppp<v":
                reducer.raw(op)
            if outputs is not None:
                outputs["group_read_halt_c"] = reducer.c - 1
        else:
            for op in continuation:
                reducer.raw(op)
        record_part("parity-reducer", reducer.code)
    source = [_char_for("o", a) for a in range(_WORDS)]
    for address, operation in startup.items():
        source[address] = _char_for(operation, address)
    for address, value in raw.items():
        source[address] = value
    if restore_labels:
        for address, char in normalizer.data.items():
            return_operation = next(
                (part[address] for part in parts if address in part), None
            )
            if return_operation is None:
                source[address] = char
            else:
                assert char == ord(_XLAT2[_char_for(return_operation, address) - 33])
    emitted: dict[int, str] = {}
    owners: dict[int, int] = {}
    for part_index, part in enumerate(parts):
        for address, operation in part.items():
            if address in emitted:
                raise AssertionError(
                    f"code parts {owners[address]} and {part_index} overlap at "
                    f"{address}: {emitted[address]} / {operation}; "
                    f"prior part ends at {max(parts[owners[address]])}, "
                    f"new part spans {min(part)}..{max(part)}"
                )
            emitted[address] = operation
            owners[address] = part_index
            source[address] = _char_for(operation, address)
    if occupied is not None:
        occupied.update(emitted)
        # An i enciphers the cell preceding its next instruction.
        occupied.update(address - 1 for address in emitted if address > 0)
    if outputs is not None and parity:
        outputs["pointer"] = helper["a1"]
    result_cell = tail_cell
    if parity:
        result_cell = mask_specs[2][0]
    return (
        "".join(chr(value) for value in source),
        cells,
        result_cell,
        len(startup) + sum(map(len, parts)),
    )


def execute_state(
    source: str, bits: tuple[int, ...], output: list[int] | None = None
) -> tuple[tuple[int, int, int, bool], list[int]]:
    """Execute ``source`` on ``bits`` and return final state and memory."""
    memory = list(_initial_memory(source))
    state = (0, 0, 0, False)
    inputs = iter(48 + bit for bit in bits)
    for _ in range(100_000):
        char = next(inputs) if _op(memory[state[1]], state[1]) == "/" else None
        state, writes, effect = _advance(state, memory, char)
        for address, value in writes:
            memory[address] = value
        if effect is not None and output is not None:
            output.append(effect)
        if state[3]:
            return state, memory
    raise AssertionError("address fold did not halt")


def execute(source: str, bits: tuple[int, ...]) -> list[int]:
    """Execute ``source`` on ``bits`` and return final memory."""
    return execute_state(source, bits)[1]


def run(source: str, result_cell: int, bits: tuple[int, ...]) -> int:
    """Execute ``source`` on ``bits`` and return the folded accumulator."""
    return execute(source, bits)[result_cell]


def main() -> None:
    """Check all fixed paths and the combined 8,192-row A path."""
    ordinary_sizes = []
    for z in range(3):
        source, _cells, result_cell, size = build(z)
        address_prefix = [0, 1] if z == 0 else [1, z - 1]
        for bits in itertools.product(range(2), repeat=12):
            assert run(source, result_cell, bits) == group_word(
                [*address_prefix, *bits]
            )
        ordinary_sizes.append(size)
    special_sizes = []
    for selected in range(3):
        for z in (1, 2):
            source, _cells, result_cell, size = build(z, selected)
            selector_suffix = selected >> 1, selected & 1, z - 1
            for lower_bits in itertools.product(range(2), repeat=9):
                bits = (*lower_bits, *selector_suffix)
                assert run(source, result_cell, bits) == group_word([0, 0, *bits])
            special_sizes.append(size)
    for selected in (0, 1):
        source, _cells, result_cell, size = build(0, selected)
        for lower_bits in itertools.product(range(2), repeat=9):
            bits = (*lower_bits, 1, 1, selected)
            assert run(source, result_cell, bits) == group_word([0, 0, *bits])
        special_sizes.append(size)
    dynamic_a, _cells, result_cell, dynamic_size = build(None)
    for bits in itertools.product(range(2), repeat=13):
        assert run(dynamic_a, result_cell, bits) == group_word([1, *bits])
    dynamic_ab, _dynamic_cells, result_cell, dynamic_ab_size = build(
        None, dispatch_ab=True
    )
    for head in ((1, 0), (1, 1), (0, 1)):
        for tail_bits in itertools.product(range(2), repeat=12):
            bits = (*head, *tail_bits)
            assert run(dynamic_ab, result_cell, bits) == group_word(list(bits))
    for selector_bits in itertools.product(range(2), repeat=12):
        bits = (0, 0, *selector_bits)
        assert run(dynamic_ab, result_cell, bits) == group_word(list(bits))
    occupied: set[int] = set()
    outputs: dict[str, int] = {}
    dynamic_parity, parity_groups, parity_operand_cell, dynamic_parity_size = build(
        None,
        dispatch_ab=True,
        parity=True,
        high_pointer=True,
        high_parity=True,
        occupied=occupied,
        outputs=outputs,
    )
    parity_result_cells = parity_groups[-1]
    assert parity_result_cells == (145, 139, 144)
    pointer_cell = outputs["pointer"]
    table_cells: set[int] = set()
    read_probes: list[tuple[tuple[int, ...], int]] = []
    for bits in itertools.product(range(2), repeat=14):
        word = group_word(list(bits))
        pointer = _crazy(ALL2 - 2, word)
        table_cells.update(_crazy(ALL2 - 2 + offset, word) + 1 for offset in range(3))
        if (
            all(pointer + offset not in occupied for offset in (1, 2, 3))
            and len(read_probes) < 8
        ):
            read_probes.append((bits, pointer))
        state, memory = execute_state(dynamic_parity, bits)
        assert state[1:3] == (
            outputs["continuation_c"],
            outputs["continuation_d"],
        )
        assert state[0] in STORED_PARITY
        assert memory[pointer_cell] == pointer
        assert memory[parity_operand_cell] == parity_operand(pointer)
        assert tuple(memory[cell] for cell in parity_result_cells) == tuple(
            STORED_PARITY[(pointer + 1 + offset) % 2] for offset in range(3)
        )
    probe_outputs: dict[str, int] = {}
    probe, _, _, _ = build(
        None,
        dispatch_ab=True,
        parity=True,
        high_pointer=True,
        high_parity=True,
        group_read=True,
        outputs=probe_outputs,
    )
    assert len(read_probes) == 8
    for bits, pointer in read_probes:
        program = list(probe)
        expected = STORED_PARITY[pointer % 2]
        for offset, op in enumerate("j*<", 1):
            address = pointer + offset
            value = _char_for(op, address)
            program[address] = chr(value)
            expected = _crazy(expected, value)
        printed: list[int] = []
        state, memory = execute_state("".join(program), bits, printed)
        assert state[1] == probe_outputs["group_read_halt_c"]
        assert memory[pointer_cell] == pointer
        assert printed == [expected & 0xFF]
    print(
        "fixed address paths: 16,384/16,384 correct, "
        f"ordinary {ordinary_sizes}, special {special_sizes}; "
        f"dynamic A: 8,192/8,192 correct, {dynamic_size}; "
        f"dynamic A/B/C/D: 16,384/16,384 correct, "
        f"{dynamic_ab_size} code cells; parity words: 49,152/49,152 correct, "
        f"{dynamic_parity_size} code cells, {len(occupied & table_cells)} table "
        "collisions"
    )


if __name__ == "__main__":
    main()
