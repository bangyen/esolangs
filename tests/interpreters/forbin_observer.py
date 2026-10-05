"""Compare separately parsed syntax and every activation, loop row and I/O."""

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import ScriptedIO
from tests.interpreters.forbin_reference import Function, InvalidError
from tests.interpreters.forbin_stepped_reference import SteppedReference
from tests.interpreters.views import view as vm_view


class SyntaxPair:
    def __init__(self, native, reference):
        self.functions = {}
        assert native.keys() == reference.keys()
        for name in reference:
            self.function(native[name], reference[name])

    def function(self, native, reference):
        if native in self.functions:
            assert self.functions[native] is reference
            return
        self.functions[native] = reference
        assert native.name == reference.name
        assert native.args == reference.parameters
        assert native.nested.keys() == reference.children.keys()
        for name in reference.children:
            self.function(native.nested[name], reference.children[name])
        self.statements(native.body, reference.statements)

    def expression(self, native, reference):
        if native[0] == "lit":
            assert native[1] == reference
            return
        if native[0] == "fnlit":
            self.function(native[1], reference)
            return
        tag = {"var": "name", "not": "negate", "call": "invoke"}[native[0]]
        assert reference[0] == tag
        if tag == "name":
            assert native[1] == reference[1]
        else:
            self.expression(native[1], reference[1])
            if tag == "invoke":
                self.expressions(native[2], reference[2])

    def expressions(self, native, reference):
        assert len(native) == len(reference)
        for left, right in zip(native, reference, strict=False):
            self.expression(left, right)

    def statements(self, native, reference):
        assert len(native) == len(reference)
        for left, right in zip(native, reference, strict=False):
            tag = {
                "assign": "bind",
                "call": "invoke",
                "for": "loop",
                "return": "return",
            }[left[0]]
            assert right[0] == tag
            if tag == "return":
                self.expression(left[1], right[1])
            elif tag == "bind":
                assert left[1] == right[1]
                self.expressions(left[2], right[2])
            elif tag == "invoke":
                self.expression(left[1], right[1])
                self.expressions(left[2], right[2])
            else:
                self.header(left[1], right[1])
                self.statements(left[2], right[2])

    def header(self, native, reference):
        if native[0] == "range":
            assert reference[0] == "range"
            assert [native[1]] == reference[1]
            self.expressions(native[2:], reference[2])
            return
        assert reference[0] == "iteration"
        assert native[1] == reference[1]
        patterns = native[2]
        assert len(patterns) == len(reference[2])
        for pattern, row in zip(patterns, reference[2], strict=False):
            items = pattern[1] if pattern[0] == "group" else [pattern]
            assert len(items) == len(row)
            for value, expected in zip(items, row, strict=False):
                if value[0] == "*":
                    assert expected is None
                else:
                    self.expression(value[1], expected)

    def value(self, native):
        if type(native) is int or type(native) is str:
            return native
        return self.functions[native]

    def bindings(self, values):
        return {name: self.value(value) for name, value in values.items()}


def compare(machine, ref, io, pair):
    pair.functions[machine.global_frame.fn] = ref.global_scope.function
    assert pair.bindings(machine.global_frame.locals) == ref.global_scope.values
    assert machine.halted == ref.halted
    assert len(machine.frames) == len(ref.activations)
    for frame, active in zip(machine.frames, ref.activations, strict=False):
        assert pair.functions[frame.fn] is active.scope.function
        assert pair.bindings(frame.locals) == active.scope.values
        assert (frame.pos, frame.for_names, frame.for_ind, frame.for_body_pos) == (
            active.index,
            active.names,
            active.next_row,
            active.body_index,
        )
        assert (frame.for_rows is None) == (active.rows is None)
        if frame.for_rows is not None:
            assert [
                [pair.value(value) for value in row] for row in frame.for_rows
            ] == active.rows
        pair.statements(frame.for_body, active.body)
        parent = frame.parent
        scope = active.scope.parent
        while parent or scope:
            assert parent is not None
            assert scope is not None
            assert pair.functions[parent.fn] is scope.function
            assert pair.bindings(parent.locals) == scope.values
            parent = parent.parent
            scope = scope.parent
    assert machine.reader.bits == ref.unread_bits()
    assert machine.reader.reads == ref.bit_reads
    assert (io.position(), io.reads, io.past_end, io.getvalue()) == (
        ref.offset,
        ref.reads,
        ref.past_end,
        ref.output,
    )
    assert vm_view(machine, "ip") == (
        tuple(active.index for active in ref.activations)
        if ref.activations
        else (ref.length,)
    )
    assert vm_view(machine, "memory") == (
        [
            value
            for value in ref.activations[-1].scope.values.values()
            if type(value) is int
        ]
        if ref.activations
        else []
    )
    assert vm_view(machine, "stack") == []
    reverse = {function: native for native, function in pair.functions.items()}

    def native_value(value):
        return reverse[value] if isinstance(value, Function) else value

    frames = tuple(
        (
            active.scope.function.name,
            active.index,
            tuple(
                sorted(
                    (
                        (name, repr(native_value(value)))
                        for name, value in active.scope.values.items()
                    )
                )
            ),
            active.next_row if active.rows is not None else -1,
            active.body_index if active.rows is not None else -1,
            reverse[active.scope.function],
            None
            if active.rows is None
            else tuple(
                tuple(native_value(value) for value in row) for row in active.rows
            ),
            () if active.rows is None else tuple(active.names),
        )
        for active in ref.activations
    )
    global_bindings = tuple(
        sorted(
            (
                (name, repr(native_value(value)))
                for name, value in ref.global_scope.values.items()
            )
        )
    )
    assert machine.snapshot() == (
        frames,
        ref.offset,
        tuple(ref.unread_bits()),
        ref.bit_reads,
        global_bindings,
    )


def check(source, stdin, machine_type, answer=None, limit=100000):
    ref = SteppedReference(source, stdin)
    io = ScriptedIO(stdin)
    machine = machine_type(source, io)
    pair = SyntaxPair(machine.globals, ref.functions)
    for generation in range(limit):
        compare(machine, ref, io, pair)
        if ref.halted:
            if answer is not None:
                assert ref.output == answer
            return {
                "halted": True,
                "generations": generation,
                "reads": ref.reads,
                "bit_reads": ref.bit_reads,
            }
        previous = machine.snapshot()
        recorded = repr(previous)
        expected = actual = None
        try:
            ref.step()
        except EOFError:
            expected = "eof"
        except InvalidError:
            expected = "invalid"
        try:
            machine.step()
        except EOFError:
            actual = "eof"
        except HaltError:
            actual = "invalid"
        assert actual == expected
        assert repr(previous) == recorded
        if expected:
            compare(machine, ref, io, pair)
            return {"error": expected, "generations": generation}
    raise RuntimeError("Forbin transition bound")
