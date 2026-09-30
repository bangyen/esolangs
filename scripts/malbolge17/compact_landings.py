"""Execute an algebraic relocation of all decoder trampolines below 6561."""

from decoder_group import _VIEW, _setup
from planner import _Planner

from esolangs.interpreters.other.malbolge import _advance, _crazy, _initial_memory, _op
from esolangs.tools._malbolge_core import _build_constants, _char_for, _g, _rot
from esolangs.tools.malbolge import _T_HELPERS, _chain, _emit_chain

ALL1, ALL2 = 29524, 59048


def masks(state: int) -> tuple[int, ...]:
    """Return trit-wise relocation operands; two ALL2 passes preserve low trits."""
    if state == 0:
        return ALL2 - 2 * 3**6, ALL2
    if state == 3:
        return ALL2 - 3**6, ALL2 - 3**7
    if state == 4:
        return ALL2 - 3**8 - 2 * (3**6 + 3**7), ALL2
    return ()


def landing(state: int, parity: int, char: int) -> int:
    """Return the relocated trampoline address for one view and source byte."""
    word = _crazy(_crazy(_VIEW[2 * state + parity], char), ALL1)
    for operand in masks(state):
        word = _crazy(operand, word)
    return word + 1


def build_kernel(state: int, parity: int) -> tuple[str, int, int]:
    """Emit a real source reading one character and retaining its landing word."""
    group = _setup(frozenset(), external_pointer=True, runtime_base=True)
    memory: dict[int, int | None] = {a: _g(a) for a in range(420)}
    pointer = next(a for a in range(130, 420) if memory[a] == 109)
    header = _Planner(421, _char_for("j", 420) + 1, memory, {})
    header.op("*", pointer)
    header.mem[pointer] = _rot(109)
    header.goto(pointer)
    header.raw("i")
    assert header.c < 811
    plan = _Planner(_rot(109) + 1, header.d, dict(header.mem), {})
    used = {pointer, 19, 20, 21, 128, 129}
    helpers = {"all1": 128, "all2": 129}
    for name, value in _T_HELPERS.items():
        cell = next(
            a for a in range(130, 420) if a not in used and plan.mem[a] == value
        )
        helpers[name] = cell
        used.add(cell)
    # The jump rotation clobbered A; an equal 0/2 pair produces ALL1.
    zeros = []
    for seed in (80, 40):
        cell = next(a for a in range(130, 420) if a not in used and plan.mem[a] == seed)
        used.add(cell)
        zeros.append(cell)
    plan.op("*", zeros[0])
    plan.mem[zeros[0]] = _rot(80)
    plan.op("p", zeros[0])
    plan.mem[zeros[0]] = ALL1
    plan.op("p", zeros[1])
    plan.mem[zeros[1]] = 0
    _build_constants(plan, helpers)
    for cell in (128, 129):
        plan.op("p", cell)
        plan.op("p", cell)
    plan.op("*", helpers["w"])
    plan.op("p", 129)
    facts = {128: ALL1, 129: ALL2, helpers["z0"]: 0}
    plan.mem.update(facts)

    def chain(cell: int, initial: int, tokens: list[str]) -> int:
        value = initial
        for token in tokens:
            _emit_chain(plan, cell, token, helpers)
            value = _chain(value, token)
            plan.mem[cell] = value
            plan.mem.update(facts)
        return value

    def constant(wanted: int) -> int:
        if wanted == ALL2:
            return 129
        cell = next(
            a for a in group.reach if a not in used and wanted in group.reach[a]
        )
        used.add(cell)
        assert plan.mem[cell] == _g(cell)
        assert chain(cell, _g(cell), group.reach[cell][wanted]) == wanted
        return cell

    def load(cell: int, value: int) -> None:
        if cell == 129:
            plan.op("*", cell)
            plan.mem[cell] = ALL2
            return
        for _ in range(2):
            plan.op("*", 129)
            plan.mem[129] = ALL2
            plan.op("p", cell)
            value = _crazy(ALL2, value)
            plan.mem[cell] = value

    view = constant(_VIEW[2 * state + parity])
    mask_cells = []
    for operand in masks(state):
        if state != 4 or operand == ALL2:
            mask_cells.append(constant(operand))
            continue
        # 81 and 36 rotate to 6561 and 2916; no constant search is needed.
        bits = []
        for seed in (81, 36):
            cell = next(
                a for a in range(130, 420) if a not in used and plan.mem[a] == seed
            )
            used.add(cell)
            bits.append(cell)
        positive = chain(bits[0], 81, ["rot"] * 6 + ["K2", "K0"])
        assert chain(bits[1], 36, ["rot"] * 6) == 3**6 + 3**7
        load(bits[1], 3**6 + 3**7)
        negative_cell = helpers["z1"]
        plan.op("p", negative_cell)
        plan.mem[negative_cell] = ALL1 - (3**6 + 3**7)
        negative = chain(negative_cell, ALL1 - (3**6 + 3**7), ["K2"])
        assert positive == ALL1 + 3**8
        assert negative == ALL2 - 2 * (3**6 + 3**7)
        load(bits[0], positive)
        plan.op("p", negative_cell)
        plan.mem[negative_cell] = _crazy(positive, negative)
        assert plan.mem[negative_cell] == operand
        mask_cells.append(negative_cell)
    for cell in (19, 20, 21):
        plan.op("*", 128)
        plan.mem[128] = ALL1
        plan.op("p", cell)
        plan.op("p", cell)
        plan.mem[cell] = ALL1
    plan.raw("/")
    for cell in (19, 20):
        plan.op("p", cell)
    load(view, _VIEW[2 * state + parity])
    plan.op("p", 20)
    plan.op("p", 21)
    for cell, operand in zip(mask_cells, masks(state), strict=True):
        load(cell, operand)
        plan.op("p", 21)
    halt = plan.c
    plan.raw("v")
    assert not plan.data
    code = {420: "j", **header.code, **plan.code}
    assert len(code) == 1 + len(header.code) + len(plan.code)
    source = [_char_for("o", a) for a in range(59049)]
    for address, operation in code.items():
        source[address] = _char_for(operation, address)
    return "".join(map(chr, source)), halt, len(code)


def run_kernel(source: str, char: int, halt: int) -> int:
    """Execute a source from reset and return its retained landing word."""
    memory = list(_initial_memory(source))
    state = (0, 0, 0, False)
    inputs = iter((char,))
    for _ in range(100_000):
        value = next(inputs) if _op(memory[state[1]], state[1]) == "/" else None
        state, writes, output = _advance(state, memory, value)
        assert output is None
        for address, value in writes:
            memory[address] = value
        if state[3]:
            assert state[1] == halt
            assert next(inputs, None) is None
            return memory[21]
    raise AssertionError("compact landing kernel did not halt")


def main() -> None:
    """Execute all ten views and 94 characters; require distinct free landings."""
    seen: set[int] = set()
    total = 0
    for state in range(5):
        code_sizes = []
        for parity in range(2):
            source, halt, size = build_kernel(state, parity)
            assert len(source) == 59049
            code_sizes.append(size)
            for char in range(33, 127):
                address = run_kernel(source, char, halt) + 1
                assert address == landing(state, parity, char)
                assert 420 < address < 6561
                assert address not in seen
                seen.add(address)
                total += 1
        print(f"state {state}: 188 source runs; {code_sizes} code cells")
    assert total == len(seen) == 940
    print("940 distinct trampolines outside the walked region and truth table")


if __name__ == "__main__":
    main()
