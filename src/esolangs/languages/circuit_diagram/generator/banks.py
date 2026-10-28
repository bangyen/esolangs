"""Share class bodies through predicate-and-function banks.

G<=2T+8n+111 gives state<=6T+25n+334, below 7T+2n-9 from n=10.
Bounded H bodies and coordinate-bucket copying use O(T) area and work.
This still does not share every residual across bodies.
"""

from __future__ import annotations

import sys
from collections.abc import Callable

from esolangs.generation.helpers import _validate_truth_table

from .forest import _Forest, _suffix_forest
from .hpool import (
    _atom_inputs,
    _large_pool_layout,
)
from .layout import _Layout, _layout_area, _RoutingLayout

type _Output = tuple[tuple[int, int], int]

# Input count where a shared suffix forest beats separate roots even with no
# repeated class.
_FOREST_PAYS_ALONE_INPUTS = 9


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
        buckets = self._copy_points(model, x, y, owner, omitted)
        self._index_points(x, y, height, width, *buckets)
        self._copy_runs(model, x, y, owner)

    def _copy_points(
        self,
        model: _Layout,
        x: int,
        y: int,
        owner: Callable[[int], int],
        omitted: set[tuple[int, int]],
    ) -> tuple[
        dict[int, list[int]],
        dict[int, list[int]],
        dict[int, list[tuple[int, int]]],
        dict[int, list[tuple[int, int]]],
    ]:
        """Copy a body's glyphs and junctions, bucketed by source coordinate."""
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
        return glyph_x, glyph_y, junction_x, junction_y

    def _index_points(
        self,
        x: int,
        y: int,
        height: int,
        width: int,
        glyph_x: dict[int, list[int]],
        glyph_y: dict[int, list[int]],
        junction_x: dict[int, list[tuple[int, int]]],
        junction_y: dict[int, list[tuple[int, int]]],
    ) -> None:
        """Fold copied points into the row and column indexes, in order."""
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

    def _copy_runs(
        self, model: _Layout, x: int, y: int, owner: Callable[[int], int]
    ) -> None:
        """Copy a body's horizontal and vertical wire runs, translated."""
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


class _SignalOwner:
    """Assign assembly signals to one body model's junction ids.

    Input-port junctions are pre-registered to their original input index;
    every other junction id gets a fresh signal on first sight, so junctions
    the body shares internally stay shared after copying.
    """

    def __init__(self, assembler: _BankAssembler) -> None:
        self._assembler = assembler
        self._mapping: dict[int, int] = {}

    def register(self, junction: int, signal: int) -> None:
        """Bind ``junction`` to ``signal`` before the copy pass sees it."""
        self._mapping[junction] = signal

    def lookup(self, junction: int) -> int:
        """Return the signal already bound to ``junction``."""
        return self._mapping[junction]

    def __call__(self, junction: int) -> int:
        """Return ``junction``'s signal, allocating a fresh one on first use."""
        if junction not in self._mapping:
            self._mapping[junction] = self._assembler.fresh()
        return self._mapping[junction]


