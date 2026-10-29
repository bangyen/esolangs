"""Inject Boolean program generator: a decision tree of ``skipq`` tests.

The only state is label-blocks and the only test is ``skipq X Y`` (textual
equality).  Each bit is read up front (one ``readto``); at depth ``d`` the node
tests input ``d`` with ``skipq INPUT ZERO``, which
skips the ``1``-subtree block when the bit is ``0``.  A leaf sends the zero or
one block and escapes.  The only forward jump is ``skip``'s first clause (a
bare ``skip`` inside a block loops back), so every escape is a ``skip``-family
command then a label opening a block.  A guarded block is entered by drifting
in, so each leaf jumps over an escape block spanning every remaining
executable line (the clause-1 landing line executes) into the inert tail;
blocks may overlap, so each leaf has its own escape label.  Above n=4 it
halves one table string with ``inject`` regexes instead (linear regex text).

Size:
    O(T) at n<=4 tree, O(T) halving above; n=4 random 1847: 262 chars,
    n=10 random 1847: 3,809 chars, n=12 random 1847: 13,167 chars.

Decisions:
    A subtree repeated at its level is written once, at its last occurrence,
    and each earlier one is a ``skip`` over a block closing just before it
    (jumps run forward only): n=4, all 65,536 tables, none longer
    ([ablations.subtree_sharing]).  At n=5 the shared tree is 1.01x the halving lookup,
    so the n<=4
    crossover stays.  A node whose halves agree is passed over.
"""

import string

from esolangs.generation.helpers import (
    _validate_truth_table,
    essential_inputs,
    grid_width,
    input_weights,
    read_at,
    short_name,
    subtree_ids,
)
from esolangs.generation.wrap import balance_score
from esolangs.languages.inject.proof_formulas import workspace
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Example, Language

__all__ = ["inject"]


_ALPHABET = string.ascii_letters
_CONSTANTS = {"o", "t", "z"}


class _Names:
    """Hand out globally unique short labels and retain escape order."""

    def __init__(self, n: int) -> None:
        self.next = 0
        self.inputs = [self.fresh() for _ in range(n)]
        self.escapes: list[str] = []

    def fresh(self) -> str:
        """Return the next label not reserved for an answer constant."""
        while (name := short_name(self.next, _ALPHABET)) in _CONSTANTS:
            self.next += 1
        self.next += 1
        return name


def _leaf(bit: str, escape: str) -> list[str]:
    """Emit a leaf: send the answer's constant block, then jump clear.

    ``skip`` then ``escape``'s opening delimiter carries control past its close.
    """
    return [f"send {'o' if bit == '1' else 'z'}", "skip", f"{escape};"]


def _tree(table: str, depth: int, n: int, names: _Names) -> list[str]:
    """Emit the decision tree for ``table``, testing input ``depth`` first.

    ``names`` records escape labels, closing order.
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
            f"skipq {names.inputs[level]} z",
            f"{label};",
            *ones,
            f"{label};",
            *zeros,
        ]

    return walk(depth, 0)


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
    is input order (the greedy order never departs from identity at n=4,
    so no reorder saving arises).
    Width selects a chunked lookup with an O(n) floor; complete commands
    never split.
    """
    if len(truth_table) <= 16:
        program = _inject_ordered(truth_table)
    else:
        program = _inject_halving(truth_table)
    widest = grid_width(program)
    if width is None or widest <= width:
        return program
    banded = _inject_banded(truth_table)
    return banded if grid_width(banded) < widest else program


def _inject_banded(truth_table: str, *, square: bool = False) -> str:
    """Select an O(m)-bit chunk of the ``m`` essential inputs, then halve it.

    ``square`` sizes the chunk to ``2**((m + 4) // 2)`` characters, so chunk
    width and the tree's line count both grow as ``sqrt(T)``.
    Ignored inputs are read and never tested (see :func:`_inject_halving`).
    """
    n = _validate_truth_table(truth_table)
    essential = essential_inputs(truth_table, n)
    table = read_at(truth_table, essential, n)
    m = len(essential)
    # >= m rows per chunk amortize O(m)-letter unique labels over the table.
    low = min(m, (m - 1).bit_length())
    if square:
        low = min(m, (m + 4) // 2)
    high = m - low
    names = _Names(n)
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
    names = _Names(n)
    lines = _preamble(names, projected)
    lines += _halve(
        names, [(h, i) for h, i in zip(weights, names.inputs, strict=True) if h]
    )
    lines.append("send t")
    return "\n".join(lines)


def _inject_ordered(truth_table: str) -> str:
    """Emit the input-order Inject program; see :func:`inject`."""
    n = _validate_truth_table(truth_table)

    names = _Names(n)
    body = [f"readto {names.inputs[d]}" for d in range(n)]
    body += _tree(truth_table, 0, n, names)

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


def _balance(table: str, default: str) -> str:
    """Race both banded lookups against the default by area.

    The narrow chunk wins at n=3..4 (``[ablations.balance_banded]``); the
    square one keeps balanced area O(T) (``[ablations.balance_square_chunk]``).
    """
    return min(
        default,
        _inject_banded(table),
        _inject_banded(table, square=True),
        key=balance_score,
    )


LANGUAGE = Language(
    "Inject",
    "inject",
    category="program_based",
    boolean=inject,
    contract=BooleanContract(
        note="send terminates each line, so the answer ends in a newline",
    ),
    balance=_balance,
    no_wrap="blocks and executable commands are delimited by source lines",
    # The wiki cat's only clean exit is a ``readto`` that gets no line.
    eof="an exhausted readto empties the block",
    # ``send`` terminates every line it writes, so the answer arrives
    # with a newline after it -- there is no other output command.
    example=Example(expected="0\n"),
    proof_workspace=(workspace, True, (5,)),
)
