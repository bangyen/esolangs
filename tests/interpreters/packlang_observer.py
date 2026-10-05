"""Compare independent Packlang frames, complete snapshots, views and ports."""

from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.other.packlang import _Machine
from tests.interpreters.packlang_program_reference import lower
from tests.interpreters.packlang_reference import Reference


def node_tree(node):
    if node is None:
        return None
    kind = node[0]
    if kind in ("number", "resolved"):
        return ("lit" if kind == "number" else "done", node[1])
    if kind == "variable":
        return ("var", node[1])
    if kind == "length":
        return ("length", node[1])
    if kind == "invert":
        return ("not", node_tree(node[1]))
    if kind == "xor":
        return ("xor", node_tree(node[1]), node_tree(node[2]))
    return ("apply", node[1], tuple(node_tree(arg) for arg in node[2]))


def store_tuple(store):
    return tuple(
        (slot, tuple(value) if isinstance(value, list) else value)
        for slot, value in sorted(store.items())
    )


def compare(machine, ref, port):
    assert machine.halted == (not ref.frames)
    expected = []
    for frame in ref.frames:
        key = (*frame["key"], frame["pc"], store_tuple(frame["store"]), frame["result"])
        expected.append((key, repr(node_tree(frame["pending"])), frame["returned"]))
    program_key = (
        tuple(
            sorted(
                (
                    key,
                    key[0],
                    tuple(function["params"]),
                    lower(function["body"]),
                    tuple(function["uses"]),
                    tuple(
                        sorted(
                            (slot, *kind) for slot, kind in function["locals"].items()
                        )
                    ),
                )
                for key, function in ref.program.functions.items()
            )
        ),
        tuple(
            sorted(
                (key, frozenset(deps)) for key, deps in ref.program.dependencies.items()
            )
        ),
        tuple(sorted((key, *kind) for key, kind in ref.program.globals.items())),
    )
    assert machine.snapshot() == (tuple(expected), ref.offset, ref.reads, program_key)
    assert machine.ip == (ref.frames[-1]["pc"] if ref.frames else 0)
    cells = []
    if ref.frames:
        for _slot, value in sorted(ref.frames[-1]["store"].items()):
            cells.extend(value) if isinstance(value, list) else cells.append(value)
    assert machine.memory == cells
    assert machine.stack == [frame["pc"] for frame in ref.frames[:-1]]
    assert (port.getvalue(), port.position(), port.reads, port.past_end) == (
        ref.output,
        ref.offset,
        ref.reads,
        ref.past_end,
    )


def check(source, stdin="", limit=100000):
    ref = Reference(source, stdin)
    port = ScriptedIO(stdin)
    machine = _Machine(source, port)
    for generation in range(limit):
        compare(machine, ref, port)
        if machine.halted:
            return {"generations": generation, "output": ref.output, "reads": ref.reads}
        before = machine.snapshot()
        frozen_hash = hash(before)
        ref.step()
        machine.step()
        assert hash(before) == frozen_hash
    raise RuntimeError("Packlang execution bound reached")
