"""Linear /// construction: unary row selection by a fixed substitution sweep.

The table is a literal with no subtrees to fold or share, and a trailing run
cannot be trimmed: the cursor ``>`` is left undecoded (116 of 126 wrong).
"""

from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Example, Language
from esolangs.tools.helpers import TEMPLATE_CHAR, _validate_truth_table, input_weights

_UNARY = "/b/a*//*a/a**//a//"
_SWEEP = "/*\\>qA/>//*\\>qB/>/"
_DECODE = "/>qA/C//>qB/D//qA///qB///C/0//D/1/"
#: Deletes an ignored input's ``X``-marked bit before the unary sweep reads it.
_IGNORE = "/Xa///Xb//"


def slashes(truth_table: str) -> str:
    """Embed ordered bits; each sweep consumes at least one indexed table row.

    Escaping the cursor in future patterns prevents earlier sweeps rewriting
    those patterns. The binary-to-unary substitutions use disjoint alphabets
    from the table and decoder. There are 2^m sweeps and 2^(m+1) table
    characters for the m inputs the table depends on.
    """
    n = _validate_truth_table(truth_table)
    weights, bits = input_weights(truth_table, n)
    table = "".join("qA" if bit == "0" else "qB" for bit in bits)
    slots = "".join(
        TEMPLATE_CHAR if weight else "X" + TEMPLATE_CHAR for weight in weights
    )
    prefix = _IGNORE if 0 in weights else ""
    return prefix + _UNARY + _SWEEP * len(bits) + _DECODE + slots + ">" + table


def _is_unfilled_template(code: str) -> bool:
    """Recognize canonical templates without reserving literal dollars in ///."""
    prefix, delimiter, data = code.partition(_DECODE)
    slots, cursor, table = data.partition(">")
    if (
        not delimiter
        or not cursor
        or TEMPLATE_CHAR not in slots
        or slots.strip(TEMPLATE_CHAR + "abX")
    ):
        return False
    if len(table) % 2 or any(
        table[i : i + 2] not in ("qA", "qB") for i in range(0, len(table), 2)
    ):
        return False
    size = len(table) // 2
    ignored = slots.count("X")
    head = _IGNORE if ignored else ""
    return (
        size == 1 << (len(slots) - 2 * ignored)
        and prefix == head + _UNARY + _SWEEP * size
    )


LANGUAGE = Language(
    "///",
    "other.slashes",
    boolean=slashes,
    contract=BooleanContract(
        note="Inputs fill the binary row index before unary table selection.",
    ),
    no_wrap="newlines are literal output and substitution data",
    example=Example(pair=("a", "b")),
)
