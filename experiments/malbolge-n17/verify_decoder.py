"""Replay the native decoder certificate against the installed generator assets."""

from __future__ import annotations

import subprocess
import tempfile
from array import array
from graphlib import TopologicalSorter
from pathlib import Path
from random import Random

from esolangs.languages.malbolge.generator import malbolge
from esolangs.languages.malbolge.generator.isa import _ACTIVE, _WORDS, _char_for
from esolangs.languages.malbolge.generator.packed import (
    _SOURCE_OPS,
    _decoder,
    _install_layout,
    _settings,
)
from esolangs.languages.malbolge.interpreter import _CRAZY, _XLAT1, _XLAT2
from esolangs.languages.malbolge.proof_formulas import _PACKED_COMMAND_BOUND
from esolangs.languages.malbolge.tests.proof_packed_decoder import main as check_cover


def _write_inputs(dest: Path) -> None:
    """Export the executable layouts, VM tables and permitted source operands."""
    decoder = _decoder()
    rng = Random(17017)
    source = malbolge("".join(str(rng.randrange(2)) for _ in range(1 << 17)))
    (dest / "initial").write_bytes(array("H", map(ord, source)).tobytes())
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
    baseline = source.encode("ascii")
    with (dest / "layouts").open("wb") as out:
        for lookup, perm in _settings()[0]:
            for polarity in range(8):
                program = bytearray(decoder.source)
                _install_layout(program, lookup, perm, polarity)
                out.write(
                    bytes([*perm, polarity]) + program[4450:4700] + program[5213:5548]
                )
                for addresses in (range(4450, 4700), range(5213, 5548)):
                    for k in addresses:
                        if program[k] != baseline[k]:
                            mutable[k] = 1
    (dest / "mutable").write_bytes(mutable)


def main() -> None:
    """Verify all rows from reset and check the union of reachable control flow."""
    check_cover()
    source = Path(__file__).with_name("verify_decoder.c").resolve()
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        _write_inputs(work)
        subprocess.run(
            ["cc", "-std=c11", "-O3", str(source), "-o", "verify"], cwd=work, check=True
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
