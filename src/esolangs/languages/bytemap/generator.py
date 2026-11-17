"""Bytemap Boolean program generator: a paged table of five-byte prints.

Row ``k`` of the table projected onto its m essential inputs is a print at
page ``H``, row ``lo``, block ``mid`` of ``k = (H * 16 + mid) * 128 + lo``:
``00 5400 01`` prints its own ``00`` byte, ``00 5603 01`` its count byte 1.
Row 0 reads the inputs, first to last, into three counters by doubling and
adding each character; an ignored input is read over its own opcode.  The
chosen page copies ``lo + 1`` into the down jump atop each of its 16
blocks and ``J - 5 * mid`` into a left jump at column J, which lands on
block ``mid`` and drops onto the print.  A page header compares ``H`` with
0, and otherwise writes the counters, ``H`` less one, into the next page's
header 130 rows down.

Size:
    O(T): at most 21T/2 + 256 chars: 10 a row, a page's header and strip
    rows about 530 per 2,048 rows, and O(n) reading.  n=4 parity: 367
    chars, n=10 random 1847: 10,847 chars.  Constant tables: 8n + 10.

Decisions:
    A jump reaches 255 cells along one row or column, so a command touches
    data only in its own row or column.  The table hangs from column 0 so
    its rows carry no padding.  When the reading code fits in 255 cells,
    row 0 is page 0's header and the counters never move; otherwise they
    ride in data slots copied forward along row 0, then back along row 1.
    The direct header saves 231 chars at n=4 parity (598 against 367) and
    405 at n=10 random 1847 (11,252 against 10,847).  No carry crosses a
    byte below 20 essential inputs, where H outgrows one byte, so the
    programs run the same under either byte order (93 rows at n = 12, 14,
    16 under a little-endian interpreter).
"""

from typing import NamedTuple

from esolangs.generation.helpers import (
    _ASCII_ZERO,
    _validate_truth_table,
    essential_inputs,
    read_at,
)
from esolangs.generation.requests import GenerationRequest
from esolangs.runtime._program import Program

__all__ = ["bytemap"]

type _Cell = tuple[int, int]

_DOWN, _LEFT, _RIGHT, _UP = 0x52, 0x54, 0x56, 0x58
_PRINT = ((0x00, 0x54, 0x00, 0x01, 0xFF), (0x00, 0x56, 0x03, 0x01, 0xFF))
_LO_BITS, _MID_BITS = 7, 4
#: Room a segment of row 0 may take, under a jump's reach.
_SEGMENT = 230


class _Grid:
    """Cells by (row, column); rendered as hex rows, unset cells ``FF``."""

    def __init__(self) -> None:
        self.cells: dict[_Cell, int] = {}

    def put(self, at: _Cell, data: tuple[int, ...] | list[int]) -> None:
        r, c = at
        for i, byte in enumerate(data):
            assert self.cells.setdefault((r, c + i), byte) == byte, (r, c + i)

    def render(self) -> str:
        rows: dict[int, dict[int, int]] = {}
        for (r, c), byte in self.cells.items():
            rows.setdefault(r, {})[c] = byte
        lines = []
        for r in range(max(rows) + 1):
            row = rows.get(r, {})
            text = "".join(
                f"{row.get(c, 0xFF):02X}" for c in range(max(row, default=-1) + 1)
            )
            while text.endswith("FF"):  # a trailing FF is an unset cell
                text = text[:-2]
            lines.append(text)
        return "\n".join(lines)


def _jump(origin: _Cell, target: _Cell) -> tuple[int, int]:
    """Return the two-byte jump from ``origin`` to ``target``."""
    (r, c), (tr, tc) = origin, target
    dr, dc = tr - r, tc - c
    assert dr == 0 or dc == 0, (origin, target)
    assert abs(dr + dc) <= 255, (origin, target)
    if dr:
        return (_DOWN if dr > 0 else _UP), abs(dr)
    return (_RIGHT if dc >= 0 else _LEFT), abs(dc)


