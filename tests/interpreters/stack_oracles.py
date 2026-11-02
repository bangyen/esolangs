"""Bounded stack-language models sharing no production parser or transitions."""

from dataclasses import dataclass

from esolangs.exceptions import HaltError
from esolangs.runtime.io import ScriptedIO


@dataclass(frozen=True)
class StackObservation:
    code: str
    ip: int
    stack: tuple[int | str, ...]
    loops: tuple[int, ...]
    output: str
    consumed: int
    halted: bool
    error: str | None


def bfstack(code: str, stdin: str, cap: int = 64) -> list[StackObservation]:
    """Scan skipped brackets at runtime; entered unmatched openers are legal."""
    stack, loops, output = [], [], []
    pc = consumed = 0
    error = None

    def snapshot():
        return StackObservation(
            code,
            pc,
            tuple(stack),
            tuple(loops),
            "".join(output),
            consumed,
            pc == len(code),
            error,
        )

    trace = [snapshot()]
    for _ in range(cap):
        if pc == len(code):
            break
        command = code[pc]
        if (command in "<+-.[" and not stack) or (command == "]" and not loops):
            error = "halt"
        elif command == "," and consumed == len(stdin):
            error = "input"
        else:
            if command == ">":
                stack.append(0)
            elif command == "<":
                stack.pop()
            elif command in "+-":
                stack[-1] = (stack[-1] + (1 if command == "+" else -1)) % 256
            elif command == ".":
                output.append(chr(stack[-1]))
            elif command == ",":
                stack.append(ord(stdin[consumed]))
                consumed += 1
            elif command == "[":
                if stack[-1]:
                    loops.append(pc)
                else:
                    depth = 1
                    while depth and pc + 1 < len(code):
                        pc += 1
                        depth += (code[pc] == "[") - (code[pc] == "]")
                    if depth:
                        pc = len(code)
                        error = "syntax"
            elif command == "]":
                pc = loops.pop() - 1
            if not error:
                pc += 1
        trace.append(snapshot())
        if error:
            break
    return trace


def underload(code: str, _stdin: str, cap: int = 64) -> list[StackObservation]:
    """Interpret growing source strings and bound their total live text."""
    stack, output = [], []
    pc = 0
    error = None

    def snapshot():
        return StackObservation(
            code, pc, tuple(stack), (), "".join(output), 0, pc == len(code), error
        )

    trace = [snapshot()]
    for _ in range(cap):
        if pc == len(code):
            break
        command = code[pc]
        after = pc + 1
        if command == "(":
            depth, end = 1, after
            while end < len(code) and depth:
                depth += (code[end] == "(") - (code[end] == ")")
                end += 1
            if depth:
                error = "halt"
            else:
                stack.append(code[after : end - 1])
                after = end
        elif command.isspace():
            pass
        elif command not in "~:!*a^S" or len(stack) < (2 if command in "~*" else 1):
            error = "halt"
        elif command == "~":
            stack[-2:] = reversed(stack[-2:])
        elif command == ":":
            stack.append(stack[-1])
        elif command == "!":
            stack.pop()
        elif command == "*":
            right = stack.pop()
            stack[-1] += right
        elif command == "a":
            stack[-1] = "(" + stack[-1] + ")"
        elif command == "^":
            code = code[:after] + stack.pop() + code[after:]
        else:
            output.append(stack.pop())
        if not error:
            pc = after
        trace.append(snapshot())
        if error or len(code) + sum(map(len, stack)) > 4096:
            break
    return trace


def observed_stack(machine_type, code, stdin, steps, *, dynamic=False):
    """Observe complete state after each step, including the failing step."""
    io = ScriptedIO(stdin)
    machine = machine_type(code, io)
    error = None

    def snapshot():
        return StackObservation(
            machine.state[0] if dynamic else code,
            machine.ip,
            tuple(machine.stack),
            () if dynamic else machine.lst,
            io.getvalue(),
            io.position(),
            machine.halted,
            error,
        )

    trace = [snapshot()]
    for _ in range(steps):
        if machine.halted:
            break
        try:
            machine.step()
        except HaltError:
            error = "halt"
        except ValueError:
            error = "syntax"
        except EOFError:
            error = "input"
        trace.append(snapshot())
        if error:
            break
    return trace


def agrees_stack(machine_type, oracle, code, stdin="", *, dynamic=False):
    expected = oracle(code, stdin)
    actual = observed_stack(
        machine_type, code, stdin, len(expected) - 1, dynamic=dynamic
    )
    assert actual == expected, (code, stdin, actual, expected)
    return expected
