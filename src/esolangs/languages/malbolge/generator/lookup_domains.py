"""Derive the packed decoder's native lookup glyph domains."""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

from esolangs.languages.malbolge.generator.isa import _ACTIVE, _WORDS, _char_for
from esolangs.languages.malbolge.interpreter import _XLAT2, _Machine, _op
from esolangs.runtime.io import ScriptedIO

if TYPE_CHECKING:
    from .packed import _Decoder

_LOOKUP = range(5213, 5548)
_GUARDS = {5585: 5617, 5657: 5687}
_HUBS = ((45925, 54673), (41551,))


def _rejoins(
    machine: _Machine,
    start: int,
    raw: int,
    operands: Mapping[int, tuple[int, ...]],
    mutable_reads: set[int],
) -> bool:
    """Propagate the guard's allowed data pointers until its return."""
    memory = machine.memory
    pointers = {raw + 1}
    for pc in range(start + 1, _GUARDS[start]):
        op = _op(memory[pc], pc)
        if op == "o":
            pointers = {(pointer + 1) % _WORDS for pointer in pointers}
            continue
        assert op == "j"
        if pointers & mutable_reads:
            return False
        following = set()
        for pointer in pointers:
            values = operands.get(pointer, ())
            if len(values) <= 1:
                values = ()
            for raw_value in (*values, memory[pointer]):
                value = raw_value
                if start <= pointer < pc and 33 <= value <= 126:
                    value = ord(_XLAT2[value - 33])
                following.add((value + 1) % _WORDS)
        pointers = following
    return pointers == {86}


def _glyph_domains(
    decoder: _Decoder, source_ops: Mapping[int, str]
) -> dict[int, dict[int, int]]:
    """Pick the legal native glyph for each available binary label."""
    hubs = decoder.hubs
    output_hubs = set(_HUBS[0] + _HUBS[1])
    lookup_operands = {
        address for address in _LOOKUP if hubs[decoder.source[address]] in output_hubs
    }
    mutable_reads = lookup_operands | {51031 + 3 * col for col in decoder.columns}
    operands = {
        address: tuple(
            ord(_XLAT2[raw - 33]) if 29524 <= address <= 29527 else raw
            for raw in (
                _char_for(op, address) for op in source_ops.get(address, _ACTIVE)
            )
        )
        for address, used in enumerate(decoder.occupied)
        if used
    }
    machine = _Machine(decoder.source.decode("ascii"), ScriptedIO("0" * 17))
    remaining = set(_GUARDS)
    palette = set(range(33, 127))
    for _ in range(12000):
        _, pc, _, halted = machine.state
        if halted:
            break
        if pc in remaining:
            palette = {
                raw
                for raw in palette
                if _rejoins(machine, pc, raw, operands, mutable_reads)
            }
            remaining.remove(pc)
            if not remaining:
                break
        machine.step()
    assert not remaining
    result: dict[int, dict[int, int]] = {}
    for address in _LOOKUP:
        options: dict[int, int] = {}
        result[address] = options
        if address not in lookup_operands:
            continue
        glyphs = sorted(
            raw
            for op in _ACTIVE
            if (raw := _char_for(op, address)) in palette
            or not (address % 3 == 2 and address <= 5492)
        )
        for bit, preferred in enumerate(_HUBS):
            for hub in preferred:
                if (
                    glyph := next((raw for raw in glyphs if hubs[raw] == hub), None)
                ) is not None:
                    options[bit] = glyph
                    break
        assert options
    return result
