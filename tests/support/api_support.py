"""Reusable api support helpers."""

from __future__ import annotations

import json
from pathlib import Path

import esolangs
import esolangs.debugger as debugger_api

SIGNATURES: dict[str, str] = json.loads(
    (Path(__file__).resolve().parents[1] / "api/signatures.json").read_text()
)


PUBLIC_MEMBERS = {
    esolangs.ProgramArtifact: {"source", "language", "settings", "scale"},
    esolangs.TemplateArtifact: {"source", "language", "bindings", "settings", "fill"},
    esolangs.TemplateBindings: {"char", "setters", "inputs", "fill"},
    esolangs.Language: {
        "describe",
        "dump_program",
        "encode_inputs",
        "generate",
        "generate_artifact",
        "load_artifact",
        "instantiate",
        "load_program",
        "name",
        "read_answer",
        "run",
    },
    esolangs.Raster: {
        "from_png",
        "language",
        "rows",
        "scale",
        "settings",
        "tagged",
        "to_png",
        "upscaled",
    },
    esolangs.DialectSettings: {"options"},
    debugger_api.Debugger: {
        "break_at",
        "break_on_cell",
        "break_on_output",
        "break_on_stack",
        "break_when",
        "clear_breakpoints",
        "dumps_on_the_post_halt_step",
        "eof_is_a_value",
        "halted",
        "ip",
        "ip_shape",
        "memory",
        "output",
        "ptr",
        "run",
        "self_halts",
        "snapshot",
        "stack",
        "step",
        "steppable_to_answer",
        "views",
        "watch_cell",
        "watch_stack",
    },
}
