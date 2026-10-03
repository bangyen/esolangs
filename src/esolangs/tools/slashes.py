"""Linear /// construction: unary row selection by a fixed substitution sweep."""

from esolangs.tools.helpers import TEMPLATE_CHAR, _validate_truth_table

PAIR = ("a", "b")
_UNARY = "/b/a*//*a/a**//a//"
_SWEEP = "/*\\>qA/>//*\\>qB/>/"
_DECODE = "/>qA/C//>qB/D//qA///qB///C/0//D/1/"


def slashes(truth_table: str) -> str:
    """Embed ordered bits; each sweep consumes at least one indexed table row.

    Escaping the cursor in future patterns prevents earlier sweeps rewriting
    those patterns. The binary-to-unary substitutions use disjoint alphabets
    from the table and decoder. There are T sweeps and 2T table characters.
    """
    n = _validate_truth_table(truth_table)
    table = "".join("qA" if bit == "0" else "qB" for bit in truth_table)
    return (
        _UNARY + _SWEEP * len(truth_table) + _DECODE + TEMPLATE_CHAR * n + ">" + table
    )


def _is_unfilled_template(code: str) -> bool:
    """Recognize canonical templates without reserving literal dollars in ///."""
    prefix, delimiter, data = code.partition(_DECODE)
    slots, cursor, table = data.partition(">")
    if not delimiter or not cursor or TEMPLATE_CHAR not in slots or slots.strip("$ab"):
        return False
    if len(table) % 2 or any(
        table[i : i + 2] not in ("qA", "qB") for i in range(0, len(table), 2)
    ):
        return False
    size = len(table) // 2
    return size == 1 << len(slots) and prefix == _UNARY + _SWEEP * size
