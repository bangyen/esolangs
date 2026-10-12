"""Share cofactors through fixed four/eight predicate-and-function banks.

For eight banks, G<=2T+8n+111 gives state<=6T+25n+334, below
7T+2n-9 from n=10; the exact n=8/9 gate caps are 511/1015.
Bounded H bodies and coordinate-bucket copying use O(T) area and work.
This still does not share every residual across bodies.
"""

from __future__ import annotations

from collections.abc import Callable

from esolangs.tools.helpers import _validate_truth_table

from .forest import _Forest, _suffix_forest
from .hpool import _h_pool_layout, _h_pool_size, _large_pool_layout
from .layout import _Layout, _RoutingLayout

type _Output = tuple[tuple[int, int], int]


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


def _cofactor_bank_layout(table: str, prefix_inputs: int = 2) -> _Layout:
    """Return four/eight banks with shared prefix complements in O(T) area."""
    from . import _circuit_diagram_model, _essential_table

    _validate_truth_table(table)
    if prefix_inputs not in (2, 3):
        raise ValueError("cofactor banks need two or three prefix inputs")
    n = len(table).bit_length() - 1
    if n < 3 or len(set(table)) == 1:
        return _circuit_diagram_model(table, None)
    prefix_order = list(range(prefix_inputs))
    size = len(table) // (1 << prefix_inputs)
    chunks = [table[i : i + size] for i in range(0, len(table), size)]
    parts: list[list[tuple[_Layout, list[int]]]] = []
    for cofactor in dict.fromkeys(chunks):
        if "1" not in cofactor:
            continue
        mask = "".join("1" if chunk == cofactor else "0" for chunk in chunks)
        models: list[tuple[_Layout, list[int]]] = []
        if "0" in mask:
            models.append((_circuit_diagram_model(mask, None), prefix_order))
        if "0" in cofactor:
            used, reduced = _essential_table(cofactor, n - prefix_inputs)
            model = (
                _h_pool_layout(reduced, input_order=used, port_inputs=n - prefix_inputs)
                if len(used) >= 6
                else _circuit_diagram_model(cofactor, None)
            )
            models.append((model, list(range(prefix_inputs, n))))
        parts.append(models)
    return _assemble_banks(parts, n, prefix_inputs, share_prefix_complements=True)


