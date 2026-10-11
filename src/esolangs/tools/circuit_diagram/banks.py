"""Share complete cofactors across four predicate-and-function banks.

For n>=8, G<=2T+4n+27 bounds written state by n+3G+1, below
7T+2n-9. Four bounded H bodies and coordinate-bucket copying use O(T)
area and work. This shares complete cofactors, not all internal residuals.
"""

from __future__ import annotations

from collections.abc import Callable

from esolangs.tools.helpers import _validate_truth_table

from .hpool import _h_pool_layout
from .layout import _Layout, _RoutingLayout


class _BankLayout(_RoutingLayout):
    def copy_block(
        self,
        model: _Layout,
        x: int,
        y: int,
        owner: Callable[[int], int],
        omitted: set[tuple[int, int]],
    ) -> None:
        """Copy into fresh rows below prior blocks, excluding external rails."""
        height, width = model.bounds()
        glyph_x: dict[int, list[int]] = {}
        glyph_y: dict[int, list[int]] = {}
        junction_x: dict[int, list[tuple[int, int]]] = {}
        junction_y: dict[int, list[tuple[int, int]]] = {}
        # Each body occupies a fresh rectangle. Coordinate buckets build
        # both ordered indexes in O(points + width + height), without
        # inserting each point into the middle of a sorted list.
        for (a, b), char in model.glyphs.items():
            if a == 0 or (a, b) in omitted:
                continue
            point = x + a, y + b
            if point in self.glyphs or point in self.junctions:
                raise AssertionError(f"bank glyph overlaps at {point}")
            self.glyphs[point] = char
            glyph_x.setdefault(a, []).append(b)
            glyph_y.setdefault(b, []).append(a)
        for (a, b), signal in model.junctions.items():
            point = x + a, y + b
            if point in self.junctions or point in self.glyphs:
                raise AssertionError(f"bank junction overlaps at {point}")
            signal = owner(signal)
            self.junctions[point] = signal
            junction_x.setdefault(a, []).append((b, signal))
            junction_y.setdefault(b, []).append((a, signal))
        for a in range(width):
            for b in glyph_x.get(a, ()):
                self._glyph_rows.setdefault(y + b, []).append(x + a)
            for b, signal in junction_x.get(a, ()):
                self._junction_rows.setdefault(y + b, []).append((x + a, signal))
        for b in range(height):
            for a in glyph_y.get(b, ()):
                self._glyph_cols.setdefault(x + a, []).append(y + b)
            for a, signal in junction_y.get(b, ()):
                self._junction_cols.setdefault(x + a, []).append((y + b, signal))
        for row, runs in model.horizontal.items():
            if y + row in self.horizontal:
                raise AssertionError("bank rows must be fresh")
            self.horizontal[y + row] = [
                (x + a, x + b, owner(signal)) for a, b, signal in runs
            ]
        for column, runs in model.vertical.items():
            translated = [(y + a, y + b, owner(signal)) for a, b, signal in runs]
            destination = self.vertical.setdefault(x + column, [])
            if destination and translated and destination[-1][1] >= translated[0][0]:
                raise AssertionError(
                    "bank vertical intervals must append below prior blocks"
                )
            destination.extend(translated)


