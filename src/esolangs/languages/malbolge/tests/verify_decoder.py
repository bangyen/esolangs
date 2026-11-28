"""Replay the native decoder certificate against the installed generator assets."""

from __future__ import annotations

import subprocess
import tempfile
from array import array
from graphlib import TopologicalSorter
from pathlib import Path

from esolangs.languages.malbolge.generator.isa import _ACTIVE, _WORDS, _char_for
from esolangs.languages.malbolge.generator.lookup_domains import _glyph_domains
from esolangs.languages.malbolge.generator.packed import (
    _SOURCE_OPS,
    _Decoder,
    _decoder,
    _install_printers,
    _lookup_image,
)
from esolangs.languages.malbolge.generator.packed_layout import (
    _COLUMN_COUNT,
    _COLUMN_DISPATCH,
    _COLUMN_MARKER_BASE,
    _COLUMN_MARKER_STRIDE,
    _HIGH_OPERAND_OFFSET,
    _LONG_HUB,
    _LOOKUP,
    _ONE_HUB,
    _PRINTERS,
    _SHORT_HUB,
    _TAPS,
    _column_marker,
)
from esolangs.languages.malbolge.interpreter import _CRAZY, _XLAT1, _XLAT2
from esolangs.languages.malbolge.proof_formulas import _PACKED_COMMAND_BOUND
from esolangs.languages.malbolge.tests.proof_packed_decoder import check_cover
from esolangs.languages.malbolge.tests.proof_packed_decoder import main as check_storage


def _domain_seed(decoder: _Decoder, image: bytes) -> bytes:
    """Supply valid prefix operands for the derived lookup domain."""
    program = bytearray(image)
    _install_printers(program, 0)
    for word, occupied in enumerate(decoder.occupied):
        if occupied:
            # The left '<' makes every right operand safe.
            op = "<" if word == 39391 else _SOURCE_OPS.get(word, _ACTIVE)[0]
            program[word] = _char_for(op, word)
    for column in decoder.columns:
        address = _column_marker(column)
        program[address] = next(
            raw for op in _ACTIVE if (raw := _char_for(op, address)) >= 83
        )
    return bytes(program)


def _write_inputs(dest: Path) -> None:
    """Export the derived layout domains, VM tables and source operands."""
    decoder = _decoder()
    glyphs = _glyph_domains(decoder, _SOURCE_OPS)
    lookup = bytes(
        values[min(values)] if values and address % 3 != 1 else decoder.source[address]
        for address, values in glyphs.items()
    )
    image = _lookup_image(lookup)
    source = _domain_seed(decoder, image)
    (dest / "lookup-domains").write_bytes(
        bytes(values.get(bit, 0) for values in glyphs.values() for bit in (0, 1))
    )
    (dest / "initial").write_bytes(array("H", iter(source)).tobytes())
    (dest / "isa").write_bytes(
        (_XLAT1 + _XLAT2).encode("ascii") + bytes(v for row in _CRAZY for v in row)
    )
    (dest / "hubs").write_bytes(array("H", decoder.hubs).tobytes())
    primary, spill, slot = zip(*decoder.locations, strict=True)
    (dest / "primary").write_bytes(array("H", primary).tobytes())
    (dest / "spill").write_bytes(array("H", spill).tobytes())
    (dest / "slots").write_bytes(bytes(slot))

    domains = array("H", [0]) * (9 * _WORDS)
    for k, occupied in enumerate(decoder.occupied):
        if occupied:
            values = [_char_for(o, k) for o in _SOURCE_OPS.get(k, _ACTIVE)]
            if 29524 <= k <= 29527:
                values = [ord(_XLAT2[v - 33]) for v in values]
            domains[9 * k : 9 * k + 1 + len(values)] = array(
                "H", [len(values), *values]
            )
    (dest / "domains").write_bytes(domains.tobytes())

    mutable = bytearray(_WORDS)

    with (dest / "layouts").open("wb") as out:
        for polarity in range(8):
            program = bytearray(image)
            _install_printers(program, polarity)
            out.write(
                bytes([polarity])
                + program[4450:4700]
                + program[_LOOKUP.start : _LOOKUP.stop]
            )
            for addresses in (range(4450, 4700), _LOOKUP):
                for k in addresses:
                    if program[k] != source[k]:
                        mutable[k] = 1
    for address in _LOOKUP:
        if glyphs.get(address) and address % 3 != 1:
            mutable[address] = 1
    (dest / "mutable").write_bytes(mutable)


def main() -> None:
    """Verify all rows from reset and check the union of reachable control flow."""
    check_storage()
    check_cover()
    source = Path(__file__).with_name("verify_decoder.c").resolve()
    layout = {
        "LOOKUP_START": _LOOKUP.start,
        "LOOKUP_END": _LOOKUP.stop,
        "COLUMN_DISPATCH": _COLUMN_DISPATCH,
        "COLUMN_COUNT": _COLUMN_COUNT,
        "HIGH_OPERAND_OFFSET": _HIGH_OPERAND_OFFSET,
        "COLUMN_MARKER_BASE": _COLUMN_MARKER_BASE,
        "COLUMN_MARKER_STRIDE": _COLUMN_MARKER_STRIDE,
        "ONE_HUB": _ONE_HUB,
        "SHORT_HUB": _SHORT_HUB,
        "LONG_HUB": _LONG_HUB,
        "PRINTER_ENTRIES": "{" + ",".join(map(str, _PRINTERS)) + "}",
        "LOOKUP_TAPS": "{" + ",".join(map(str, _TAPS)) + "}",
    }
    defines = [f"-D{name}={value}" for name, value in layout.items()]
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        _write_inputs(work)
        subprocess.run(
            ["cc", "-std=c11", "-O3", *defines, str(source), "-o", "verify"],
            cwd=work,
            check=True,
        )
        subprocess.run([str(work / "verify")], cwd=work, check=True)
        predecessors: dict[int, set[int]] = {}
        for edge in (work / "edges").read_text(encoding="ascii").splitlines():
            before, after = map(int, edge.split())
            predecessors.setdefault(after, set()).add(before)
        longest: dict[int, int] = {}
        for pc in TopologicalSorter(predecessors).static_order():
            longest[pc] = 1 + max(
                (longest[v] for v in predecessors.get(pc, ())), default=0
            )
        assert max(longest.values()) == _PACKED_COMMAND_BOUND
        print(
            f"{len(longest):,} instruction addresses in the acyclic graph, "
            f"longest path {max(longest.values()):,}"
        )


if __name__ == "__main__":
    main()
