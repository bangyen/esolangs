"""Boolfuck Boolean generator via the author's fixed Brainfuck lowering."""

from esolangs.tools.brainfuck import brainfuck

_LOWER = {
    "+": ">[>]+<[+<]>>>>>>>>>[+]<<<<<<<<<",
    "-": ">>>>>>>>>+<<<<<<<<+[>+]<[<]>>>>>>>>>[+]<<<<<<<<<",
    "<": "<<<<<<<<<",
    ">": ">>>>>>>>>",
    ",": ">,>,>,>,>,>,>,>,<<<<<<<<",
    ".": ">;>;>;>;>;>;>;>;<<<<<<<<",
    "[": ">>>>>>>>>+<<<<<<<<+[>+]<[<]>>>>>>>>>[+<<<<<<<<[>]+<[+<]",
    "]": ">>>>>>>>>+<<<<<<<<+[>+]<[<]>>>>>>>>>]<[+<]",
}


def boolfuck(truth_table: str) -> str:
    """Lower the linear Brainfuck construction with constant-size replacements."""
    return "".join(_LOWER.get(c, "") for c in brainfuck(truth_table))
