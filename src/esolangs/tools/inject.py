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

A subtree repeated at its level is written once, at its last occurrence, and
each earlier one is a ``skip`` over a block closing just before it (jumps run
forward only): n=4, all 65,536 tables, -27.1%, none longer; at n=5 the shared tree is
1.04x the halving lookup, so the n<=4 crossover stays.  A node whose halves
agree is passed over.
"""

import string

from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Language
from esolangs.tools.helpers import (
    _validate_truth_table,
    best_input_order,
    essential_inputs,
    input_weights,
    read_at,
    subtree_ids,
)

__all__ = ["inject"]


_ALPHABET = string.ascii_letters
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
    A subtree repeated at its level is written at its last occurrence in the
    text; each earlier one is a ``skip`` over a block that closes just before
    it.  A constant subtree is a leaf, and a node whose halves agree is passed
    over for its zero half.
    """
    ids = subtree_ids(table)

    def canonical(level: int, block: int) -> tuple[int, int]:
        while (
            level < n
            and ids[level][block] >= 2
            and ids[level + 1][2 * block] == ids[level + 1][2 * block + 1]
        ):
            level, block = level + 1, 2 * block
        return level, block

    # Text order is the node, its one-subtree, then its zero-subtree.
    last: dict[int, tuple[int, int]] = {}

    def scan(level: int, block: int) -> None:
        level, block = canonical(level, block)
        last[ids[level][block]] = (level, block)
        if ids[level][block] >= 2:
            scan(level + 1, 2 * block + 1)
            scan(level + 1, 2 * block)

    scan(depth, 0)
    closes: dict[int, list[str]] = {}

    def walk(level: int, block: int) -> list[str]:
        level, block = canonical(level, block)
        key = ids[level][block]
        if last[key] != (level, block):
            label = names.fresh()
            closes.setdefault(key, []).append(f"{label};")
            return ["skip", f"{label};"]
        lines = closes.get(key, [])
        if key < 2:
            escape = names.fresh()
            names.escapes.append(escape)
            return [*lines, *_leaf(str(key), escape)]
        label = names.fresh()
        ones = walk(level + 1, 2 * block + 1)
        zeros = walk(level + 1, 2 * block)
        return [
            *lines,
            f"skipq {names.inputs[perm[level]]} z",
            f"{label};",
            *ones,
            f"{label};",
            *zeros,
        ]

    return walk(depth, 0)


def _widest(program: str) -> int:
    return max(map(len, program.splitlines()))


def _preamble(names: _Names, table_line: str) -> list[str]:
    """Empty input blocks, the table ``t``, constants ``z``/``o``, then the reads."""
    lines = [f"{name};\n{name};" for name in names.inputs]
    lines += ["t;", table_line, "t;", "z;", "0", "z;", "o;", "1", "o;"]
    lines += [f"readto {name}" for name in names.inputs]
    return lines


def _halve(names: _Names, halvings: list[tuple[int, str]]) -> list[str]:
    """Narrow ``t`` by each ``(half, input name)``: a zero keeps the front half."""
    lines: list[str] = []
    for half, input_name in halvings:
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
    return lines


def inject(truth_table: str, width: int | None = None) -> str:
    """Build an Inject program computing ``truth_table``.

    Reads ``n`` lines and writes the entry plus a newline.  The split order
    is whichever is shortest (:func:`~esolangs.tools.helpers.best_input_order`);
    the ``readto`` block stays in input order.  Width selects a chunked
    lookup with an O(n) floor; complete commands never split.
    """
    if len(truth_table) <= 16:
        program = best_input_order(truth_table, _inject_ordered)
    else:
        program = _inject_halving(truth_table)
    widest = _widest(program)
    if width is None or width <= 0 or widest <= width:
        return program
    banded = _inject_banded(truth_table)
    return banded if _widest(banded) < widest else program


def _inject_banded(truth_table: str) -> str:
    """Select an O(m)-bit chunk of the ``m`` essential inputs, then halve it.

    Ignored inputs are read and never tested (see :func:`_inject_halving`).
    """
    n = _validate_truth_table(truth_table)
    essential = essential_inputs(truth_table, n)
    table = read_at(truth_table, essential, n)
    m = len(essential)
    # >= m rows per chunk amortize O(m)-letter unique labels over the table.
    low = min(m, (m - 1).bit_length())
    high = m - low
    names = _Names(n, tuple(range(n)))
    lines = _preamble(names, "0")

    def walk(start: int, stop: int, level: int) -> None:
        if level == high:
            escape = names.fresh()
            names.escapes.append(escape)
            lines.extend(["inject t=^.*$/" + table[start:stop], "skip", f"{escape};"])
            return
        middle = (start + stop) // 2
        block = names.fresh()
        lines.extend([f"skipq {names.inputs[essential[level]]} z", f"{block};"])
        walk(middle, stop, level + 1)
        lines.append(f"{block};")
        walk(start, middle, level + 1)

    # Every leaf escapes the remaining tree to the same low-input postlude.
    walk(0, len(table), 0)
    lines.extend(f"{escape};" for escape in names.escapes)
    lines += _halve(
        names,
        [(1 << (m - d - 1), names.inputs[essential[d]]) for d in range(high, m)],
    )
    lines.append("send t")
    return "\n".join(lines)


def _inject_halving(truth_table: str) -> str:
    """Select one table character with linear total regex text.

    An input's halving is its weight; an ignored input, weight 0, is read
    and never tested, and the table is indexed by the rest.
    """
    n = _validate_truth_table(truth_table)
    weights, projected = input_weights(truth_table, n)
    names = _Names(n, tuple(range(n)))
    lines = _preamble(names, projected)
    lines += _halve(
        names, [(h, i) for h, i in zip(weights, names.inputs, strict=True) if h]
    )
    lines.append("send t")
    return "\n".join(lines)


def _inject_ordered(truth_table: str, perm: tuple[int, ...]) -> str:
    """Emit one input order's Inject program; see :func:`inject`."""
    n = _validate_truth_table(truth_table)

    names = _Names(n, perm)
    body = [f"readto {names.inputs[d]}" for d in range(n)]
    body += _tree(truth_table, 0, n, names, perm)

    # Each escape block spans every later executable line, so the closes
    # follow the tree, in order of issue, ahead of the constants.
    tail = [f"{escape};" for escape in names.escapes]

    # ``z`` is also every node's comparison operand; after the closes, so no
    # escape lands inside the constants.
    tail += ["z;", "0", "z;", "o;", "1", "o;"]

    # The input blocks start empty: ``readto`` fills them, and an empty
    # block is two adjacent delimiters.
    head = [f"{name};\n{name};" for name in names.inputs]
    return "\n".join([*head, *body, *tail])


LANGUAGE = Language(
    "Inject",
    "other.inject",
    boolean=inject,
    contract=BooleanContract(
        note="send terminates each line, so the answer ends in a newline",
    ),
)
