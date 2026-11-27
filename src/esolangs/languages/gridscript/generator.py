"""GridScript Boolean program generator: a packed table indexed in one pass.

Every command sits on the node at (2,1), so the tracer's first move from
START runs them all in file order and its second leaves the 2 by 1 space.
The table read at its essential inputs is cut into 16-bit chunks, each a
decimal token; ``SPLIT`` pushes them, the high inputs build the chunk's
index in the dataspace by doubling, and ``REMOVE THIS POSITION`` loads that
chunk.  Each of the (at most four) low inputs then divides it by
``1 + bit * (2^w - 1)`` for its weight ``w``, and ``v - 2*floor(v/2)`` leaves
the answer.  Ignored inputs are read into an unused variable; a constant
table prints its bit. The packed layout is used while its index fits a
signed INT. Wider tables reduce a binary tree on the buffer using its
input bits and the identity a + bit*(b-a).

Size:
    Theta(T) text. The packed route uses decimal chunks; tree labels are
    sized by subtree height so their weighted total is linear in T.
    n=4 parity: 411 chars, n=10 random 1847: 1,097 chars.

Decisions:
    Chunks are always the widest that fit, 2^min(k, 4) bits for k kept
    inputs.  A race over narrower widths saved 27.7% at n=4 but 1.5% at
    n=7 and 0.1% at n=8 on random tables; it was retired 2026-11-27.

    The screening probe's tree of SELECT subroutine calls emits 37,391
    chars at n=8; its buffer lookup (one PUSH per bit) 3,910.  Every
    division here lands in the dataspace, which holds only INTs, so the
    page's unstated INT/INT quotient type cannot change the answer; chunks
    stay under 2^16, exact even as 32-bit FLOATs.
"""

from esolangs.generation.helpers import _validate_truth_table
from esolangs.generation.projection import essential_inputs, read_at
from esolangs.generation.requests import GenerationRequest
from esolangs.runtime._program import Program

#: Table bits per chunk: the largest power of two whose chunks fit an INT.
_CHUNK_INPUTS = 4
_INDEX_BITS = 31


def _build(n: int, kept: list[int], table: str, low: int) -> list[str]:
    """Commands with ``low`` inputs selecting a bit inside each chunk."""
    high = len(kept) - low
    size = 1 << low
    chunks = [
        sum(int(table[at + b]) << b for b in range(size))
        for at in range(0, len(table), size)
    ]
    cmds = [f"SPLIT '{' '.join(map(str, chunks))}'" if high else f"STORE {chunks[0]}"]
    slot = {i: s for s, i in enumerate(kept)}
    for i in range(n):
        s = slot.get(i)
        if s is None:
            cmds.append("INPUT z")
        elif s < high:
            cmds += (
                ["INPUT"] if s == 0 else ["INPUT a", "MULTIPLY BY 2", "INCREMENT BY a"]
            )
            if s == high - 1:
                cmds.append("REMOVE THIS POSITION")
        else:
            cmds.append("INPUT a")
            weight = 1 << (len(kept) - 1 - s)
            if weight > 1:
                cmds.append(f"MULTIPLY a BY {(1 << weight) - 1}")
            cmds += ["INCREMENT a", "DIVIDE BY a"]
    if low:
        cmds += ["STORE TO c", "DIVIDE BY 2", "MULTIPLY BY -2", "INCREMENT BY c"]
    return [*cmds, "PRINT"]


def _height_name(height: int) -> str:
    """Name an input by its subtree height, shortest names nearest the leaves."""
    digits = []
    while height:
        height, digit = divmod(height - 1, 26)
        digits.append(chr(ord("a") + digit))
    return "x" + "".join(reversed(digits))


def _tree(n: int, kept: list[int], table: str) -> list[str]:
    """Read the bits, then reduce pairs of zero-or-one buffer values."""
    names = [_height_name(height) for height in range(len(kept), 0, -1)]
    inputs = dict(zip(kept, names, strict=True))
    commands = [
        f"INPUT INT TO {inputs[i]}" if i in inputs else "INPUT z" for i in range(n)
    ]

    def emit(start: int, width: int, depth: int) -> None:
        if width == 1:
            commands.append(f"PUSH {table[start]}")
            return
        half = width // 2
        emit(start, half, depth + 1)
        emit(start + half, half, depth + 1)
        commands.extend(
            (
                "REMOVE TOP TO b",
                "REMOVE TOP TO a",
                "DECREMENT b BY a",
                f"MULTIPLY b BY {names[depth]}",
                "INCREMENT b BY a",
                "PUSH b",
            )
        )

    emit(0, len(table), 0)
    commands.extend(("REMOVE TOP", "PRINT"))
    return commands


def gridscript(truth_table: str) -> str:
    """Build a GridScript program printing ``truth_table[row]`` for the inputs."""
    n = _validate_truth_table(truth_table)
    kept = essential_inputs(truth_table, n)
    if not kept:
        cmds = ["INPUT z"] * n + [f"PRINT {truth_table[0]}"]
    else:
        table = read_at(truth_table, kept, n)
        least_low = max(0, len(kept) - _INDEX_BITS)
        most_low = min(len(kept), _CHUNK_INPUTS)
        if least_low > most_low:
            cmds = _tree(n, kept, table)
        else:
            cmds = _build(n, kept, table, most_low)
    return "#B.\n@width 2\n@height 1\n(1,1):START\n" + "".join(
        f"(2,1):{c}\n" for c in cmds
    )


def gridscript_request(request: GenerationRequest) -> Program:
    """Emit source through a typed backend request."""
    return gridscript(request.table)
