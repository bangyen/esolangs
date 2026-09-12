r"""Execute a Line program's walked path tree against a Brainfuck-style."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field

from extract import DEFAULT_UNIT, OpCall, Stroke, Vertex, classify_ops


@dataclass
class IO:
    r"""Pluggable input/output for :func:`run`, mirroring `i`/`o`'s wiki."""

    read: Callable[[], int] = field(default=lambda: int(input("Input: ")))
    write: Callable[[int], None] = field(default=lambda value: print(value))


@dataclass
class _Compiled:
    r"""One stroke's classified ops plus its two possible next strokes."""

    ops: list[OpCall]
    end: tuple[int, int]
    zero: _Compiled | None
    nonzero: _Compiled | None
    # Set only on a leaf whose.
    # (see _compile).
    # either another stroke's own.
    # remaining ops -- deliberately.
    # first time that point was.
    # replay them every iteration.
    goto: _Compiled | None = None


def _compile(stroke: Stroke, unit: int) -> _Compiled:
    r"""Classify every stroke in ``stroke``'s tree exactly once,."""
    # Every real (non-resume-point).
    # kept alongside its compiled.
    # point can be tested against.
    # vertex hits and a point.
    strokes: list[tuple[_Compiled, list[Vertex], list[OpCall]]] = []
    leaves: list[_Compiled] = []
    resume_cache: dict[tuple[int, int], _Compiled] = {}

    def build(node: Stroke) -> _Compiled:
        ops = classify_ops(node.vertices, unit)
        last = node.vertices[-1]
        compiled = _Compiled(ops=ops, end=(last.y, last.x), zero=None, nonzero=None)
        if node.zero is not None:
            compiled.zero = build(node.zero)
        if node.nonzero is not None:
            compiled.nonzero = build(node.nonzero)
        if compiled.zero is None and compiled.nonzero is None:
            leaves.append(compiled)
        strokes.append((compiled, node.vertices, ops))
        return compiled

    def resume(target: _Compiled, remaining: list[OpCall]) -> _Compiled:
        if remaining == target.ops:
            return target
        key = id(target), len(remaining)
        if key not in resume_cache:
            resume_cache[key] = _Compiled(
                ops=remaining,
                end=target.end,
                zero=target.zero,
                nonzero=target.nonzero,
                goto=target.goto,
            )
        return resume_cache[key]

    def find_merge(
        point: tuple[int, int], exclude: _Compiled
    ) -> tuple[_Compiled, list[OpCall]] | None:
        py, px = point
        for target, vertices, ops in strokes:
            if target is exclude:
                # A leaf's own final.
                # itself (it is where point.
                # entirely rather than checking.
                # fact, so the search keeps.
                # *different* stroke instead of.
                continue
            last = vertices[-1]
            if (last.y, last.x) == point:
                # This stroke's own final.
                # point (a fork) or a genuine.
                # shared corner, so matching it.
                # common case: a loop-back.
                return target, []
            for i in range(len(vertices) - 1):
                v0, v1 = vertices[i], vertices[i + 1]
                # Strictly interior to this.
                # both ends.
                # (a corner within the stroke,.
                # deliberately excluded too,.
                # segment being tested: every.
                # exactly the fork's own end.
                # a vertex-equality test alone.
                # sharing that corner, not just.
                # confirmed to misfire on a.
                # matched an unrelated.
                # start at the same point.
                # A genuine drawn merge, by.
                # a real leg's own ink.
                # merge point, which sits.
                # straight run, not on any of.
                # requiring strict interior.
                # than a stroke's own final.
                # it is what a real merge.
                dy, dx = v1.y - v0.y, v1.x - v0.x
                oy, ox = py - v0.y, px - v0.x
                if dy * ox - dx * oy != 0:
                    continue
                t_num = oy * dy + ox * dx
                t_den = dy * dy + dx * dx
                if 0 < t_num < t_den:
                    return target, [c for c in ops if c.index >= i + 1]
        return None

    root = build(stroke)
    for leaf in leaves:
        match = find_merge(leaf.end, exclude=leaf)
        if match is None:
            continue
        target, remaining = match
        leaf.goto = resume(target, remaining)
    return root


def compile_program(stroke: Stroke, unit: int = DEFAULT_UNIT) -> _Compiled:
    r"""Compile ``stroke`` once for repeated :func:`run_compiled` calls."""
    return _compile(stroke, unit)


def run_compiled(program: _Compiled, io: IO | None = None) -> dict[int, int]:
    r"""Run a program returned by :func:`compile_program`."""
    if io is None:
        io = IO()
    tape: dict[int, int] = defaultdict(int)
    pointer = 0

    node: _Compiled | None = program
    while node is not None:
        for call in node.ops:
            if call.op == "+":
                tape[pointer] += call.count
            elif call.op == "-":
                tape[pointer] -= call.count
            elif call.op == ">":
                pointer += 1
            elif call.op == "<":
                pointer -= 1
            elif call.op == "i":
                tape[pointer] = io.read()
            elif call.op == "o":
                io.write(tape[pointer])
            else:  # pragma: no cover - defensive, classify_ops emits no others
                raise ValueError(f"unknown opcode {call.op!r}")

        if node.zero is None and node.nonzero is None:
            node = node.goto
            if node is None:
                return dict(tape)
            continue
        node = node.zero if tape[pointer] == 0 else node.nonzero

    return dict(tape)


def run(
    stroke: Stroke,
    io: IO | None = None,
    unit: int = DEFAULT_UNIT,
) -> dict[int, int]:
    r"""Execute ``stroke``'s full walked tree, returning the final tape."""
    return run_compiled(compile_program(stroke, unit), io)


if __name__ == "__main__":
    import sys

    from extract import extract

    result = extract(sys.argv[1])
    final_tape = run(result)
    nonzero_cells = {k: v for k, v in sorted(final_tape.items()) if v != 0}
    print(f"final tape (nonzero cells): {nonzero_cells}")
