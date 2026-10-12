"""Build capped Unary programs; halt means zero, a fixed loop means one.

Inputs are bytes 0 and 255. Complementing a read with + gives 1 and 0
without an ASCII prelude. Source counts grow exponentially in decoded
commands; refuse before allocating more than 256 Mi characters of zeros. No repeated
residual survives the admitted nine-command source budget.
"""

from esolangs.compressed import CompressedText, TextLimits
from esolangs.exceptions import GeneratorCapError
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Example, Language
from esolangs.tools.helpers import (
    _validate_truth_table,
    decision_tree_body,
    essential_inputs,
    move_text,
)
from esolangs.tools.wrap import wrap_chars

_MAX_SOURCE = 256 * 1024 * 1024
_LIMITS = TextLimits(32 * 1024 * 1024, _MAX_SOURCE, 256 * 1024)


def _decoded(truth_table: str) -> str:
    """Return ordered reads followed by a conditional fixed loop."""
    n = _validate_truth_table(truth_table)
    kept = essential_inputs(truth_table, n)
    if not kept:
        return "," * n + (">+[]" if truth_table[0] == "1" else "")
    if len(kept) == 1:
        index = kept[0]
        reads = "," * (index + 1)
        if index < n - 1:
            reads += ">" + "," * (n - index - 1) + "<"
        return reads + ("+" if truth_table[0] == "1" else "") + "[]"
    if truth_table == "0" * (len(truth_table) - 1) + "1":
        # Each nonzero read enters the next guard; a zero exits to halt.
        return "," + ">," * (n - 1) + "[<" * (n - 1) + "[]" + "]" * (n - 1)
    # Complemented bytes are bits; reversing the table complements every input.
    reads = ">>".join(",+" for _ in range(n))
    body, pos = decision_tree_body(
        truth_table[::-1], ">", "<", tuple(range(n)), 2 * (n - 1)
    )
    return reads + body + move_text(pos, 2 * n, ">", "<") + "[]"


def unary(truth_table: str) -> CompressedText:
    """Return gzip source within the file and expanded-work budgets."""
    n = _validate_truth_table(truth_table)
    # Every path must read n inputs, so every encoding has at least n commands.
    if n > 9:
        raise GeneratorCapError("Unary needs at least 8**n zeros; max-inputs=9")
    count = 1
    for command in _decoded(truth_table):
        count = 8 * count + "><+-.,[]".index(command)
        if count > _MAX_SOURCE:
            raise GeneratorCapError(
                "Unary source exceeds the 256 Mi-character generation-work cap"
            )
    return CompressedText.repeated("0", count, limits=_LIMITS)


LANGUAGE = Language(
    "Unary",
    "unary",
    category="tape_based",
    boolean=unary,
    generator_max_inputs=9,
    compressed_source=True,
    benchmark_tables=("00", "01", "10", "11", "0001"),
    generator_restrictions=(
        "raw export 32 Mi characters; generation 256 Mi characters; "
        "gzip 256 KiB; table-dependent caps"
    ),
    contract=BooleanContract(
        alphabet=("\x00", "\xff"),
        input_shape="char_stream",
        answer_mode="termination",
        answer_values=("halts", "diverges"),
        note="Bytes 0/255 encode inputs; halt means 0, a fixed cycle means 1.",
    ),
    wrap=wrap_chars,
    eof="stores zero",
    example=Example(expected="", expected_compared=False),
)
