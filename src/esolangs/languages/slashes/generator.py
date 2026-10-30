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

The table is a literal with no subtrees to fold or share.  Constants delete
the input letters and print their literal answer.

Size:
    O(T) chars, ~22% fewer on random tables than T full sweeps
    ([ablations.sweep_count]); worst case unchanged; n=10 random
    1847: 15,809 chars, n=12 random 1847: 63,805 chars.

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
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Example, Language, Shape

#: Binary to unary, most significant bit first: the row as that many ``*``.
_UNARY = "/b/a*//*a/a**//a//"
#: One sweep: a star deletes a ``qA`` at the cursor, then one deletes a
#: ``qB``.  The pattern's ``\>`` keeps this sweep from rewriting later ones:
#: unescaped, they become ``/>/>/`` and every non-constant row through n=2
#: hangs (60 of 72).
_SWEEP = "/*\\>qA/>//*\\>qB/>/"
#: Mark the entry at the cursor, delete the others, print the mark's digit.
_DECODE = "/>qA/C//>qB/D//qA///qB///C/0//D/1/"
#: Deletes an ignored input's ``X``-marked bit before the unary sweep reads it.
_IGNORE = "/Xa///Xb//"
#: A constant table needs no row: delete the inputs, leave the answer.
_CONSTANT = "/a///b//"


def _sweeps(bits: str) -> int:
    """Sweeps that delete the first ``len(bits) - 1`` entries.

    A sweep deletes one entry, or two when a ``0`` is followed by a ``1``
    (``qA`` then ``qB``); fewer stars than entries leave later sweeps idle.
    """
    done = sweeps = 0
    while done < len(bits) - 1:
        done += 2 if bits[done : done + 2] == "01" else 1
        sweeps += 1
    return sweeps


def slashes(truth_table: str) -> str:
    """Return the rules, then the input slots, the cursor and the table.

    Each sweep deletes at least one entry while stars remain, so the sweeps
    that clear the first 2^m - 1 entries (at most 2^m - 1) reach any row of
    the 2^m entries for the m inputs the table depends on.
    The unary rules use letters the table and decoder never contain.
    """
    n = _validate_truth_table(truth_table)
    if len(set(truth_table)) == 1:
        # Delete the input letters; no cursor or unary sweep selects a constant.
        return _CONSTANT + TEMPLATE_CHAR * n + truth_table[0]
    weights, bits = input_weights(truth_table, n)
    table = "".join("qA" if bit == "0" else "qB" for bit in bits)
    slots = "".join(
        TEMPLATE_CHAR if weight else "X" + TEMPLATE_CHAR for weight in weights
    )
    prefix = _IGNORE if 0 in weights else ""
    return prefix + _UNARY + _SWEEP * _sweeps(bits) + _DECODE + slots + ">" + table


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
        or slots.strip(TEMPLATE_CHAR + "abX")
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
    return prefix == head + _UNARY + _SWEEP * _sweeps(bits)


LANGUAGE = Language(
    "///",
    "slashes",
    category="program_based",
    id="slashes",
    aliases=("Slashalash",),
    path_like_source=True,
    boolean=slashes,
    # Not a tree: an indexed table rewrite.
    shape=Shape.LOOKUP,
    contract=BooleanContract(
        note="Inputs fill the binary row index before unary selection; "
        "constant tables delete the input letters and print their answer.",
    ),
    no_wrap="newlines are literal output and substitution data",
    wrap_balance=_balance,
    example=Example(pair=("a", "b"), unfilled=_is_unfilled_template),
)
