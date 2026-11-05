"""1 + i Boolean program generator: a decision tree of function literals.

A node pushes its 0- and 1-child as function literals, reads its bit with
``B`` and lets ``?`` invoke one.  ``?`` leaves both literals on the stack, and
nothing ever returns to them, so they are left there.  A node whose halves
agree (``subtree_ids``) reads its bit and drops it: ``B$`` then the child.  A
nested constant subtable reads its bits with bare ``B``, then prints ``iic+`` (0) or
``ici*`` (1); a last-level node prints ``b`` or ``1 - b`` (``b > 0``), and a
node of two constants reads both bits, drops the last and prints that.
Two-input tails use products, zero-on-true comparisons, or (-1) to the
input sum. Projected parity uses that sum directly; integer powers stay exact.

Size:
    O(T), at most 4n + 4 steps; n=10 and: 136 chars, n=10 random 1847: 3,294 chars.
    Root constants: n + 5/3 chars and commands for zero/one.

Decisions:
    Other repeats are not shared: a deeper function needs a whole-stack roll.
    A constant drains with bare ``B`` before ``p``: nothing reads the stack
    after it, so bare ``B`` replaces ``B$`` (2n+5 -> n+5 a table).  Output
    follows the last read; printing first was 1 char shorter on a constant
    pair.  Leaving the literals makes the stack grow two a level (workspace,
    not size).
"""

from esolangs.generation.helpers import (
    _validate_truth_table,
    essential_inputs,
    read_at,
    subtree_ids,
)
from esolangs.languages.one_i.descriptor import LANGUAGE as LANGUAGE

_CONSTANT = ("iic+", "ici*")


def one_i(truth_table: str) -> str:
    """Build a 1 + i program printing ``truth_table[row]`` for the inputs."""
    n = _validate_truth_table(truth_table)
    if truth_table == "1" * len(truth_table):
        # A duplicated real value makes `>` false, whose specified value is one.
        return "B" * n + ":>p"
    # [ablations.parity_reader_20261102]: named exact arithmetic, no library.
    # [ablations.canonical_projection_20261102]: physical reads stay ordered.
    used = essential_inputs(truth_table, n)
    if not used:
        return "B" * n + _CONSTANT[0] + "p"
    reduced = read_at(truth_table, used, n)
    m = len(used)
    parity = _parity_reader(reduced, used, n)
    if parity is not None:
        return parity
    ids = subtree_ids(reduced)

    out: list[str] = []

    def node(depth: int, k: int) -> None:
        sub = ids[depth][k]
        previous = used[depth - 1] + 1 if depth else 0
        if sub < 2:
            out.append("B" * (n - previous) + _CONSTANT[sub] + "p")
            return
        out.append("B$" * (used[depth] - previous))
        zero, one = ids[depth + 1][2 * k], ids[depth + 1][2 * k + 1]
        if depth == m - 1:
            reads = "B" + "B$" * (n - used[-1] - 1)
            out.append(reads + ("p" if zero == 0 else "iic+>p"))
            return
        if depth == m - 2:
            reads = (
                "B" + "B$" * (used[-1] - used[-2] - 1) + "B" + "B$" * (n - used[-1] - 1)
            )
            if zero < 2 and one < 2:
                out.append(reads + "$" + ("p" if zero == 0 else "iic+>p"))
                return
        if zero == one:
            out.append("B$")
            node(depth + 1, 2 * k)
            return
        # [ablations.direct_two_input_20261102]: derive the terminal Boolean.
        if depth == m - 2:
            code = _two_input(reduced[4 * k : 4 * k + 4])
            out.append(code.replace("BB", reads, 1))
            return
        # Emit once: recursively concatenating whole children costs O(T*n).
        out.append("[")
        node(depth + 1, 2 * k)
        out.append("][")
        node(depth + 1, 2 * k + 1)
        out.append("]B?")

    node(0, 0)
    return "".join(out)


_NEGATE = "::+<"


def _two_input(block: str) -> str:
    """Derive a two-bit minterm, its complement, or parity, without a table."""
    ones = block.count("1")
    if ones == 2:
        assert block in ("0110", "1001")
        return "ii*BB+^::+" + ("<" if block[0] == "0" else ">") + "p"
    point = block.index("1" if ones == 1 else "0")
    if point == 3:
        code = "BB*"
    elif point in (1, 2):
        code = "BB" + ("<" if point == 1 else ">")
    else:
        code = "BB+" + _NEGATE
    if (ones == 3) != (point in (1, 2)):
        code += _NEGATE
    return code + "p"


def _parity_reader(t: str, used: list[int], n: int) -> str | None:
    """Evaluate projected parity as (-1) to the input sum, draining ignored bits."""
    if not used:
        return None
    reads = "".join("B" if i in used else "B$" for i in range(n))
    if len(used) == 1:
        return reads + ("p" if t[0] == "0" else "iic+>p")
    pattern = "01"
    for _ in range(len(used) - 1):
        pattern += pattern.translate(str.maketrans("01", "10"))
    if t not in (pattern, pattern.translate(str.maketrans("01", "10"))):
        return None
    return (
        "ii*"
        + reads
        + "+" * (len(used) - 1)
        + "^::+"
        + ("<" if t[0] == "0" else ">")
        + "p"
    )
