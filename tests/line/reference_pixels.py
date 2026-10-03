"""Independent whole-segment model for unit-20 Line drawings."""

from collections import defaultdict
from fractions import Fraction
from io import BytesIO
from itertools import groupby, pairwise
from math import gcd

from PIL import Image

D = ((-1, 0), (-1, 1), (0, 1), (1, 1), (1, 0), (1, -1), (0, -1), (-1, -1))


def vectorize(data):
    im = Image.open(BytesIO(data)).convert("L")
    w, _h = im.size
    black = {(i // w, i % w) for i, pixel in enumerate(im.tobytes()) if pixel < 128}
    # A scaled thin drawing consists of complete square pixel blocks.
    scale = 0
    for _, row in groupby(sorted(black), key=lambda p: p[0]):
        xs = [x for y, x in row]
        run = 1
        for a, b in pairwise(xs):
            if b == a + 1:
                run += 1
            else:
                scale = gcd(scale, run)
                run = 1
        scale = gcd(scale, run)
    assert scale
    if scale > 1:
        blocks = {(y // scale, x // scale) for y, x in black}
        assert len(black) == len(blocks) * scale**2, "nonuniform magnification"
        black = blocks
    core = [
        (y, x)
        for y, x in black
        if all((y + dy, x + dx) in black for dy in (-1, 0, 1) for dx in (-1, 0, 1))
    ]
    assert core
    my = sum(y for y, x in core) / len(core)
    mx = sum(x for y, x in core) / len(core)
    sy = sum((y - my) ** 3 for y, x in core)
    sx = sum((x - mx) ** 3 for y, x in core)
    heading = (0 if sy < 0 else 4) if abs(sy) > abs(sx) else (6 if sx < 0 else 2)
    root = (round(my), round(mx))
    segments = []
    for y, x in sorted(black):
        for d in (0, 1, 2, 3):
            dy, dx = D[d]
            if (y - dy, x - dx) in black:
                continue
            n = 0
            while (y + dy * (n + 1), x + dx * (n + 1)) in black:
                n += 1
            if n >= 15:
                segments.append(((y, x), (y + dy * n, x + dx * n), d, n))
    points = [{a, b} for a, b, d, n in segments]

    def cross(a, b):
        return a[0] * b[1] - a[1] * b[0]

    for i, (a, b, d, n) in enumerate(segments):
        v = D[d]
        for j in range(i):
            c, e, k, m = segments[j]
            u = D[k]
            den = cross(v, u)
            if den:
                delta = (c[0] - a[0], c[1] - a[1])
                t = Fraction(cross(delta, u), den)
                s = Fraction(cross(delta, v), den)
                if -1 <= t <= n + 1 and -1 <= s <= m + 1:
                    point = (a[0] + v[0] * t, a[1] + v[1] * t)
                    assert all(p.denominator == 1 for p in point), (
                        point,
                        "half pixel intersection",
                    )
                    point = tuple(int(p) for p in point)
                    points[i].add(point)
                    points[j].add(point)
            else:
                for p in (a, b):
                    for q in (c, e):
                        if max(abs(p[0] - q[0]), abs(p[1] - q[1])) <= 1:
                            points[i].add(q)
                            points[j].add(p)
    graph = defaultdict(dict)
    for (a, b, d, _n), ps in zip(segments, points, strict=True):
        v = D[d]
        ordered = sorted(ps, key=lambda p: (p[0] - a[0]) * v[0] + (p[1] - a[1]) * v[1])
        # Off-by-one endpoints are replaced by their exact line intersection.
        intersections = ps - {a, b}
        ordered = [
            p
            for p in ordered
            if p not in (a, b)
            or not any(
                max(abs(p[0] - q[0]), abs(p[1] - q[1])) <= 1 for q in intersections
            )
        ]
        for p, q in pairwise(ordered):
            graph[p][d] = q
            graph[q][(d + 4) % 8] = p
    # Entry centroid lies inside the arrow's straight stem, not at a graph corner.
    candidates = []
    for a, b, d, n in segments:
        if d in (heading, (heading + 4) % 8):
            v = D[d]
            delta = (root[0] - a[0], root[1] - a[1])
            t = delta[0] * v[0] + delta[1] * v[1]
            if cross(delta, v) == 0 and 0 <= t <= n:
                candidates.append((a, b, d, n))
    assert len(candidates) == 1, (root, heading, candidates)
    a, b, d, n = candidates[0]
    destination = b if d == heading else a
    # Find the first split point in the entry direction.
    v = D[heading]
    on_line = [
        p
        for p in graph
        if cross((p[0] - root[0], p[1] - root[1]), v) == 0
        and (p[0] - root[0]) * v[0] + (p[1] - root[1]) * v[1] > 0
    ]
    destination = min(
        on_line, key=lambda p: max(abs(p[0] - root[0]), abs(p[1] - root[1]))
    )
    graph[root][heading] = destination
    return graph, root, heading


def trace(graph, start, heading):
    vertices = []
    seen = set()
    p = start
    d = heading
    while (p, d) not in seen:
        seen.add((p, d))
        vertices.append((*p, d))
        p = graph[p][d]
        onward = set(graph[p]) - {(d + 4) % 8}
        if not onward:
            return [*vertices, (*p, None)], None, None, None
        if onward == {(d + 2) % 8, (d - 2) % 8}:
            return [*vertices, (*p, None)], (p, (d + 2) % 8), (p, (d - 2) % 8), None
        distances = {k: min((k - d) % 8, (d - k) % 8) for k in onward}
        best = min(distances.values())
        choices = [k for k, v in distances.items() if v == best]
        assert len(choices) == 1, (p, d, onward)
        if len(graph[p]) == 3:
            return [*vertices, (*p, None)], None, None, (p, choices[0])
        d = choices[0]
    raise AssertionError("loop without fork")


def read_operations(vertices):
    legs = []
    for a, b in pairwise(vertices):
        d = a[2]
        length = max(abs(b[0] - a[0]), abs(b[1] - a[1]))
        if length < 3:
            continue
        if legs and legs[-1][0] == d:
            legs[-1] = (d, legs[-1][1] + length)
        else:
            legs.append((d, length))
    if not legs:
        return []
    heading = legs[0][0]
    i = 0
    result = []
    symbols = (
        ("i", ((1, 1), (6, 2), (1, 1))),
        ("o", ((6, 1), (1, 2), (6, 1))),
        (">", ((1, 1), (6, 1))),
        ("<", ((7, 1), (2, 1))),
    )
    while i < len(legs):
        if legs[i][0] == heading:
            i += 1
            continue
        candidate = [
            ((d - heading) % 8, round(length / 20)) for d, length in legs[i : i + 3]
        ]
        for symbol, shape in symbols:
            if tuple(candidate[: len(shape)]) == shape and all(
                abs(legs[i + k][1] - 20 * count) <= 2
                for k, (_, count) in enumerate(shape)
            ):
                if i + len(shape) < len(legs):
                    result.append((symbol, 1))
                i += len(shape)
                break
        else:
            relative, length = candidate[0]
            if relative in (1, 7) and abs(legs[i][1] - 20 * length) <= 2:
                if i + 1 < len(legs):
                    result.append(("+" if relative == 1 else "-", length))
            else:
                heading = legs[i][0]
            i += 1
    return result


def program(data):
    graph, root, heading = vectorize(data)
    start = (root, heading)
    paths = {}
    pending = [start]
    while pending:
        pose = pending.pop()
        if pose in paths:
            continue
        vertices, zero, nonzero, onward = trace(graph, *pose)
        paths[pose] = (read_operations(vertices), zero, nonzero, onward)
        pending.extend(child for child in (zero, nonzero, onward) if child is not None)
    return paths, start


def evaluate(paths, start, values, cap=10000):
    cells = {}
    pointer = consumed = 0
    output = []
    node = start
    for _ in range(cap):
        ops, zero, nonzero, onward = paths[node]
        for op, count in ops:
            cell = cells.get(pointer, 0)
            if op == "+":
                cells[pointer] = cell + count
            elif op == "-":
                cells[pointer] = cell - count
            elif op == ">":
                pointer += 1
            elif op == "<":
                pointer -= 1
            elif op == "i":
                cells[pointer] = values[consumed]
                consumed += 1
            elif op == "o":
                output.append(cell)
        if zero is None:
            if onward is None:
                return output, cells, consumed
            node = onward
        else:
            node = zero if cells.get(pointer, 0) == 0 else nonzero
    raise AssertionError("execution cap")
