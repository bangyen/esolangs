"""Revision 158921 Codesick, using a character lexer and sequential string maps."""

import itertools
import random

import pytest

from esolangs.languages.codesick.interpreter import _Machine
from tests.interpreters.oracle_support import observed


def _tokens(source):
    at = 0
    while at < len(source):
        if source[at].isspace():
            at += 1
            continue
        start = at
        if source[at] == ";":
            at += 1
            yield start, None
        elif source[at] == '"':
            at += 1
            text = []
            while at < len(source):
                char = source[at]
                if char == "\\" and at + 1 < len(source) and source[at + 1] == '"':
                    text.append('"')
                    at += 2
                elif char == '"':
                    at += 1
                    break
                else:
                    text.append(char)
                    at += 1
            else:
                raise ValueError
            yield start, ("".join(text), False)
        else:
            while (
                at < len(source) and not source[at].isspace() and source[at] not in ';"'
            ):
                at += 1
            yield start, (source[start:at], True)


def _instruction(words, offset):
    keyword = ("codesick", True)
    if words and words[0] == keyword:
        label, args = None, words[1:]
    elif len(words) > 1 and words[1] == keyword:
        label, args = words[0], words[2:]
    else:
        raise ValueError
    if len(args) not in (4, 5) or keyword in args or label == keyword:
        raise ValueError
    if label == ("out", True) or ("out", True) in args[1:]:
        raise ValueError
    if len(args) == 4:
        args = [*args[:2], ("", False), *args[2:]]
    return offset, label, args


def _parse(source, stdin):
    words, pending, offset, literals = [], [], 0, set()
    for at, token in _tokens(source):
        if not words:
            offset = at
        if token is not None:
            words.append(token)
            continue
        instruction = _instruction(words, offset)
        label = instruction[1]
        if label is not None and label != ("in", True):
            if label[0] in literals:
                raise ValueError
            literals.add(label[0])
        pending.append(instruction)
        words = []
    if words:
        raise ValueError
    reads = any(
        token == ("in", True) for _, label, args in pending for token in [label, *args]
    )

    def resolve(token):
        if token is None or token == ("out", True):
            return None
        return stdin if token == ("in", True) else token[0]

    program = [
        (at, resolve(label), *(resolve(arg) for arg in args))
        for at, label, args in pending
    ]
    return program, reads


def _model(source, stdin):
    try:
        program, reads = _parse(source, stdin)
    except ValueError:
        return "syntax", [(None, False, "", 0, 0)]
    labels = {row[1]: i for i, row in enumerate(program) if row[1] is not None}
    memory, pc, output = {}, 0 if program else None, ""
    consumed = len(stdin) if reads else 0

    def star(name):
        return memory.get(name, name)

    def view():
        changed = tuple(sorted((k, v) for k, v in memory.items() if k != v))
        ip = len(source) if pc is None else program[pc][0]
        return ((pc, changed, ip), pc is None, output, consumed, consumed)

    trace = [view()]
    # Eight transitions bound alias-driven repeated string doubling.
    for _ in range(8):
        if pc is None:
            break
        _, _, a, b, c, d, e = program[pc]
        if a is None:
            output += b
        else:
            memory[a] = star(a) + star(b)
        memory[c] = star(star(c))
        destination = e
        if a is not None:
            text, needle = star(a), star(d)
            found = text.find(needle)
            if found >= 0:
                memory[a] = text[:found] + text[found + len(needle) :]
                destination = d  # repo jump/output adapters follow the primary examples
        pc = labels.get(destination)
        trace.append(view())
    if pc is None:
        trace.extend([view()] * 3)
    return None, trace


def _agrees(factory, source, stdin):
    expected = _model(source, stdin)
    assert (
        observed(
            factory,
            source,
            stdin,
            lambda m: (m.pc, tuple(sorted(m.memory.items())), m.ip),
            cap=8,
        )
        == expected
    ), (source, stdin)
    return expected


