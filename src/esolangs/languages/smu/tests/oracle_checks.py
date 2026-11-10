"""Run-level string evaluator using explicit bit streams."""

import re
from itertools import product

import pytest

from esolangs.exceptions import HaltError
from esolangs.languages.smu.interpreter import _Machine
from esolangs.runtime.io import ScriptedIO
from tests.interpreters.oracle_support import observed
from tests.support import workspace_oracle as workspace

_WORKSPACE = workspace.workspace_model(
    "smu-v1",
    "code instruction fresh stopped stack variables incoming remaining "
    "outgoing used input_cursor",
)


def _instructions(code):
    """Yield literal contents or individual commands."""
    start = None
    depth = 0
    for index, char in enumerate(code):
        if char == "(":
            if not depth:
                start = index + 1
            depth += 1
        elif char == ")":
            depth -= 1
            if depth < 0:
                raise ValueError
            if not depth:
                yield True, code[start:index]
        elif not depth:
            yield False, char
    if depth:
        raise ValueError


def _model(code, stdin):
    stack = []
    variables = {}
    output = []
    bits = ["|+"[(ord(char) >> shift) & 1] for char in stdin for shift in range(8)]
    reads = 0
    steps = 0
    error = None
    while steps < 64:
        try:
            instructions = list(_instructions(code))
        except ValueError:
            error = "halt"
            break
        stack.append(bits[reads] if reads < len(bits) else "=")
        reads += reads < len(bits)
        steps += len(instructions) + 2
        for literal, token in instructions:
            if literal:
                stack.append(token)
            elif token == "|" and stack:
                text = stack.pop()
                if text:
                    stack.extend((text[1:], text[0]))
            elif token in "=+" and len(stack) >= 2:
                right, left = stack.pop(), stack.pop()
                if token == "=":
                    variables[right] = left
                else:
                    stack.append(variables.get(left, "") + variables.get(right, ""))
        text = stack.pop() if stack else ""
        if re.search(r"[^|+=]", text):
            error = "halt"
            break
        output.extend(int(char == "+") for char in text if char != "=")
        if not stack:
            break
        code = stack.pop()
    else:
        raise AssertionError("oracle corpus must terminate")
    packed = "".join(
        chr(sum(bit << shift for shift, bit in enumerate(output[i : i + 8])))
        for i in range(0, len(output) - (len(output) % 8 if error else 0), 8)
    )
    return error, packed, (reads + 7) // 8, stack, variables


def _command(code, pc, stack, variables):
    """Apply one independently decoded command to reference containers."""
    token = code[pc]
    pc += 1
    if token == "(":
        start, depth = pc, 1
        while depth:
            depth += (code[pc] == "(") - (code[pc] == ")")
            pc += 1
        stack.append(code[start : pc - 1])
    elif token == "|" and stack:
        text = stack.pop()
        if text:
            stack.extend((text[1:], text[0]))
    elif token in "=+" and len(stack) >= 2:
        right, left = stack.pop(), stack.pop()
        if token == "=":
            variables[right] = left
        else:
            stack.append(variables.get(left, "") + variables.get(right, ""))
    return pc


