"""Model the scope and deque rules of https://esolangs.org/wiki/Nybbleist (17325).

Use the repository's high-first byte framing and zero padding at halt.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from esolangs.languages.nybbleist.interpreter import prepare_machine
from tests.interpreters.oracle_support import checker

_STEPS = 64


@dataclass(frozen=True, eq=False)
class _Block:
    body: tuple[str | _Block, ...]
    label: str = ""


def _source(block):
    return "".join(
        item if isinstance(item, str) else f"[{_source(item)}]{item.label}"
        for item in block.body
    )


@dataclass
class _Frame:
    block: _Block
    code: list[str | _Block]
    labels: dict[str, int | _Block]
    position: int = 0
    stack: list[int] = field(default_factory=list)


def _frame(block):
    code = []
    labels = {}
    for item in block.body:
        if isinstance(item, _Block):
            if item.label:
                labels[item.label] = item
            code.append(item)
        elif item.startswith(":"):
            labels[item[1:]] = len(code)
        elif item[0] in "*!":
            code.extend(item[0] + value for value in item[1:])
        else:
            code.append(item)
    return _Frame(block, code, labels)


def _predict(block, stdin):
    root = _frame(block)
    frames = [root]
    registers = {"X": 0, "Y": 0}
    history = {}
    written = []
    read = 0

    def view(*, halted=False):
        state = registers["X"], registers["Y"], tuple(frames[-1].stack)
        output = "".join(
            chr(16 * written[i - 1] + written[i]) for i in range(1, len(written), 2)
        )
        cursor = (read + 1) // 2
        return state, halted, output, cursor, cursor

    trace = [view()]
    for _ in range(_STEPS):
        frame = frames[-1]
        halted = False
        if frame.position == len(frame.code):
            history[frame.block] = tuple(frames.pop().stack)
        else:
            item = frame.code[frame.position]
            frame.position += 1
            if isinstance(item, _Block):
                frames.append(_frame(item))
            else:
                op, arg = item[0], item[1:]
                if op in "#%":
                    if op == "#" or not frame.stack:
                        target = frame.labels[arg]
                        if isinstance(target, _Block):
                            frames.append(_frame(target))
                        else:
                            frame.position = target
                elif op == "|":
                    frame.stack[:] = history.get(frame.block, ())
                elif op in "<>":
                    registers[arg] = frame.stack.pop(0 if op == "<" else -1)
                elif op == "?":
                    byte = ord(stdin[read // 2])
                    registers[arg] = byte % 16 if read % 2 else byte // 16
                    read += 1
                elif op in "*!":
                    value = registers[arg] if arg in registers else int(arg, 16)
                    (frame.stack if op == "*" else written).append(value)
                elif op == "@":
                    halted = True
                else:
                    raise AssertionError(item)
        if halted or (len(frames) == 1 and root.position == len(root.code)):
            if len(written) % 2:
                written.append(0)
            trace.extend([view(halted=True)] * 4)
            return None, trace
        trace.append(view())
    raise AssertionError("Nybbleist model fixture exceeded its step bound")


def _machine(block, io):
    return prepare_machine(_source(block), {})(io)


def _view(machine):
    memory = machine.memory
    return memory["X"], memory["Y"], machine.stack


_check = checker(_predict, _view, cap=_STEPS)


def check_raw_nybbleist():
    same_label = _Block(("*9", "*8", "<Y", "!3Y"), "1")
    nested = _Block(("*5", same_label, "#1", ">X", "!3X"), "1")
    inner_history = _Block(("|", "%0", ">X", "!3X", "#2", ":0", "!41", ":2", "*4"), "1")
    outer_history = _Block(
        (inner_history, "|", "%0", ">X", "!3X", "#2", ":0", "!42", ":2", "*6"), "1"
    )
    for block, stdin, output in (
        (_Block(("*7", "#1", ">X", "!3X", "@", nested)), "", "9957"),
        (_Block(("*7", "#1", "#1", ">X", "!3X", "@", outer_history)), "", "AB467"),
        (_Block(("?X", "?Y", "!YX", "!4", "@")), "A", "\x14@"),
        (_Block(("!414",)), "", "A@"),
    ):
        error, trace = _check(_machine, block, stdin)
        assert error is None
        assert trace[-1][1:3] == (True, output)
