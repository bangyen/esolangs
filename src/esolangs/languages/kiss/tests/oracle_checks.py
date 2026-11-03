"""Revision 159488 Kiss, using whole application trees and head rewrites."""

import itertools
import random

import pytest

from esolangs.languages.kiss.interpreter import _Machine
from tests.interpreters.oracle_support import observed


def _parse(source):
    tokens = iter(c for c in source if not c.isspace())

    def group(*, nested):
        term = None
        for char in tokens:
            if char == ")":
                if not nested or term is None:
                    raise ValueError
                return term
            if char == "(":
                atom = group(nested=True)
            elif char in "KS":
                atom = char
            else:
                raise ValueError
            term = atom if term is None else [term, atom]
        if nested or term is None:
            raise ValueError
        return term

    return group(nested=False)


def _spine(term):
    args = []
    while not isinstance(term, str):
        args.append(term[1])
        term = term[0]
    return [term, *reversed(args)]


def _dag(items):
    """Lossless shared observation format; no reduction is performed here."""
    memo, nodes, edges = {}, {}, []

    def ref(term):
        if isinstance(term, str):
            return term
        if id(term) not in memo:
            pair = ref(term[0]), ref(term[1])
            if pair not in nodes:
                nodes[pair] = len(edges)
                edges.append(pair)
            memo[id(term)] = nodes[pair]
        return memo[id(term)]

    return tuple(map(ref, items)), tuple(edges)


def _model(source, stdin):
    try:
        term = _parse(source)
    except ValueError:
        return "syntax", [(None, False, "", 0, 0)]
    consumed, ended, bits, exit_code, output, error = 0, False, 0, None, "", None

    def view():
        items = _spine(term)
        return (
            (_dag(items), ended, bits, exit_code, (len(items) - 1,)),
            exit_code is not None,
            output,
            consumed,
            consumed,
        )

    trace = [view()]
    for _ in range(16):
        if exit_code is not None:
            break
        head, *args = _spine(term)
        arity = 2 if head == "K" else 3
        if len(args) >= arity:
            result = (
                args[0] if head == "K" else [[args[0], args[2]], [args[1], args[2]]]
            )
            for arg in args[arity:]:
                result = [result, arg]
            term = result
        elif not args:
            exit_code = int(head == "S")
        elif len(args) == 1:
            output += "0" if head == "K" else "1"
            term = args[0]
        elif ended or consumed == len(stdin):
            ended, error = True, "input"
        else:
            char = stdin[consumed]
            consumed += 1
            if char == "\n":
                ended, error = True, "input"
            elif char not in "01":
                error = "argument"
            else:
                bits += 1
                term = args[int(char)]
        trace.append(view())
        if error:
            break
    if exit_code is not None:
        trace.extend([view()] * 3)
    return error, trace


def _agrees(factory, source, stdin):
    expected = _model(source, stdin)
    assert (
        observed(
            factory,
            source,
            stdin,
            lambda m: (_dag(m.stack), m.ended, m.bits, m.exit_code, m.ip),
            cap=16,
        )
        == expected
    ), (source, stdin)
    return expected


def check_raw_kiss():
    corpus = [
        "".join(p) for n in range(1, 6) for p in itertools.product("KS", repeat=n)
    ]
    rng = random.Random(20261103)
    corpus += [
        " ".join(rng.choices(("K", "S", "(K K)", "(S K)", "(S S S)", "(S (K S))"), k=4))
        for _ in range(64)
    ]
    corpus += [
        "S (K K) (S K)",
        "S(S S)(S S)",
        "K (S K K) S K",
        "S (K (S K K)) (S K K) K",
        " K\nS ",
        "",
        "()",
        "(K",
        "K)",
        "x",
        "( )",
        "K(",
    ]
    corpus.append("S(SKK)(SKK)(S(SKK)(SKK))")
    inputs = ("", "0", "1\nextra", "\n1", "x", " 0")
    results = [_agrees(_Machine, code, stdin) for code in corpus for stdin in inputs]
    assert {error for error, _ in results} == {None, "syntax", "input", "argument"}
    assert any(not trace[-1][1] for error, trace in results if error is None)
    assert _model("S (K K) (S K)", "0")[1][-1][2] == "0"
    assert _model("S (K K) (S K)", "1")[1][-1][2] == "1"
    controls = {
        "K": ("K S K", ""),
        "S": ("S K K S", ""),
        "input": ("S K S", "0"),
        "exit": ("S", ""),
        "posthalt": ("K", ""),
    }
    for fault, (source, stdin) in controls.items():

        class Fault(_Machine):
            mode = fault

            def __init__(self, code, io):
                if self.mode == "input":
                    read = io.input_char
                    io.input_char = lambda: ord("1") if read() == ord("0") else ord("0")
                super().__init__(code, io)

            def step(self):
                if self.halted:
                    if self.mode == "posthalt":
                        self.io.print_str("extra")
                    return
                before = self.state
                super().step()
                if (self.mode == "K" and before[0] == "K") or (
                    self.mode == "S" and before[0] == "S"
                ):
                    self.state = "K", None
                elif self.mode == "exit" and self.halted:
                    self.exit_code = 0

        with pytest.raises(AssertionError):
            _agrees(Fault, source, stdin)
    return len(results), len(controls)
