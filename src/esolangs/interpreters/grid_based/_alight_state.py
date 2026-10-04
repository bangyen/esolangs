"""Cycle-safe value equality and alias-preserving Alight snapshots."""

from typing import cast


def _equal(left: object, right: object) -> bool:
    """Compare list contents, including cyclic graphs, without recursion."""
    pending = [(left, right)]
    seen: set[tuple[int, int]] = set()
    while pending:
        a, b = pending.pop()
        if isinstance(a, list) and isinstance(b, list):
            if len(a) != len(b):
                return False
            pair = (id(a), id(b))
            if pair in seen:
                continue
            seen.add(pair)
            pending.extend(zip(a, b, strict=True))
        elif isinstance(a, list) or isinstance(b, list) or a != b:
            return False
    return True


def _freeze(value: object) -> object:
    """Encode the object graph without losing aliases or recursing on cycles."""
    indices: dict[int, int] = {}
    pending: list[object] = []

    def edge(item: object) -> object:
        if not isinstance(item, dict | list | tuple):
            return ("value", item)
        identity = id(item)
        if identity not in indices:
            indices[identity] = len(pending)
            pending.append(item)
        return ("reference", indices[identity])

    root = edge(value)
    nodes: list[object] = []
    cursor = 0
    while cursor < len(pending):
        item = pending[cursor]
        if isinstance(item, dict):
            nodes.append(("dict", tuple((k, edge(v)) for k, v in sorted(item.items()))))
        else:
            values = cast(list[object] | tuple[object, ...], item)
            nodes.append(
                (
                    "list" if isinstance(item, list) else "tuple",
                    tuple(map(edge, values)),
                )
            )
        cursor += 1
    return root, tuple(nodes)
