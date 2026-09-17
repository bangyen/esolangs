"""Boolean-function generator for Inject.

The only state is the program's label-blocks and the only test is
``skipq X Y`` (textual equality), so a table is a decision tree of
string comparisons against a constant block.  Three facts, checked
against the interpreter: the only forward jump is ``skip``'s first
clause (a bare ``skip`` inside a block loops back), so every escape is
"``skip``-family command, then a label that opens a block"; a guarded
block is entered by drifting into it, so a taken branch falls out the
bottom and each leaf must jump clear; and the clause-1 landing line
executes, so a leaf jumps over an escape block spanning every remaining
executable line into the inert tail.  Blocks may overlap, so each leaf
has its own escape label, all closing consecutively in the tail.

The bits are read up front (one ``readto`` each) so every path reads
``n`` times.  At depth ``d`` the node tests ``perm[d]`` (identity and
greedy compete) with ``skipq INPUT ZERO``, which fires when the bit is
``0`` and skips the ``1``-subtree block.  A leaf sends the zero or one
block and escapes; the two constants serve as operands and answers.
"""

from esolangs.tools.helpers import (
    _validate_truth_table,
    best_input_order,
    constant_span_test,
)

__all__ = ["inject"]


_ALPHABET = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
_CONSTANTS = {"o", "t", "z"}


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

    ``skip`` then ``escape``'s opening delimiter carries control past its close.
    """
    return [f"send {'o' if bit == '1' else 'z'}", "skip", f"{escape};"]


def _tree(
    table: str, depth: int, n: int, names: _Names, perm: tuple[int, ...]
) -> list[str]:
    """Emit the decision tree for ``table``, testing input ``perm[depth]`` first.

    ``table`` is in the permuted frame; ``names`` records escape labels, closing order.
    """
    constant = constant_span_test(table)

    def walk(start: int, stop: int, level: int) -> list[str]:
        # A constant subtree needs no further tests: whatever the remaining
        # bits are, the answer is the same, so the node collapses to its leaf.
        if level == n or constant(start, stop):
            escape = names.fresh()
            names.escapes.append(escape)
            return _leaf(table[start], escape)

        middle = (start + stop) // 2
        zeros = walk(start, middle, level + 1)
        ones = walk(middle, stop, level + 1)
        block = names.fresh()
        return [
            f"skipq {names.inputs[perm[level]]} z",
            f"{block};",
            *ones,
            f"{block};",
            *zeros,
        ]

    return walk(0, len(table), depth)


def inject(truth_table: str) -> str:
    """Build an Inject program computing ``truth_table``.

    Reads ``n`` lines and writes the entry plus a newline.  The split order
    is whichever is shortest (:func:`~esolangs.tools.helpers.best_input_order`);
    the ``readto`` block stays in input order.
    """
    if len(truth_table) <= 16:
        return best_input_order(truth_table, _inject_ordered)
    return _inject_halving(truth_table)


def _inject_halving(truth_table: str) -> str:
    """Select one table character with linear total regex text."""
    n = _validate_truth_table(truth_table)
    names = _Names(n, tuple(range(n)))
    lines = [f"{name};\n{name};" for name in names.inputs]
    lines += ["t;", truth_table, "t;", "z;", "0", "z;", "o;", "1", "o;"]
    lines += [f"readto {name}" for name in names.inputs]

    for depth, input_name in enumerate(names.inputs):
        half = 1 << (n - depth - 1)
        one = names.fresh()
        zero = names.fresh()
        # A zero skips the prefix deletion; a one skips the suffix deletion.
        lines += [
            f"skipq {input_name} z",
            f"{one};",
            "inject t=^" + "." * half + "/",
            f"{one};",
            f"skipq {input_name} o",
            f"{zero};",
            "inject t=" + "." * half + "$/",
            f"{zero};",
        ]
    lines.append("send t")
    return "\n".join(lines)


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
