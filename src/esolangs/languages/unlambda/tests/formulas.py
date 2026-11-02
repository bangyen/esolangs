"""Unlambda's workspace: program weight, bound-share copies, frame depths."""

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
        # depth d>=2: 16n+16-8d+sum(bl(i), i=1..d). Its increments
        # bl(d)-8 increase, so the maximum is at depth 2 or n+1.
        depths = sum(bl(i) for i in range(1, n + 2))
        return 16 * n + 17 + max(16 * n + 3, 8 * n + 8 + depths) + bl(n)
    term = _parse(program)
    frames = 3 * n + 9
    return (
        16 * (_weight(term) + n * _bound_weight(term)) + frames * bl(frames) + 9 + bl(n)
    )


FORMULAS = {"workspace": (_workspace, False, _ARITIES)}
