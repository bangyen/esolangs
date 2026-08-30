"""A minimal baseline JPEG reader, so a photographed or re-saved drawing loads.

Reading only, and only baseline sequential DCT -- the mode every ordinary
encoder produces by default.  Progressive JPEG, arithmetic coding, and 12-bit
samples raise rather than being guessed at.

This is the one piece of Line's tooling that genuinely reimplements a
library's algorithm rather than discovering it never needed one (see the
dependency notes in ``extract.py``, where every other removal turned on the
call not actually wanting what it asked for).  JPEG has no such shortcut: the
format *is* Huffman coding over quantized DCT coefficients, so decoding it
means doing that.  It is smaller than its reputation -- the entropy decoder
is a canonical-code table and a bit reader, and the inverse DCT is a pair of
8-point sums -- but it is real work, and it is here because dropping Pillow
otherwise left the pipeline reading strictly less than it used to.

A caution that belongs with the format rather than this module: JPEG is
lossy, and its block quantization erases pixels straight out of a 1px stroke.
A Line drawing rendered at 1x survives to about quality 34 and is destroyed
by 28; the same program rendered at 2x (see ``render.render``'s ``scale``)
holds to quality 15 and reconstructs exactly.  Prefer PNG for storage; this
exists so an image that has been through a lossy pipeline is still readable.
"""

from __future__ import annotations

import math

# Zig-zag order: JPEG stores a block's 64 coefficients along diagonals, from
# the DC term outward, so that the high-frequency tail a quantizer is likely
# to zero out lands together at the end of the run.
_ZIGZAG = (
    0, 1, 8, 16, 9, 2, 3, 10,
    17, 24, 32, 25, 18, 11, 4, 5,
    12, 19, 26, 33, 40, 48, 41, 34,
    27, 20, 13, 6, 7, 14, 21, 28,
    35, 42, 49, 56, 57, 50, 43, 36,
    29, 22, 15, 23, 30, 37, 44, 51,
    58, 59, 52, 45, 38, 31, 39, 46,
    53, 60, 61, 54, 47, 55, 62, 63,
)  # fmt: skip

# Separable 8-point IDCT basis, precomputed once: _COS[x][u] is the
# contribution of frequency u to sample x, and _SCALE folds in the 1/sqrt(2)
# the DC term carries in the DCT-III definition.
_COS = [[math.cos((2 * x + 1) * u * math.pi / 16) for u in range(8)] for x in range(8)]
_SCALE = [1 / math.sqrt(2)] + [1.0] * 7

# Markers, from the JPEG spec.  Only the ones that change decoding are named.
_SOI = 0xD8
_EOI = 0xD9
_SOS = 0xDA
_DQT = 0xDB
_DHT = 0xC4
_DRI = 0xDD
_APP0 = 0xE0
_COM = 0xFE
# Start-of-frame variants.  0xC0/0xC1 are the baseline sequential modes this
# decodes; the rest are named so the refusal can say which one was found.
_SOF_NAMES = {
    0xC0: "baseline sequential",
    0xC1: "extended sequential",
    0xC2: "progressive",
    0xC3: "lossless",
    0xC5: "differential sequential",
    0xC6: "differential progressive",
    0xC7: "differential lossless",
    0xC9: "arithmetic extended sequential",
    0xCA: "arithmetic progressive",
    0xCB: "arithmetic lossless",
    0xCD: "arithmetic differential sequential",
    0xCE: "arithmetic differential progressive",
    0xCF: "arithmetic differential lossless",
}
_SUPPORTED_SOF = (0xC0, 0xC1)


class _Component:
    """One colour channel's sampling factors, tables and decoded plane."""

    __slots__ = ("ac_table", "dc_table", "h", "identifier", "plane", "quant", "v")

    def __init__(self, identifier: int, h: int, v: int, quant: int) -> None:
        """Record a channel's identifier, sampling factors and quant table."""
        self.identifier = identifier
        self.h = h
        self.v = v
        self.quant = quant
        self.dc_table = 0
        self.ac_table = 0
        self.plane: list[list[int]] = []


