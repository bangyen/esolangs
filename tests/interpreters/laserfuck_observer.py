from esolangs.interpreters.grid_based.laserfuck import _Machine
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.randomness import FirstDraw
from tests.interpreters.laserfuck_reference import Beam, Reference


def check(source, text, heading):
    lines = source.splitlines()
    width = max(map(len, lines), default=0)
    grid = tuple(line.ljust(width) for line in lines)
    starts = [
        (r, c) for r, line in enumerate(grid) for c, op in enumerate(line) if op == "o"
    ]
    assert len(starts) == 1
    row, col = starts[0]
    ref = Reference(grid, [Beam(row, col, "UDLR"[heading])], input_text=text)
    io = ScriptedIO(text)
    vm = _Machine(lines, io, FirstDraw(heading, rest=0))
    low = high = dirty = 0
    verified = {}
    for _generation in range(1000000):
        low = min(low, ref.pointer)
        high = max(high, ref.pointer)
        coordinate = low
        for segment in vm.tape:
            previous = verified.get(coordinate)
            if previous is not segment or coordinate <= dirty < coordinate + len(
                segment
            ):
                expected = tuple(
                    (ref.cells[i], int(i in ref.touched))
                    for i in range(coordinate, coordinate + len(segment))
                )
                assert segment == expected
                verified[coordinate] = segment
            coordinate += len(segment)
        assert coordinate == high + 1
        assert vm.ptr == ref.pointer - low
        assert vm.ind == ref.active
        assert vm.lsrs == [(b.row, b.col, "UDLR".index(b.direction)) for b in ref.beams]
        assert vm.jmp == frozenset(i for i, b in enumerate(ref.beams) if b.skip)
        assert io.position() == ref.reads
        assert vm.halted == (not ref.beams)
        assert io.getvalue() == ""
        if not ref.beams:
            break
        dirty = ref.pointer
        ref.step()
        vm.step()
    else:
        raise AssertionError("generation bound")
    assert ref.reads == len(text)
    shown = [ref.cells[i] for i in sorted(ref.touched) if ref.cells[i] >= 0]
    output = (
        "".join(chr(v) for v in shown)
        if grid[0][0] == "ÿ"
        else "\n".join(map(str, shown))
    )
    vm.step()
    assert io.getvalue() == output
    return output, _generation
