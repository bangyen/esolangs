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
    esolangs.Catalog: {
        "languages",
        "resolve",
        "bind",
        "with_language",
    },
    esolangs.ExecutionLimits: {
        "preparation_timeout",
        "execution_timeout",
        "total_timeout",
        "max_steps",
        "max_output",
        "max_memory",
    },
    esolangs.ExecutionOutcome: {"status", "observation", "error", "bound", "unwrap"},
    esolangs.ExecutionResult: {
        "output",
        "steps",
        "input_position",
        "input_reads",
        "input_past_end",
        "completion",
    },
    esolangs.PreparedProgram: {
        "evaluate",
        "artifact",
        "catalog",
        "language",
        "run",
        "make_vm",
        "make_debugger",
        "execute",
    },
    esolangs.ProgramArtifact: {
        "source",
        "language",
        "settings",
        "scale",
        "input_arity",
        "evaluate",
    },
    esolangs.TemplateArtifact: {
        "source",
        "language",
        "bindings",
        "settings",
        "fill",
        "evaluate",
        "spans",
    },
    esolangs.TemplateBindings: {"char", "setters", "inputs", "fill"},
    esolangs.Language: {
        "catalog",
        "settings",
        "from_source",
        "from_file",
        "execute",
        "prepare",
        "describe",
        "to_json",
        "encode_inputs",
        "evaluate",
        "generate",
        "instantiate",
        "from_json",
        "name",
        "read_answer",
        "run",
        "to_file",
        "make_vm",
        "make_debugger",
    },
    esolangs.Raster: {
        "from_png",
        "rows",
        "to_png",
        "upscaled",
    },
    esolangs.DialectSettings: {"language", "options"},
    esolangs.BooleanEvaluation: {"answer", "observation", "termination"},
    esolangs.CompressedText: {
        "chunks",
        "from_chunks",
        "limits",
        "plain_chunks",
        "repeated",
        "to_file",
        "to_gzip",
        "wrapped",
    },
    # No defaults, so its three fields are not class attributes.
    esolangs.TextLimits: set(),
    esolangs.LanguageInfo: set(esolangs.LanguageInfo.__slots__),
    # Fields without defaults are not class attributes.
    esolangs.LanguageDeclaration: {
        "aliases",
        "backend",
        "has_backend",
        "id",
        "parameterized",
        "source_suffix",
    },
    esolangs.DialectSchema: {"language", "choices", "defaults", "validate"},
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
        "observation",
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
