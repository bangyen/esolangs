"""CreativeScript v2 Boolean program generator: shift the table by the row.

Straight-line code, no jump.  ``set! N`` holds the table, read at its
essential inputs, as one integer with bit ``r`` the answer for row ``r``.
Each essential input ``x`` (least significant first) multiplies a divisor
``p`` by ``1 + x(Q - 1)`` with ``Q = 2**2**m`` kept by squaring, so ``p`` ends
as ``2**row``; ``N // p mod 2`` is the answer.  An ignored input is read
into a scratch variable.

Size:
    Theta(T) text for the literal plus 5 lines an essential input;
    n=4 parity: 320 chars, n=10 parity: 1,025 chars.
    Constants use 6n+6 chars, n+1 commands and 1+bl(n+1)+bl(2n-1) written bits.
"""

from esolangs.generation.helpers import (
    _validate_truth_table,
    essential_inputs,
    read_at,
)
from esolangs.languages.creativescript_v2.descriptor import LANGUAGE as LANGUAGE
from esolangs.runtime.memory import format_integer


def creativescript_v2(truth_table: str) -> str:
    """Build a program printing ``truth_table[row]`` for the n input integers."""
    n = _validate_truth_table(truth_table)
    essential = essential_inputs(truth_table, n)
    table = read_at(truth_table, essential, n)
    name = {k: f"x{k}" for k in essential}
    reads = [f"in! {name.get(k, 'z')}" for k in range(n)]
    if not essential:
        return "\n".join([*reads, f"say! {table}"])
    literal = f"set! N {format_integer(int(table[::-1], 2))}"
    lines = [literal, "set! one 1", "set! two 2", "set! q 2", *reads]
    for count, k in enumerate(reversed(essential)):
        # t = 1 + x(Q - 1): 1 for a zero bit, Q for a one.
        lines += ["sub! q one t", f"mul! t {name[k]} t"]
        lines += ["add! t one p"] if not count else ["add! t one t", "mul! p t p"]
        if count < len(essential) - 1:
            lines.append("mul! q q q")
    return "\n".join([*lines, "div! N p N", "mod! N two N", "out! N"])
