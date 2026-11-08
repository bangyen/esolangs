"""Tuple/list rewriting model of Stisp's grammar and execution sections.

https://esolangs.org/wiki/Stisp. Closed proper lists, nonlinear variables,
argument substitution, rule priority, frame insertion and bounded recursion.
Unmatched frames and result printing retain the public contract's decisions.
"""

from itertools import product

import pytest

from esolangs.languages.stisp.interpreter import _Machine
from tests.interpreters.oracle_support import observed, overread
from tests.support import workspace_oracle as workspace

_WORKSPACE = workspace.workspace_model("stisp-v1", "expression frames rendered")


def _text(term):
    return term if isinstance(term, str) else "(" + " ".join(map(_text, term)) + ")"


def _frames(frames):
    return "".join(
        " -> " + name + "[" + ", ".join(map(_text, args)) + "]" for name, args in frames
    )


def _unify(pattern, value, bindings):
    if isinstance(pattern, str):
        if pattern[0].islower():
            if pattern in bindings:
                return bindings[pattern] == value
            bindings[pattern] = value
            return True
        return pattern == value
    return (
        isinstance(value, tuple)
        and len(pattern) == len(value)
        and all(_unify(p, v, bindings) for p, v in zip(pattern, value, strict=True))
    )


def _substitute(term, bindings):
    if isinstance(term, str):
        return bindings.get(term, term)
    return tuple(_substitute(part, bindings) for part in term)


def _model(equations, head, frames):
    frames = list(frames)
    rendered, trace = False, []
    for tick in range(13):
        row = ((head, tuple(frames), rendered), not frames, "", 0, 0)
        trace.append(row)
        if not frames:
            final = ((head, (), True), True, _text(head), 0, 0)
            return None, trace + [final] * 3
        if tick == 12:
            break
        name, args = frames[0]
        for pattern, block, parameters, result, pending in equations:
            bindings = {}
            if name != block or not _unify(
                (pattern, parameters), (head, args), bindings
            ):
                continue
            head = _substitute(result, bindings)
            frames[:1] = [(n, _substitute(a, bindings)) for n, a in pending]
            break
        else:
            return "halt", [*trace, row]
    return None, trace


def _decode(term):
    if isinstance(term, str):
        return term
    parts = []
    while term:
        head, term = term
        parts.append(_decode(head))
    return tuple(parts)


def _view(machine):
    frames, pending = [], machine.frames
    while pending is not None:
        (name, args), pending = pending
        frames.append((name, tuple(map(_decode, args))))
    return _decode(machine.head), tuple(frames), machine.rendered


def _encode(term):
    if isinstance(term, str):
        return term
    result = ()
    for part in reversed(term):
        result = (_encode(part), result)
    return result


def _parts(row):
    head, frames, rendered = row[0]
    return (
        _encode(head),
        tuple((name, tuple(map(_encode, args))) for name, args in frames),
        rendered,
    )


def _check(factory, equations, head, frames):
    source = (
        "\n".join(
            _text(p)
            + _frames(((name, args),))
            + " = "
            + _text(result)
            + _frames(pending)
            + ";"
            for p, name, args, result, pending in equations
        )
        + "\n"
        + _text(head)
        + _frames(frames)
    )
    workspace.agrees(
        _model(equations, head, frames),
        (factory, source, "unused"),
        (_WORKSPACE, _parts),
        _view,
        context=source,
        cap=12,
    )


def check_raw_stisp():
    terms = ("A", "B", (), ("A",), ("A", "B"), (("B",), "A"))
    equations = (
        ("x", "same", ("x",), "YES", ()),
        ("x", "same", ("y",), "NO", ()),
        ("x", "pair", ("y",), ("x", "y"), ()),
        ("x", "copy", (), "x", (("same", ("x",)),)),
        ("x", "twice", (), "x", (("copy", ()), ("copy", ()))),
        (("x", "x"), "unpair", (), "x", ()),
        ("x", "forever", (), "x", (("forever", ()),)),
    )
    for head, arg in product(terms, repeat=2):
        for frames in (
            (),
            (("same", (arg,)),),
            (("pair", (arg,)),),
            (("twice", ()),),
            (("unpair", ()),),
            (("pair", (arg,)), ("copy", ())),
            (("forever", ()),),
        ):
            _check(_Machine, equations, head, frames)
    for source in ("", "x", "A -> f[", "x -> f[] = y; A -> f[]", "(A B . C)"):
        assert observed(_Machine, source, "unused", _view) == (
            "syntax",
            [(None, False, "", 0, 0)],
        )

    class SkipsFrame(_Machine):
        def step(self):
            if self.frames:
                self.frames = self.frames[1]
            else:
                super().step()

    class RepeatsResult(_Machine):
        def step(self):
            if self.halted:
                self.rendered = False
            super().step()

    for factory, frames in (
        (SkipsFrame, (("pair", ("B",)),)),
        (RepeatsResult, ()),
        (overread(_Machine), (("copy", ()),)),
    ):
        with pytest.raises(AssertionError):
            _check(factory, equations, "A", frames)

    workspace.check_erasures(
        _WORKSPACE, _check, _Machine, equations, "A", (("pair", ("B",)),)
    )
