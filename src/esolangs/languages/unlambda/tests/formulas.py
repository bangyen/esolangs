"""Unlambda's logical workspace: weighted terms and bound-share copies."""

from esolangs.languages.unlambda.interpreter import _App, _Cmd, _parse, _Term

_ARITIES = (2, 3, 4)


def _weight(term: _Term) -> int:
    """Leaves of ``term``, each ``k`` and ``s`` counted twice."""
    total, todo = 0, [term]
    while todo:
        node = todo.pop()
        if isinstance(node, _App):
            todo += (node.f, node.a)
        else:
            total += 2 if isinstance(node, _Cmd) and node.name in "ks" else 1
    return total


def _bound_weight(term: _Term) -> int:
    """Weight of the largest ``X`` in an ``@`-node applied to ``dX``, else 0."""
    best, todo = 0, [term]
    while todo:
        node = todo.pop()
        if not isinstance(node, _App):
            continue
        todo += (node.f, node.a)
        if (
            isinstance(node.f, _App)
            and node.f.f == _Cmd("@")
            and isinstance(node.a, _App)
            and node.a.f == _Cmd("d")
        ):
            best = max(best, _weight(node.a.a))
    return best


def workspace_terms(n: int, program: str) -> dict[str, int]:
    """Distinguish the constant chain and measure the other terms."""
    if program.replace("\n", "") in ("`@`d" * n + ".0", "`@`d" * n + ".1"):
        return {"C": 1, "P": 0, "S": 0}
    term = _parse(program)
    return {"C": 0, "P": _weight(term), "S": _bound_weight(term)}
