"""Native execution control shared by the streaming-fold tests."""

from esolangs.languages.line.generator.forward import (
    streaming_canvas as forward_canvas,
)
from esolangs.languages.line.interpreter.extract import extract
from esolangs.languages.line.interpreter.simulate import (
    IO,
    _advance,
    _freeze_program,
    compile_program,
    run_node,
)
from scripts.benchmark import WrittenState


def _check(table, tmp_path, rows=None, scale=1):
    built = forward_canvas(table, 10**9)
    assert built is not None
    graph, plan = built
    canvas = plan()
    assert canvas.width * canvas.height == plan.area
    assert forward_canvas(table, plan.area) is None
    canvas = canvas.upscale(scale)
    path = str(tmp_path / "forward.png")
    canvas.save(path)
    frames = _freeze_program(compile_program(extract(path)))
    n = len(table).bit_length() - 1
    bound = n + 1 + (3 * n - 2).bit_length() + (n - 1).bit_length()
    bound += (2 * n - 1).bit_length() + sum(
        max(1, cell.bit_length()) + 1 for cell in range(n)
    )
    maximum = 0
    for row in range(1 << n) if rows is None else rows:
        inputs = [(row >> shift) & 1 for shift in range(n - 1, -1, -1)]
        values = iter(inputs)
        output = []
        run_node(graph, IO(read=values.__next__, write=output.append))
        assert output == [int(table[row])]
        values = iter(inputs)
        state = (0, 0, 0, ())
        written = WrittenState((0, 0, 0, (), 0))
        output = []
        reads = commands = 0
        while state[0] is not None:
            frame = frames[state[0]]
            at = state[1]
            value = (
                next(values)
                if at < len(frame.ops) and frame.ops[at][0] == "i"
                else None
            )
            reads += value is not None
            state, value = _advance(state, frames, value)
            if value is not None:
                output.append(value)
            commands += 1
            assert commands <= 5 * n
            node, at, pointer, tape = state
            assert all(0 <= cell < n and value in (0, 1) for cell, value in tape)
            written.sample(
                (
                    node,
                    at,
                    pointer,
                    tuple((cell, value) for cell, value in tape if value),
                    max(0, 2 * reads - 1),
                )
            )
        assert reads == n
        assert output == [int(table[row])]
        assert written.bits <= bound
        maximum = max(maximum, commands)
    return plan.area, maximum
