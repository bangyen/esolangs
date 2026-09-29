"""Emit and execute the ordinary B path of the seventeen-input address fold."""

import itertools

from address17 import LOW, PIN, gadget, group_word

from esolangs.interpreters.other.malbolge import (
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
from esolangs.tools.malbolge import _T_HELPERS, _emit_chain, _Planner, _valid_chars


def build(
    z: int | None = 0,
    selected: int | None = None,
    *,
    dispatch_ab: bool = False,
) -> tuple[str, tuple[tuple[int, int, int], ...], int, int]:
    """Return an address path; ``z=None`` dispatches A's two variants."""
    if z not in (None, 0, 1, 2):
        raise ValueError(z)
    if z is None and selected is not None:
        raise ValueError(selected)
    if dispatch_ab and z is not None:
        raise ValueError(z)
    if selected not in (None, 0, 1, 2):
        raise ValueError(selected)
    startup = {10: "j", 11: "*", 12: "j", 13: "p", 14: "j", 15: "*", 16: "j", 17: "i"}
    raw = {125: 103, 126: 124}
    used = {*range(18), 125, 126}

    def walked(value: int) -> int:
        cell = next(
            a for a in range(34, _ENTRY) if a not in used and value in _valid_chars(a)
        )
        used.add(cell)
        raw[cell] = value
        return cell

    reset = walked(33), walked(46), walked(81)
    helper = {"all1": walked(_g(128)), "all2": walked(_g(129))}
    for name, value in _T_HELPERS.items():
        helper[name] = walked(value)
    normal_count = 4 if selected is None else 3
    normal = tuple(
        (walked(LOW[0]), walked(LOW[1]), walked(LOW[2])) for _ in range(normal_count)
    )
    pin = None if selected is None else (walked(PIN[0]), walked(PIN[1]), walked(PIN[2]))
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
    path = _Planner(3272, 126, memory, {})
    path.op("*", reset[0])
    path.op("p", reset[1])
    path.op("p", reset[2])
    _build_constants(path, helper)
    for cell in (helper["all1"], helper["all2"]):
        path.op("p", cell)
        path.op("p", cell)
    path.op("*", helper["w"])
    path.op("p", helper["all2"])
    constants = {"K0": helper["z0"], "K1": helper["all1"], "K2": helper["all2"]}
    parts: list[dict[int, str]] = []
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
        parts.append(path.code)
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
            parts.append(branch.code)

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
                parts.append(branch.code)
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
            special = _Planner(nested[1][0], ordinary_branch + 1, special_memory, {})
            for group in normal:
                for operation in _GADGET:
                    if operation == "/":
                        special.raw("/")
                    elif operation[0] == "K":
                        special.op("*", constants[operation])
                    else:
                        special.op("p", group[int(operation)])
            special.raw("v")
            parts.append(special.code)
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
    _emit_chain(path, tail_cell, "K0", helper)
    for group in normal:
        for operation in _GADGET:
            if operation == "/":
                path.raw("/")
            elif operation[0] == "K":
                path.op("*", constants[operation])
            else:
                path.op("p", group[int(operation)])
    if pin is not None:
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
    swap_cells = slots[0][1], slots[1][1], slots[2][2], top[1], top[2]
    for cell, two in zip(swap_cells, twos, strict=True):
        path.op("*", helper["all1"])
        path.op("p", two)
        path.op("p", cell)
    for group in (*slots, top):
        path.op("*", helper["all2"])
        path.op("p", group[2])
    path.op("*", helper["w"])
    for group in slots:
        path.op("p", group[2])
        path.op("*", group[2])
        path.op("p", group[1])
        path.op("*", group[1])
    path.op("p", z_cell)
    path.op("*", z_cell)
    path.op("p", top[2])
    path.op("*", top[2])
    path.op("*", helper["all2"])
    path.op("p", top[1])
    path.op("p", top[2])
    path.op("*", top[2])
    path.op("p", helper["all1"])
    path.op("*", helper["all2"])
    path.op("p", helper["all1"])
    path.op("p", tail_cell)
    path.raw("v")
    parts.append(path.code)
    source = [_char_for("o", a) for a in range(_WORDS)]
    for address, operation in startup.items():
        source[address] = _char_for(operation, address)
    for address, value in raw.items():
        source[address] = value
    emitted: dict[int, str] = {}
    for part in parts:
        for address, operation in part.items():
            if address in emitted and emitted[address] != operation:
                raise AssertionError(
                    f"conflicting code at {address}: {emitted[address]} / {operation}"
                )
            emitted[address] = operation
            source[address] = _char_for(operation, address)
    return (
        "".join(chr(value) for value in source),
        cells,
        tail_cell,
        len(startup) + sum(map(len, parts)),
    )


def execute(source: str, bits: tuple[int, ...]) -> list[int]:
    """Execute ``source`` on ``bits`` and return final memory."""
    memory = list(_initial_memory(source))
    state = (0, 0, 0, False)
    inputs = iter(48 + bit for bit in bits)
    for _ in range(100_000):
        char = next(inputs) if _op(memory[state[1]], state[1]) == "/" else None
        state, writes, _ = _advance(state, memory, char)
        for address, value in writes:
            memory[address] = value
        if state[3]:
            return memory
    raise AssertionError("address fold did not halt")


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
    dynamic_ab, dynamic_cells, result_cell, dynamic_ab_size = build(
        None, dispatch_ab=True
    )
    for head in ((1, 0), (1, 1), (0, 1)):
        for tail_bits in itertools.product(range(2), repeat=12):
            bits = (*head, *tail_bits)
            assert run(dynamic_ab, result_cell, bits) == group_word(list(bits))
    for selector_bits in itertools.product(range(2), repeat=12):
        memory = execute(dynamic_ab, (0, 0, *selector_bits))
        for group, start in zip(dynamic_cells, range(0, 12, 3), strict=True):
            expected = gadget(
                LOW, [48 + bit for bit in selector_bits[start : start + 3]]
            )
            assert (memory[group[1]], memory[group[2]]) == expected
    print(
        "fixed address paths: 16,384/16,384 correct, "
        f"ordinary {ordinary_sizes}, special {special_sizes}; "
        f"dynamic A: 8,192/8,192 correct, {dynamic_size}; "
        f"dynamic A/B: 12,288/12,288 correct + 4,096 special prefixes, "
        f"{dynamic_ab_size} code cells"
    )


if __name__ == "__main__":
    main()
