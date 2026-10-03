"""Independent mutable Line tape and control-flow oracle."""

import itertools
import random

import pytest

from esolangs.interpreters.tape_based.line.simulate import _advance, _Frame


class Reference:
    def __init__(self):
        self.node = 0
        self.at = self.pointer = 0
        self.cells = {}

    def state(self):
        return self.node, self.at, self.pointer, tuple(sorted(self.cells.items()))

    def step(self, program, value):
        if self.node is None:
            return None
        ops, zero, nonzero, onward = program[self.node]
        cell = self.cells.get(self.pointer, 0)
        if self.at == len(ops):
            if zero is None and nonzero is None:
                self.node = onward
            else:
                self.cells.setdefault(self.pointer, 0)
                self.node = zero if cell == 0 else nonzero
            self.at = 0
            return None
        op, count = ops[self.at]
        output = None
        if op in ("+", "-"):
            self.cells[self.pointer] = cell + (count if op == "+" else -count)
        elif op in (">", "<"):
            self.pointer += 1 if op == ">" else -1
        elif op == "i":
            if value is None:
                raise ValueError("input transition requires a value")
            self.cells[self.pointer] = value
        elif op == "o":
            self.cells.setdefault(self.pointer, 0)
            output = cell
        else:
            raise ValueError(f"unknown opcode {op!r}")
        self.at += 1
        return output


def compare(program, values=(), cap=30):
    compiled = tuple(
        _Frame(tuple(ops), (), (0, 0), zero, nonzero, onward)
        for ops, zero, nonzero, onward in program
    )
    expected = Reference()
    actual = expected.state()
    inputs = iter(values)
    consumed = 0
    seen = set()
    output = []
    for step in range(cap + 1):
        assert actual == expected.state()
        if expected.node is None:
            assert _advance(actual, compiled) == (actual, None)
            return "halt", output, expected
        if (actual, consumed) in seen:
            return "cycle", output, expected
        seen.add((actual, consumed))
        if step == cap:
            return "bounded", output, expected
        ops = program[expected.node][0]
        value = (
            next(inputs, None)
            if expected.at < len(ops) and ops[expected.at][0] == "i"
            else None
        )
        if value is not None:
            consumed += 1
        before, fingerprint = actual, hash(actual)
        try:
            result = expected.step(program, value)
        except ValueError as error:
            message = str(error)
            with pytest.raises(ValueError, match=r".") as caught:
                _advance(actual, compiled, value)
            assert str(caught.value) == message
            assert actual == expected.state()
            return "error", output, expected
        actual, result_actual = _advance(actual, compiled, value)
        assert result_actual == result
        assert hash(before) == fingerprint
        if result is not None:
            output.append(result)
    raise AssertionError("unreachable")


@pytest.mark.medium
@pytest.mark.parametrize("cap", [0, 1, 2, 7, 30])
@pytest.mark.parametrize("values", [(), (0,), (-257, 256), (3, 0, -1, 10**40)])
def test_exhaustive_straight_transitions(values, cap):
    tokens = [
        ("+", 1),
        ("+", 3),
        ("-", 1),
        ("-", 2),
        (">", 1),
        ("<", 1),
        ("i", 1),
        ("o", 1),
    ]
    for length in range(4):
        for ops in itertools.product(tokens, repeat=length):
            compare([(ops, None, None, None)], values, cap)


@pytest.mark.medium
@pytest.mark.parametrize("seed", range(8))
def test_seeded_counted_ops_forks_and_reconnections(seed):
    randomizer = random.Random(6250 + seed)
    for _ in range(100):
        program = []
        for _ in range(3):
            ops = [
                (randomizer.choice("+-<>io"), randomizer.choice((1, 2, 7)))
                for _ in range(randomizer.randrange(5))
            ]
            program.append(
                (
                    ops,
                    randomizer.choice((None, 0, 1, 2)),
                    randomizer.choice((None, 0, 1, 2)),
                    randomizer.choice((None, 0, 1, 2)),
                )
            )
        compare(program, (-7, 0, 1, 257, 10**30), cap=80)


def test_positive_controls_negative_pointer_cells_and_branch_polarity():
    program = [
        ((("<", 1), ("-", 7), ("o", 1), (">", 1), ("i", 1)), 1, 2, None),
        ((("+", 3), ("o", 1)), None, None, None),
        ((("-", 2), ("o", 1)), None, None, None),
    ]
    for value, answer in ((0, 3), (7, 5), (-7, -9)):
        status, output, tape = compare(program, (value,))
        assert status == "halt"
        assert output == [-7, answer]
        assert tape.cells == {-1: -7, 0: answer}


def test_positive_control_reconnection_counts_down_and_loop_does_not_halt():
    program = [
        ((("+", 3),), None, None, 1),
        ((), 3, 2, None),
        ((("o", 1), ("-", 1)), None, None, 1),
        ((("o", 1),), None, None, None),
    ]
    status, output, tape = compare(program, cap=40)
    assert status == "halt"
    assert output == [3, 2, 1, 0]
    assert tape.cells == {0: 0}
    assert compare([((), None, None, 0)])[0] == "cycle"


