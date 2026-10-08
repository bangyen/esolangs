"""Smu Boolean generator: a decision tree of runs, one input bit per run.

A node ``(c0)(c1)n`` stores its halves under the input bit's own names,
``(+)=(|)=``, and ``()+`` pushes the value of the variable the bit names,
the half to run next.  Bytes arrive low bit first, so the input's value is
the first bit of its byte; seven skip programs ``k`` pushed above the half
drop the byte's other bits, one run each, and ``()`` is the node's own
(empty) output.  A leaf ``z``/``o`` drops its bit and outputs the eight bits
of ``'0'``/``'1'``.  A constant subtree folds to a leaf wrapped in one pad
``(X)m`` per skipped level: ``m`` stores X under both bit names, so every
table reads all its bytes.  A node whose halves are equal, as at an input
the table ignores, is a pad of its one half.  Source: 5 characters a node,
3 a pad.

Equal subtables at one level are one subtree, and a subtree two parents
reach is a macro of its own when that is shorter: defined once, named at
each use.  Inlining a kept macro never saves (its test only gets easier as
its uses multiply), so the program is never longer than the plain tree.
"""

from collections import Counter
from string import ascii_letters

from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Language
from esolangs.tools.helpers import (
    _validate_truth_table,
    constant_span_test,
    subtree_ids,
)
from esolangs.tools.wrap import wrap_chars

#: ``k`` drops a run's bit and outputs nothing; ``n`` is a node less its
#: halves, ``m`` a pad; ``z``/``o`` print ``'0'`` (0x30), ``'1'`` (0x31) low bit first.
_MACROS = (
    "k((())=())k"
    "n(+)=(|)=()+kkkkkkk()n"
    "m(+)=(+)()+(|)=()+kkkkkkk()m"
    "z(())=(||||++||)z"
    "o(())=(+|||++||)o"
)


#: Macro names end in a letter, any but the five above; digits extend them.
_LETTERS = "".join(c for c in ascii_letters if c not in "knmzo")


def _name(index: int) -> str:
    """Return the ``index``-th macro name, shortest first."""
    digits, letter = divmod(index, len(_LETTERS))
    return f"{digits or ''}{_LETTERS[letter]}"


def smu(truth_table: str) -> str:
    """Return a Smu program printing ``truth_table``'s row for its input bytes."""
    n = _validate_truth_table(truth_table)
    constant = constant_span_test(truth_table)
    ids = subtree_ids(truth_table)
    kids: dict[tuple[int, int], tuple[tuple[int, int], ...]] = {}
    text: dict[tuple[int, int], str] = {}

    def walk(level: int, lo: int, hi: int) -> tuple[int, int]:
        key = (level, ids[level][lo >> (n - level)])
        if key in kids:
            return key
        if level == n or constant(lo, hi):
            pads = n - level
            kids[key] = ()
            text[key] = "(" * pads + "zo"[truth_table[lo] == "1"] + ")m" * pads
        else:
            mid = (lo + hi) // 2
            zero, one = walk(level + 1, lo, mid), walk(level + 1, mid, hi)
            kids[key] = (zero,) if zero == one else (zero, one)
        return key

    root = walk(0, 0, 1 << n)
    uses = Counter(child for pair in kids.values() for child in pair)
    shared = sorted((k for k in kids if uses[k] > 1 and kids[k]), key=uses.__getitem__)
    names = {key: _name(index) for index, key in enumerate(reversed(shared))}
    parts = [_MACROS]
    for key, pair in kids.items():  # post-order: children are rendered first
        if len(pair) == 1:
            text[key] = f"({text[pair[0]]})m"
        elif pair:
            zero, one = (text[child] for child in pair)
            text[key] = f"({zero})({one})n"
        name = names.get(key)
        if name and (uses[key] - 1) * len(text[key]) > (uses[key] + 2) * len(name):
            parts.append(name + text[key] + name)
            text[key] = name
    parts.append(text[root])
    return "".join(parts)


LANGUAGE = Language(
    "Smu",
    "stack_based.smu",
    boolean=smu,
    contract=BooleanContract(
        input_shape="char_stream",
        note="Smu reads one bit a run, low bit of each byte first, and "
        "packs its output bits into bytes the same way",
    ),
    wrap=wrap_chars,
)
