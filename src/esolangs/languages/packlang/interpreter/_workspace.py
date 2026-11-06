"""Logical suspended expressions, independent of parser repr and cycle keys."""

from collections.abc import Hashable

from esolangs.runtime._state import WorkspaceModel, WorkspaceVariant

_WORKSPACE_MODEL = WorkspaceModel(
    "packlang-v1", ("frames", "input_cursor", "input_reads")
)


def _term(value: object) -> Hashable:
    """Freeze expression nodes iteratively; constructor names are schema metadata."""
    frozen: dict[int, Hashable] = {}
    pending = [(value, False)]
    while pending:
        node, ready = pending.pop()
        if id(node) in frozen:
            continue
        if node is None or isinstance(node, (str, int)):
            frozen[id(node)] = node
            continue
        if not isinstance(node, tuple):
            raise TypeError("workspace expressions require parser values")
        tagged = bool(node) and isinstance(node[0], str)
        parts = node[1:] if tagged else node
        if ready:
            frozen[id(node)] = WorkspaceVariant(
                str(node[0]) if tagged else "arguments",
                tuple(frozen[id(part)] for part in parts),
            )
        else:
            pending.append((node, True))
            pending.extend((part, False) for part in parts)
    return frozen[id(value)]