def test_unknown_opcode_and_missing_input_are_rejections():
    assert compare([((("x", 1),), None, None, None)])[0] == "error"
    assert compare([((("i", 1),), None, None, None)])[0] == "error"


def graph_reference(root, values, cap=10_000):
    node = root
    pointer = consumed = 0
    cells = {}
    output = []
    for _ in range(cap):
        if node is None:
            return output, cells, consumed
        op = node.op
        cell = cells.get(pointer, 0)
        if op == "?":
            node = node.zero if cell == 0 else node.nonzero
            continue
        if op == "+":
            cells[pointer] = cell + 1
        elif op == "-":
            cells[pointer] = cell - 1
        elif op in (">", "<"):
            pointer += 1 if op == ">" else -1
        elif op == "i":
            cells[pointer] = values[consumed]
            consumed += 1
        elif op == "o":
            output.append(cell)
        node = node.next if node.next is not None else node.goto
    raise AssertionError("graph did not halt within cap")


@pytest.mark.medium
@pytest.mark.parametrize("n", [1, 2, 3])
@pytest.mark.parametrize("reverse", [False, True])
def test_generated_boolean_graphs(n, reverse):
    from esolangs.interpreters.tape_based.line.simulate import IO, run_node
    from esolangs.tools.line import line_boolean

    for value in range(1 << (1 << n)):
        table = format(value, f"0{1 << n}b")
        root = line_boolean(table, reverse=reverse)
        for row, answer in enumerate(table):
            bits = [int(bit) for bit in format(row, f"0{n}b")]
            output, _, reads = graph_reference(root, bits)
            assert output == [int(answer)]
            assert reads == n
            actual_output = []
            inputs = iter(bits)
            actual_reads = []

            def read(inputs=inputs, actual_reads=actual_reads):
                actual_reads.append(True)
                return next(inputs)

            run_node(root, IO(read=read, write=actual_output.append))
            assert actual_output == output
            assert len(actual_reads) == reads


def glyph_vertices(op, count, heading, unit):
    """Construct the published glyphs, without renderer templates."""
    from esolangs.interpreters.tape_based.line.lattice import Vertex

    forward = heading
    right = (heading[1], -heading[0])
    left = (-right[0], -right[1])
    diagonal_right = (forward[0] + right[0], forward[1] + right[1])
    diagonal_left = (forward[0] + left[0], forward[1] + left[1])
    legs = [(forward, 2)]
    if op in ("+", "-"):
        legs.append((diagonal_right if op == "+" else diagonal_left, count))
    elif op in (">", "<"):
        legs.extend(
            [
                (diagonal_right if op == ">" else diagonal_left, 1),
                (left if op == ">" else right, 1),
            ]
        )
    elif op == "i":
        legs.extend([(diagonal_right, 1), (left, 2), (diagonal_right, 1)])
    elif op == "o":
        legs.extend([(left, 1), (diagonal_right, 2), (left, 1)])
    else:
        raise ValueError(op)
    legs.append((forward, 2))
    directions = [(-1, 0), (-1, 1), (0, 1), (1, 1), (1, 0), (1, -1), (0, -1), (-1, -1)]
    result = []
    y = x = 0
    for (dy, dx), length in legs:
        direction = (max(-1, min(1, dy)), max(-1, min(1, dx)))
        result.append(Vertex(y, x, directions.index(direction)))
        y += dy * length * unit
        x += dx * length * unit
    result.append(Vertex(y, x, None))
    return result


@pytest.mark.parametrize("heading", [(-1, 0), (0, 1), (1, 0), (0, -1)])
@pytest.mark.parametrize("unit", [1, 5, 20, 40])
@pytest.mark.parametrize("op", "+-<>io")
def test_published_glyphs_at_each_orientation_and_unit(op, unit, heading):
    from esolangs.interpreters.tape_based.line.extract import classify_ops

    counts = (1, 2, 3, 7) if op in "+-" else (1,)
    for count in counts:
        calls = classify_ops(glyph_vertices(op, count, heading, unit), unit)
        assert [(call.op, call.count, call.index) for call in calls] == [(op, count, 1)]


@pytest.mark.medium
@pytest.mark.parametrize("heading", [(-1, 0), (0, 1), (1, 0), (0, -1)])
def test_adjacent_published_glyphs_do_not_change_identity(heading):
    from esolangs.interpreters.tape_based.line.extract import classify_ops
    from esolangs.interpreters.tape_based.line.lattice import Vertex

    for length in range(1, 4):
        for ops in itertools.product("+-<>io", repeat=length):
            vertices = []
            y = x = 0
            for op in ops:
                glyph = glyph_vertices(op, 1, heading, 20)
                vertices.extend(
                    Vertex(point.y + y, point.x + x, point.heading)
                    for point in glyph[:-1]
                )
                y += glyph[-1].y
                x += glyph[-1].x
            vertices.append(Vertex(y, x, None))
            # Adjacent straight legs form one maximal geometric run.
            vertices = [
                point
                for i, point in enumerate(vertices)
                if i == 0 or point.heading != vertices[i - 1].heading
            ]
            calls = classify_ops(vertices)
            assert [(call.op, call.count) for call in calls] == [(op, 1) for op in ops]