class _BankAssembler:
    """Lay per-cofactor body models into one shared-bank layout.

    Bodies are copied into fresh row bands below the input and complement
    rails; each class's term outputs are ANDed with their mask, then all
    terms OR together. The mutable assembly state -- the signal serial, the
    current row, the rail endpoints, feeds, term results, held suffix roots,
    and the online carry tree -- lives on the instance instead of in nested
    closures.
    """

    def __init__(
        self,
        parts: list[list[tuple[_Layout, list[int]]]],
        n: int,
        prefix_inputs: int,
        *,
        shared_suffix: _Forest | None = None,
        left_returns: bool = False,
    ) -> None:
        """Capture the parts and set up the empty assembly state."""
        self.parts = parts
        self.n = n
        self.prefix_inputs = prefix_inputs
        self.shared_suffix = shared_suffix
        self.left_returns = left_returns
        widths = [model.bounds()[1] for models in parts for model, _ in models]
        if shared_suffix is not None:
            widths.append(shared_suffix[0].bounds()[1])
        self.right = max(widths) + 2 * n + 12
        self.body_x = 2 * n + 8
        self.layout = _BankLayout()
        self.serial = n
        self.reached: dict[int, tuple[int, int]] = {}
        self.feeds: list[tuple[int, tuple[int, int]]] = []
        self.results: list[tuple[tuple[int, int], int]] = []
        self.y = 2 * n + 8 + 4 * prefix_inputs
        self.held: list[tuple[tuple[int, int], int] | None] = [None] * len(parts)
        carry_levels = (len(parts) - 1).bit_length() + 1
        self.carry: list[_Output | None] = [None] * carry_levels
        self.temporary = self.right + 22 + 2 * carry_levels

    def fresh(self) -> int:
        """Allocate the next unused signal id."""
        self.serial += 1
        return self.serial - 1

    def join_carry(self, older: _Output, newer: _Output) -> _Output:
        """OR two pending carry roots into one, advancing past the gate."""
        gx, gy = self.temporary + 4, self.y + 4
        value = self.fresh()
        self.layout.glyph(gx, gy, "o")
        self.layout.junction(gx + 1, gy, value)
        for index, (point, signal) in enumerate((older, newer)):
            self.layout.route(point, (gx - 1, gy - 1 if index == 0 else gy + 1), signal)
        # The 16-class probe's two-row return hit lower-port clearance; use four.
        self.layout.route((gx + 1, gy), (gx + 1, gy + 4), value)
        self.layout.route((gx + 1, gy + 4), (self.temporary, gy + 4), value)
        self.y = gy + 8
        return (self.temporary, gy + 4), value

    def assemble(self) -> _Layout:
        """Build the bank layout: rails, bodies, feeds, then the output OR."""
        self._emit_input_rails()
        for group, models in self._assembly_groups():
            self._assemble_group(group, models)
        self._route_feeds()
        if len(self.parts) > 1:
            return self._fold_online_returns()
        return self._fold_term_results()

    def _assembly_groups(self) -> list[tuple[int, list[tuple[_Layout, list[int]]]]]:
        """Return the part groups in assembly order, shared suffix first."""
        groups = list(enumerate(self.parts))
        if self.shared_suffix is not None:
            groups.insert(
                0,
                (
                    -1,
                    [(self.shared_suffix[0], list(range(self.prefix_inputs, self.n)))],
                ),
            )
        return groups

    def _emit_input_rails(self) -> None:
        """Run the n input ports down the left edge and record their points."""
        for i in range(self.n):
            column = 2 * i + 2
            self.layout.input_port(2 * i, column, i)
            self.reached[i] = (column, 2 * i)

    def _assemble_group(
        self, group: int, models: list[tuple[_Layout, list[int]]]
    ) -> None:
        """Copy one cofactor class's bodies, then combine its term outputs."""
        held_root = self.held[group] if group >= 0 else None
        outputs: list[tuple[tuple[int, int], int]] = (
            [] if held_root is None else [held_root]
        )
        for model, port_order in models:
            self._assemble_model(group, model, port_order, outputs)
        if group == -1:
            return
        if len(outputs) == 2:
            output = self._and_term_outputs(outputs)
        else:
            [output] = outputs
        self._queue_term_output(group, output)
        self.y += 8

    def _assemble_model(
        self,
        group: int,
        model: _Layout,
        port_order: list[int],
        outputs: list[tuple[tuple[int, int], int]],
    ) -> None:
        """Copy one body into fresh rows and record its output endpoint."""
        owner = _SignalOwner(self)
        self._register_ports(model, port_order, owner)
        outpoints = [point for point, char in model.glyphs.items() if char == ":"]
        out = outpoints[0]
        endpoint = out[0] - 2, out[1]
        omitted = {
            cell for point in outpoints for cell in (point, (point[0] - 1, point[1]))
        }
        self.layout.copy_block(model, self.body_x, self.y, owner, omitted)
        if group == -1:
            self._hold_suffix_roots(model, owner)
        else:
            outputs.append(
                (
                    (self.body_x + endpoint[0], self.y + endpoint[1]),
                    owner(model.junctions[endpoint]),
                )
            )
        self.y += model.bounds()[0] + 8

    def _register_ports(
        self, model: _Layout, port_order: list[int], owner: _SignalOwner
    ) -> None:
        """Bind the body's input-port junctions to the original input indices."""
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
            owner.register(signal, i)
            self.feeds.append((i, (self.body_x + x, self.y + row)))

    def _hold_suffix_roots(self, model: _Layout, owner: _SignalOwner) -> None:
        """Park the shared suffix roots past the term-result rails."""
        if self.shared_suffix is None:
            raise AssertionError("missing suffix forest")
        for index, point in enumerate(self.shared_suffix[1]):
            if point is None:
                continue
            source = self.body_x + point[0], self.y + point[1]
            signal = owner(model.junctions[point])
            # Hold roots beyond term-result rails; each ends at its
            # consuming AND, which may follow earlier carry ORs.
            column = self.right + 25 + 2 * len(self.parts) + 2 * index
            self.layout.route(source, (column, source[1]), signal, "across")
            self.held[index] = ((column, source[1]), signal)

    def _and_term_outputs(self, outputs: list[tuple[tuple[int, int], int]]) -> _Output:
        """AND a class's two term outputs (mask and body) into one signal."""
        gx, gy = self.right + 8, self.y + 4
        value = self.fresh()
        self.layout.glyph(gx, gy, "a")
        self.layout.junction(gx + 1, gy, value)
        for j, (source, signal) in enumerate(outputs):
            target = gx - 1, gy - 1 if j == 0 else gy + 1
            via = self.right + 2 + 2 * j, target[1]
            if self.shared_suffix is not None and j == 0:
                # A held root must descend before returning left;
                # returning on its footer row crosses other exports.
                above = via[0], gy - 4
                self.layout.route(source, above, signal, "down")
                self.layout.route(above, via, signal)
            else:
                self.layout.route(source, via, signal, "across")
            self.layout.route(via, target, signal)
        self.y = gy + 8
        return (gx + 1, gy), value

    def _queue_term_output(self, group: int, output: _Output) -> None:
        """Queue one class's term output for the final OR.

        With online returns the terms fold into a binary carry tree as they
        arrive; otherwise each term waits on its own result rail.
        """
        source, signal = output
        if len(self.parts) > 1:
            self.layout.route(source, (self.temporary, source[1]), signal)
            self._stash_carry(((self.temporary, source[1]), signal))
        else:
            column = max(self.right + 22 + 2 * group, source[0])
            if source != (column, source[1]):
                self.layout.route(source, (column, source[1]), signal)
            self.results.append(((column, source[1]), signal))

    def _stash_carry(self, current: _Output) -> None:
        """Fold ``current`` into the carry tree and park it in a free slot."""
        depth = 0
        while (pending := self.carry[depth]) is not None:
            current = self.join_carry(pending, current)
            self.carry[depth] = None
            depth += 1
        point, signal = current
        if self.left_returns:
            # Four rows clear the producing gate's lower input port.
            landing = point[0], point[1] + 4
            self.layout.route(point, landing, signal, "down")
            slot = 2 * depth + 1, landing[1]
            self.layout.route(landing, slot, signal, "across")
        else:
            slot = self.right + 22 + 2 * depth, point[1]
            self.layout.route(point, slot, signal)
        self.carry[depth] = slot, signal

    def _route_feeds(self) -> None:
        """Drop each input rail down to the body rows that read it."""
        for i, target in self.feeds:
            self.layout.route(self.reached[i], target, i)
            self.reached[i] = self.reached[i][0], target[1]

    def _fold_online_returns(self) -> _Layout:
        """OR the carry tree's pending roots and emit the output glyphs."""
        pending_roots = [pending for pending in self.carry if pending is not None]
        result = pending_roots[0]
        # Fold small rightmost blocks first: OR depth stays ceil(log2 q).
        for pending in pending_roots[1:]:
            result = self.join_carry(pending, result)
        point, signal = result
        endpoint = point[0], self.y + 4
        self.layout.route(point, endpoint, signal)
        self.layout.glyph(endpoint[0] + 1, endpoint[1], "-")
        self.layout.glyph(endpoint[0] + 2, endpoint[1], ":")
        return self.layout

    def _fold_term_results(self) -> _Layout:
        """Emit the output glyphs for the one queued term result."""
        [(point, _signal)] = self.results
        self.layout.glyph(point[0] + 1, point[1], "-")
        self.layout.glyph(point[0] + 2, point[1], ":")
        return self.layout


