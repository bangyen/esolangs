"""Piet block traversal using coordinate extrema and set closure."""

from functools import lru_cache

from tests.piet.piet_commands import command

WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
HUES = (
    (255, 0, 0),
    (255, 255, 0),
    (0, 255, 0),
    (0, 255, 255),
    (0, 0, 255),
    (255, 0, 255),
)
PALETTE = {}
for hue, base in enumerate(HUES):
    for light in range(3):
        rgb = tuple(
            (192 if value == 0 else 255)
            if light == 0
            else value
            if light == 1
            else 192
            if value
            else 0
            for value in base
        )
        PALETTE[rgb] = (hue, light)


def colour(pixel):
    return pixel if pixel in PALETTE or pixel == BLACK else WHITE


def neighbor(point, heading):
    x, y = point
    if heading == 0:
        return (x + 1, y)
    if heading == 1:
        return (x, y + 1)
    if heading == 2:
        return (x - 1, y)
    return (x, y - 1)


def at(rows, point):
    x, y = point
    return colour(rows[y][x]) if 0 <= y < len(rows) and 0 <= x < len(rows[0]) else BLACK


@lru_cache(maxsize=8192)
def block(rows, start):
    group = {start}
    wanted = at(rows, start)
    while True:
        expanded = group | {
            neighbor(p, d)
            for p in group
            for d in range(4)
            if at(rows, neighbor(p, d)) == wanted
        }
        if expanded == group:
            return frozenset(group)
        group = expanded


def exit_codel(group, heading, chooser):
    if heading == 0:
        edge = max((x for x, y in group))
        candidates = [(x, y) for x, y in group if x == edge]
        return sorted(candidates, key=lambda p: p[1], reverse=chooser == 1)[0]
    if heading == 1:
        edge = max((y for x, y in group))
        candidates = [(x, y) for x, y in group if y == edge]
        return sorted(candidates, key=lambda p: p[0], reverse=chooser == -1)[0]
    if heading == 2:
        edge = min((x for x, y in group))
        candidates = [(x, y) for x, y in group if x == edge]
        return sorted(candidates, key=lambda p: p[1], reverse=chooser == -1)[0]
    edge = min((y for x, y in group))
    candidates = [(x, y) for x, y in group if y == edge]
    return sorted(candidates, key=lambda p: p[0], reverse=chooser == 1)[0]


def slide(rows, point, heading, chooser):
    visited = set()
    while (point, heading, chooser) not in visited:
        visited.add((point, heading, chooser))
        target = neighbor(point, heading)
        pixel = at(rows, target)
        if pixel == WHITE:
            point = target
        elif pixel != BLACK:
            return (target, heading, chooser)
        else:
            chooser = -chooser
            heading = (heading + 1) % 4
    return None


def advance(state, rows):
    point, heading, chooser, stack, halted = state
    if halted:
        return (state, None)
    pixel = at(rows, point)
    if pixel == WHITE:
        result = slide(rows, point, heading, chooser)
        return (
            (point, heading, chooser, stack, True)
            if result is None
            else (*result, stack, False),
            None,
        )
    group = block(rows, point)
    for attempt in range(8):
        target = neighbor(exit_codel(group, heading, chooser), heading)
        new = at(rows, target)
        if new == WHITE:
            result = slide(rows, target, heading, chooser)
            return (
                (point, heading, chooser, stack, True)
                if result is None
                else (*result, stack, False),
                None,
            )
        if new != BLACK:
            old_hue, old_light = PALETTE[pixel]
            hue, light = PALETTE[new]
            values, turn, toggle, effect = command(
                ((hue - old_hue) % 6, (light - old_light) % 3), len(group), stack
            )
            return (
                (
                    target,
                    (heading + turn) % 4,
                    -chooser if toggle % 2 else chooser,
                    values,
                    False,
                ),
                effect,
            )
        if attempt % 2 == 0:
            chooser = -chooser
        else:
            heading = (heading + 1) % 4
    return ((point, heading, chooser, stack, True), None)
