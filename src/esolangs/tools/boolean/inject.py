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

The bits are read up front, one ``readto`` per input, into blocks ``i0`` ..
``i{n-1}``.  Reading first rather than at the tree's nodes is what keeps
the read count equal on every path -- the boolean contract requires exactly
``n`` reads whatever the inputs are -- and it also lets a node test a bit
more than once for free.

The tree then walks the table.  At depth ``d`` the node tests bit ``d``
against the constant block ``zero``:

* ``skipq i{d} zero`` fires when the bit **is** ``0``, so the block it
  guards is the ``1``-subtree, which is skipped exactly then;
* falling through enters that block, which holds the ``1``-subtree.

A leaf sends ``zero`` or ``one`` and then escapes.  Because a constant
block is both a comparison operand and an answer, the program needs only
the two of them.

The tail holds ``zero;``/``one;`` (the answer constants) and the closing
delimiters of every escape block, all of which are inert: control reaches
the tail only by a leaf's escape jump, and a line whose first word is not a
command is a no-op.
"""

from esolangs.tools.boolean.helpers import _validate_truth_table

__all__ = ["inject"]


def _leaf(bit: str, escape: str) -> list[str]:
    """Emit a leaf: send the answer's constant block, then jump clear.

    The escape is ``skip`` followed by ``escape``'s opening delimiter, so
    clause 1 carries control past that block's close -- which the caller
    places after every remaining executable line.
    """
    return [f"send {'one' if bit == '1' else 'zero'}", "skip", f"{escape};"]


def _tree(table: str, depth: int, n: int, state: dict[str, int]) -> list[str]:
    """Emit the decision tree for ``table``, testing bit ``depth`` first.

    ``state`` carries the running count of escape labels handed out, so
    each leaf gets a distinct one.
    """
    # A constant subtree needs no further tests: whatever the remaining
    # bits are, the answer is the same, so the node collapses to its leaf.
    # This is what makes a table depending on one input cost a single test
    # rather than ``n`` of them.
    if depth == n or table == table[0] * len(table):
        state["leaves"] += 1
        return _leaf(table[0], f"e{state['leaves'] - 1}")

    half = len(table) // 2
    zeros = _tree(table[:half], depth + 1, n, state)
    ones = _tree(table[half:], depth + 1, n, state)

    # ``skipq`` fires when the bit equals ``zero``, so the guarded block is
    # the one-subtree: it is skipped exactly when the bit is 0, and entered
    # by falling through when the bit is 1.
    block = f"b{depth}_{state['blocks']}"
    state["blocks"] += 1
    return [
        f"skipq i{depth} zero",
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
    """
    n = _validate_truth_table(truth_table)

    state = {"leaves": 0, "blocks": 0}
    body = [f"readto i{d}" for d in range(n)]
    body += _tree(truth_table, 0, n, state)

    # Every escape block has to span all the remaining executable lines, so
    # the closes come after the tree and before the data tail.  They are
    # emitted innermost-last: a leaf that escapes must clear every *later*
    # leaf's code too, and closing them in order of issue does that.
    tail = [f"e{i};" for i in range(state["leaves"])]

    # The constants.  ``zero`` is both the comparison operand for every
    # node and the answer for a 0 leaf; ``one`` is only an answer.  They sit
    # after the escape closes, so no escape jump can land inside them.
    tail += ["zero;", "0", "zero;", "one;", "1", "one;"]

    # The input blocks start empty: ``readto`` fills them, and an empty
    # block is two adjacent delimiters.
    head = [f"i{d};\n i{d};".replace(" ", "") for d in range(n)]
    return "\n".join([*head, *body, *tail])
