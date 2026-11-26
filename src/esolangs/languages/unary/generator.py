"""Unary Boolean program generator: a Brainfuck program written as a count of zeros.

A Unary program is N zeros.  N in binary is a 1, then three bits per
Brainfuck command in ``><+-.,[]`` order, so the generator writes Brainfuck
and counts.  Halting answers 0; ``[]`` on a nonzero cell loops forever and
answers 1.  The identity is ``,[]``: binary ``1 101 110 111``, 887 zeros,
which halt on input 0 and loop on 255.

Inputs are bytes 0 and 255. Complementing a read with + gives 1 and 0
without an ASCII prelude. This construction unrolls all n reads, so its
source has at least n commands and ``8**n`` zeros; it accepts at most nine
inputs.

Size:
    Each command multiplies the count by eight, so growth is exponential
    in the command count.  n=1 parity: 887 chars, n=2 and: 27,452,351
    chars (n=2's ``0001``), n=2 random 1847: 109 chars.
    n=1 one: 6,903 chars.

Raises:
    GeneratorCapError: the zero count passes 256 Mi (n=2's ``0110``).

Decisions:
    No repeated residual survives the admitted nine-command source budget.
"""

from collections.abc import Callable

from esolangs.compressed import CompressedText, TextLimits
from esolangs.exceptions import GeneratorCapError
from esolangs.generation.helpers import _validate_truth_table, move_text, subtree_ids
from esolangs.generation.projection import essential_inputs
from esolangs.generation.requests import GenerationRequest
from esolangs.languages.unary import COMMANDS
from esolangs.languages.unary.descriptor import check_arity
from esolangs.runtime._program import Program

_MAX_SOURCE = 256 * 1024 * 1024
_LIMITS = TextLimits(
    plain_chars=32 * 1024 * 1024,
    generation_chars=_MAX_SOURCE,
    gzip_bytes=256 * 1024,
)


def _decision_body(table: str, n: int, emit: Callable[[str], None]) -> int:
    """Emit the Unary tape tree, leaving its answer bit in cell 2n."""
    ids = subtree_ids(table)
    pos = 2 * (n - 1)

    def move(target: int) -> None:
        nonlocal pos
        emit(move_text(pos, target, ">", "<"))
        pos = target

    def branch(depth: int, block: int) -> None:
        residual = ids[depth][block]
        if residual == 1:
            move(2 * n)
            emit("+")
        elif residual > 1:
            move(2 * depth)
            node(depth, block)

    def node(depth: int, block: int) -> None:
        zero = 2 * block
        one = zero + 1
        below = ids[depth + 1]
        if below[zero] == below[one]:
            branch(depth + 1, zero)
            return

        bit = 2 * depth
        flag = bit + 1
        move(flag)
        emit("+")
        move(bit)
        emit("[-")
        move(flag)
        emit("-")  # The one arm disarms the zero arm.
        branch(depth + 1, one)
        move(bit)
        emit("]")
        move(flag)
        emit("[-")
        branch(depth + 1, zero)
        move(flag)
        emit("]")

    move(0)
    node(0, 0)
    return pos


def _emit(truth_table: str, n: int, emit: Callable[[str], None]) -> None:
    """Emit ordered reads followed by a conditional fixed loop."""
    kept = essential_inputs(truth_table, n)
    if not kept:
        # Decrement maps both input bytes, 0 and 255, to a nonzero cell.
        emit("," * n + ("-[]" if truth_table[0] == "1" else ""))
        return
    if len(kept) == 1:
        # One input decides: loop on its cell, after + if the table negates it.
        index = kept[0]
        reads = "," * (index + 1)
        if index < n - 1:
            reads += ">" + "," * (n - index - 1) + "<"
        emit(reads + ("+" if truth_table[0] == "1" else "") + "[]")
        return
    if truth_table == "0" * (len(truth_table) - 1) + "1":
        # Each nonzero read enters the next guard; a zero exits to halt.
        emit("," + ">," * (n - 1) + "[<" * (n - 1) + "[]" + "]" * (n - 1))
        return
    # Complemented bytes are bits; reversing the table complements every input.
    emit(">>".join(",+" for _ in range(n)))
    pos = _decision_body(truth_table[::-1], n, emit)
    emit(move_text(pos, 2 * n, ">", "<") + "[]")


def unary(truth_table: str) -> CompressedText:
    """Compress zeros, stopping emission at the first over-budget command."""
    n = _validate_truth_table(truth_table)
    check_arity(n)
    count = 1

    def encode(brainfuck: str) -> None:
        nonlocal count
        for command in brainfuck:
            count = 8 * count + COMMANDS.index(command)
            if count > _MAX_SOURCE:
                raise GeneratorCapError(
                    "Unary source exceeds the 256 Mi-character generation-work cap: "
                    "its length is 8 to the power of this table's Brainfuck "
                    "program length, so only tables with a very short one fit "
                    "(7 of the 16 two-input tables)"
                )

    _emit(truth_table, n, encode)
    return CompressedText.repeated("0", count, limits=_LIMITS)


def unary_request(request: GenerationRequest) -> Program:
    """Emit source through the declared generation request interface."""
    return unary(request.table)
