"""HQ9+ with headers Boolean program generator: the table as one integer.

A constant table reads every input and prints its value directly. Otherwise,
``STARTUP`` stores the table in ``t``, row r at bit r. Each ``r`` reads b and
sets ``p`` to ``p * p * (b + 1)``, ending at ``2^row``. ``o`` divides ``t`` by
``p`` and tests the quotient's parity against twice its half.

Size:
    Nonconstant: 317 + n chars plus the flow's n + 1 numbers, the checksum and the
    table's decimal digits, at most floor(T log10 2) + 1; 4n + 9 steps;
    n=10 parity: 661 chars, n=10 random 1847: 661 chars; n=8 zero: 180 chars.

Decisions:
    A decision tree over ``'JZ`` jumps lists every command number in the
    flow, so its flow alone is O(T log T).
"""

from esolangs.generation.helpers import _validate_truth_table
from esolangs.languages.hq9_with_headers.descriptor import LANGUAGE as LANGUAGE
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
    constant = truth_table.count(truth_table[0]) == len(truth_table)
    if constant:
        reads: tuple[str, ...] = (_READ[0],)
        answer: tuple[str, ...] = (f'p("{truth_table[0]}")',)
        startup: tuple[str, ...] = ("p()",)
    else:
        with digit_limit_for(len(truth_table)):
            table = str(int(truth_table[::-1], 2))
        reads, answer = _READ, _ANSWER
        startup = ("p = 1", "two = 2", f"t = {table}")
    program = "r" * n + "o"
    pad = " " * 8
    lines = [
        "==== HEADER ====",
        "COMMAND FLOW",
        "    " + ",".join(str(k) for k in range(1, n + 2)),
        "CHARACTER SEMANTICS",
        "    r",
        *(pad + line for line in reads),
        "    o",
        *(pad + line for line in answer),
        "STARTUP",
        *("    " + line for line in startup),
        "CHECKSUM",
        f"    {sum(map(ord, program)) % 1024 + 43}",
        "==== END HEADER ====",
        program,
    ]
    return "\n".join(lines) + "\n"
