"""Raw BFStack corpus, including lazy bracket errors and a broken push control."""

import itertools
import random
from contextlib import suppress

import pytest

from esolangs.languages.bfstack.interpreter import _Machine
from esolangs.runtime.io import ScriptedIO
from tests.interpreters.oracle_support import decorate_io
from tests.interpreters.stack_oracles import agrees_stack as _agrees_stack
from tests.interpreters.stack_oracles import bfstack
from tests.support.workspace_oracle import (
    WorkspaceWitness,
    charged_bits,
    check_erasures,
    workspace_model,
)

_WORKSPACE = workspace_model(
    "bfstack-v1", "data_stack loop_stack instruction input_cursor"
)


def _parts(row):
    return row.stack, row.loops, row.ip, row.consumed


def agrees_stack(*args, **kwargs):
    return _agrees_stack(*args, **kwargs, workspace=(_WORKSPACE, _parts))


def corpus():
    corpus = [
        "".join(seq)
        for n in range(4)
        for seq in itertools.product("><+-,.[]x", repeat=n)
    ]
    corpus += [">+[", ">[", ">+[]", ">+[>+<-]>.", ",[.<,]"]
    corpus += [">[[+]]", ">+[[", ">+<]", ">[[]"]
    corpus += [">" + "+" * 256 + ".", ">-."]
    rng = random.Random(20261102)
    corpus += [
        "".join(
            rng.choices([">", "<", "+", "-", ",", ".", "[", "]", "[-]", "[>+<-]"], k=8)
        )
        for _ in range(64)
    ]
    for stdin in ("", "\x00\xff", "A\nB", "λ"):
        for code in corpus:
            yield code, stdin, 64
    for code, stdin in (
        (",+.", "\xff"),
        (",-.", "\0"),
        (",.", "λ"),
        (",.", "😀"),
        (",.", "\ud800"),
        ("x\n\rλ", ""),
        (">[", ""),
        (">+[", ""),
        (",", ""),
        (">+[]", ""),
    ):
        yield code, stdin, 64


def check_raw_bfstack() -> None:
    results = [
        agrees_stack(_Machine, bfstack, code, stdin, cap=cap)[-1]
        for code, stdin, cap in corpus()
    ]
    assert {r.error for r in results} == {None, "input", "syntax", "halt"}
    assert any(not r.halted and not r.error for r in results)
    assert any(r.loops and r.halted for r in results)
    assert bfstack(">+[", "")[-1].loops == (2,)
    assert bfstack(">[", "")[-1].halted
    assert bfstack(">-.", "")[-1].output == "\xff"

    class WrongPush(_Machine):
        def step(self):
            push = not self.halted and self.code[self.ip] == ">"
            super().step()
            if push:
                self.state = type(self.state)(self.ind, (*self.stk[:-1], 1), self.lst)

    with pytest.raises(AssertionError):
        agrees_stack(WrongPush, bfstack, ">+.")

    check_erasures(_WORKSPACE, agrees_stack, _Machine, bfstack, ",[.-]", "A")

    wrong_text = decorate_io(
        _Machine, "print_char", lambda write: lambda char: write(chr(ord(char) ^ 1))
    )

    with pytest.raises(AssertionError):
        agrees_stack(wrong_text, bfstack, ",.", "A")
    for code, stdin in ((",", ""), (">[", "")):
        machine = _Machine(code, ScriptedIO(stdin))
        witness = WorkspaceWitness(_WORKSPACE)
        for row in bfstack(code, stdin):
            witness.sample(machine.workspace_snapshot(), _parts(row))
            if row.error or row.halted:
                break
            with suppress(EOFError, ValueError):
                machine.step()
        for attempt in range(2, 5):
            if code == ",":
                with pytest.raises(EOFError):
                    machine.step()
            else:
                machine.step()
            witness.sample(machine.workspace_snapshot(), _parts(row))
            assert machine.io.position() == machine.io.progress() == row.consumed
            assert machine.io.getvalue() == row.output
            assert machine.halted == row.halted
            assert machine.io.reads == row.consumed
            assert machine.io.past_end == (attempt if code == "," else 0)
    for code, stdin, bits in (
        ("", "", 0),
        (">", "", 2),
        (">+[", "", 5),
        (">[", "", 3),
        (",+.", "\xff", 11),
        (",-.", "\0", 11),
        (",.", "😀", 20),
    ):
        rows = agrees_stack(_Machine, bfstack, code, stdin)
        assert charged_bits(_WORKSPACE, map(_parts, rows)) == bits
    assert bfstack(",+.", "\xff")[-1].output == "\0"
    assert bfstack(",-.", "\0")[-1].output == "\xff"