def _build_huffman(counts: bytes, symbols: bytes) -> dict[tuple[int, int], int]:
    """Build a canonical Huffman table keyed by ``(bit length, code)``.

    JPEG stores only how many codes exist at each length 1..16 and the symbols
    in order; the codes themselves are implied, assigned in increasing order
    with a shift at each new length.  Keying by length as well as value is
    what makes the lookup unambiguous -- code 0 of length 2 is a different
    entry from code 0 of length 3.
    """
    table: dict[tuple[int, int], int] = {}
    code = 0
    index = 0
    for length in range(1, 17):
        for _ in range(counts[length - 1]):
            table[(length, code)] = symbols[index]
            code += 1
            index += 1
        code <<= 1
    return table


class _BitReader:
    """MSB-first bit reader over entropy-coded data, undoing byte stuffing.

    Inside the entropy stream a literal 0xFF byte is written as ``FF 00`` so
    it cannot be mistaken for a marker; the extra zero is skipped here.  A
    real marker (``FF`` followed by anything else) means this scan is over.
    """

    __slots__ = ("bit", "data", "pos")

    def __init__(self, data: bytes, pos: int = 0) -> None:
        """Start reading at byte ``pos`` of ``data``."""
        self.data = data
        self.pos = pos
        self.bit = 0

    def at_marker(self) -> bool:
        """Whether the reader is sitting on a marker rather than on data.

        A literal 0xFF inside the entropy stream is stuffed as ``FF 00``, so
        ``FF`` followed by anything else is a real marker and the coded data
        has ended here.
        """
        if self.pos + 1 >= len(self.data):
            return self.pos >= len(self.data)
        return self.data[self.pos] == 0xFF and self.data[self.pos + 1] != 0x00

    def read_bit(self) -> int:
        """Read one bit, or 0 once the data ends or a marker is reached.

        Neither is treated as an error: an encoder may leave the final byte
        short of a boundary, and a decoder that has consumed all the
        coefficients a block declares should stop at the marker rather than
        read through it.  Genuine truncation is better surfaced by the
        coverage check downstream than by an exception here.
        """
        if self.at_marker():
            return 0
        byte = self.data[self.pos]
        value = (byte >> (7 - self.bit)) & 1
        self.bit += 1
        if self.bit == 8:
            self.bit = 0
            # Step over the stuffed zero that followed a literal 0xFF.
            self.pos += 2 if byte == 0xFF else 1
        return value

    def receive(self, length: int) -> int:
        """Read ``length`` bits as an unsigned integer, most significant first."""
        value = 0
        for _ in range(length):
            value = (value << 1) | self.read_bit()
        return value

    def decode(self, table: dict[tuple[int, int], int]) -> int:
        """Read one Huffman-coded symbol, lengthening the code until it hits."""
        code = 0
        for length in range(1, 17):
            code = (code << 1) | self.read_bit()
            symbol = table.get((length, code))
            if symbol is not None:
                return symbol
        raise ValueError("bad Huffman code in JPEG entropy data")

    def align(self) -> None:
        """Skip to the next byte boundary, as a restart marker requires."""
        if self.bit:
            self.bit = 0
            self.pos += 1

    def skip_restart(self) -> bool:
        """Consume a restart marker if one is next, reporting whether it was.

        The encoder pads the last entropy byte before a restart, so aligning
        first is what puts the marker at ``pos``.
        """
        self.align()
        if (
            self.pos + 1 < len(self.data)
            and self.data[self.pos] == 0xFF
            and 0xD0 <= self.data[self.pos + 1] <= 0xD7
        ):
            self.pos += 2
            return True
        return False


def _extend(value: int, length: int) -> int:
    """Sign-extend a JPEG magnitude-category value.

    Coefficients are stored as a category (how many bits) plus those bits,
    where the low half of each category's range means negative.  Category 3
    covers -7..-4 and 4..7, for instance.
    """
    if length == 0:
        return 0
    return value if value >= (1 << (length - 1)) else value - (1 << length) + 1


