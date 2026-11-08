"""Independent flood-fill Piet model for standard colours and black, 32 steps.

https://www.dangermouse.net/esoteric/piet.html, blocks, execution and commands.
All stack commands, DP/CC edge selection, blocked exits and IO; white slides
and inferred scales remain in raw tests. Failed commands follow Decisions.
"""

import re
from itertools import product
from operator import add, floordiv, gt, mod, mul, sub

from esolangs.languages.piet.interpreter import _Machine
from esolangs.raster import Raster
from tests.interpreters.oracle_support import reject_faults
from tests.support import workspace_oracle as workspace

_WORKSPACE = workspace.workspace_model(
    "piet-v1", "position direction chooser stack input_cursor stopped input_reads"
)

_HEX = (
    ("ffc0c0", "ff0000", "c00000"),
    ("ffffc0", "ffff00", "c0c000"),
    ("c0ffc0", "00ff00", "00c000"),
    ("c0ffff", "00ffff", "00c0c0"),
    ("c0c0ff", "0000ff", "0000c0"),
    ("ffc0ff", "ff00ff", "c000c0"),
)
_PALETTE = tuple(tuple(tuple(bytes.fromhex(code)) for code in row) for row in _HEX)
_BLACK = (0, 0, 0)
_DECODE = {
    pixel: (hue, light)
    for hue, row in enumerate(_PALETTE)
    for light, pixel in enumerate(row)
}
_DIRECTIONS = ((1, 0), (0, 1), (-1, 0), (0, -1))


def _block(rows, origin):
    colour, pending, seen = rows[origin[1]][origin[0]], [origin], {origin}
    while pending:
        x, y = pending.pop()
        for dx, dy in _DIRECTIONS:
            point = x + dx, y + dy
            a, b = point
            if (
                0 <= b < len(rows)
                and 0 <= a < len(rows[0])
                and point not in seen
                and rows[b][a] == colour
            ):
                seen.add(point)
                pending.append(point)
    return seen


def _destination(rows, block, dp, cc):
    for attempt in range(8):
        dx, dy = _DIRECTIONS[dp]
        edge = max(
            block, key=lambda p: (p[0] * dx + p[1] * dy, cc * (p[1] * dx - p[0] * dy))
        )
        x, y = edge[0] + dx, edge[1] + dy
        if 0 <= y < len(rows) and 0 <= x < len(rows[0]) and rows[y][x] != _BLACK:
            return (x, y), dp, cc
        if attempt % 2 == 0:
            cc = -cc
        else:
            dp = (dp + 1) % 4
    return None


class _Port:
    def __init__(self, stdin):
        self.stdin, self.cursor, self.reads, self.output = stdin, 0, 0, ""

    def read(self, numeric):
        if numeric:
            while self.cursor < len(self.stdin) and self.stdin[self.cursor].isspace():
                self.cursor += 1
        start = self.cursor
        if self.cursor == len(self.stdin):
            return None
        if not numeric:
            self.cursor += 1
            self.reads += 1
            return ord(self.stdin[start])
        while self.cursor < len(self.stdin) and not self.stdin[self.cursor].isspace():
            self.cursor += 1
        self.reads += 1
        text = self.stdin[start : self.cursor]
        return int(text) if re.fullmatch(r"[+-]?[0-9]+", text) else None


def _roll(stack):
    if len(stack) < 2:
        return
    depth, count = stack[-2:]
    if not 0 <= depth <= len(stack) - 2:
        return
    del stack[-2:]
    if depth:
        count %= depth
        if count:
            stack[-depth:] = stack[-count:] + stack[-depth:-count]


def _operation(change, size, stack, dp, cc, port):
    binary = {
        (1, 0): add,
        (1, 1): sub,
        (1, 2): mul,
        (2, 0): floordiv,
        (2, 1): mod,
        (3, 0): gt,
    }
    if change in binary:
        if len(stack) >= 2 and not (change in ((2, 0), (2, 1)) and stack[-1] == 0):
            value = binary[change](*stack[-2:])
            stack[-2:] = [int(value)]
    elif change == (0, 1):
        stack.append(size)
    elif change == (0, 2) and stack:
        stack.pop()
    elif change == (2, 2) and stack:
        stack[-1] = int(stack[-1] == 0)
    elif change == (3, 1) and stack:
        dp = (dp + stack.pop()) % 4
    elif change == (3, 2) and stack:
        cc *= (-1) ** (stack.pop() % 2)
    elif change == (4, 0) and stack:
        stack.append(stack[-1])
    elif change == (4, 1):
        _roll(stack)
    elif change in ((4, 2), (5, 0)):
        value = port.read(change == (4, 2))
        if value is not None:
            stack.append(value)
    elif change in ((5, 1), (5, 2)) and stack:
        value = stack.pop()
        if change == (5, 1):
            port.output += str(value)
        elif 0 <= value <= 0x10FFFF and not 0xD800 <= value <= 0xDFFF:
            port.output += chr(value)
    return dp, cc