def _assemble_banks(
    parts: list[list[tuple[_Layout, list[int]]]],
    n: int,
    prefix_inputs: int,
    *,
    share_prefix_complements: bool,
    shared_suffix: _Forest | None = None,
    online_returns: bool = False,
    left_returns: bool = False,
) -> _Layout:
    prefix_order = list(range(prefix_inputs))
    widths = [model.bounds()[1] for models in parts for model, _ in models]
    if shared_suffix is not None:
        widths.append(shared_suffix[0].bounds()[1])
    right = max(widths) + 2 * n + 12
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
            if share_prefix_complements and ports == prefix_order:
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
    y = 2 * n + 8 + 4 * prefix_inputs
    held: list[tuple[tuple[int, int], int] | None] = [None] * len(parts)
    carry_levels = (len(parts) - 1).bit_length() + 1
    carry: list[_Output | None] = [None] * carry_levels
    temporary = right + 22 + 2 * carry_levels

    def join_carry(older: _Output, newer: _Output) -> _Output:
        nonlocal y
        gx, gy = temporary + 4, y + 4
        value = fresh()
        layout.glyph(gx, gy, "o")
        layout.junction(gx + 1, gy, value)
        for index, (point, signal) in enumerate((older, newer)):
            layout.route(point, (gx - 1, gy - 1 if index == 0 else gy + 1), signal)
        # The 16-class probe's two-row return hit lower-port clearance; use four.
        layout.route((gx + 1, gy), (gx + 1, gy + 4), value)
        layout.route((gx + 1, gy + 4), (temporary, gy + 4), value)
        y = gy + 8
        return (temporary, gy + 4), value

    groups = list(enumerate(parts))
    if shared_suffix is not None:
        groups.insert(0, (-1, [(shared_suffix[0], list(range(prefix_inputs, n)))]))
    for group, models in groups:
        held_root = held[group] if group >= 0 else None
        outputs: list[tuple[tuple[int, int], int]] = (
            [] if held_root is None else [held_root]
        )
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
            if share_prefix_complements and port_order == prefix_order:
                for (x, row), char in model.glyphs.items():
                    if char != "~":
                        continue
                    i = owners[model.junctions[x - 1, row]]
                    source, signal = negative[i]
                    owners[model.junctions[x + 1, row]] = signal
                    target = body_x + x + 1, y + row
                    negative_feeds.append((i, target))
                    removed.add((x, row))
            outpoints = [point for point, char in model.glyphs.items() if char == ":"]
            out = outpoints[0]
            endpoint = out[0] - 2, out[1]
            omitted = {
                cell
                for point in outpoints
                for cell in (point, (point[0] - 1, point[1]))
            }
            layout.copy_block(model, body_x, y, owner, removed | omitted)
            for i, target in negative_feeds:
                source, signal = negative[i]
                layout.route(source, target, signal)
                negative[i] = ((source[0], target[1]), signal)
            if group == -1:
                if shared_suffix is None:
                    raise AssertionError("missing suffix forest")
                for index, point in enumerate(shared_suffix[1]):
                    if point is None:
                        continue
                    source = body_x + point[0], y + point[1]
                    signal = owner(model.junctions[point])
                    # Hold roots beyond term-result rails; each ends at its
                    # consuming AND, which may follow earlier carry ORs.
                    column = right + 25 + 2 * len(parts) + 2 * index
                    layout.route(source, (column, source[1]), signal, "across")
                    held[index] = ((column, source[1]), signal)
            else:
                outputs.append(
                    (
                        (body_x + endpoint[0], y + endpoint[1]),
                        owner(model.junctions[endpoint]),
                    )
                )
            y += model.bounds()[0] + 8
        if group == -1:
            continue
        if len(outputs) == 2:
            gx, gy = right + 8, y + 4
            value = fresh()
            layout.glyph(gx, gy, "a")
            layout.junction(gx + 1, gy, value)
            for j, (source, signal) in enumerate(outputs):
                target = gx - 1, gy - 1 if j == 0 else gy + 1
                via = right + 2 + 2 * j, target[1]
                if shared_suffix is not None and j == 0:
                    # A held root must descend before returning left;
                    # returning on its footer row crosses other exports.
                    above = via[0], gy - 4
                    layout.route(source, above, signal, "down")
                    layout.route(above, via, signal)
                else:
                    layout.route(source, via, signal, "across")
                layout.route(via, target, signal)
            output = (gx + 1, gy), value
            y = gy + 8
        else:
            [output] = outputs
        source, signal = output
        # A sole suffix class has no mask: its held root is already farther
        # right. Keep that endpoint so the output glyphs follow its wire.
        if online_returns and len(parts) > 1:
            layout.route(source, (temporary, source[1]), signal)
            current = (temporary, source[1]), signal
            depth = 0
            while (pending := carry[depth]) is not None:
                current = join_carry(pending, current)
                carry[depth] = None
                depth += 1
            point, signal = current
            if left_returns:
                # Four rows clear the producing gate's lower input port.
                landing = point[0], point[1] + 4
                layout.route(point, landing, signal, "down")
                slot = 2 * depth + 1, landing[1]
                layout.route(landing, slot, signal, "across")
            else:
                slot = right + 22 + 2 * depth, point[1]
                layout.route(point, slot, signal)
            carry[depth] = slot, signal
        else:
            column = max(right + 22 + 2 * group, source[0])
            if source != (column, source[1]):
                layout.route(source, (column, source[1]), signal)
            results.append(((column, source[1]), signal))
        y += 8
    for i, target in feeds:
        layout.route(reached[i], target, i)
        reached[i] = reached[i][0], target[1]
    if online_returns and len(parts) > 1:
        pending_roots = [pending for pending in carry if pending is not None]
        result = pending_roots[0]
        # Fold small rightmost blocks first: OR depth stays ceil(log2 q).
        for pending in pending_roots[1:]:
            result = join_carry(pending, result)
        point, signal = result
        endpoint = point[0], y + 4
        layout.route(point, endpoint, signal)
        layout.glyph(endpoint[0] + 1, endpoint[1], "-")
        layout.glyph(endpoint[0] + 2, endpoint[1], ":")
        return layout
    # Each term arrives once; OR depth is bounded by the prefix arity.
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


def _residual_class_bank_candidate(
    table: str, ceiling: int | None = None
) -> _Layout | None:
    """Choose separate or shared suffix roots by exact area, preserving ties."""
    separate = _class_bank_layout(table, ceiling, shared=False)
    shared_ceiling = ceiling
    if separate is not None:
        height, width = separate.bounds()
        shared_ceiling = (
            height * width if ceiling is None else min(ceiling, height * width)
        )
    forest = _class_bank_layout(table, shared_ceiling, shared=True)
    if forest is None:
        return separate
    if separate is None:
        return forest
    height, width = forest.bounds()
    old_height, old_width = separate.bounds()
    return forest if height * width < old_height * old_width else separate


def _online_bank_area_floor(
    dimensions: list[tuple[int, int]], n: int, prefix: int, q: int, ands: int
) -> int:
    """Bound the final output row and last carry OR, including partial bands."""
    if q < 2 or not dimensions:
        return 0
    # The final output sits at y+4: copied bands, ANDs, q-1 carry
    # joins and group gaps determine y. The last OR forces this width.
    height = (
        2 * n
        + 8
        + 4 * prefix
        + sum(h + 8 for h, w in dimensions)
        + 20 * q
        + 12 * ands
        - 7
    )
    width = max(w for h, w in dimensions) + 2 * n + 40 + 2 * ((q - 1).bit_length() + 1)
    return height * width


