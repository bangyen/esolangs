"""Emit and execute each decoder helper initializer after the shared setup."""

from address_gadget import execute_state
from decoder_group import _BASES, _Group, _setup
from setup_consumer import check_setup_memory, control_inputs
from shared_fold import build_shared_fold

from esolangs.interpreters.other.malbolge import _crazy
from esolangs.tools._malbolge_core import _char_for, _g
from esolangs.tools.malbolge import _chain, _Planner


def helper_values(group: _Group) -> dict[int, int]:
    """Return clear/view words and the three traced read-only navigation words."""
    values = dict((*group.clear, *zip(group.view_cells, _BASES, strict=True)))
    # The 94-residue runtime-entry trace also reads these unchanged pointers.
    values.update({cell: _g(cell) for cell in (153, 174, 236)})
    return values


def helper_chunks(
    group: _Group,
    cell: int,
    wanted: int,
    source: int,
    constants: dict[str, int],
    *,
    initial: int | None = None,
    copy_cell: int = 19,
) -> list[list[tuple[str, int, int | None]]]:
    """Return initializer chunks, each independent of the incoming accumulator."""
    direct = initial is not None
    initial = _g(cell) if initial is None else initial
    chunks: list[list[tuple[str, int, int | None]]] = [
        [("*", constants["all1"], 29524), ("p", target, None), ("p", target, 29524)]
        for target in (copy_cell, cell)
    ]
    chunks.extend(
        (
            [("*", constants["all2"], 59048), ("p", source, _crazy(59048, initial))],
            [
                ("*", constants["all2"], 59048),
                ("p", source, initial),
                ("p", copy_cell, _crazy(initial, 29524)),
                ("p", cell, initial),
            ],
        )
    )
    if direct:
        chunks = []
        recipe_cell = next(
            a for a in group.reach if _g(a) == initial and wanted in group.reach[a]
        )
    else:
        recipe_cell = cell
    value = initial
    for token in () if wanted == initial else group.reach[recipe_cell][wanted]:
        value = _chain(value, token)
        if token == "rot":
            chunks.append([("*", cell, value)])
        else:
            name, uniform = {
                "K0": ("z0", 0),
                "K1": ("all1", 29524),
                "K2": ("all2", 59048),
            }[token]
            chunks.append([("*", constants[name], uniform), ("p", cell, value)])
    assert value == wanted
    return chunks


def emit_helper(
    plan: _Planner,
    group: _Group,
    cell: int,
    wanted: int,
    constants: dict[str, int],
) -> None:
    """Reset an unknown helper, copy its scalar seed, then run its known chain."""
    facts = {constants["all1"]: 29524, constants["all2"]: 59048, constants["z0"]: 0}
    initial = _g(cell)
    excluded = set(helper_values(group)) | set(facts) | {19}
    source = next(
        address
        for address, value in plan.mem.items()
        if address >= 130 and address not in excluded and value == initial
    )
    for chunk in helper_chunks(group, cell, wanted, source, constants):
        for operation, target, value in chunk:
            plan.op(operation, target)
            plan.mem[target] = value


def main() -> None:
    """Check ten separate emitted initializers, not a combined decoder setup."""
    group = _setup(
        frozenset({142, 145, 139, 144}), external_pointer=True, runtime_base=True
    )
    total = 0
    for cell, wanted in helper_values(group).items():
        outputs: dict[str, int] = {}
        plans: list[_Planner] = []
        occupied: set[int] = set()
        source, groups, _, _ = build_shared_fold(
            decoder_constants=True,
            decoder_plans=plans,
            outputs=outputs,
            occupied=occupied,
        )
        entry = plans[0]
        replaced_halt = entry.c
        pointer = next(
            address
            for address, value in entry.mem.items()
            if address >= 130 and value == 59
        )
        word = 59
        for _ in range(5):
            entry.op("*", pointer)
            word = _chain(word, "rot")
            entry.mem[pointer] = word
        assert word == 14337
        entry.goto(pointer)
        entry.raw("i")
        body = _Planner(word + 1, entry.d, dict(entry.mem), dict(entry.data))
        constants = {
            "all1": outputs["decoder_all1"],
            "all2": outputs["decoder_all2"],
            "z0": outputs["decoder_zero"],
        }
        emit_helper(body, group, cell, wanted, constants)
        body.raw("<")
        body.raw("v")
        code = dict(entry.code)
        assert not set(code) & set(body.code)
        code.update(body.code)
        assert set(code) & occupied == {replaced_halt}, (cell, body.c)
        assert body.data == entry.data
        rendered = list(source)
        for address, operation in code.items():
            rendered[address] = chr(_char_for(operation, address))
        source = "".join(rendered)
        for bits in control_inputs():
            printed: list[int] = []
            state, memory = execute_state(source, bits, printed)
            assert state[1] == body.c - 1
            assert printed == [wanted & 255]
            assert memory[cell] == wanted
            check_setup_memory(memory, groups, outputs, group, bits)
            total += 1
        print(f"helper {cell}={wanted}: 32 source runs, {len(body.code)} body cells")
    assert total == 320
    print("all ten separate helper initializers passed; combined layout pending")


if __name__ == "__main__":
    main()
