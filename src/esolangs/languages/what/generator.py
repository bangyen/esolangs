"""What!? Boolean program generator: a row index counted down a run chain.

``??`` reads each bit and ``.2*.??+`` folds it into the index by Horner's
rule.  Beside a 1, the index ``W`` loses one ``-`` a row up to each change
point ``b``, wrapping below 0 to 65536 less, so ``[2^k>`` holds exactly
for rows ``r >= b`` and writes the run's answer; ``.!`` prints the last.
Past 15 inputs, blocks of ``2^15`` rows reload ``W`` behind a sentinel
65535 and a guard on the high bits, which ``???`` put in ``W``'s string.

Size:
    Through 15 inputs, 7n + 12 chars plus 7 + len(str(2^n)) per change
    point and one per row up to the last, at most 13T + 7n; 6T + 6n + 5
    steps at most; n=10 parity: 8,607 chars, n=10 random 1847: 6,880
    chars.

Decisions:
    Literal row numbers per change point are O(T log T), smaller only
    while digits are few: 11,240 against 12,358 chars at n=10.
"""

from esolangs.generation.helpers import _validate_truth_table
from esolangs.generation.wrap import wrap_tokens
from esolangs.registry._language import Language

#: Wrapped values stay at or above 65536 - 2^15, valid ones below 2^15.
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
        answer = 48 + int(truth_table[start])
        if high:
            label = f"{start >> low:0{high}b}"
            parts.append(f'65535["{label}":{_LOAD}.{answer},]')
        else:
            parts.append(f"{_LOAD}.{answer},")
        last = 0
        for offset in range(1, block):
            row = start + offset
            if truth_table[row] != truth_table[row - 1]:
                answer = 48 + int(truth_table[row])
                parts.append("-" * (offset - last) + f"[{block}>.{answer},]")
                last = offset
    parts.append(".!")
    return "".join(parts)


def _wrap(program: str, width: int) -> str:
    """Break between tokens, never inside a literal, a ``?`` run or a test."""
    return wrap_tokens(program, width, r'\[(?:\d+>|"[01]+":)|\d+|\?+|[\s\S]')


LANGUAGE = Language(
    "What!?",
    "what",
    category="tape_based",
    boolean=what,
    eof="a read at EOF yields 0",
    # Whitespace only separates tokens, so a newline between two is harmless.
    wrap=_wrap,
)