def _class_bank_layout(
    table: str, ceiling: int | None = None, *, shared: bool
) -> _Layout | None:
    """Share workspace-admitted seven/eight-input classes across all prefixes.

    A fixed class cap bounds H-mask copying; counted gates enforce workspace.
    """
    from . import _essential_table

    n = _validate_truth_table(table)
    tail = 7 if n % 2 else 8
    prefix = n - tail
    if prefix < 2 or len(set(table)) == 1:
        return None
    size = 1 << tail
    chunks = [table[start : start + size] for start in range(0, len(table), size)]
    classes = [chunk for chunk in dict.fromkeys(chunks) if "1" in chunk]
    # Keep the former implied class cap independently of the gate count:
    # sparse masks can fit the workspace even when their worst-case bound cannot.
    # The fixed nine-input atom also shares internal seven-input residuals
    # across its four distinct roots: dense9 executes in 258,216 characters.
    if len(classes) >= 1 << (tail + 1) or not any(
        "0" in chunk and (chunks.count(chunk) > 1 or (shared and n == 9))
        for chunk in classes
    ):
        return None
    forest = _suffix_forest(classes, tail) if shared else None
    if forest is not None and ceiling is not None:
        height, width = forest[0].bounds()
        # Copying removes two output cells but adds a larger positive offset;
        # retained endpoint rows therefore bound the assembled area below.
        if height * width > ceiling:
            return None
    parts: list[list[tuple[_Layout, list[int]]]] = []
    dimensions = [] if forest is None else [forest[0].bounds()]
    ands = sum("0" in chunk for chunk in classes)
    for chunk in classes:
        mask = "".join("1" if word == chunk else "0" for word in chunks)
        models: list[tuple[_Layout, list[int]]] = []
        for word, ports, order in (
            (mask, prefix, list(range(prefix))),
            (chunk, tail, list(range(prefix, n))),
        ):
            if "0" not in word or (shared and order[0] != 0):
                continue
            used, reduced = _essential_table(word, ports)
            model = _large_pool_layout(
                reduced, input_order=used, port_inputs=ports, ceiling=ceiling
            )
            if model is None:
                return None
            dimensions.append(model.bounds())
            if (
                ceiling is not None
                and _online_bank_area_floor(dimensions, n, prefix, len(classes), ands)
                > ceiling
            ):
                return None
            models.append((model, order))
        parts.append(models)
    # Keep H-mask complements inside their copied blocks so each local wire
    # retains its original driver and coordinate-bucket copying stays linear.
    gates = sum(
        sum(char in "ao~xX" for char in model.glyphs.values())
        for models in parts
        for model, _ in models
    )
    if forest is not None:
        gates += sum(char in "ao~xX" for char in forest[0].glyphs.values())
    # At most one AND per class and q-1 ORs; constants only reduce this count.
    if gates + 2 * len(classes) - 1 > 2 * len(table) + 8 * n + 111:
        return None
    model = _assemble_banks(
        parts,
        n,
        prefix,
        share_prefix_complements=False,
        shared_suffix=forest,
        online_returns=True,
    )
    height, width = model.bounds()
    return model if ceiling is None or height * width <= ceiling else None


def _repeated_cofactor_bank(table: str) -> _Layout | None:
    """Return a bank candidate when a nonconstant top-level cofactor repeats."""
    size = len(table) // 4
    chunks = [table[start : start + size] for start in range(0, len(table), size)]
    if not any(
        "0" in chunk and "1" in chunk and chunks.count(chunk) > 1 for chunk in chunks
    ):
        return None
    return _cofactor_bank_layout(table)


def _bank_exceeds_area(table: str, prefix_inputs: int, ceiling: int) -> bool:
    """Reject a bank whose retained H term glyphs already exceed the ceiling."""
    from . import _essential_table

    inputs = len(table).bit_length() - 1 - prefix_inputs
    size = 1 << inputs
    for chunk in dict.fromkeys(table[i : i + size] for i in range(0, len(table), size)):
        if "0" not in chunk or "1" not in chunk:
            continue
        used, _ = _essential_table(chunk, inputs)
        if len(used) < 6:
            continue
        tail = 3 if len(used) % 2 else 4
        leaf_side, offset = (96, 88) if tail == 3 else (192, 176)
        # The bottom-right prefix leaf always retains its term AND glyph,
        # even for an unselected chunk. Copying removes only external ports
        # and output glyphs. Translation can only enlarge this rectangle.
        far = 8 * inputs + 8 + _h_pool_size(len(used) - tail, tail) - leaf_side
        if (far + offset + 1) * (far + 9) > ceiling:
            return True
    return False


def _cofactor_bank_candidate(table: str, ceiling: int | None = None) -> _Layout | None:
    """Return the smaller named four/eight-bank candidate, preserving ties."""
    four = (
        _repeated_cofactor_bank(table)
        if ceiling is None or not _bank_exceeds_area(table, 2, ceiling)
        else None
    )
    eight = (
        _cofactor_bank_layout(table, 3)
        if ceiling is None or not _bank_exceeds_area(table, 3, ceiling)
        else None
    )
    if eight is None:
        return four
    if four is None:
        return eight
    four_height, four_width = four.bounds()
    eight_height, eight_width = eight.bounds()
    return eight if eight_height * eight_width < four_height * four_width else four
