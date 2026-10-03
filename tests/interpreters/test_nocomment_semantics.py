"""Independent mutable NoComment model; wiki 103548 and LF-stripping dialect."""

import itertools

import pytest

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.tape_based.nocomment import _Machine, run


class Reference:
    def __init__(self, source, size=4096, cells=None, stack=(), pointer=0):
        if size < 1:
            raise ValueError(f"the NoComment tape needs at least one cell, got {size}")
        self.code = "".join(char for char in source if char != "\n")
        self.cells = list(cells) if cells is not None else [0] * size
        self.stack = list(stack)
        self.pointer = pointer
        self.ip = 0
        self.output = ""

    @property
    def halted(self):
        return self.ip >= len(self.code)

    def snapshot(self):
        return bytes(self.cells), tuple(self.stack), self.pointer, self.ip, 0

    def step(self):
        if self.halted:
            return
        command = self.code[self.ip]
        value = self.cells[self.pointer]
        following = self.ip + 1
        if command == "i":
            self.cells[self.pointer] = (value + 1) & 255
        elif command == "d":
            self.cells[self.pointer] = (value - 1) & 255
        elif command == "c":
            self.cells[self.pointer] = 0
        elif command in ("l", "r"):
            self.pointer = (self.pointer + (-1 if command == "l" else 1)) % len(
                self.cells
            )
        elif command == "n":
            self.stack.append(value)
        elif command == "f":
            if not self.stack:
                raise HaltError(
                    f"'f' at position {self.ip} pops the stack and the stack is empty"
                )
            self.cells[self.pointer] = self.stack.pop()
        elif command in ("s", "b"):
            if value:
                if not self.stack:
                    raise HaltError(
                        f"{command!r} at position {self.ip} peeks the stack "
                        "and the stack is empty"
                    )
                distance = self.stack[-1] * (1 if command == "s" else -1)
                following += distance
                if following not in range(len(self.code)):
                    raise HaltError(
                        f"{command!r} at position {self.ip} jumps {distance:+d} "
                        f"to {following}, outside the program's "
                        f"0..{len(self.code) - 1}"
                    )
        elif command == "o":
            self.output += chr(value)
        else:
            raise ValueError(f"unrecognized NoComment command {command!r}")
        self.ip = following


def inspect(actual):
    assert actual.ip == actual.ind
    assert actual.memory == list(actual.tape)
    assert actual.snapshot() == (
        bytes(actual.tape),
        actual.stack,
        actual.ptr,
        actual.ind,
        actual.io.position(),
    )
    assert actual.io.position() == 0
    assert actual.io.past_end == 0
    return actual.snapshot(), actual.halted, actual.io.getvalue()


def compare(source, size=7, cap=24, cells=None, stack=(), pointer=0):
    expected = Reference(source, size, cells, stack, pointer)
    actual = _Machine(source, ScriptedIO("unused\x00\n\u0101"), size)
    actual.state = (
        0,
        pointer,
        bytes(expected.cells),
        tuple(stack),
        expected.cells[pointer],
        False,
    )
    assert actual.code == expected.code
    assert inspect(actual) == (expected.snapshot(), expected.halted, expected.output)
    visited = {expected.snapshot()}
    for _ in range(cap):
        frozen = actual.snapshot()
        frozen_hash = hash(frozen)
        error = None
        try:
            expected.step()
        except (HaltError, ValueError) as caught:
            error = caught
        if error is not None:
            with pytest.raises(type(error)) as caught:
                actual.step()
            assert str(caught.value) == str(error)
        else:
            actual.step()
        assert inspect(actual) == (
            expected.snapshot(),
            expected.halted,
            expected.output,
        ), source
        assert hash(frozen) == frozen_hash
        if error is not None:
            return expected, "error"
        if expected.halted:
            terminal = inspect(actual)
            actual.step()
            actual.step()
            assert inspect(actual) == terminal
            return expected, "halt"
        if expected.snapshot() in visited:
            return expected, "cycle"
        visited.add(expected.snapshot())
    return expected, "bounded"


def corpus():
    for length in range(4):
        for tokens in itertools.product("idclrnfsbox\n", repeat=length):
            yield "".join(tokens)
    yield from (
        "inbb",
        "inso",
        "cbo",
        "ciinsiio",
        "ciindbo",
        "ciinsio",
        "insxoo",
        "i \to",
        "i\ro",
        "I",
        "\u2003",
        "ci" + "n" * 260 + "f" * 260 + "o",
        "dno",
        "i" * 256 + "o",
        "i" * 257 + "rlo",
    )