def _model(rows, stdin):
    point, dp, cc, stack = (0, 0), 0, -1, []
    done, trace, port = rows[0][0] == _BLACK, [], _Port(stdin)

    def row():
        return (
            (point, dp, cc, tuple(stack), port.reads),
            done,
            port.output,
            port.cursor,
            port.cursor,
        )

    for tick in range(33):
        trace.append(row())
        if done:
            return None, trace + [row()] * 3
        if tick == 32:
            break
        block = _block(rows, point)
        exit_ = _destination(rows, block, dp, cc)
        if exit_ is None:
            done = True
            continue
        target, dp, cc = exit_
        before, after = (
            _DECODE[rows[point[1]][point[0]]],
            _DECODE[rows[target[1]][target[0]]],
        )
        change = ((after[0] - before[0]) % 6, (after[1] - before[1]) % 3)
        dp, cc = _operation(change, len(block), stack, dp, cc, port)
        point = target
    return None, trace


def _view(machine):
    return machine.current, machine.dp, machine.cc, machine.stack, machine._input_reads


def _check(factory, rows, stdin="unused"):
    def actual(program, io):
        return factory(program, io, scale=1)

    workspace.agrees(
        _model(rows, stdin),
        (actual, Raster(rows), stdin),
        (_WORKSPACE, lambda row: (*row[0][:4], row[-1], row[1], row[0][4])),
        _view,
        cap=32,
        context=(rows, stdin),
    )


def _strip(changes, size=1):
    hue = light = 0
    row = [_PALETTE[0][0]] * size
    for dh, dl in changes:
        hue, light = (hue + dh) % 6, (light + dl) % 3
        row.append(_PALETTE[hue][light])
    return (tuple(row),)


def check_raw_piet():
    colours = tuple(_DECODE)
    for first, second in product(colours, repeat=2):
        _check(_Machine, ((first, first, second),), "3 A\n")
    for cells in product(
        (_BLACK, _PALETTE[0][0], _PALETTE[0][1], _PALETTE[1][0]), repeat=4
    ):
        _check(_Machine, (cells[:2], cells[2:]))
    stacks = (
        (),
        (1,),
        (8, 3),
        (-8, 3),
        (3, 3),
        (1, 2, 3, 3, 1),
        (1, -2),
        (5, 0, 3),
        (4, 0),
        (1, 2, 2, 0),
        (-1, 3),
    )
    for stack, change in product(stacks, product(range(6), range(3))):
        changes = ((4, 2),) * len(stack) + (change, (5, 1))
        _check(_Machine, _strip(changes), " ".join(map(str, stack)))
    for size in range(1, 8):
        _check(_Machine, _strip(((0, 1), (5, 1)), size))
    for hue, light, stdin in product(
        range(6), range(3), ("", "-3 2 A", "λ\n", "1_0", "٣", "0 0", "55296")
    ):
        red = _PALETTE[0][0]
        middle = (red, red, _PALETTE[0][1], _PALETTE[hue][light], _PALETTE[5][2])
        _check(
            _Machine,
            (
                (red, _BLACK, _BLACK, _BLACK, _PALETTE[5][2]),
                middle,
                (_BLACK,) * 4 + (_PALETTE[5][2],),
            ),
            stdin,
        )

    class WrongStack(_Machine):
        def step(self):
            super().step()
            point, dp, cc, stack, done = self.state
            self.state = point, dp, cc, (*stack, 99), done

    reject_faults(_check, _Machine, WrongStack, ((_PALETTE[0][0], _PALETTE[0][1]),))

    workspace.check_erasures(
        _WORKSPACE, _check, _Machine, _strip(((4, 2), (5, 1))), "3 A"
    )
