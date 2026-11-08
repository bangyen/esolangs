"""Revision 189093 Suffolk, using sparse cells and an explicit cyclic cursor."""

import itertools
import random
from unittest.mock import patch

import pytest

from esolangs.languages.suffolk import interpreter as suffolk
from esolangs.languages.suffolk.interpreter import _Machine
from esolangs.runtime.io import ScriptedIO
from tests.interpreters.oracle_support import checker as oracle_checker


def _model(source, stdin):
    if not source:
        return "syntax", [(None, False, "", 0, 0)]
    pc, pointer, accumulator, extent, cells = 0, 0, 0, 1, {}
    consumed, exhausted, output, error = 0, False, "", None

    def view():
        tape = tuple(cells.get(i, 0) for i in range(extent))
        return (
            (pc, pointer, accumulator, tape, tape, pc),
            exhausted,
            output,
            consumed,
            consumed,
        )

    trace = [view()]
    for _ in range(64):
        if exhausted:
            break
        command = source[pc]
        if command == ">":
            pointer += 1
            extent = max(extent, pointer + 1)
        elif command == "<":
            accumulator += cells.get(pointer, 0)
            pointer = 0
        elif command == "!":
            cells[pointer] = max(0, cells.get(pointer, 0) + 1 - accumulator)
            pointer, accumulator = 0, 0
        elif command == ",":
            if consumed == len(stdin):
                accumulator, exhausted = 0, True
            else:
                accumulator += ord(stdin[consumed])
                consumed += 1
        elif command == "." and accumulator:
            if accumulator - 1 > 0x10FFFF:
                error = "syntax"  # native chr rejects a code beyond Unicode
            else:
                output += chr(accumulator - 1)
        if not error:
            pc = (pc + 1) % len(source)
        trace.append(view())
        if error:
            break
    if exhausted:
        trace.extend([view()] * 3)
    return error, trace


_agrees = oracle_checker(_model, lambda m: (*m.state, tuple(m.memory), m.ip))


def _run_agrees(runner, source, stdin):
    error, trace = _model(source, stdin)
    assert error is None
    seen = set()
    for state, halted, output, consumed, progress in trace:
        key = (*state[:4], progress, halted)
        if halted or key in seen:
            expected = output, consumed, progress
            break
        seen.add(key)
    else:
        raise AssertionError("runner case has no bounded stop certificate")

    class Bounded(_Machine):
        steps = 0

        def step(self):
            self.steps += 1
            assert self.steps <= 64, "runner exceeded the independent stop certificate"
            super().step()

    io = ScriptedIO(stdin)
    with patch.object(suffolk, "_Machine", Bounded):
        runner(source, io)
    assert (io.getvalue(), io.position(), io.progress()) == expected


def _runner_checks():
    cases = (("x", ""), ("!<.", ""), (",.", "\x00\x00"), (",.", "B"))
    for source, stdin in cases:
        _run_agrees(suffolk.run, source, stdin)

    def missing_input_progress(source, io):
        from esolangs.languages.suffolk.interpreter import _Machine as CurrentMachine

        machine, seen = CurrentMachine(source, io), set()
        while not machine.halted:
            key = machine.state
            if key in seen:
                return
            seen.add(key)
            machine.step()

    with pytest.raises(AssertionError):
        _run_agrees(missing_input_progress, ",.", "\x00\x00")
    return len(cases)


def check_raw_suffolk():
    atoms = "><!,.x"
    corpus = ["".join(p) for n in range(4) for p in itertools.product(atoms, repeat=n)]
    rng = random.Random(20261103)
    corpus += ["".join(rng.choices(atoms, k=16)) for _ in range(128)]
    corpus += [
        ">!><",
        ",,.",
        ".",
        "!<!<<!",
        "!,.",
        ",>!<.",
        ">>!>>><",
        "λ\n",
        ">" * 80,
        "x",
    ]
    inputs = ("", "AB\n", "\x00\xff", "λ", "\U0010ffff" * 2)
    results = [
        _agrees(_Machine, source, stdin) for source in corpus for stdin in inputs
    ]
    assert {error for error, _ in results} == {None, "syntax"}
    assert any(not trace[-1][1] for error, trace in results if error is None)
    assert _model(",.", "B")[1][-1][2] == "A"
    controls = {
        "right": (">", ""),
        "rewind": (">!><", ""),
        "sum": ("!<", ""),
        "clamp": (",!", "B"),
        "clear": (",!", "B"),
        "read": (",,", "AB"),
        "eof": (",", ""),
        "output": (",.", "B"),
        "wrap": ("x", ""),
        "syntax": ("", ""),
        "posthalt": (",", ""),
    }
    for fault, (source, stdin) in controls.items():

        class Fault(_Machine):
            mode = fault

            def __init__(self, code, io):
                if self.mode == "eof":
                    io.input_char = lambda: 0
                super().__init__("x" if self.mode == "syntax" else code, io)

            def step(self):
                if self.halted:
                    if self.mode == "posthalt":
                        self.io.print_str("extra")
                    return
                pc, pointer, acc, tape = self.state
                command = self.code[pc]
                super().step()
                at, ptr, total, values = self.state
                if (self.mode == "right" and command == ">") or (
                    self.mode == "rewind" and command == "<"
                ):
                    ptr = pointer
                elif self.mode == "sum" and command == "<":
                    total = acc
                elif self.mode == "clamp" and command == "!":
                    changed = list(values)
                    changed[pointer] = tape[pointer] + 1 - acc
                    values = tuple(changed)
                elif self.mode == "clear" and command == "!":
                    total = acc
                elif self.mode == "read" and command == "," and not self.halted:
                    total -= acc
                elif self.mode == "output" and command == ".":
                    self.io.print_str("\n")
                elif self.mode == "wrap":
                    self._exhausted = True
                self.state = at, ptr, total, values

        with pytest.raises(AssertionError):
            _agrees(Fault, source, stdin)
    return len(results) + _runner_checks(), len(controls) + 1
