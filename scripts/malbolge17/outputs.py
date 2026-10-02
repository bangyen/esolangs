"""Exhaustive facts about the one printed word of a valid Malbolge run.

    uv run python scripts/malbolge17/outputs.py

Checks, over all 59,049 accumulator values ``A``: ``*`` of a plain character
(33..126) never prints ``0``/``1``; ``p`` with a plain operand prints a digit
for at most 30 operands; no ``A`` offers either digit among the admissible
characters at every residue; and landing on a cell (``A`` = its address minus
one) then ``p`` offers both digits at only 202 addresses.  See "Seventeen:
straight-line programs" in docs/proofs/malbolge-scaling.md.
"""

from __future__ import annotations

from esolangs.interpreters.other.malbolge import _crazy
from esolangs.tools.malbolge.core import _char_for, _rot

W = 59049
PLAIN = range(33, 127)
OPS = "ji*p</vo"


def _digit(y: int) -> int | None:
    return (y & 255) - 48 if y & 255 in (48, 49) else None


def main() -> None:
    """Print the counts quoted in the proof notes."""
    assert all(_digit(_rot(m)) is None for m in PLAIN)
    adm = [[_char_for(op, h) for op in OPS] for h in range(94)]
    most = either = both = 0
    for a in range(W):
        bits = {m: _digit(_crazy(a, m)) for m in PLAIN}
        most = max(most, sum(b is not None for b in bits.values()))
        seen = [{bits[m] for m in adm[h]} for h in range(94)]
        either = max(either, *(sum(b in s for s in seen) for b in (0, 1)))
        both = max(both, sum({0, 1} <= s for s in seen))
    landing = sum(
        {0, 1} <= {_digit(_crazy(h - 1, _char_for(op, h))) for op in OPS}
        for h in range(1, W)
    )
    print(f"plain operands printing a digit, best A: {most} of 94")
    print(f"residues offering a given digit, best A: {either} of 94")
    print(f"residues offering both digits, best A: {both} of 94")
    print(f"landing addresses offering both digits: {landing} of {W}")


if __name__ == "__main__":
    main()
