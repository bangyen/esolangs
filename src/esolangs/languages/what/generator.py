"""What!? Boolean program generator: a row index tested against change points.

``??`` reads each bit and ``.2*.??+`` folds it into the index ``W`` by
Horner's rule.  The last row's answer is written, then for each change point
``b`` from the last down ``[b>`` holds exactly for rows ``r < b`` and writes
the answer below ``b``; ``.!`` prints the last write.
Past 15 inputs, blocks of ``2^15`` rows reload ``W`` behind a sentinel
65535 and a guard on the high bits, which ``???`` put in ``W``'s string.

Size:
    Through 15 inputs, 7n + 12 chars plus 7 and the row's digits per change
    point; 5T + 6n + 6 steps at most; n=10 parity: 6,846 chars (was 9,289),
    n=10 random 1847: 5,287 chars (was 7,405).

Decisions:
    Counting ``W`` down a ``-`` a row cost 12 and the gap a change point,
    never under the literal: ``and`` was 335 chars at n=8, ``nor`` 81.
"""

from esolangs.generation.helpers import _validate_truth_table
from esolangs.generation.wrap import TokenWrapper
from esolangs.languages.what.proof_formulas import workspace
from esolangs.registry._language import Language

#: Row literals stay below 2^15, at most 5 digits.
_LOW_INPUTS = 15
#: Copies the index from two slots left into ``W``, leaving 1 between.
_LOAD = ",0+.0+,1."


def what(truth_table: str) -> str:
    """Build a What!? program printing ``truth_table[row]`` for the inputs."""
    n = _validate_truth_table(truth_table)
    low = min(n, _LOW_INPUTS)
    high = n - low
    block = 1 << low
    w = 2 * low
    parts = ["." * w + "???" * high + "," * w if high else ""]
    parts.append("??" + ".2*.??+" * (low - 1) + "..")
    for start in range(0, len(truth_table), block):
        rows = truth_table[start : start + block]
        answer = 48 + int(rows[-1])
        if high:
            label = f"{start >> low:0{high}b}"
            parts.append(f'65535["{label}":{_LOAD}.{answer},]')
        else:
            parts.append(f"{_LOAD}.{answer},")
        # Last change point first: each row keeps its nearest write above.
        for row in range(len(rows) - 1, 0, -1):
            if rows[row] != rows[row - 1]:
                parts.append(f"[{row}>.{48 + int(rows[row - 1])},]")
    parts.append(".!")
    return "".join(parts)


#: Break between tokens, never inside a literal, a ``?`` run or a test.
_wrap = TokenWrapper(r'\[(?:\d+>|"[01]+":)|\d+|\?+|[\s\S]')


LANGUAGE = Language(
    "What!?",
    "what",
    category="tape_based",
    boolean=what,
    eof="a read at EOF yields 0",
    # Whitespace only separates tokens, so a newline between two is harmless.
    wrap=_wrap,
    proof_workspace=(workspace, True, (3, 4, 5, 6)),
)
