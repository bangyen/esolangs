"""Replay the native decoder certificate against the installed generator assets."""

from __future__ import annotations

import argparse
import subprocess
import tempfile
from array import array
from graphlib import TopologicalSorter
from pathlib import Path
from random import Random

from esolangs.languages.malbolge.generator import malbolge
from esolangs.languages.malbolge.generator.isa import _ACTIVE, _WORDS, _char_for
from esolangs.languages.malbolge.generator.lookup_domains import _LOOKUP, _glyph_domains
from esolangs.languages.malbolge.generator.packed import (
    _SOURCE_OPS,
    _Decoder,
    _decoder,
    _install_layout,
    _layouts,
)
from esolangs.languages.malbolge.interpreter import _CRAZY, _XLAT1, _XLAT2
from esolangs.languages.malbolge.proof_formulas import _PACKED_COMMAND_BOUND
from esolangs.languages.malbolge.tests.proof_packed_decoder import main as check_cover


def _domain_seed(decoder: _Decoder, lookup: bytes) -> bytes:
    """Supply valid prefix operands independently of the stored lookup cover."""
    program = bytearray(decoder.source)
    _install_layout(program, lookup, (0, 1, 2), 0)
    for word, occupied in enumerate(decoder.occupied):
        if occupied:
            # The left '<' makes every right operand safe.
            op = "<" if word == 39391 else _SOURCE_OPS.get(word, _ACTIVE)[0]
            program[word] = _char_for(op, word)
    for column in decoder.columns:
        address = 51031 + 3 * column
        program[address] = next(
            raw for op in _ACTIVE if (raw := _char_for(op, address)) >= 83
        )
    return bytes(program)


def _write_inputs(dest: Path, *, domain_proof: bool = False) -> None:
    """Export layouts, VM tables and permitted source operands."""
    decoder = _decoder()
    glyphs = _glyph_domains(decoder, _SOURCE_OPS) if domain_proof else {}
    layouts: tuple[tuple[bytes, tuple[int, ...]], ...]
    if domain_proof:
        lookup = bytes(
            values[min(values)]
            if values and address % 3 != 1
            else decoder.source[address]
            for address, values in glyphs.items()
        )
        source = _domain_seed(decoder, lookup)
        layouts = ((lookup, (0, 1, 2)),)
        (dest / "lookup-domains").write_bytes(
            bytes(values.get(bit, 0) for values in glyphs.values() for bit in (0, 1))
        )
    else:
        rng = Random(17017)
        source = malbolge(
            "".join(str(rng.randrange(2)) for _ in range(1 << 17))
        ).encode("ascii")
        layouts = _layouts()
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
        for lookup, perm in layouts:
            for polarity in range(8):
                program = bytearray(decoder.source)
                _install_layout(program, lookup, perm, polarity)
                out.write(
                    bytes([*perm, polarity]) + program[4450:4700] + program[5213:5548]
                )
                for addresses in (range(4450, 4700), range(5213, 5548)):
                    for k in addresses:
                        if program[k] != source[k]:
                            mutable[k] = 1
    for address in _LOOKUP:
        if glyphs.get(address) and address % 3 != 1:
            mutable[address] = 1
    (dest / "mutable").write_bytes(mutable)


def main(*, domain_proof: bool = False) -> None:
    """Verify all rows from reset and check the union of reachable control flow."""
    if not domain_proof:
        check_cover()
    source = Path(__file__).with_name("verify_decoder.c").resolve()
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        _write_inputs(work, domain_proof=domain_proof)
        flags = ["-DMALBOLGE_DOMAIN_PROOF"] if domain_proof else []
        subprocess.run(
            ["cc", "-std=c11", "-O3", *flags, str(source), "-o", "verify"],
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
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--domains", action="store_true", help="Verify all derived lookup glyphs"
    )
    main(domain_proof=parser.parse_args().domains)