def _class_gate_cap(table_size: int, n: int) -> int:
    """Return the gate budget that keeps written state below 7T+2n-9."""
    return 2 * table_size + 8 * n + 111


def _gate_count(model: _Layout) -> int:
    """Return how many gate glyphs (``a o ~ x X``) ``model`` draws."""
    return sum(char in "ao~xX" for char in model.glyphs.values())


def _chunks(table: str, size: int) -> list[str]:
    """Cut ``table`` into consecutive subtables of ``size`` rows."""
    return [table[start : start + size] for start in range(0, len(table), size)]


def _assemble_banks(
    parts: list[list[tuple[_Layout, list[int]]]],
    n: int,
    prefix_inputs: int,
    *,
    shared_suffix: _Forest | None = None,
    left_returns: bool = False,
) -> _Layout:
    """Assemble per-cofactor bodies into one shared-bank layout.

    Thin wrapper over :class:`_BankAssembler`, which holds the mutable
    assembly state.
    """
    return _BankAssembler(
        parts,
        n,
        prefix_inputs,
        shared_suffix=shared_suffix,
        left_returns=left_returns,
    ).assemble()


def _residual_class_bank_candidate(
    table: str, ceiling: int | None = None
) -> _Layout | None:
    """Choose separate or shared suffix roots by exact area, preserving ties."""
    separate = _class_bank_layout(table, ceiling, shared=False)
    shared_ceiling = ceiling
    if separate is not None:
        area = _layout_area(separate)
        shared_ceiling = area if ceiling is None else min(ceiling, area)
    forest = _class_bank_layout(table, shared_ceiling, shared=True)
    if forest is None:
        return separate
    if separate is None:
        return forest
    return forest if _layout_area(forest) < _layout_area(separate) else separate


