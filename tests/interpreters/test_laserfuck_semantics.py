import copy
import random

import pytest

from esolangs.interpreters.grid_based.laserfuck import _Machine
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.persistent import chunked, flatten
from esolangs.interpreters.randomness import FirstDraw
from tests.interpreters.laserfuck_reference import Beam, Reference


@pytest.mark.parametrize("shard", range(20))
def test_program_states(shard):
    randomizer = random.Random(604)
    records = []
    for case in range(2000):
        grid = [
            "".join(randomizer.choice("  ++--><#x/\\_|()^v{},*") for _ in range(5))
            for _ in range(5)
        ]
        grid[2] = grid[2][:2] + "o" + grid[2][3:]
        if case % 20 != shard:
            continue
        heading = case % 4
        split = (case // 4) % 2
        text = "A\nλ🙂" * 25
        ref = Reference(tuple(grid), [Beam(2, 2, "UDLR"[heading])], input_text=text)
        vm = _Machine(grid, ScriptedIO(text), FirstDraw(heading, rest=split))
        failure = None
        for generation in range(60):
            low = min(ref.cells)
            expected_tape = [
                (ref.cells[i], int(i in ref.touched))
                for i in range(low, max(ref.cells) + 1)
            ]
            comparisons = {
                "tape": (list(flatten(vm.tape)), expected_tape),
                "pointer": (vm.ptr, ref.pointer - low),
                "active": (vm.ind, ref.active),
                "skips": (
                    sorted(vm.jmp),
                    [i for i, b in enumerate(ref.beams) if b.skip],
                ),
                "beams": (
                    vm.lsrs,
                    [(b.row, b.col, "UDLR".index(b.direction)) for b in ref.beams],
                ),
            }
            failed = {k: v for k, v in comparisons.items() if v[0] != v[1]}
            if failed:
                failure = {"generation": generation, "fields": failed}
                break
            assert vm.io.position() == ref.reads
            if not ref.beams:
                vm.step()
                expected_output = "\n".join(
                    str(ref.cells[i]) for i in sorted(ref.touched) if ref.cells[i] >= 0
                )
                assert vm.io.getvalue() == expected_output
                before = vm.io.getvalue()
                vm.step()
                assert vm.io.getvalue() == before
                break
            if len(ref.beams) > 30:
                break
            ref.step(byte=65, split=split)
            vm.step()
        records.append(
            {
                "case": case,
                "grid": grid,
                "heading": heading,
                "split": split,
                "generations": generation,
                "failure": failure,
            }
        )
    assert not [r for r in records if r["failure"]]


@pytest.mark.parametrize("shard", range(10))
def test_branch_states(shard):
    rng = random.Random(605)
    transitions = 0
    for case in range(1000):
        grid = [
            "".join(rng.choice(" ++--><#x/\\_|()^v{}*") for _ in range(5))
            for _ in range(5)
        ]
        grid[2] = grid[2][:2] + "o" + grid[2][3:]
        if case % 10 != shard:
            continue
        vm = _Machine(grid, ScriptedIO(""), FirstDraw(case % 4))
        initial = vm.branching_snapshot()
        assert not vm.branching_halted(initial)
        assert {s[2][0][2] for s in vm.branching_successors(initial, 100)} == set(
            range(4)
        )
        ref = Reference(tuple(grid), [Beam(2, 2, "UDLR"[case % 4])])
        for generation in range(40):
            low = min(ref.cells)
            state = (
                chunked(
                    tuple(
                        (ref.cells[i], int(i in ref.touched))
                        for i in range(low, max(ref.cells) + 1)
                    )
                ),
                ref.pointer - low,
                tuple((b.row, b.col, "UDLR".index(b.direction)) for b in ref.beams),
                ref.active,
                frozenset(i for i, b in enumerate(ref.beams) if b.skip),
            )
            assert vm.branching_halted(state) == (not ref.beams)
            if not ref.beams or len(ref.beams) > 30:
                break

            def normalized(s):
                return (tuple(flatten(s[0])), *s[1:])

            def packed(r):
                lo = min(r.cells)
                return (
                    tuple(
                        (r.cells[i], int(i in r.touched))
                        for i in range(lo, max(r.cells) + 1)
                    ),
                    r.pointer - lo,
                    tuple((b.row, b.col, "UDLR".index(b.direction)) for b in r.beams),
                    r.active,
                    frozenset(i for i, b in enumerate(r.beams) if b.skip),
                )

            expected = []
            for split in range(2):
                branch = copy.deepcopy(ref)
                branch.step(split=split)
                expected.append(packed(branch))
            actual = vm.branching_successors(state, 100)
            assert actual is not None
            assert {normalized(s) for s in actual} == set(expected), (case, generation)
            ref.step(split=case % 2)
            transitions += 1
    for source in ([], ["oo"], ["no laser"]):
        vm = _Machine(source, ScriptedIO(""), FirstDraw(3))
        assert vm.branching_halted(vm.branching_snapshot()) == vm.halted


def test_command_transitions():
    import itertools

    from esolangs.interpreters.grid_based.laserfuck import _advance
    from esolangs.interpreters.persistent import chunked, flatten
    from tests.interpreters.laserfuck_reference import Beam, Reference

    count = 0
    for op, d, value, split, index, flags in itertools.product(
        "><+-,x*_(|)/\\^v{}#?",
        range(4),
        [0, 1, -1, 2**31 - 1, -(2**31)],
        range(2),
        range(2),
        [frozenset(), frozenset({0}), frozenset({1}), frozenset({0, 1})],
    ):
        ref = Reference(
            (op,),
            [Beam(0, 0, "UDLR"[d], i in flags) for i in range(2)],
            cells={0: value},
            active=index,
        )
        ref.beams[index].row, ref.beams[index].col = {
            "U": (1, 0),
            "D": (-1, 0),
            "L": (0, 1),
            "R": (0, -1),
        }["UDLR"[d]]
        ref.beams[index].skip = False
        ref.step(byte=65, split=split)
        state = (
            chunked(((value, 0),)),
            0,
            ((0, 0, d), (0, 0, d)),
            index,
            flags - {index},
            (0, 0, d),
        )
        tape, ptr, beams, active, skips, _pos = _advance(state, op, 0, 0, d, 65, split)
        low = min(ref.cells)
        expected = [
            (ref.cells[i], int(i in ref.touched))
            for i in range(low, max(ref.cells) + 1)
        ]
        assert list(flatten(tape)) == expected, (op, d, value, "tape")
        assert ptr == ref.pointer - low, (op, "pointer")
        assert beams == tuple(
            (b.row, b.col, "UDLR".index(b.direction)) for b in ref.beams
        ), (op, d, "beams")
        assert active == ref.active, (op, "active")
        assert skips == frozenset(i for i, b in enumerate(ref.beams) if b.skip), (
            op,
            "skips",
        )
        count += 1
    assert count == 6080


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        (["ÿo+x"], "\x01"),
        (["o+>+x"], "1\n1"),
        (["o-x"], ""),
        (["o+-x"], "0"),
        (["oo"], ""),
        (["no start"], ""),
    ],
)
def test_output_profile(source, expected):
    io = ScriptedIO("")
    vm = _Machine(source, io, FirstDraw(3, rest=0))
    for _ in range(30):
        if vm.halted:
            break
        vm.step()
    assert vm.halted
    vm.step()
    assert io.getvalue() == expected
    vm.step()
    assert io.getvalue() == expected


def test_cursorless_input_progress():
    from esolangs.interpreters.io import IO

    class Cursorless(IO):
        def __init__(self):
            self.reads = 0

        def input_char(self, _prompt="Input: "):
            if self.reads == 8:
                raise EOFError
            self.reads += 1
            return 65

        def position(self):
            return None

    io = Cursorless()
    vm = _Machine(["},v", "^o{"], io, FirstDraw(3, rest=0))
    seen = set()
    for _ in range(100):
        state = vm.snapshot()
        assert state not in seen
        seen.add(state)
        try:
            vm.step()
        except EOFError:
            break
    else:
        raise AssertionError("missing EOF")
    assert io.reads == 8
