"""Check the landing index and execute its emitted routes."""

from esolangs.languages.malbolge.generator.emitter import _Landings, _Planner
from esolangs.languages.malbolge.generator.isa import _g, _program, _render
from esolangs.languages.malbolge.interpreter import _advance, _initial_memory


def check_navigation() -> None:
    """Verify the index against direct enumeration, including changed cells."""
    ceiling = 282
    memory: dict[int, int | None] = {a: _g(a) for a in range(ceiling)}
    index = _Landings(memory, ceiling)
    for cell, value in ((34, None), (83, 180), (211, 59048), (34, 42)):
        index.update(cell, memory[cell], value)
        memory[cell] = value
    for floor, cap in ((34, 34), (50, 74), (100, 127), (128, 200)):
        for start in range(0, ceiling, 7):
            expected = next(
                (
                    a
                    for a in range(start, ceiling)
                    if (v := memory[a]) is not None and floor <= v + 1 <= cap
                ),
                None,
            )
            assert index.first(start, floor, cap, None) == expected
    walked: dict[int, int | None] = {a: _g(a) for a in range(ceiling)}
    for start, target in ((190, 35), (40, 120), (225, 160), (150, 210)):
        planner = _Planner(700, start, walked.copy(), {}, ceiling=ceiling)
        planner.goto(target)
        words = _program(planner.code) | planner.data
        mem = list(_initial_memory(_render(words, planner.c)))
        for address, value in walked.items():
            assert value is not None
            mem[address] = value
        state = 0, 700, start, False
        for _ in range(planner.c - 700):
            state, writes, _ = _advance(state, mem)
            for address, value in writes:
                mem[address] = value
        assert state == (0, planner.c, target, False)
