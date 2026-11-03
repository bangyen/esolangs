"""Dense-memory reference for raw AddSubJump images."""

from itertools import product

from esolangs.languages.addsubjump.interpreter import _Machine
from tests.interpreters.oracle_support import observed


def _model(words, stdin):
    memory = list(words)
    flags = {-3: 0, -4: 0, -9: 0}
    pc = cursor = 0
    output = ""
    trace = []

    def load(address):
        nonlocal cursor
        if address == -1:
            if cursor == len(stdin):
                raise EOFError
            value = ord(stdin[cursor])
            cursor += 1
            return value
        if address >= 0:
            return memory[address] if address < len(memory) else 0
        return flags.get(address, {-6: 1, -8: -1}.get(address, 0))

    def view():
        return (
            (pc, tuple(memory), flags[-3], flags[-4], flags[-9]),
            not 0 <= pc < len(memory),
            output,
            cursor,
            cursor,
        )

    for step in range(17):
        row = view()
        trace.append(row)
        if row[1]:
            return None, trace + [row] * 3
        if step == 16:
            break
        a, b, target, mode = [load(pc + i) for i in range(4)]
        try:
            sign = -1 if load(mode) > 0 else 1
            operand = load(b)
        except EOFError:
            return "input", [*trace, view()]
        value = operand if a == -1 else load(a) + sign * operand
        if a == -1:
            output += chr(value % 256)
        elif a >= 0:
            memory.extend([0] * max(0, a + 1 - len(memory)))
            memory[a] = value
        elif a in flags:
            flags[a] = value
        if flags[-9]:
            flags[-3], flags[-4] = int(value == 0), int(value < 0)
        pc = target
    return None, trace


def check_raw_addsubjump():
    def state(vm):
        return vm.ip, tuple(vm.memory), vm.zf, vm.nf, vm.fum

    for a, b, mode, stdin in product(
        (-10, -9, -4, -3, -1, 0, 8, 12), (-8, -6, -1, 8), (-8, -6, -1), ("", "AΩ")
    ):
        words = [-9, -6, 4, -7, a, b, -1, mode, 3]
        code = " ".join(map(str, words))
        assert observed(_Machine, code, stdin, state, cap=16) == _model(words, stdin)
