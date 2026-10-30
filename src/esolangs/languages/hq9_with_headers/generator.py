"""HQ9+ with headers Boolean program generator: the table as one integer.

``STARTUP`` sets ``t`` to the table read as binary, row r at bit r.  Each
``r`` command reads a bit b and sets ``p`` to ``p * p * (b + 1)``, so after
the last input ``p`` is ``2^row``.  ``o`` divides ``t`` by ``p`` and prints
whether the quotient is odd: ``[~:: q h ...]`` against twice its half.

Size:
    317 + n chars plus the flow's n + 1 numbers, the checksum and the
    table's decimal digits, at most floor(T log10 2) + 1; 4n + 9 steps;
    n=10 parity: 661 chars, n=10 random 1847: 661 chars.

Decisions:
    A decision tree over ``'JZ`` jumps lists every command number in the
    flow, so its flow alone is O(T log T).
"""

from esolangs.generation.helpers import _validate_truth_table
from esolangs.registry._language import Language, Shape
from esolangs.runtime._digits import digit_limit_for


def _hex(command: str) -> str:
    """``command`` as the uppercase hex bytes ``[~::]`` takes."""
    return command.encode().hex().upper()


_READ = ("[>>. b]", "[MUL p p p]", "b++", "[MUL p b p]")
_ANSWER = (
    "[DIV t p q]",
    "[DIV q two h]",
    "[ADD h h h]",
    f"[~:: q h {_hex('p("1")')} {_hex('p("0")')}]",
)


def hq9_with_headers(truth_table: str) -> str:
    """Build an HQ9+ with headers program printing ``truth_table[row]``."""
    n = _validate_truth_table(truth_table)
    with digit_limit_for(len(truth_table)):
        table = str(int(truth_table[::-1], 2))
    program = "r" * n + "o"
    pad = " " * 8
    lines = [
        "==== HEADER ====",
        "COMMAND FLOW",
        "    " + ",".join(str(k) for k in range(1, n + 2)),
        "CHARACTER SEMANTICS",
        "    r",
        *(pad + line for line in _READ),
        "    o",
        *(pad + line for line in _ANSWER),
        "STARTUP",
        "    p = 1",
        "    two = 2",
        f"    t = {table}",
        "CHECKSUM",
        f"    {sum(map(ord, program)) % 1024 + 43}",
        "==== END HEADER ====",
        program,
    ]
    return "\n".join(lines) + "\n"


LANGUAGE = Language(
    "HQ9+ with headers",
    "hq9_with_headers",
    category="other",
    boolean=hq9_with_headers,
    # Not a tree: the table is one decimal literal the reads divide down.
    shape=Shape.LOOKUP,
    eof="a read at EOF yields 0",
    empty_program=(
        "HQ9+ with headers: line 1: the source must start with '==== HEADER ===='"
    ),
    no_wrap="a line break ends a header line; only a trailing \\ joins two",
)