def _idct_2d(block: list[float]) -> list[float]:
    """Inverse DCT on one 8x8 block, done as rows then columns.

    The 2-D transform is separable, so this is 16 eight-point sums rather than
    one 64x64 one.  Straightforward rather than one of the fast factorizations
    (AAN and friends): a Line drawing is a handful of blocks, and the plain
    form is the one that can be read against the spec's own definition.
    """
    rows = [0.0] * 64
    for y in range(8):
        base = y * 8
        for x in range(8):
            cosines = _COS[x]
            total = 0.0
            for u in range(8):
                coefficient = block[base + u]
                if coefficient:
                    total += _SCALE[u] * coefficient * cosines[u]
            rows[base + x] = total / 2

    out = [0.0] * 64
    for x in range(8):
        column = [rows[y * 8 + x] for y in range(8)]
        for y in range(8):
            cosines = _COS[y]
            total = 0.0
            for v in range(8):
                coefficient = column[v]
                if coefficient:
                    total += _SCALE[v] * coefficient * cosines[v]
            out[y * 8 + x] = total / 2
    return out


def _clamp(value: float) -> int:
    """Round to the nearest byte level, saturating at both ends.

    The IDCT works in floating point and its output can land a little outside
    0-255 on sharp edges, which is exactly what a 1px stroke is made of.
    """
    level = int(value + 128.5)
    return 0 if level < 0 else (255 if level > 255 else level)


def _parse_segments(
    data: bytes,
) -> tuple[
    dict[int, list[int]],
    dict[tuple[int, int], dict[tuple[int, int], int]],
    tuple[int, int, list[_Component]],
    int,
    int,
]:
    """Walk the marker segments, returning everything the scan needs."""
    if len(data) < 2 or data[0] != 0xFF or data[1] != _SOI:
        raise ValueError("not a JPEG file (no start-of-image marker)")

    quant: dict[int, list[int]] = {}
    huffman: dict[tuple[int, int], dict[tuple[int, int], int]] = {}
    frame: tuple[int, int, list[_Component]] | None = None
    restart_interval = 0
    pos = 2

    while pos < len(data):
        if data[pos] != 0xFF:
            pos += 1
            continue
        marker = data[pos + 1]
        pos += 2
        if marker in (0xFF, 0x00) or marker == _SOI:
            continue
        if marker == _EOI:
            break
        if 0xD0 <= marker <= 0xD7:  # standalone restart markers
            continue
        length = (data[pos] << 8) | data[pos + 1]
        body = data[pos + 2 : pos + length]

        if marker == _DQT:
            index = 0
            while index < len(body):
                precision, table_id = body[index] >> 4, body[index] & 15
                index += 1
                if precision:  # 16-bit quantization values
                    values = [
                        (body[index + 2 * i] << 8) | body[index + 2 * i + 1]
                        for i in range(64)
                    ]
                    index += 128
                else:
                    values = list(body[index : index + 64])
                    index += 64
                quant[table_id] = values
        elif marker == _DHT:
            index = 0
            while index < len(body):
                table_class, table_id = body[index] >> 4, body[index] & 15
                counts = body[index + 1 : index + 17]
                total = sum(counts)
                symbols = body[index + 17 : index + 17 + total]
                huffman[(table_class, table_id)] = _build_huffman(counts, symbols)
                index += 17 + total
        elif marker == _DRI:
            restart_interval = (body[0] << 8) | body[1]
            if restart_interval:
                # Refused rather than decoded: an implementation that got this
                # subtly wrong was tried and produced desynchronised garbage
                # partway down the image (correct for ~180 MCUs, then noise
                # where the reference is flat white), which is the worst
                # possible outcome -- a plausible-looking wrong drawing.
                # Restart markers are an error-resilience feature for lossy
                # transports; no encoder writes them by default, and nothing
                # that produces a Line drawing has reason to. Refusing keeps
                # the failure loud until someone has a real file that needs it.
                raise ValueError(
                    "JPEGs with restart markers are not supported "
                    f"(restart interval {restart_interval})"
                )
        elif marker in _SOF_NAMES:
            if marker not in _SUPPORTED_SOF:
                raise ValueError(
                    f"unsupported JPEG mode ({_SOF_NAMES[marker]}); "
                    "only baseline sequential JPEG is supported"
                )
            precision = body[0]
            if precision != 8:
                raise ValueError(f"unsupported JPEG sample precision {precision}")
            height = (body[1] << 8) | body[2]
            width = (body[3] << 8) | body[4]
            components = []
            for i in range(body[5]):
                offset = 6 + i * 3
                components.append(
                    _Component(
                        body[offset],
                        body[offset + 1] >> 4,
                        body[offset + 1] & 15,
                        body[offset + 2],
                    )
                )
            frame = (width, height, components)
        elif marker == _SOS:
            if frame is None:
                raise ValueError("JPEG scan before frame header")
            count = body[0]
            for i in range(count):
                identifier, tables = body[1 + 2 * i], body[2 + 2 * i]
                for component in frame[2]:
                    if component.identifier == identifier:
                        component.dc_table = tables >> 4
                        component.ac_table = tables & 15
            return quant, huffman, frame, restart_interval, pos + length
        pos += length

    raise ValueError("JPEG has no scan data")


