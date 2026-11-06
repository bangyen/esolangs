"""Smu Boolean program generator: a decision tree of runs, one bit per run.

A node ``(c0)(c1)n`` stores its halves under the input bit's own names,
``(+)=(|)=``, and ``()+`` pushes the value of the variable the bit names,
the half to run next.  Bytes arrive low bit first, so the input's value is
the first bit of its byte; seven skip programs ``k`` pushed above the half
drop the byte's other bits, one run each, and ``()`` is the node's own
(empty) output.  A leaf ``z``/``o`` drops its bit and outputs the eight bits
of ``'0'``/``'1'``.  A node whose halves are equal, as at an input the
table ignores, is a pad of its one half; a constant subtree is pads all
the way down to its leaf.  Source: 3 characters a node, 2 a pad, once
the delimiter macros pay (below); 5 and 3 otherwise.

``X`` = ``)(``, ``Y`` = ``)n`` and ``W`` = ``)m`` spell a node as ``(aXbY``
and a pad as ``(aW``; each is defined (4 characters) only when it occurs
more than 4 times.

Equal subtables at one level are one subtree, and a subtree two parents
reach is a macro of its own when that is shorter: defined once, named at
each use.

Size:
    O(T) worst case, at most 6T+86 chars; O(n) steps, one run per input
    bit.  n=10 parity: 224 chars, n=10 and: 182 chars, n=10
    random 1847: 1,190 chars. Constants: n=8: 75 chars; 55n+5 commands.

Decisions:
    Inlining a kept macro never saves: its test only gets easier as its
    uses multiply.

    A constant span is not folded to a padded leaf: the folded text is
    embedded whole at every parent and a folded leaf has no children, so
    it can never be a macro; the pad descent shares one constant subtree
    per level instead, and measures smaller on random tables
    ([ablations.constant_fold]).
"""

from collections import Counter
from string import ascii_letters

from esolangs.generation.decision import decision_layers
from esolangs.generation.helpers import _validate_truth_table

#: ``k`` drops a run's bit and outputs nothing; ``n`` is a node less its
#: halves, ``m`` a pad; ``z``/``o`` print ``'0'`` (0x30), ``'1'`` (0x31) low bit first.
_SKIP = "k((())=())k"
_NODE = "n(+)=(|)=()+kkkkkkk()n"
_PAD = "m(+)=(+)()+(|)=()+kkkkkkk()m"
# A leaf is terminal, so its discarded input may overwrite the empty name.
# Skip runs retain their nonempty target: another program follows them.
_LEAVES = ("z()=(||||++||)z", "o()=(+|||++||)o")
_MACROS = _SKIP + _NODE + _PAD + "".join(_LEAVES)

#: Delimiter macros, each defined only where its uses pay the 4 characters.
_DELIMS = {"X": "X)(X", "Y": "Y)nY", "W": "W)mW"}


#: Macro names end in one of 44 unreserved letters; digits extend them.
_LETTERS = "".join(c for c in ascii_letters if c not in "knmzoXYW")


def _name(index: int) -> str:
    """Return the ``index``-th macro name, shortest first."""
    digits, letter = divmod(index, len(_LETTERS))
    return f"{digits or ''}{_LETTERS[letter]}"


def smu(truth_table: str) -> str:
    """Return a Smu program printing ``truth_table``'s row for its input bytes."""
    n = _validate_truth_table(truth_table)
    if truth_table == truth_table[0] * len(truth_table):
        bit = int(truth_table[0])
        delimiter = _DELIMS["W"] if n > 4 else ""
        close = "W" if n > 4 else ")m"
        return _SKIP + _PAD + _LEAVES[bit] + delimiter + "(" * n + "zo"[bit] + close * n
    diagram = decision_layers(truth_table)
    kids: dict[tuple[int, int], tuple[tuple[int, int], ...]] = {}
    text: dict[tuple[int, int], str] = {}

    def place(level: int, node: int) -> tuple[int, int]:
        key = (level, node)
        if key in kids:
            return key
        if level == n:
            kids[key] = ()
            text[key] = "zo"[node]
        else:
            low, high = diagram.children[level][node]
            zero, one = place(level + 1, low), place(level + 1, high)
            kids[key] = (zero,) if zero == one else (zero, one)
        return key

    # Macro names and definitions retain zero-first dependency order.
    root = place(0, diagram.root)
    uses = Counter(child for pair in kids.values() for child in pair)
    shared = sorted((k for k in kids if uses[k] > 1 and kids[k]), key=uses.__getitem__)
    names = {key: _name(index) for index, key in enumerate(reversed(shared))}

    def render(delims: str) -> str:
        """The program with the delimiter macros in ``delims`` defined."""
        join, close, pad = (c if c in delims else _DELIMS[c][1:-1] for c in "XYW")
        parts = [_MACROS + "".join(_DELIMS[c] for c in delims)]
        body: dict[tuple[int, int], str] = {}
        for key, pair in kids.items():  # post-order: children are rendered first
            if len(pair) == 1:
                body[key] = f"({body[pair[0]]}{pad}"
            elif pair:
                zero, one = (body[child] for child in pair)
                body[key] = f"({zero}{join}{one}{close}"
            else:
                body[key] = text[key]
            name = names.get(key)
            if name and (uses[key] - 1) * len(body[key]) > (uses[key] + 2) * len(name):
                parts.append(name + body[key] + name)
                body[key] = name
        parts.append(body[root])
        return "".join(parts)

    used = render("XYW")[len(_MACROS) + 12 :]
    return render("".join(c for c in "XYW" if used.count(c) > 4))