def _pool_budget(ceiling: int | None) -> int | None:
    """Return the bank area budget: ``ceiling``, unbounded when ``None``.

    ``None`` when nothing fits. The bank gate caps already bound the work.
    """
    if ceiling is None:
        return sys.maxsize
    return ceiling if ceiling > 0 else None


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
    tail = _atom_inputs(n)
    prefix = n - tail
    if prefix < 2 or len(set(table)) == 1:
        return None
    size = 1 << tail
    chunks = _chunks(table, size)
    classes = [chunk for chunk in dict.fromkeys(chunks) if "1" in chunk]
    # Keep the former implied class cap independently of the gate count:
    # sparse masks can fit the workspace even when their worst-case bound cannot.
    # At n=9 the shared forest pays without a repeated class: it folds the
    # four distinct roots' internal seven-input residuals together (dense9
    # executes in 258,216 characters; random n=9 tables save 40% of chars,
    # 20% of area, over separate roots, 40 tables).
    if len(classes) >= 1 << (tail + 1) or not any(
        "0" in chunk
        and (chunks.count(chunk) > 1 or (shared and n == _FOREST_PAYS_ALONE_INPUTS))
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
    gates = sum(_gate_count(model) for models in parts for model, _ in models)
    if forest is not None:
        gates += _gate_count(forest[0])
    # At most one AND per class and q-1 ORs; constants only reduce this count.
    if gates + 2 * len(classes) - 1 > _class_gate_cap(len(table), n):
        return None
    model = _assemble_banks(
        parts,
        n,
        prefix,
        shared_suffix=forest,
    )
    return model if ceiling is None or _layout_area(model) <= ceiling else None
