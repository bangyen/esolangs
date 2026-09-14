"""Boolean-function generator for Inject.

Inject has no numbers, no cells and no arithmetic: the only state is the
text of the program's own label-blocks, and the only test is ``skipq X Y``,
which asks whether two blocks are *textually equal*.  So a truth table is
evaluated as a decision tree whose every node is a string comparison
against a constant block, and whose leaves ``send`` a constant.

Three facts about the language shape the whole construction, each checked
against the interpreter rather than argued from the spec.

**The only forward jump is ``skip``'s first clause.**  A bare ``skip``
inside a block is clause 2 -- it jumps *backwards*, to the innermost
enclosing block's opening label, which is an infinite loop.  Clause 1 fires
only when the very next line opens a block, and then continues after that
block's closing delimiter.  So every conditional and every escape in the
program is spelled "``skip``-family command, then a label that opens a
block", and a jump's distance is chosen by choosing where that block ends.

**A guarded block is entered by drifting into it.**  Nothing "calls" a
block; when the guard does not fire, control simply flows onto the next
line, which is the block's opening delimiter, and then into the block.
That means a taken branch also *falls out the bottom* of its block into
whatever follows, so each leaf must end by jumping clear of everything
after it.

**The clause-1 landing line executes.**  Jumping to just past a block's end
lands on a real line, and if that line opens another block, control drifts
into that one too.  A leaf therefore cannot jump to "the end"; it jumps
over an escape block that spans *every remaining executable line*, landing
in the inert data tail.  Labels are strictly two-occurrence, so each leaf
carries its own escape label -- legal because blocks may overlap, and the
escape blocks all close consecutively in the tail.

Layout
------

The bits are read up front, one ``readto`` per input, into compactly named
blocks.  Reading first rather than at the tree's nodes is what keeps
the read count equal on every path -- the boolean contract requires exactly
``n`` reads whatever the inputs are -- and it also lets a node test a bit
more than once for free.

The tree then walks the table.  At depth ``d`` the node tests the input
the chosen order puts there (``perm[d]``; the shortest of the ``n!``
orders wins, ties keeping the identity) against the constant zero block:

* ``skipq INPUT ZERO`` fires when the bit **is** ``0``, so the block
  it guards is the ``1``-subtree, which is skipped exactly then;
* falling through enters that block, which holds the ``1``-subtree.

A leaf sends the zero or one block and then escapes.  Because a constant
block is both a comparison operand and an answer, the program needs only
the two of them.

The tail holds the answer constants and the closing
delimiters of every escape block, all of which are inert: control reaches
the tail only by a leaf's escape jump, and a line whose first word is not a
command is a no-op.
"""

from esolangs.tools.helpers import _validate_truth_table, best_input_order

__all__ = ["inject"]


_ALPHABET = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
_CONSTANTS = {"o", "z"}


def _word(index: int) -> str:
    """Return the ``index``th shortest alphabetic identifier."""
    base = len(_ALPHABET)
    chars = []
    index += 1
    while index:
        index, digit = divmod(index - 1, base)
        chars.append(_ALPHABET[digit])
    return "".join(reversed(chars))


class _Names:
    """Hand out globally unique short labels and retain escape order."""

    def __init__(self, n: int, perm: tuple[int, ...]) -> None:
        self.next = 0
        self.inputs = [""] * n
        # Deeper inputs occur in more guards, so they get the shortest names.
        for input_index in reversed(perm):
            self.inputs[input_index] = self.fresh()
        self.escapes: list[str] = []

    def fresh(self) -> str:
        """Return the next label not reserved for an answer constant."""
        while (name := _word(self.next)) in _CONSTANTS:
            self.next += 1
        self.next += 1
        return name


def _leaf(bit: str, escape: str) -> list[str]:
    """Emit a leaf: send the answer's constant block, then jump clear.

    The escape is ``skip`` followed by ``escape``'s opening delimiter, so
    clause 1 carries control past that block's close -- which the caller
    places after every remaining executable line.
    """
    return [f"send {'o' if bit == '1' else 'z'}", "skip", f"{escape};"]


def _tree(
    table: str, depth: int, n: int, names: _Names, perm: tuple[int, ...]
) -> list[str]:
    """Emit the decision tree for ``table``, testing input ``perm[depth]`` first.

    ``table`` is in the permuted frame, so its bit ``depth`` is original
    input ``perm[depth]`` -- ``perm`` is spent only on the block a node
    names.  ``names`` also records escape labels in closing order.
    """
    # A constant subtree needs no further tests: whatever the remaining
    # bits are, the answer is the same, so the node collapses to its leaf.
    # This is what makes a table depending on one input cost a single test
    # rather than ``n`` of them.
    if depth == n or table == table[0] * len(table):
        escape = names.fresh()
        names.escapes.append(escape)
        return _leaf(table[0], escape)

    half = len(table) // 2
    zeros = _tree(table[:half], depth + 1, n, names, perm)
    ones = _tree(table[half:], depth + 1, n, names, perm)

    # ``skipq`` fires when the bit equals zero, so the guarded block is
    # the one-subtree: it is skipped exactly when the bit is 0, and entered
    # by falling through when the bit is 1.
    block = names.fresh()
    return [
        f"skipq {names.inputs[perm[depth]]} z",
        f"{block};",
        *ones,
        f"{block};",
        *zeros,
    ]


def inject(truth_table: str) -> str:
    """Build an Inject program computing ``truth_table``.

    The program reads ``n`` lines of input -- one bit per line, the
    convention the boolean harness feeds -- and writes the table's entry
    for that combination, followed by a newline (``send`` terminates every
    line it writes).

    The construction is a decision tree of ``skipq`` guards over blocks
    holding the stored input bits; see the module docstring for why the
    reads are hoisted and why each leaf carries its own escape label.

    **The tree splits on its inputs in whichever order emits the shortest
    program** (:func:`~esolangs.tools.helpers.best_input_order`).
    The ``readto`` block stays in input order, so only the block a
    ``skipq`` names moves.
    """
    return best_input_order(truth_table, _inject_ordered)


def _inject_ordered(truth_table: str, perm: tuple[int, ...]) -> str:
    """Emit one input order's Inject program; see :func:`inject`."""
    n = _validate_truth_table(truth_table)

    names = _Names(n, perm)
    body = [f"readto {names.inputs[d]}" for d in range(n)]
    body += _tree(truth_table, 0, n, names, perm)

    # Every escape block has to span all the remaining executable lines, so
    # the closes come after the tree and before the data tail.  They are
    # emitted innermost-last: a leaf that escapes must clear every *later*
    # leaf's code too, and closing them in order of issue does that.
    tail = [f"{escape};" for escape in names.escapes]

    # The constants.  ``z`` is both the comparison operand for every node
    # and the answer for a 0 leaf; ``o`` is only an answer.  They sit
    # after the escape closes, so no escape jump can land inside them.
    tail += ["z;", "0", "z;", "o;", "1", "o;"]

    # The input blocks start empty: ``readto`` fills them, and an empty
    # block is two adjacent delimiters.
    head = [f"{name};\n{name};" for name in names.inputs]
    return "\n".join([*head, *body, *tail])