def _op(
    code: int,
    at: _Cell,
    a: _Cell | None,
    b: _Cell | None,
    w: _Cell,
    n: int,
) -> list[int]:
    """Return an arithmetic command at ``at``; ``None`` is the invalid jump."""
    return [
        code,
        *(_jump(at, a) if a else (0, 0)),
        *(_jump(at, b) if b else (0, 0)),
        *_jump(at, w),
        n,
    ]


def _copy(at: _Cell, source: _Cell, dest: _Cell, n: int) -> list[int]:
    """Return ``A0`` adding the invalid jump's 0 to ``source``: a copy."""
    return _op(0xA0, at, None, source, dest, n)


class _Layout(NamedTuple):
    """Where the counters, the data and page 0's entry sit."""

    offset: dict[str, int]
    width: dict[str, int]
    at_data: dict[str, int]
    data: list[int]
    k_v: int
    b0: int
    entry: _Cell


def _emit(
    lay: _Layout, at: _Cell, unit: tuple[str, ...], v0: _Cell, d0: _Cell
) -> list[int]:
    """Return one unit's bytes at ``at``, the counters at ``v0``, data at ``d0``."""

    def v(p: str) -> _Cell:
        return v0[0], v0[1] + lay.offset[p]

    def d(name: str) -> _Cell:
        return d0[0], d0[1] + lay.at_data[name]

    kind, *rest = unit
    if kind == "ignore":
        return [0x1A, _LEFT, 0, 1]
    part = rest[0]
    size = lay.width.get(part, 1)
    if kind == "first":
        return [0x1A, *_jump(at, (v0[0], v0[1] + lay.offset[part] + size - 1)), 1]
    if kind == "bit":
        s0 = d("S_" + part)
        read = [0x1A, *_jump(at, (s0[0], s0[1] + size - 1)), 1]
        c1, c2 = (at[0], at[1] + 4), (at[0], at[1] + 12)
        return (
            read
            + _op(0xA0, c1, v(part), v(part), v(part), size)
            + _op(0xA0, c2, v(part), s0, v(part), size)
        )
    fix = {"lo": (0xA0, "lo", "dd"), "mid5": (0xA2, "mid", "minus5")}
    fix |= {"mid": (0xA0, "mid", "cc"), "H": (0xA0, "H", "CH")}
    code, counter, constant = fix[part]
    return _op(code, at, v(counter), d(constant), v(counter), lay.width[counter])


def _units(n: int, part_of: dict[int, str]) -> list[tuple[int, tuple[str, ...]]]:
    """Return each input's unit: an ignored read, a first read, or a bit."""
    units: list[tuple[int, tuple[str, ...]]] = []
    for i in range(n):
        if i not in part_of:
            units.append((4, ("ignore",)))
            continue
        part = part_of[i]
        first = all(part_of.get(k) != part for k in range(i))
        units.append((4, ("first", part)) if first else (20, ("bit", part)))
    return units