def _quoted(text):
    return '"' + text.replace('"', '\\"') + '"'


def check_raw_codesick():
    corpus = [
        "a codesick " + " ".join(map(_quoted, args)) + ' "halt";'
        for args in itertools.product(("a", "b", ""), repeat=4)
    ]
    rng = random.Random(20261103)
    corpus.extend(
        "\n".join(
            f"{label} codesick "
            + " ".join(
                _quoted(rng.choice(("a", "b", "c", "", "halt"))) for _ in range(5)
            )
            + ";"
            for label in ("a", "b", "c")
        )
        for _ in range(64)
    )
    corpus += [
        "",
        " \n",
        'codesick out "Hello, world!" * *;',
        "cat codesick out in * cat;",
        "codesick out 4 * *;",
        "codesick in a 0 1; 0 codesick out 0 * halt; 1 codesick out 1 * 1;",
        "in codesick out in * in;",
        'in codesick out x * in; "x" codesick out y * halt;',
        'codesick "out" "in" "codesick" "x";',
        'codesick out "a; b" * *;',
        r'codesick out "a\"b" * *;',
        "codesick a a a a halt;",
        'codesick "" "" "" "" "";',
        'codesick out "λ\n" * *;',
    ]
    corpus += [r'codesick out "a\b" * *;', r"codesick out \ * *;"]
    inputs = ("", "0", "1", "x", "λ\n")
    results = [_agrees(_Machine, code, stdin) for code in corpus for stdin in inputs]
    invalid = (
        ";",
        "codesick;",
        "codesick a b c;",
        "codesick a b c d e f;",
        "out codesick a b c d;",
        "codesick a out c d;",
        "codesick a codesick c d;",
        "a codesick x x x x; a codesick y y y y;",
        "codesick in a b c",
        'codesick out "unterminated * *;',
        'codesick out "x\\" * *;',
    )
    invalid += ('codesick out in * *; codesick out "x\\" * *;',)
    results += [_agrees(_Machine, code, "unread") for code in invalid]
    assert {error for error, _ in results} == {None, "syntax"}
    assert any(not trace[-1][1] for error, trace in results if error is None)
    assert _model('codesick out "Hello, world!" * *;', "")[1][-1][2] == "Hello, world!"
    controls = {
        "append": ("codesick a b x z halt;", ""),
        "delete": ("codesick aaa a x a halt;", ""),
        "alias": ("codesick a b a z halt;", ""),
        "output": ("codesick out a * halt;", ""),
        "input": ("codesick out in * halt;", "abc"),
        "quoted": ('codesick out "in" * halt;', "abc"),
        "syntax": ("codesick in a b c", "unread"),
        "offset": ("  codesick out x * halt;", ""),
        "posthalt": ("codesick out x * halt;", ""),
    }
    for fault, (source, stdin) in controls.items():

        class Fault(_Machine):
            mode = fault

            def __init__(self, code, io):
                if self.mode == "input":
                    io.input_all = lambda: "abc"
                elif self.mode == "quoted":
                    code = code.replace('"in"', "in")
                super().__init__(code + ";" if self.mode == "syntax" else code, io)
                if self.mode == "offset":
                    self.offsets = [0] * len(self.offsets)

            def step(self):
                if self.halted:
                    if self.mode == "posthalt":
                        self.io.print_str("extra")
                    return
                instruction = self.program[self.pc]
                super().step()
                _, a, _b, _c, _d, _e = instruction
                if self.mode == "append":
                    self.memory[a] = "wrong"
                elif self.mode == "delete":
                    self.memory[a] = ""
                elif self.mode == "alias":
                    self.memory[a] = "a"
                elif self.mode == "output":
                    self.io.print_str("\n")

        with pytest.raises(AssertionError):
            _agrees(Fault, source, stdin)
    return len(results), len(controls)
