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


def _workspace(n: int, program: str) -> int:
    """Tight constant task/frame peaks; otherwise 16(P+nS)+D bl(D)+9+bl(n)."""
    bl = int.bit_length
    if program.replace("\n", "") in ("`@`d" * n + ".0", "`@`d" * n + ".1"):
        # Task: 16n+8; character/done/input: 9+bl(n). At continuation
        # depth d>=2, live terms cost 16n+16-8d, maximized at d=2.
        # Cached continuation depths do not belong to logical workspace.
        return 32 * n + 17 + bl(n)
    term = _parse(program)
    frames = 3 * n + 9
    return (
        16 * (_weight(term) + n * _bound_weight(term)) + frames * bl(frames) + 9 + bl(n)
    )