def bytemap(truth_table: str) -> str:
    """Build a program printing ``truth_table[row]`` after reading every input."""
    n = _validate_truth_table(truth_table)
    essential = essential_inputs(truth_table, n)
    table = read_at(truth_table, essential, n)
    if not essential:
        # Each read writes its character over its own, already-run opcode.
        return "1A540001" * n + "".join(f"{b:02X}" for b in _PRINT[table == "1"])
    m = len(essential)
    lo_bits = min(m, _LO_BITS)
    mid_bits = min(m - lo_bits, _MID_BITS)
    h_bits = m - lo_bits - mid_bits
    rows, blocks, pages = 1 << lo_bits, 1 << mid_bits, 1 << h_bits
    k_h = (h_bits + 7) // 8
    # The counters, in a header's order: [mid][lo][H], H lowest, so one
    # subtraction of 1 decrements it.
    offset = {"mid": 0, "lo": int(mid_bits > 0)}
    offset["H"] = offset["lo"] + 1
    k_v = offset["H"] + k_h
    width = {"mid": 1, "lo": 1, "H": k_h}
    assert k_v <= 8, "a header holds at most 8 counter bytes"
    part_of: dict[int, str] = {}
    for j, i in enumerate(essential):
        part_of[i] = "H" if j < h_bits else "mid" if j < h_bits + mid_bits else "lo"
    units = _units(n, part_of)
    fixups: list[tuple[int, tuple[str, ...]]] = [(8, ("fix", "lo"))]
    if mid_bits:
        fixups += [(8, ("fix", "mid5")), (8, ("fix", "mid"))]
    if h_bits:
        fixups.append((8, ("fix", "H")))
    b0 = 5 * blocks  # the counters' column, just right of the strip
    jpos = b0 + 8 + 8 * blocks + 8 * (mid_bits > 0)
    zero = {
        p: (_ASCII_ZERO * ((1 << bits) - 1)) % (1 << 8 * width[p])
        for p, bits in (("H", h_bits), ("mid", mid_bits), ("lo", lo_bits))
    }
    k_c = max(k_h, 1)
    ch = (-zero["H"]) % (1 << 8 * k_c)
    # Data: [S_mid][S_lo][S_H][dd][minus5][cc][CH]
    data = [0, 0, *[0] * k_c, (1 - zero["lo"]) % 256, 0xFB]
    data += [(jpos + 5 * zero["mid"]) % 256, *ch.to_bytes(k_c, "big")]
    at_data = {"S_mid": 0, "S_lo": 1, "S_H": 2, "dd": 2 + k_c}
    at_data |= {"minus5": 3 + k_c, "cc": 4 + k_c, "CH": 5 + k_c}
    code = sum(length for length, _ in units + fixups)
    # Direct: row 0 is page 0's header, so the counters never move.
    start = b0 + (20 if pages > 1 else k_v)
    top = 0 if code + 2 + len(data) + start <= 255 else 1
    grid = _Grid()
    _pages(grid, table, top, rows, blocks, pages, k_v, k_h, offset, jpos)
    entry = (top, b0 + 8) if pages > 1 else (top, b0 - 2)
    lay = _Layout(offset, width, at_data, data, k_v, b0, entry)
    if top == 0:
        grid.put((0, 0), [_RIGHT, start])
        col = start
        for length, unit in units + fixups:
            grid.put(
                (0, col), _emit(lay, (0, col), unit, (0, b0), (0, start + code + 2))
            )
            col += length
        grid.put((0, col), [*_jump((0, col), entry)])
        grid.put((0, col + 2), data)
        return grid.render()
    _long(grid, lay, units, fixups)
    return grid.render()


def _long(
    grid: _Grid,
    lay: _Layout,
    units: list[tuple[int, tuple[str, ...]]],
    fixups: list[tuple[int, tuple[str, ...]]],
) -> None:
    """Lay row 0 as segments [copy][units][jump][slot], then return on row 1.

    A slot is [V][data]; each segment copies V from the last slot, so every
    reference stays inside a jump's reach.
    """
    k_v, b0 = lay.k_v, lay.b0
    slot_len = k_v + len(lay.data)
    segments: list[list[tuple[int, tuple[str, ...]]]] = [[]]
    used = 0
    for item in units:
        if used + item[0] + 10 + slot_len > _SEGMENT and segments[-1]:
            segments.append([])
            used = 8
        segments[-1].append(item)
        used += item[0]
    segments.append(fixups)
    col, previous, x_down = 0, -1, 0
    for index, segment in enumerate(segments):
        last = index == len(segments) - 1
        body = sum(length for length, _ in segment) + 8 * (previous >= 0)
        slot = col + body + 2
        if previous >= 0:
            grid.put((0, col), _copy((0, col), (0, previous), (0, slot), k_v))
            col += 8
        for length, unit in segment:
            grid.put((0, col), _emit(lay, (0, col), unit, (0, slot), (0, slot + k_v)))
            col += length
        grid.put((0, col), [_DOWN, 1] if last else [_RIGHT, slot + slot_len - col])
        filler = lay.data if last else [0] * len(lay.data)
        grid.put((0, slot), [0] * k_v + filler)
        previous, x_down, col = slot, col, slot + slot_len
    grid.put((1, x_down), [_RIGHT, previous - x_down])
    at = previous
    source: _Cell = (0, previous)
    while at - b0 > 240:
        # Land past page 0's header cells, which end at b0 + 20.
        nxt = max(at - 230, b0 + 21 + k_v)
        dest = nxt - k_v - 1
        grid.put((1, at), _copy((1, at), source, (1, dest), k_v))
        grid.put((1, at + 8), [*_jump((1, at + 8), (1, nxt))])
        source, at = (1, dest), nxt
    grid.put((1, at), _copy((1, at), source, (1, b0), k_v))
    grid.put((1, at + 8), [*_jump((1, at + 8), lay.entry)])