@pytest.mark.medium
@pytest.mark.parametrize("size", [1, 2, 7])
@pytest.mark.parametrize("cap", [0, 1, 2, 7, 24])
def test_exhaustive_commands_lf_and_bounded_execution(size, cap):
    for source in corpus():
        compare(source, size, cap)


@pytest.mark.medium
@pytest.mark.parametrize("command", list("idclrnfsbo"))
def test_seeded_byte_stack_and_jump_boundaries(command):
    for size in (1, 2, 7):
        for value, stack in itertools.product(
            (0, 1, 2, 254, 255), ((), (0,), (1,), (2,), (255,), (17, 2, 1))
        ):
            for pointer in (0, size - 1):
                cells = [17] * size
                cells[pointer] = value
                compare(command + "o", size, 7, cells, stack, pointer)
    for tail in ("", "o", "oo", "ooo"):
        for value in (0, 1, 2, 3, 4):
            for stack in ((), (0,), (1,), (2,), (3,), (255,)):
                compare("o" + command + tail, 2, 12, [value, 31], stack)


def test_snapshot_normalizes_dirty_and_committed_cell_representations():
    machine = _Machine("irlnfo", ScriptedIO(), 7)
    machine.step()
    dirty = machine.snapshot()
    assert machine.tape[0] == 1
    machine.state = (1, 0, bytes((1, 0, 0, 0, 0, 0, 0)), (), 1, False)
    assert machine.snapshot() == dirty
    machine.state = (1, 0, bytes(7), (), 1, True)
    assert machine.snapshot() == dirty
    assert machine.memory == [1, 0, 0, 0, 0, 0, 0]
    machine.step()
    assert machine.ptr == 1
    assert machine.tape[0] == 1


@pytest.mark.medium
def test_default_wrap_and_public_run_forwards_configured_size():
    for size in (1, 2, 4096, 8192):
        compare("l", size, 1)
        code = "i" + "r" * size + "o"
        expected = Reference(code, size)
        actual = _Machine(code, ScriptedIO(), size)
        while not expected.halted:
            expected.step()
            actual.step()
            assert actual.ip == expected.ip
            assert actual.ptr == expected.pointer
        assert inspect(actual) == (expected.snapshot(), True, expected.output)
        assert expected.output == "\x01"
        io = ScriptedIO()
        run(code, io, size)
        assert io.getvalue() == expected.output
    assert _Machine("l", ScriptedIO()).size == 4096
    for size in (0, -1, -4096):
        with pytest.raises(ValueError, match="at least one cell") as caught:
            _Machine("i", ScriptedIO(), size)
        assert (
            str(caught.value)
            == f"the NoComment tape needs at least one cell, got {size}"
        )


WIKI_HELLO = (
    "iiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiii"
    "iiiiiiiiiiiioiiiiiiiiiiiiiiiiiiiiiiiiiiiiioiiiiiiiooiiioriii"
    "iiiiiiiiiiiiiiiiiiiiiiiiiiiiiolnnddddddddddddddddddddddddofo"
    "iiiofdddoddddddddorioriiiiiiiiiio"
)


@pytest.mark.medium
def test_published_hello_and_cell_copy_add_subtract_not():
    reference, verdict = compare(WIKI_HELLO, cap=2000)
    assert verdict == "halt"
    assert reference.output == "Hello World!\n"
    for value in (0, 1, 127, 255):
        result, verdict = compare("nrf", cells=[value] + [0] * 6, cap=3)
        assert verdict == "halt"
        assert result.cells[:2] == [value, value]
        result, verdict = compare(
            "rnciiinclsrilrnlfrffl", cells=[value] + [0] * 6, cap=100
        )
        assert verdict == "halt"
        assert result.cells[0] == int(value == 0)
        assert result.stack == []
        assert result.pointer == 0
    for operation, code in (
        (1, "lnciiiiiiiirrdlilnrrbllfr"),
        (-1, "lnciiiiiiiirrdldlnrrbllfr"),
    ):
        for left, right in itertools.product((0, 1, 2, 127, 255), repeat=2):
            result, verdict = compare(
                code, cells=[0, left, right, 0, 0, 0, 0], pointer=1, cap=10000
            )
            assert verdict == "halt"
            assert result.cells[1:3] == [(left + operation * right) & 255, 0]
