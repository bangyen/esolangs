"""What!? Boolean program generator: a row index tested against change points.

``??`` reads each bit and ``.2*.??+`` folds it into the index ``W`` by
Horner's rule.  The last row's answer is written, then for each change point
``b`` from the last down ``[b>`` holds exactly for rows ``r < b`` and writes
the answer below ``b``; ``.!`` prints the last write.
Past 15 inputs, blocks of ``2^15`` rows reload ``W`` behind a sentinel
65535 and a guard on the high bits, which ``???`` put in ``W``'s string.

Size:
    Through 15 inputs, 7n + 1 chars plus 7 and the row's digits per change
    point; past 15 inputs, B high-block labels add B(n-15) chars,
    B=2**(n-15). Constants use 3n+2 chars, n+2 commands and
    256+bl(n+2)+bl(2n-1) written bits at most.
    5T + 6n - 5 steps at most through n=15; n=10 parity: 6,835 chars,
    n=10 random 1847: 5,276 chars.

Decisions:
    Through 15 inputs the Horner index already neighbours the answer slot:
    omitting its copy saves eleven commands per nonconstant run
    ([ablations.trick_prototype_20261102_drop_index_copy]).
    High blocks still need guarded reloads.
    Counting ``W`` down a ``-`` a row cost 12 and the gap a change point,
    never under the literal: ``and`` was 335 chars at n=8, ``nor`` 81.
"""

from esolangs.generation.helpers import _validate_truth_table
from esolangs.generation.lookup import change_points

#: Row literals stay below 2^15, at most 5 digits.
_LOW_INPUTS = 15
#: Copies the index from two slots left into ``W``, leaving 1 between.
_LOAD = ",0+.0+,1."


def what(truth_table: str) -> str:
    """Build a What!? program printing ``truth_table[row]`` for the inputs."""
    n = _validate_truth_table(truth_table)
    if len(set(truth_table)) == 1:
        return "?? " * (n - 1) + f"??{truth_table[0]}!!"
    if n <= _LOW_INPUTS:
        parts = ["??" + ".2*.??+" * (n - 1) + f".{48 + int(truth_table[-1])},"]
        parts.extend(
            f"[{row}>.{48 + int(truth_table[row - 1])},]"
            for row in reversed(change_points(truth_table))
        )
        return "".join(parts) + ".!"
    low = _LOW_INPUTS
    high = n - low
    block = 1 << low
    w = 2 * low
    parts = ["." * w + "???" * high + "," * w]
    parts.append("??" + ".2*.??+" * (low - 1) + "..")
    for start in range(0, len(truth_table), block):
        rows = truth_table[start : start + block]
        answer = 48 + int(rows[-1])
        # The loop runs only past the n <= _LOW_INPUTS return above, so
        # high >= 1 always and every block carries its label.
        label = f"{start >> low:0{high}b}"
        parts.append(f'65535["{label}":{_LOAD}.{answer},]')
        # Last change point first: each row keeps its nearest write above.
        for row in reversed(change_points(rows)):
            parts.append(f"[{row}>.{48 + int(rows[row - 1])},]")
    parts.append(".!")
    return "".join(parts)


#: Break between tokens, never inside a literal, a ``?`` run or a test.
