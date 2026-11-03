"""Sticker geometry computed with dot and cross products."""

from itertools import product

import pytest

from esolangs.languages.rubic.interpreter import _Machine
from esolangs.runtime.io import ScriptedIO

_NORMALS = {
    "w": (0, 1, 0),
    "w'": (0, -1, 0),
    "g": (0, 0, 1),
    "g'": (0, 0, -1),
    "o": (-1, 0, 0),
    "o'": (1, 0, 0),
}
_LAYERS = dict(
    zip("udfblrmes", ("w", "w'", "g", "g'", "o", "o'", "o'", "w", "g"), strict=True)
)


def _dot(a, b):
    return sum(x * y for x, y in zip(a, b, strict=True))


def _quarter(vector, axis):
    x, y, z = vector
    a, b, c = axis
    cross = (y * c - z * b, z * a - x * c, x * b - y * a)
    parallel = _dot(vector, axis)
    return tuple(
        component + parallel * normal
        for component, normal in zip(cross, axis, strict=True)
    )


def _model(turns):
    stickers = [
        (position, normal, colour)
        for position in product((-1, 0, 1), repeat=3)
        for colour, normal in _NORMALS.items()
        if _dot(position, normal) == 1
    ]
    for face, suffix in turns:
        axis = _NORMALS[_LAYERS[face]]
        layer = int(face not in "mes")
        for _ in range({"": 1, "2": 2, "'": 3}[suffix]):
            stickers = [
                (_quarter(p, axis), _quarter(n, axis), c)
                if _dot(p, axis) == layer
                else (p, n, c)
                for p, n, c in stickers
            ]
    centres = {colour: normal for p, normal, colour in stickers if p == normal}
    return "".join(
        chr(
            sum(
                n == centres[face] and p != n and colour == target
                for p, n, colour in stickers
            )
        )
        for face, target in product(_NORMALS, repeat=2)
    )


def _check(factory, turns):
    source = " ".join(
        [face.upper() + suffix for face, suffix in turns]
        + [f".{face}{target} !" for face, target in product(_NORMALS, repeat=2)]
    )
    io = ScriptedIO("unused")
    machine = factory(source, io)
    for _ in range(80):
        if machine.halted:
            break
        machine.step()
    assert machine.halted
    assert io.position() == 0
    assert io.getvalue() == _model(turns), turns


def check_raw_rubic():
    for turn in product(_LAYERS, ("", "2", "'")):
        _check(_Machine, (turn,))
        _check(_Machine, (("r", ""), turn, ("f", "'"), ("u", "2")))
    _check(_Machine, ())

    class InvertedTurn(_Machine):
        def __init__(self, code, io):
            super().__init__(code.replace("R ", "R' ", 1), io)

    with pytest.raises(AssertionError):
        _check(InvertedTurn, (("r", ""), ("f", "")))
