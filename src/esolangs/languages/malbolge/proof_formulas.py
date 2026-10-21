"""Executed command bounds."""

from esolangs.languages.malbolge.interpreter import _op


def execution(_: int, program: str) -> int:
    """The worst row: the straight-line main code, then the longest stub.

    Execution walks from cell 0 through the main code's closing ``i``, the
    first ``i`` the store decodes to.  An operand stub walks ``d`` from its
    landing, at least 34, to its last operand, at most cell 234, in four
    commands more than that span: 204 at most (``0`` and ``x`` run three).
    """
    end = next(a for a, char in enumerate(program) if _op(ord(char), a) == "i")
    return end + 1 + 204
