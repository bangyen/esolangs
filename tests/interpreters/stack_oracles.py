"""Bounded stack-language models sharing no production parser or transitions."""

from dataclasses import dataclass

from esolangs.exceptions import HaltError
from esolangs.runtime.io import ScriptedIO
from tests.support.model_input import matching_delimiter
from tests.support.workspace_oracle import WorkspaceWitness


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
                    span = matching_delimiter(code[pc + 1 :], "[", "]")
                    if span is None:
                        pc = len(code)
                        error = "syntax"
                    else:
                        pc += span
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
            span = matching_delimiter(code[after:], "(", ")")
            if span is None:
                error = "halt"
            else:
                stack.append(code[after : after + span - 1])
                after += span
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


def observed_stack(machine_type, code, stdin, steps, *, dynamic=False, workspace=None):
    """Observe complete state after each step, including the failing step."""
    io = ScriptedIO(stdin)
    machine = machine_type(code, io)
    error = None

    def snapshot():
        if workspace is not None:
            workspace(machine)
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


def agrees_stack(
    machine_type, oracle, code, stdin="", *, dynamic=False, cap=64, workspace=None
):
    expected = oracle(code, stdin, cap)
    capture = None
    if workspace is not None:
        model, project = workspace
        witness, rows = WorkspaceWitness(model), iter(expected)

        def capture(machine):
            parts = project(next(rows))
            captured = machine.workspace_snapshot()
            witness.sample(captured, parts)

    actual = observed_stack(
        machine_type, code, stdin, len(expected) - 1, dynamic=dynamic, workspace=capture
    )
    if workspace is not None:
        witness.finish()
    assert actual == expected, (code, stdin, actual, expected)
    return expected
