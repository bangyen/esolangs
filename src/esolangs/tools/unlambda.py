r"""Unlambda boolean program builder: a decision tree of promises.

Each half of a node is a ``d`` promise, forced by the ``?`` test that selects
it: Unlambda evaluates an argument before applying it, so a half spelled
inline would read twice a level and print both answers.  ``?c`` hands its
argument the spec's ``i`` on a match and ``v`` otherwise, which is the whole
conditional and makes a node 25 characters, ``29T - 25`` in all.  The ``?1``
flag is computed *before* the zero half runs, since that half's read replaces
the character ``?`` looks at -- testing it afterwards asked about a deeper
level's character and fired both halves on ``0`` then ``1``.
"""

from __future__ import annotations

from esolangs.tools.helpers import _validate_truth_table, separated_tree_text

#: ``@`` reads a line and applies its argument -- the promise of everything
#: after the read -- to ``i``, or to ``v`` at end of input.
_READ = "`@`d"
#: ``` ``flag half v ``: on ``i`` the half is forced, on ``v`` both are eaten.
_FORCE = "``"
#: Compute the ``?1`` flag, run the term after it, return the flag anyway.
_FLAG_ONE = "``k`?1i"
_IF_ZERO = _FORCE + "`?0i`d"
_HEAD = _READ + _FORCE + _FLAG_ONE + _IF_ZERO
_ELSE = "v`d"
_CLOSE = "v"
#: One unread input at a collapsed leaf: read a line, drop the flag.
_SKIP = "``k`@i"
#: Keep a collapsed leaf's value ``v``, not the read's flag.
_INERT = "``kv"


def unlambda(truth_table: str) -> str:
    """Return an Unlambda program computing ``truth_table``.

    Reads ``n`` lines, one ``0``/``1`` per input in table order, and prints
    the answer digit.
    """
    n = _validate_truth_table(truth_table)

    def leaf(level: int, row: int) -> str:
        # ``v`` because every enclosing branch applies this value again; the
        # reads below a collapsed leaf are the interface and stay.
        printing = f"`.{truth_table[row]}v"
        unread = n - level
        return printing if not unread else _INERT + _SKIP * unread + printing

    return separated_tree_text(
        truth_table, leaf, head=_HEAD, between=_ELSE, close=_CLOSE
    )
