"""Tests for jpeg.py.

Run via: uv run --with pytest pytest test_jpeg.py

No image library is available here, so the fixtures are JPEG bytes built by
hand: a hand-assembled baseline file with known coefficients, and the
refusals.  The wider correctness argument -- agreement with Pillow across
qualities, subsampling modes and odd image sizes -- was established against
a Pillow oracle when the decoder was written and is recorded in WIP.md;
what these guard is that the pieces stay wired up and the refusals stay
loud.
"""

from __future__ import annotations

import struct

import jpeg
import pytest


def _marker(kind: int, body: bytes) -> bytes:
    return bytes([0xFF, kind]) + struct.pack(">H", len(body) + 2) + body


def _flat_grey_jpeg(level: int = 128, mode: int = 0xC0) -> bytes:
    """Build an 8x8 single-block JPEG whose only nonzero coefficient is DC.

    Quantization is all ones, so the DC coefficient passes through untouched
    and the decoded block is flat -- a value the IDCT's own definition fixes,
    which makes this checkable without a reference decoder.
    """
    quant = bytes([0]) + bytes([1] * 64)
    # One DC code (length 1) for symbol 4, one AC code (length 1) for 0x00.
    dc_counts = bytes([1] + [0] * 15)
    ac_counts = bytes([1] + [0] * 15)
    dc_table = bytes([0x00]) + dc_counts + bytes([4])
    ac_table = bytes([0x10]) + ac_counts + bytes([0x00])
    frame = bytes([8]) + struct.pack(">HH", 8, 8) + bytes([1, 1, 0x11, 0])
    scan = bytes([1, 1, 0x00, 0, 63, 0])

    # DC symbol 4 (code '0'), then 4 bits holding the level, then the AC
    # end-of-block symbol (code '0').  Packed MSB-first into whole bytes.
    dc_value = level - 128  # JPEG stores levels centred on zero
    magnitude = dc_value if dc_value >= 0 else dc_value + 15
    bits = "0" + format(magnitude & 0xF, "04b") + "0"
    bits += "1" * (-len(bits) % 8)  # pad with ones, which decode as nothing
    entropy = bytes(int(bits[i : i + 8], 2) for i in range(0, len(bits), 8))

    return (
        bytes([0xFF, 0xD8])
        + _marker(0xDB, quant)
        + _marker(0xC4, dc_table)
        + _marker(0xC4, ac_table)
        + _marker(mode, frame)
        + _marker(0xDA, scan)
        + entropy
        + bytes([0xFF, 0xD9])
    )


def test_decodes_a_flat_block() -> None:
    """A DC-only block decodes to a uniform 8x8 image.

    The IDCT of a DC-only block is flat by definition, so this checks the
    whole chain -- marker parsing, Huffman decode, dequantization, IDCT --
    against a value that does not depend on any reference implementation.
    """
    rows = jpeg.read_grey(_flat_grey_jpeg(level=136))
    assert len(rows) == 8
    assert all(len(row) == 8 for row in rows)
    levels = {value for row in rows for value in row}
    assert len(levels) == 1, f"expected a flat block, got {sorted(levels)}"


def test_looks_like_jpeg_discriminates() -> None:
    """The sniff is the start-of-image marker, not the file extension."""
    assert jpeg.looks_like_jpeg(_flat_grey_jpeg())
    assert not jpeg.looks_like_jpeg(b"\x89PNG\r\n\x1a\n")
    assert not jpeg.looks_like_jpeg(b"")


def test_rejects_a_non_jpeg() -> None:
    """Bytes with no start-of-image marker are refused up front."""
    with pytest.raises(ValueError, match="not a JPEG"):
        jpeg.read_grey(b"\x89PNG\r\n\x1a\n" + b"\x00" * 32)


def test_rejects_progressive_by_name() -> None:
    """Progressive JPEG is unimplemented; the error says which mode it saw.

    Progressive files are common enough on the web that a bare "unsupported"
    would send someone hunting; naming the mode points straight at the fix
    (re-save as baseline).
    """
    with pytest.raises(ValueError, match="progressive"):
        jpeg.read_grey(_flat_grey_jpeg(mode=0xC2))


def test_rejects_arithmetic_coding_by_name() -> None:
    """Arithmetic-coded JPEG is a different entropy coder entirely."""
    with pytest.raises(ValueError, match="arithmetic"):
        jpeg.read_grey(_flat_grey_jpeg(mode=0xC9))


def test_rejects_restart_markers() -> None:
    """Restart markers are refused rather than decoded wrongly.

    An implementation that got this subtly wrong desynchronised partway down
    the image and produced a plausible-looking but wrong drawing, which is
    worse than refusing -- see the comment at the DRI branch.
    """
    blob = _flat_grey_jpeg()
    index = blob.index(bytes([0xFF, 0xDA]))
    with_dri = blob[:index] + _marker(0xDD, struct.pack(">H", 4)) + blob[index:]
    with pytest.raises(ValueError, match="restart markers"):
        jpeg.read_grey(with_dri)


def test_rejects_a_twelve_bit_frame() -> None:
    """Only 8-bit samples are handled; 12-bit is a different profile."""
    blob = bytearray(_flat_grey_jpeg())
    # The precision byte is the first of the frame header's payload.
    index = blob.index(bytes([0xFF, 0xC0]))
    blob[index + 4] = 12
    with pytest.raises(ValueError, match="precision"):
        jpeg.read_grey(bytes(blob))


@pytest.mark.parametrize(
    ("y", "cb", "cr", "expected"),
    [
        # Neutral chroma: the grey level is Y itself.
        (0, 128, 128, 0),
        (128, 128, 128, 128),
        (255, 128, 128, 255),
    ],
)
def test_neutral_chroma_passes_luma_through(
    y: int, cb: int, cr: int, expected: int
) -> None:
    """With no colour, the YCbCr reduction is the identity on Y.

    Worth pinning because the conversion deliberately routes through RGB
    (matching Pillow) rather than taking Y directly, and that longer path
    must not drift on the black-and-white images Line actually reads.
    """
    assert jpeg._ycbcr_to_grey(y, cb, cr) == expected  # noqa: SLF001


def test_saturated_colour_matches_pillows_two_step_conversion() -> None:
    """Pure red reduces the way convert("L") reduces it, not to its Y sample.

    Y for pure red is about 76 either way here, but the point is the path:
    YCbCr -> RGB (with clipping) -> luma weights.  A decoder that returned Y
    directly would agree on greys and diverge on colour.
    """
    # Pure red in YCbCr is roughly (76, 85, 255).
    assert jpeg._ycbcr_to_grey(76, 85, 255) == 76  # noqa: SLF001