def _decode_scan(
    data: bytes,
    start: int,
    quant: dict[int, list[int]],
    huffman: dict[tuple[int, int], dict[tuple[int, int], int]],
    frame: tuple[int, int, list[_Component]],
    restart_interval: int,
) -> None:
    """Decode the entropy-coded scan into each component's pixel plane.

    Blocks arrive grouped into MCUs (minimum coded units): one MCU holds
    ``h * v`` blocks of each component, so a subsampled chroma channel
    contributes fewer blocks per MCU than luma and ends up with a smaller
    plane, which :func:`_upsample` later stretches back out.
    """
    width, height, components = frame
    max_h = max(c.h for c in components)
    max_v = max(c.v for c in components)
    mcu_width, mcu_height = max_h * 8, max_v * 8
    mcus_x = (width + mcu_width - 1) // mcu_width
    mcus_y = (height + mcu_height - 1) // mcu_height

    for component in components:
        component.plane = [
            [0] * (mcus_x * component.h * 8) for _ in range(mcus_y * component.v * 8)
        ]

    reader = _BitReader(data, start)
    predictions = {component.identifier: 0 for component in components}
    block = [0.0] * 64

    for mcu in range(mcus_x * mcus_y):
        if restart_interval and mcu and mcu % restart_interval == 0:
            # A restart marker resets the DC predictors and realigns the bit
            # reader, so a corrupt stretch cannot desynchronise the whole rest
            # of the image.
            reader.skip_restart()
            predictions = {component.identifier: 0 for component in components}

        mcu_x, mcu_y = mcu % mcus_x, mcu // mcus_x
        for component in components:
            dc_table = huffman[(0, component.dc_table)]
            ac_table = huffman[(1, component.ac_table)]
            quant_table = quant[component.quant]
            for by in range(component.v):
                for bx in range(component.h):
                    for i in range(64):
                        block[i] = 0.0

                    length = reader.decode(dc_table)
                    diff = _extend(reader.receive(length), length)
                    predictions[component.identifier] += diff
                    block[0] = float(predictions[component.identifier] * quant_table[0])

                    index = 1
                    while index < 64:
                        symbol = reader.decode(ac_table)
                        run, size = symbol >> 4, symbol & 15
                        if size == 0:
                            if run != 15:  # end of block
                                break
                            index += 16  # ZRL: sixteen zero coefficients
                            continue
                        index += run
                        if index > 63:
                            break
                        value = _extend(reader.receive(size), size)
                        block[_ZIGZAG[index]] = float(value * quant_table[index])
                        index += 1

                    pixels = _idct_2d(block)
                    plane = component.plane
                    origin_y = (mcu_y * component.v + by) * 8
                    origin_x = (mcu_x * component.h + bx) * 8
                    for y in range(8):
                        row = plane[origin_y + y]
                        for x in range(8):
                            row[origin_x + x] = _clamp(pixels[y * 8 + x])


