r"""Unlambda boolean program builder: a decision tree of promises.

``unlambda(truth_table)`` emits one node per subtable.  A node reads with
``@``, asks ``?1`` and ``?0`` about the character it got, and evaluates the
matching half; a leaf prints its bit.  Both halves are spelled, so the
emission is ``a * T + b`` characters -- 25 per internal node, four for a
leaf and six more per input it leaves unread.

Everything here turns on ``d``, because Unlambda evaluates an argument
before applying it: spelling a subtree inline would evaluate *both* halves,
reading twice per level and printing both answers.  ``d`` is the only way to
hold a subtree unevaluated, and a promise is forced by applying it, so each
half is a promise forced exactly when its branch is taken.

``?c`` applies its argument to ``i`` when the character matches and to ``v``
when it does not -- the spec's two values, and what makes the branch this
short.  ```?ci`` evaluates to that flag, and ``` ``flag promise v `` is the
whole conditional: ``i`` keeps the promise and then applies it to ``v``,
which forces it, while ``v`` swallows both and does nothing.  No separate
forcing step is needed, which is why a node is 25 characters rather than 29.

The order of the two tests is the correctness argument.  ``?`` reads the
*one* current character, and the zero branch's subtree reads the next input,
which replaces it -- so a node that tested ``?0``, ran the subtree, then
tested ``?1`` was asking about a character from a deeper level, and fired
both halves on an input like ``0`` then ``1``.  The ``?1`` flag is therefore
evaluated first and held as a value across the zero branch: ```k`?1i X``
computes the flag, then runs ``X``, and returns the flag.
"""

from __future__ import annotations

from esolangs.tools.helpers import _validate_truth_table, separated_tree_text

#: ``@`` reads a line, then applies its argument to ``i`` (or ``v`` at end of
#: input).  That argument is the promise of everything after the read, so the
#: tests run once the character is there rather than before it.
_READ = "`@`d"
#: ``` ``flag half v ``: the flag applied to the half and then to ``v``.  On
#: ``i`` that forces the half; on ``v`` it is two swallowed arguments.
_FORCE = "``"
#: Compute the ``?1`` flag, then evaluate the term after this and return the
#: flag anyway -- ``k``'s sequencing, and what keeps the flag from a later
#: character.
_FLAG_ONE = "``k`?1i"
#: The ``?0`` flag, against the promise that follows it.
_IF_ZERO = _FORCE + "`?0i`d"
#: The node body, up to the zero half.
_HEAD = _READ + _FORCE + _FLAG_ONE + _IF_ZERO
#: Close the zero half and open the one half, held by ``d``.
_ELSE = "v`d"
#: Close the one half.
_CLOSE = "v"
#: One unread input at a collapsed leaf: ```@i`` reads a line and hands the
#: flag to ``i``, which drops it.
_SKIP = "``k`@i"
#: Wrap a collapsed leaf so its value is ``v`` and not the read's flag: the
#: branch that took this half applies that value again.
_INERT = "``kv"


def unlambda(truth_table: str) -> str:
    """Return an Unlambda program computing ``truth_table``.

    Reads ``n`` lines, one ``0``/``1`` per input in table order, and prints
    the answer digit.
    """
    n = _validate_truth_table(truth_table)

    def leaf(level: int, row: int) -> str:
        # Print the bit and return ``v``: every enclosing branch applies this
        # value again, and ``v`` is what makes that print nothing.  A
        # collapsed leaf reads the inputs below it first -- the reads are the
        # interface -- and is wrapped so its value is still ``v``.
        printing = f"`.{truth_table[row]}v"
        unread = n - level
        return printing if not unread else _INERT + _SKIP * unread + printing

    return separated_tree_text(
        truth_table, leaf, head=_HEAD, between=_ELSE, close=_CLOSE
    )
