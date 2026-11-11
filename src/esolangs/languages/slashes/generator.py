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

from esolangs.generation.helpers import (
    _validate_truth_table,
    input_weights,
)
from esolangs.generation.requests import BalanceRequest, GenerationRequest
from esolangs.generation.template import (
    InputSlot,
    TemplateLayout,
    TemplateToken,
    layout_fragments,
)
from esolangs.generation.token_balance import balanced_token_width
from esolangs.generation.wrap import balance_score, wrap_character_slots

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


_INPUT = InputSlot(1)


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
    return _layout(truth_table).source


def _layout(truth_table: str) -> TemplateLayout:
    n = _validate_truth_table(truth_table)
    if len(set(truth_table)) == 1:
        # The a/b pattern is parsed but cannot match the literal digit.
        return layout_fragments(("/", *(_INPUT,) * n, "//" + truth_table[0]))
    weights, bits = input_weights(truth_table, n)
    table = "".join("qA" if bit == "0" else "qB" for bit in bits)
    prefix = _IGNORE if 0 in weights else ""
    parts: list[TemplateToken] = [prefix + _UNARY + _sweep_rules(bits) + _DECODE]
    for weight in weights:
        if not weight:
            parts.append("X")
        parts.append(_INPUT)
    parts.append(">" + table)
    return layout_fragments(parts)


#: Deletes every later newline, so the rest wraps anywhere.
_NEWLINES = "/\n//"


def slashes_request(request: GenerationRequest) -> TemplateLayout:
    """Emit source through the declared generation request interface."""
    return _layout(request.table)


def slashes_balance_request(request: BalanceRequest) -> TemplateLayout:
    """Compare the original with a character fold guarded by a newline rule."""
    layout = request.source
    if not isinstance(layout, TemplateLayout):
        raise TypeError("balancing needs a rendered template with slots")
    prefixed = TemplateLayout(
        _NEWLINES + layout.source,
        tuple(
            (start + len(_NEWLINES), end + len(_NEWLINES))
            for start, end in layout.spans
        ),
    )
    folded = wrap_character_slots(prefixed, balanced_token_width(list(prefixed.source)))
    return min(layout, folded, key=lambda candidate: balance_score(candidate.source))