def _trace(code, stdin):
    """Step strings and bit buffers independently at every public boundary."""
    stack, variables = [], {}
    pc = incoming = remaining = outgoing = used = cursor = 0
    reads = past_end = 0
    fresh, stopped = True, False
    output, error, trace = "", None, []

    def row():
        parts = (
            code,
            pc,
            fresh,
            stopped,
            tuple(stack),
            frozenset(variables.items()),
            incoming,
            remaining,
            outgoing,
            used,
            cursor,
        )
        return (parts, reads, past_end), stopped, output, cursor, cursor

    trace.append(row())
    for _ in range(64):
        if fresh:
            if not remaining and cursor < len(stdin):
                incoming = ord(stdin[cursor]) % 256
                cursor += 1
                reads += 1
                remaining = 8
            if remaining:
                stack.append("+" if incoming % 2 else "|")
                incoming //= 2
                remaining -= 1
            else:
                past_end += 1
                stack.append("=")
            fresh = False
        elif pc < len(code):
            pc = _command(code, pc, stack, variables)
        else:
            text = stack.pop() if stack else ""
            if set(text) - set("|+="):
                error = "halt"
            else:
                for bit in text:
                    if bit != "=":
                        outgoing += (bit == "+") * 2**used
                        used += 1
                        if used == 8:
                            output += chr(outgoing)
                            outgoing = used = 0
                if not stack:
                    if used:
                        output += chr(outgoing)
                        outgoing = used = 0
                    stopped = True
                else:
                    candidate = stack.pop()
                    try:
                        list(_instructions(candidate))
                    except ValueError:
                        error = "halt"
                    else:
                        code, pc, fresh = candidate, 0, True
        trace.append(row())
        if error:
            break
        if stopped:
            trace.extend([row()] * 3)
            break
    else:
        raise AssertionError("oracle corpus must terminate within 64 steps")
    return error, trace


def _check_workspace(factory, source, expanded, stdin):
    expected = _trace(expanded, stdin)

    def view(machine):
        parts = (
            machine.code,
            machine.pc,
            machine.fresh,
            machine.done,
            tuple(machine.stack),
            frozenset(machine.values.items()),
            machine.incoming,
            machine.remaining,
            machine.outgoing,
            machine.used,
            machine.io.progress(),
        )
        return parts, machine.io.reads, machine.io.past_end

    checked = workspace.workspace_view(
        expected[1], _WORKSPACE, lambda row: row[0][0], view
    )
    assert observed(factory, source, stdin, checked, cap=64) == expected, (
        source,
        stdin,
    )


def _check(factory, source, expanded, stdin):
    io = ScriptedIO(stdin)
    machine = factory(source, io)
    error = None
    try:
        for _ in range(64):
            if machine.halted:
                break
            machine.step()
        else:
            raise AssertionError("interpreter exceeded the corpus bound")
    except HaltError:
        error = "halt"
    actual = error, io.getvalue(), io.position(), machine.stack, machine.values
    assert actual == _model(expanded, stdin), (source, stdin)
    _check_workspace(factory, source, expanded, stdin)


def check_raw_smu():
    tokens = ("()", "(+)", "(|)", "(=)", "((+))", "|", "+", "=")
    for commands, stdin in product(product(tokens, repeat=3), ("", "A", "ÿ")):
        code = "".join(commands)
        _check(_Machine, code, code, stdin)
    for source, expanded in (
        ("9x(+++++++++)9x 9x & ignored\n= ", "(+++++++++)="),
        ("a(+)a b a (|) b b", "(+)(|)"),
        ("(+)()=()()+=()", "(+)()=()()+=()"),
        ("((+))((|))", "((+))((|))"),
    ):
        _check(_Machine, source, expanded, "A")

    _check(_Machine, "()()()", "()()()", "Ā")

    class MissingOutput(_Machine):
        def _write(self, _text):
            pass

    with pytest.raises(AssertionError):
        _check(MissingOutput, "(+)", "(+)", "")

    # Populate variables, both bit buffers, dynamic programs and failed boundaries.
    for code, stdin in (
        ("(+)()=()()+=()", "A"),
        ("(+++++++++)", ""),
        ("(|+|+|+|+)", "ÿ"),
        ("(())|()", ""),
        ("((+))", ""),
        ("", ""),
        ("", "Ā"),
        ("()", ""),
    ):
        _check_workspace(_Machine, code, code, stdin)
        workspace.check_erasures(
            _WORKSPACE, _check_workspace, _Machine, code, code, stdin
        )

    repeated_eof = _trace("()", "")
    assert repeated_eof[1][-1][0][1:] == (0, 2)

    class ErasedReadCounts(_Machine):
        def _read_bit(self):
            value = super()._read_bit()
            self.io._reads = self.io._past_end = 0
            return value

    for stdin in ("", "A"):
        with pytest.raises(AssertionError):
            _check_workspace(ErasedReadCounts, "()", "()", stdin)