def _pages(
    grid: _Grid,
    table: str,
    top: int,
    rows: int,
    blocks: int,
    pages: int,
    k_v: int,
    k_h: int,
    offset: dict[str, int],
    jpos: int,
) -> None:
    """Lay each page: header row r, strip row r + 1, table rows r + 2 on."""
    b0 = 5 * blocks
    stride = rows + 2
    has_mid = blocks > 1
    for page in range(pages):
        r = top + page * stride
        grid.put((r, b0 - 2), [_DOWN, 1])
        grid.put((r, b0), [0] * k_v)
        h = b0 + 8
        if page < pages - 1:
            grid.put(
                (r, h),
                [
                    0xC3,
                    *_jump((r, h), (r, b0 + offset["H"])),
                    0,
                    0,
                    k_h,
                    *_jump((r, h), (r, b0 - 2)),
                    *_jump((r, h), (r, h + 10)),
                ],
            )
            grid.put((r, h + 10), [_DOWN, 2])
            # Row r + 2: copy the counters, H less one, to the next page; the
            # 1 sits in H's byte, so no borrow crosses bytes and either byte
            # order gives the same cells.  Row r + 3: zero these back to the
            # source's bytes, so a passed page leaves no written cell behind.
            carry, clear = (r + 2, b0), (r + 3, b0)
            const = (r + 2, b0 + 20)
            grid.put(carry, _op(0xA1, carry, (r, b0), const, (r + stride, b0), k_v))
            grid.put((r + 2, b0 + 8), [_RIGHT, 2, _DOWN, 1])
            grid.put((r + 2, h + 10), [_LEFT, h + 10 - b0])
            grid.put(const, [0] * (k_v - 1) + [1])
            grid.put(clear, _op(0xA1, clear, (r, b0), (r, b0), (r, b0), k_v))
            grid.put((r + 3, b0 + 8), [_DOWN, stride - 3, _LEFT, 10])
        elif pages > 1:
            grid.put((r, h), [_LEFT, h - b0 + 2])
        strip = r + 1
        for block in range(blocks):
            grid.put((strip, 5 * block), [_DOWN, 1])
        grid.put((strip, b0 - 2), [_RIGHT, 2])
        e = jpos + 2  # the copied counters: [cc][dd] or [dd]
        e_dd = e + int(has_mid)
        grid.put((strip, b0), _copy((strip, b0), (r, b0), (strip, e), 1 + int(has_mid)))
        x = b0 + 8
        for block in range(blocks):
            grid.put(
                (strip, x), _copy((strip, x), (strip, e_dd), (strip, 5 * block + 1), 1)
            )
            x += 8
        if has_mid:
            grid.put((strip, x), _copy((strip, x), (strip, e), (strip, jpos + 1), 1))
            x += 8
        assert x == jpos <= 255
        grid.put((strip, jpos), [_LEFT, jpos])
        grid.put((strip, e), [0] * (e_dd - e + 1))
        base = page * blocks * rows
        for block in range(blocks):
            for lo in range(rows):
                bit = table[base + block * rows + lo] == "1"
                grid.put((r + 2 + lo, 5 * block), _PRINT[bit])


def bytemap_request(request: GenerationRequest) -> Program:
    """Emit source through a typed backend request."""
    return bytemap(request.table)
