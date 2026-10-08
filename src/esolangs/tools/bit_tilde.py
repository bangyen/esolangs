"""Boolean generator for bit tilde."""

from esolangs.tools.helpers import _validate_truth_table, essential_inputs, read_at

__all__ = ["bit_tilde"]


#: Cells the prologue plants below the table: the ``0`` window at 10..17,
#: the ``1`` window at 1..8, and the two walk terminators at 18 and 27.
_BIT_TILDE_PLANTED = (3, 4, 8, 12, 13, 18, 27)

#: Step two cells left and flip, which runs forever over a zero lane and
#: stops on the planted 1 it clears.  The leading ``<~`` primes the loop.
_BIT_TILDE_WALK = "<~{<<~}"


def bit_tilde(truth_table: str) -> str:
    """Return a bit~ program for a binary, MSB-first ``2**n`` truth table.

    Entries occupy every other cell; the intervening lane stays zero so
    weighted conditional left jumps run once. Each read lands the next bit
    at the current pointer; Horner-weighted jumps select the table entry.
    Its bit selects one of two walks, whose final positions print distinct
    eight-cell windows planted as ASCII zero and one in the prologue.
    """
    n = _validate_truth_table(truth_table)

    used = essential_inputs(truth_table, n) or [0]
    table = read_at(truth_table, used, n)
    width = len(used)
    # Two cells an entry, above the planted region (max 27, lowest entry 32),
    # and even so that the reads stay in the lane whose jumps land in the zero one.
    start = 2 * len(table) + 34

    planted = set(_BIT_TILDE_PLANTED)
    planted.update(
        start - 2 * index - 2 for index, bit in enumerate(table) if bit == "1"
    )

    prog: list[str] = []
    pos = 0
    for cell in sorted(planted):
        prog.append(">" * (cell - pos) + "~")
        pos = cell
    prog.append(">" * (start - pos))

    depth = {stream: level for level, stream in enumerate(used)}
    for i in range(n):
        # ``)`` XORs; the flip three along, in the jump lane, is undone. A jump
        # sends later reads below this bit; an unused input reads one up.
        if i in depth:
            weight = 2 << (width - 1 - depth[i])
            prog.append(
                ")>>>~>>>>{" + "<" * weight + "}" + "<" * 7
            )  # undo the 7 cells advanced
        else:
            prog.append(">)>>~<<<")

    prog.append("<<{" + _BIT_TILDE_WALK + "}" + _BIT_TILDE_WALK)
    prog.append("<" * 17 + "(")
    return "".join(prog)
