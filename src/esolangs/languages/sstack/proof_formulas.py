"""Snapshot-bit bounds."""

from esolangs.languages.sstack.interpreter import _parse


def workspace_terms(_: int, program: str) -> dict[str, int]:
    """Count parsed commands to bound the cursor."""
    return {"K": len(_parse(program))}