def _cofactor_bank_layout(table: str) -> _Layout:
    """Return a four-bank layout with shared prefix complements in O(T) area."""
    from . import _circuit_diagram_model, _essential_table

    _validate_truth_table(table)
    n = len(table).bit_length() - 1
    if n < 3 or len(set(table)) == 1:
        return _circuit_diagram_model(table, None)
    chunks = [
        table[i : i + len(table) // 4] for i in range(0, len(table), len(table) // 4)
    ]
    parts: list[list[tuple[_Layout, list[int]]]] = []
    for cofactor in dict.fromkeys(chunks):
        if "1" not in cofactor:
            continue
        mask = "".join("1" if chunk == cofactor else "0" for chunk in chunks)
        models: list[tuple[_Layout, list[int]]] = []
        if "0" in mask:
            models.append((_circuit_diagram_model(mask, None), [0, 1]))
        if "0" in cofactor:
            used, reduced = _essential_table(cofactor, n - 2)
            model = (
                _h_pool_layout(reduced, input_order=used, port_inputs=n - 2)
                if len(used) >= 6
                else _circuit_diagram_model(cofactor, None)
            )
            models.append((model, list(range(2, n))))
        parts.append(models)
    right = (
        max(model.bounds()[1] for models in parts for model, _ in models) + 2 * n + 12
    )
    body_x = 2 * n + 8
    layout = _BankLayout()
    serial = n

    def fresh() -> int:
        nonlocal serial
        serial += 1
        return serial - 1

    reached: dict[int, tuple[int, int]] = {}
    for i in range(n):
        column = 2 * i + 2
        layout.glyph(0, 2 * i, "-")
        layout.junction(column, 2 * i, i)
        layout.run_horizontal(0, column, 2 * i, i)
        reached[i] = (column, 2 * i)
    feeds: list[tuple[int, tuple[int, int]]] = []
    negative: dict[int, tuple[tuple[int, int], int]] = {}
    required = set()
    for models in parts:
        for model, ports in models:
            if ports == [0, 1]:
                for (x, row), char in model.glyphs.items():
                    if char == "~":
                        required.add(model.junctions[x - 1, row])
    for i in sorted(required):
        column, row = right + 12 + 4 * i, 2 * n + 4 + 4 * i
        signal = fresh()
        layout.glyph(column - 1, row, "~")
        layout.junction(column, row, signal)
        layout.route(reached[i], (column - 2, row), i)
        reached[i] = reached[i][0], row
        negative[i] = ((column, row), signal)
    results: list[tuple[tuple[int, int], int]] = []
    y = 2 * n + 16
    for group, models in enumerate(parts):
        outputs: list[tuple[tuple[int, int], int]] = []
        for model, port_order in models:
            owners: dict[int, int] = {}
            rows = sorted(
                row for (x, row), char in model.glyphs.items() if x == 0 and char == "-"
            )
            if len(rows) != len(port_order):
                raise AssertionError(
                    "bank input ports do not match the original port order"
                )
            first_junction: dict[int, int] = {}
            for x, row in model.junctions:
                first_junction[row] = min(x, first_junction.get(row, x))
            for row, i in zip(rows, port_order, strict=True):
                x = first_junction[row]
                signal = model.junctions[x, row]
                owners[signal] = i
                feeds.append((i, (body_x + x, y + row)))

            def owner(signal: int, mapping: dict[int, int] = owners) -> int:
                if signal not in mapping:
                    mapping[signal] = fresh()
                return mapping[signal]

            removed = set()
            negative_feeds: list[tuple[int, tuple[int, int]]] = []
            if port_order == [0, 1]:
                for (x, row), char in model.glyphs.items():
                    if char != "~":
                        continue
                    i = owners[model.junctions[x - 1, row]]
                    source, signal = negative[i]
                    owners[model.junctions[x + 1, row]] = signal
                    target = body_x + x + 1, y + row
                    negative_feeds.append((i, target))
                    removed.add((x, row))
            out = next(point for point, char in model.glyphs.items() if char == ":")
            endpoint = out[0] - 2, out[1]
            layout.copy_block(
                model, body_x, y, owner, removed | {out, (out[0] - 1, out[1])}
            )
            for i, target in negative_feeds:
                source, signal = negative[i]
                layout.route(source, target, signal)
                negative[i] = ((source[0], target[1]), signal)
            outputs.append(
                (
                    (body_x + endpoint[0], y + endpoint[1]),
                    owner(model.junctions[endpoint]),
                )
            )
            y += model.bounds()[0] + 8
        if len(outputs) == 2:
            gx, gy = right + 8, y + 4
            value = fresh()
            layout.glyph(gx, gy, "a")
            layout.junction(gx + 1, gy, value)
            for j, (source, signal) in enumerate(outputs):
                target = gx - 1, gy - 1 if j == 0 else gy + 1
                via = right + 2 + 2 * j, target[1]
                layout.route(source, via, signal, "across")
                layout.route(via, target, signal)
            output = (gx + 1, gy), value
            y = gy + 8
        else:
            [output] = outputs
        source, signal = output
        column = right + 22 + 2 * group
        layout.route(source, (column, source[1]), signal)
        results.append(((column, source[1]), signal))
        y += 8
    for i, target in feeds:
        layout.route(reached[i], target, i)
        reached[i] = reached[i][0], target[1]
    # Every independent term arrives once; the OR tree has depth at most two.
    row = y + 8
    column = right + 22 + 2 * len(parts) + 4
    while len(results) > 1:
        following = []
        for i in range(0, len(results), 2):
            if i + 1 == len(results):
                following.append(results[i])
                continue
            value = fresh()
            layout.glyph(column, row, "o")
            layout.junction(column + 1, row, value)
            for j, (source, signal) in enumerate(results[i : i + 2]):
                layout.route(
                    source, (column - 1, row - 1 if j == 0 else row + 1), signal
                )
            following.append(((column + 1, row), value))
            row += 4
            column += 6
        results = following
    [(point, signal)] = results
    layout.glyph(point[0] + 1, point[1], "-")
    layout.glyph(point[0] + 2, point[1], ":")
    return layout


def _repeated_cofactor_bank(table: str) -> _Layout | None:
    """Return a bank candidate when a nonconstant top-level cofactor repeats."""
    size = len(table) // 4
    chunks = [table[start : start + size] for start in range(0, len(table), size)]
    if not any(
        "0" in chunk and "1" in chunk and chunks.count(chunk) > 1 for chunk in chunks
    ):
        return None
    return _cofactor_bank_layout(table)
