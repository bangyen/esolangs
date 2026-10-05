# ruff: noqa: SLF001 - instruction primitives are the semantic test surface.
"""Geometric routes and independent Boolean merge rules."""

import itertools

from esolangs.interpreters.grid_based.thisthat import _Machine, _Pointer
from esolangs.interpreters.io import ScriptedIO


def test_routing_rules():
    vectors = ((1, 0), (-1, 0), (0, -1), (0, 1))
    names = {(1, 0): "E", (-1, 0): "W", (0, -1): "N", (0, 1): "S"}
    black_sides = {"◐": (-1, 0), "◑": (1, 0), "◒": (0, 1), "◓": (0, -1)}
    checks = 0
    center = (2, 2)

    def grid(node):
        return ["▣    ", "  ◯  ", " ◯" + node + "◯ ", "  ◯  ", "     "]

    for node, previous_side in itertools.product(black_sides, (None, *vectors)):
        previous = (
            None
            if previous_side is None
            else (2 + previous_side[0], 2 + previous_side[1])
        )
        black = black_sides[node]
        white = (-black[0], -black[1])
        incoming = (
            None if previous_side is None else (-previous_side[0], -previous_side[1])
        )
        machine = _Machine(grid(node), ScriptedIO(""))
        for channel, value in (
            ("execution", None),
            ("data", None),
            ("data", 0),
            ("data", 1),
        ):
            pointer = _Pointer(center, previous, channel, value)
            if channel == "data":
                expected = incoming if value is None else white if value == 0 else black
            elif incoming is None:
                expected = None
            elif previous_side == white:
                expected = incoming
            elif previous_side == black:
                expected = black
            else:
                expected = (-incoming[1], incoming[0])
            assert machine._router_direction(node, pointer) == (
                None if expected is None else names[expected]
            )
            following = []
            machine._advance_one(pointer, following)
            expected_pointers = (
                []
                if expected is None
                else [_Pointer((2 + expected[0], 2 + expected[1]), center)]
            )
            assert following == expected_pointers, (
                node,
                previous_side,
                channel,
                value,
                following,
                expected_pointers,
            )
            checks += 1
    for node in "▲▶▼◀△▷▽◁":
        direction = (
            vectors["▶◀▲▼".index(node)]
            if node in "▶◀▲▼"
            else vectors["▷◁△▽".index(node)]
        )
        for previous_side in (None, *vectors):
            previous = (
                None
                if previous_side is None
                else (2 + previous_side[0], 2 + previous_side[1])
            )
            for channel, value in (
                ("execution", None),
                ("data", None),
                ("data", 0),
                ("data", 1),
            ):
                machine = _Machine(grid(node), ScriptedIO(""))
                following = []
                pointer = _Pointer(center, previous, channel, value)
                machine._advance_one(pointer, following)
                allowed = (
                    node in "▲▶▼◀"
                    or previous_side is None
                    or previous_side in (direction, (-direction[0], -direction[1]))
                )
                expected = (
                    []
                    if not allowed
                    else [
                        _Pointer(
                            (2 + direction[0], 2 + direction[1]), center, channel, value
                        )
                    ]
                )
                assert following == expected
                checks += 1
    assert checks == 240


def test_logic_rules():
    class Choice:
        def __init__(self, index):
            self.index = index

        def randbelow(self, upper):
            assert 0 <= self.index < upper
            return self.index

    center = (2, 2)
    exits = ((3, 2), (1, 2), (2, 1), (2, 3))
    checks = 0

    def grid(node):
        return ["▣    ", "  ◯  ", " ◯" + node + "◯ ", "  ◯  ", "     "]

    def emitted(pointer, channel, value):
        return [
            _Pointer(point, center, channel, value)
            for point in exits
            if point != pointer.previous
        ]

    for count in range(1, 6):
        for bits in itertools.product((0, 1), repeat=count):
            arrived = [
                _Pointer(center, exits[index % 4], "data", bit)
                for index, bit in enumerate(bits)
            ]
            for node in "◘□■▦":
                value = (
                    1 - int(all(bits))
                    if node == "◘"
                    else 1 - int(any(bits))
                    if node == "□"
                    else int(any(bits))
                    if node == "■"
                    else sum(bits) % 2
                )
                for selected in range(count) if node == "◘" else (0,):
                    machine = _Machine(grid(node), ScriptedIO(""), Choice(selected))
                    following = []
                    machine._merge(node, arrived, following)
                    assert following == emitted(arrived[selected], "data", value), (
                        node,
                        bits,
                        selected,
                    )
                    checks += 1
    for count in range(1, 5):
        arrived = [_Pointer(center, exits[index % 4]) for index in range(count)]
        for node in "◘□■▦":
            for selected in range(count) if node == "◘" else (0,):
                machine = _Machine(grid(node), ScriptedIO(""), Choice(selected))
                following = []
                machine._merge(node, arrived, following)
                expected = (
                    emitted(arrived[selected], "execution", None)
                    if node == "◘"
                    else [
                        _emitted
                        for pointer in arrived
                        for _emitted in emitted(
                            pointer, "data", {"□": 0, "■": 1, "▦": None}[node]
                        )
                    ]
                )
                assert following == expected
                checks += 1
    for count in range(5):
        for channels in itertools.product(("execution", "data"), repeat=count):
            arrived = [
                _Pointer(
                    center, exits[index % 4], channel, 1 if channel == "data" else None
                )
                for index, channel in enumerate(channels)
            ]
            machine = _Machine(grid("◈"), ScriptedIO(""))
            following = []
            machine._merge("◈", arrived, following)
            expected = (
                arrived
                if count < 2
                else [
                    _emitted
                    for pointer in arrived
                    for _emitted in emitted(pointer, pointer.channel, pointer.value)
                ]
            )
            assert following == expected
            checks += 1