def _upsample(
    component: _Component, width: int, height: int, max_h: int, max_v: int
) -> list[list[int]]:
    """Stretch a subsampled component's plane back to full image size."""
    step_x, step_y = max_h // component.h, max_v // component.v
    plane = component.plane
    if step_x == 1 and step_y == 1:
        return [row[:width] for row in plane[:height]]
    return [
        [plane[y // step_y][x // step_x] for x in range(width)] for y in range(height)
    ]


def _ycbcr_to_grey(y: int, cb: int, cr: int) -> int:
    """Convert one YCbCr pixel to the grey level ``convert("L")`` would give.

    Not simply Y, though for a black-and-white drawing it is within a level of
    it.  Pillow converts YCbCr to RGB and *then* reduces with the ITU-R 601-2
    luma weights, and the RGB step clips each channel to 0-255 on the way --
    so a saturated colour comes out differently from its Y sample.  Following
    the same path keeps this a faithful decoder rather than one that happens
    to agree on the images Line cares about.
    """
    cb -= 128
    cr -= 128
    red = y + 1.402 * cr
    green = y - 0.344136 * cb - 0.714136 * cr
    blue = y + 1.772 * cb
    clip = (
        0 if red < 0 else (255 if red > 255 else int(red + 0.5)),
        0 if green < 0 else (255 if green > 255 else int(green + 0.5)),
        0 if blue < 0 else (255 if blue > 255 else int(blue + 0.5)),
    )
    return (clip[0] * 19595 + clip[1] * 38470 + clip[2] * 7471 + 0x8000) >> 16


def read_grey(data: bytes) -> list[bytearray]:
    """Decode baseline JPEG bytes to one ``bytearray`` of grey levels per row.

    A single-component file is already greyscale.  Three components are
    YCbCr, reduced through :func:`_ycbcr_to_grey` so the result matches what
    Pillow's ``convert("L")`` produces for the same file.
    """
    quant, huffman, frame, restart_interval, scan_start = _parse_segments(data)
    width, height, components = frame
    if len(components) not in (1, 3):
        raise ValueError(
            f"unsupported JPEG with {len(components)} colour components; "
            "only greyscale and YCbCr are supported"
        )

    _decode_scan(data, scan_start, quant, huffman, frame, restart_interval)

    max_h = max(c.h for c in components)
    max_v = max(c.v for c in components)
    luma = _upsample(components[0], width, height, max_h, max_v)
    if len(components) == 1:
        return [bytearray(row) for row in luma]

    # Chroma planes are box-upsampled (each sample repeated over its block)
    # where Pillow interpolates.  On saturated colour that shows as a
    # difference of up to ~17 levels along sharp colour edges; on the
    # black-and-white drawings this exists to read, the two agree to within
    # one level and produce byte-identical ink masks at every quality and
    # subsampling mode tested.  Interpolating would be a fidelity improvement
    # for photographs, which is not what this module is for.
    blue_chroma = _upsample(components[1], width, height, max_h, max_v)
    red_chroma = _upsample(components[2], width, height, max_h, max_v)
    return [
        bytearray(
            _ycbcr_to_grey(luma[y][x], blue_chroma[y][x], red_chroma[y][x])
            for x in range(width)
        )
        for y in range(height)
    ]


def read_grey_file(path: str) -> list[bytearray]:
    """Read a JPEG file from ``path`` as one ``bytearray`` of levels per row."""
    with open(path, "rb") as handle:
        return read_grey(handle.read())


def looks_like_jpeg(data: bytes) -> bool:
    """Whether ``data`` starts with a JPEG start-of-image marker."""
    return len(data) >= 2 and data[0] == 0xFF and data[1] == _SOI
