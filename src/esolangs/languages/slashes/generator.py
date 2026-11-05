"""/// Boolean program generator: rewrite rules turn the inputs into a row number.

A ``/pattern/replacement/`` rule rewrites the rest of the program until the
pattern is gone, so the program is a list of rules followed by its data:
the inputs as ``a`` (0) and ``b`` (1), a cursor ``>``, and the table as
``qA`` (0) and ``qB`` (1).  For ``0110`` on inputs 1, 0 the rules take the
data from ``ba>qAqBqBqA`` through

    a*a>qAqBqBqA     /b/a*/      a 1 becomes a and a star
    aa**>qAqBqBqA    /*a/a**/    a star doubles as it passes an a
    **>qAqBqBqA      /a//        the a's go: row 2 is two stars
    >qBqA            sweeps      each star deletes the entry at the cursor
    1                decode      the entry at the cursor is its digit

The table is a literal with no subtrees to fold or share.  Constants parse
the input letters as a rule pattern that cannot match their literal answer.

Size:
    O(T) chars: run sweeps expand from one fixed macro
    ([ablations.sweep_macro_runs_20261102]); n=10 random
    1847: 2,404 chars, n=12 random 1847: 9,297 chars.
    Constants: n + 4 chars and three commands.

Decisions:
    ``balance=True`` prefixes a rule deleting every later newline, and
    folds the whole program square ([ablations.balance_newline_rule]).
    A trailing run of the table cannot be trimmed: the cursor ``>`` is left
    undecoded (116 of 126 wrong).
"""

import re

from esolangs.generation.helpers import (
    TEMPLATE_CHAR,
    _validate_truth_table,
    input_weights,
)
from esolangs.generation.token_balance import balanced_token_width
from esolangs.generation.wrap import _join_tokens, _tokens, balance_score

#: Binary to unary, most significant bit first: the row as that many ``*``.
_UNARY = "/b/a*//*a/a**//a//"
#: One sweep: a star deletes a ``qA`` at the cursor, then one deletes a
#: ``qB``.  The pattern's ``\>`` keeps this sweep from rewriting later ones:
#: unescaped, they become ``/>/>/`` and every non-constant row through n=2
#: hangs (60 of 72).
_SWEEP = "/*\\>qA/>//*\\>qB/>/"
#: Quoting preserves the backslash that shields later sweep patterns.
_SWEEP_DEF = "/S/" + _SWEEP.replace("\\", "\\\\").replace("/", "\\/") + "/"
#: Mark the entry at the cursor, delete the others, print the mark's digit.
_DECODE = "/>qA/C//>qB/D//qA///qB///C/0//D/1/"
#: Deletes an ignored input's ``X``-marked bit before the unary sweep reads it.
_IGNORE = "/Xa///Xb//"
#: Former constant prefix, retained to recognize old templates.
_CONSTANT = "/a///b//"


def _sweeps(bits: str) -> int:
    """Sweeps that delete the first ``len(bits) - 1`` entries.

    Each rule repeats, so a sweep consumes one ``0*1*`` block; only a
    ``10`` transition in the required prefix needs another sweep.
    """
    return 1 + bits.count("10", 0, len(bits) - 1) if len(bits) > 1 else 0


def _sweep_rules(bits: str) -> str:
    """Spell repeated sweeps directly until their fixed macro is shorter."""
    count = _sweeps(bits)
    if len(_SWEEP_DEF) + count < len(_SWEEP) * count:
        return _SWEEP_DEF + "S" * count
    return _SWEEP * count


def slashes(truth_table: str) -> str:
    """Return the rules, then the input slots, the cursor and the table.

    Each sweep deletes at least one entry while stars remain, so the sweeps
    that clear the first 2^m - 1 entries (at most 2^m - 1) reach any row of
    the 2^m entries for the m inputs the table depends on.
    The unary rules use letters the table and decoder never contain.
    """
    n = _validate_truth_table(truth_table)
    if len(set(truth_table)) == 1:
        # The a/b pattern is parsed but cannot match the literal digit.
        return _constant_pattern(n, truth_table[0])
    weights, bits = input_weights(truth_table, n)
    table = "".join("qA" if bit == "0" else "qB" for bit in bits)
    slots = "".join(
        TEMPLATE_CHAR if weight else "X" + TEMPLATE_CHAR for weight in weights
    )
    prefix = _IGNORE if 0 in weights else ""
    return prefix + _UNARY + _sweep_rules(bits) + _DECODE + slots + ">" + table


def _constant_pattern(n: int, bit: str) -> str:
    """Parse all input letters as a rule pattern that cannot match the answer."""
    return "/" + TEMPLATE_CHAR * n + "//" + bit


#: Deletes every later newline, so the rest wraps anywhere.
_NEWLINES = "/\n//"


def _balance(program: str) -> str:
    """Return the program behind :data:`_NEWLINES`, folded square.

    A break may fall anywhere, inside a rule too: the newline rule runs first
    and every later newline is gone before a rule is read.  Template runs
    stay whole.  The unwrapped line stays a candidate for tiny tables.
    """
    tokens = _tokens(_NEWLINES + program, r"[\s\S]")
    width = balanced_token_width(tokens)
    return min(program, _join_tokens(tokens, width, ""), key=balance_score)


def _is_unfilled_template(code: str) -> bool:
    """Recognize canonical templates without reserving literal dollars in ///."""
    if TEMPLATE_CHAR in code and re.fullmatch(r"/[$ab]+//[01]", code):
        return True
    if code.startswith(_CONSTANT):
        data = code[len(_CONSTANT) :]
        return (
            len(data) > 1
            and data[-1] in "01"
            and TEMPLATE_CHAR in data[:-1]
            and not data[:-1].strip(TEMPLATE_CHAR + "ab")
        )
    prefix, delimiter, data = code.partition(_DECODE)
    slots, cursor, table = data.partition(">")
    if (
        not delimiter
        or not cursor
        or TEMPLATE_CHAR not in slots
        or not re.fullmatch(r"(?:X?[$ab])+", slots)
    ):
        return False
    if not re.fullmatch(r"(?:q[AB])*", table):
        return False
    ignored = slots.count("X")
    head = _IGNORE if ignored else ""
    read = len(slots) - 2 * ignored  # negative: more X than slots, not ours
    if read < 0 or len(table) != 2 << read:
        return False
    bits = table.replace("qA", "0").replace("qB", "1")
    return prefix == head + _UNARY + _sweep_rules(bits)
