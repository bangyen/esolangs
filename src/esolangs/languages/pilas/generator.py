"""Pilas Boolean program generator: a decision tree on line one.

Line two idles in ``0{0}``, a loop that never exits, so only line one's
pointer can end the run.  Each node reads a byte, subtracts 48 to get the
bit ``b`` and runs ``:{Z+2+1}1-:{O+1+1}1-``: the first ``{`` enters only
on ``b = 0`` and leaves a 2 behind, the second only on the one arm. Before
shortening, each nested subtree pushes one 0; ``+`` folds it into the flag and
each node, like each leaf, leaves one 0 for its parent.  A span whose
halves are opposite constants reads the rest, then prints its first input's
byte, or 97 minus it. Adjacent zero-push/add identities are omitted.

Size:
    O(T) in the tree's nodes; n=4 parity: 250 chars.
    Root constants retain k bytes: 3n+13-2k+2b chars, 4n-2k+15+4b steps;
    6k+14+bl(3n+10)+bl(n) written bits at most, within 3n+24.

Decisions:
    Residues fold with ``+``, not ``~``: a moved value would land on line
    two's stack, where its ``{`` would pop it instead of its own 0.
"""

from esolangs.generation.helpers import _validate_truth_table, subtree_ids

#: Pushes 48, the byte ``'0'``.
_ZERO_BYTE = "6:+:+:+"
#: Reads one input byte as its bit.
_READ = "," + _ZERO_BYTE + "-"
#: Reads one input byte and leaves a 0 for it, skipping the 48.
_DROP = ",:-"
#: Pushes 97 = 48 + 49, so ``97 - byte`` is the other bit's byte.
_NINETY_SEVEN = _ZERO_BYTE + ":+1+"


def pilas(truth_table: str) -> str:
    """Build a Pilas program printing ``truth_table[row]`` for the inputs."""
    n = _validate_truth_table(truth_table)
    if len(set(truth_table)) == 1:
        # ASCII 0/1 is nonzero, so {} discards a byte. Retention costs six bits.
        # Reserve 14 plus pointer/input widths within the unchanged 3n+24 bound.
        keep = min(
            n, max(0, (3 * n + 10 - (3 * n + 10).bit_length() - n.bit_length()) // 6)
        )
        bump = "1+" if truth_table[0] == "1" else ""
        return "," * keep + ",{}" * (n - keep) + _ZERO_BYTE + bump + ".\n0{0}"
    ids = subtree_ids(truth_table)
    parts: list[str] = []

    def emit(depth: int, slot: int) -> None:
        node = ids[depth][slot]
        if node < 2:
            left = n - depth
            bump = "1+" if node else ""
            parts.append(_DROP * left + _ZERO_BYTE + bump + ".0" + "+" * left)
            return
        zero, one = ids[depth + 1][2 * slot : 2 * slot + 2]
        if zero < 2 and one < 2:
            # The first input is the answer: read the rest away (each folds
            # into it as 0), then print its byte, or 97 minus it.
            rest = n - depth - 1
            head = "," if not zero else _NINETY_SEVEN + ",-"
            parts.append(head + _DROP * rest + "+" * rest + ".0")
            return
        if zero == one:
            # An ignored input is still read, then zeroed and folded away.
            parts.append(_DROP)
            emit(depth + 1, 2 * slot)
            parts.append("+")
            return
        parts.append(_READ + ":{")
        emit(depth + 1, 2 * slot)
        parts.append("+2+1}1-:{")
        emit(depth + 1, 2 * slot + 1)
        parts.append("+1+1}1-")

    emit(0, 0)
    # A child's zero residue followed by + is an identity. Cancel in one
    # pass; repeated replacement is quadratic on nested 00++ spellings.
    line: list[str] = []
    for part in parts:
        for char in part:
            if char == "+" and line and line[-1] == "0":
                line.pop()
            else:
                line.append(char)
    return "".join(line) + "\n0{0}"
