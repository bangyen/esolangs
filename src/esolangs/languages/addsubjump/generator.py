"""AddSubJump Boolean program generator: self-modifying jumps over a residual tree.

Each input is read into a cell as a byte and, if tested, hoisted to 0 or 4; a
node adds that to its goto's own ``c`` operand to pick the zero or one
trampoline.  The shared-residual tree in input order races the packed decoder
over essential inputs, which indexes ``m``-bit cells; the shorter ships.

Size:
    Packed is O(T) cells over O(T/log T) words; n=4 parity: 614 chars,
    n=10 random 1847: 2,043 chars, n=10 and: 1,107 chars.

Decisions:
    Interning equal packed cells saves 0.00% at n=8: a running operand reads
    them, so equal cells cannot share a word and a constant run costs a cell each.
"""

from esolangs.generation.helpers import (
    _ASCII_ONE,
    _ASCII_ZERO,
    _residual_ids,
    _validate_truth_table,
    constant_span_test,
    input_weights,
    stored_inputs,
)
from esolangs.generation.wrap import wrap_grid
from esolangs.languages.addsubjump.proof_formulas import execution, workspace
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Language

#: The ``d`` operand of every instruction: cell 7, the last word of the
#: first data block, which nothing writes, so ``*d > 0`` never holds and the
#: instruction adds.  One digit where the special zero ``-7`` spent two.
_ADD = 7

#: Memory layout.  Each instruction occupies ``_WORD`` consecutive cells, and
#: every instruction word is four cells ``(a, b, c, d)``: ``a``/``b`` are the
#: addends, ``c`` is the literal jump destination, and ``d`` is the
#: conditional cell.  A jump destination of ``_WORD * i`` is therefore the
#: first cell of instruction ``i``.
_WORD = 4
#: Operand offsets within one instruction word.
_A_OPERAND, _B_OPERAND, _C_OPERAND = 0, 1, 2


def _cell(instruction: int, operand: int = _A_OPERAND) -> int:
    """Memory address of ``operand`` (default ``a``) of ``instruction``."""
    return _WORD * instruction + operand


class _TrampolineLabels:
    """Hands out unique trampoline label pairs for ``branch_positive``.

    An explicit allocator instead of a ``nonlocal`` counter: the label
    counter is mutable allocator state, and the class makes its ownership
    visible at the call site.
    """

    def __init__(self) -> None:
        self._next = 0

    def branch_pair(self) -> tuple[str, str]:
        """Return the next ``(positive, zero)`` trampoline label pair."""
        tag = self._next
        self._next += 1
        return f"branch_{tag}_positive", f"branch_{tag}_zero"


type _Operand = int | str
type _Instruction = tuple[_Operand, _Operand, _Operand, _Operand]


def _memory(
    instructions: list[_Instruction],
    values: dict[str, int],
    targets: dict[str, int],
    names: list[str] | None = None,
) -> list[int]:
    """Resolve operands and literal jumps, allocating names in mention order."""
    base = _WORD * len(instructions)
    # A dict, not a list: list ``in`` + ``.index`` per operand was 2.4s of a
    # 3.8s six-input build (2026-10-11); one is now 0.2 ms, tree and packed
    # candidates both (2026-10-21).
    address = {
        name: base + index
        for index, name in enumerate(dict.fromkeys(values if names is None else names))
    }
    memory = [0] * (base + len(address))

    def operand(value: _Operand) -> int:
        return address[value] if isinstance(value, str) else value

    for i, (a, b, target, d) in enumerate(instructions):
        if target == "next":
            c = _cell(i + 1)
        elif isinstance(target, str):
            c = _cell(targets[target])
        else:
            c = target
        memory[_cell(i) : _cell(i) + _WORD] = [operand(a), operand(b), c, operand(d)]
    for name, value in values.items():
        memory[address[name]] = value
    return memory


def addsubjump(truth_table: str) -> str:
    """Build an AddSubJump program for ``truth_table`` (length ``2**n``, MSB first)."""
    n = _validate_truth_table(truth_table)
    # The shared tree wins on and/or and parity at every n and never on
    # random tables past n=5 ([ablations.residual_tree_route]).
    tree = _addsubjump_ordered(truth_table, tuple(range(n)), shared=True)
    return min((_addsubjump_packed(truth_table), tree), key=len)


def _addsubjump_packed(truth_table: str) -> str:
    """Emit the packed decoder over the essential inputs."""
    n = _validate_truth_table(truth_table)
    weights, projected = input_weights(truth_table, n)
    if all(weights):
        return _packed_build(truth_table, weights)
    # The full-table build never won against this one: 0 of 322 tables with
    # ignored inputs (n=6..8, 1..n-1 essential), so it is not raced.
    return _packed_build(projected, weights)


class _PackedBuilder:
    """Builder state for the packed decoder: instructions and their labels.

    The emit helpers and the build phases append to one instruction list,
    mark its labels, and patch two of its operands once the chunk cells are
    known; that shared state lives here instead of in closures over one
    function's locals.
    """

    def __init__(self, truth_table: str, weights: list[int]) -> None:
        self.truth_table = truth_table
        self.weights = weights
        self.chunk_width = max(sum(bool(weight) for weight in weights), 1)
        # ``c`` is a literal destination (the wiki's ``goto c``), so a label
        # or ``"next"`` resolves straight into the operand and an ``int``
        # is already one.  A computed jump is therefore a *write* to an
        # instruction's own ``c`` cell, which is what
        # :meth:`branch_positive` does below.
        self.instructions: list[_Instruction] = []
        self.labels: dict[str, int] = {}
        self.values: dict[str, int] = {
            "ZERO": 0,
            "ONE": 1,
            "FOUR": 4,
            "C48": 48,
            "N": self.chunk_width,
            "INDEX": 0,
            "TMP": 0,
            "COUNT": self.chunk_width,
            "OFFSET": 0,
            "TABLE": 0,
            "SHIFT": 0,
            "Q": 0,
            "R": 0,
            "OUT": _ASCII_ZERO,
        }
        self.trampolines = _TrampolineLabels()
        # Instruction indices the packing phase patches afterwards.
        self.load_operand_increment = 0
        self.load_chunk = 0

    def build(self) -> str:
        """Emit the decoder's phases in order and pack its chunk cells."""
        self.read_inputs()
        self.select_chunk()
        self.divide_chunk()
        return self.pack_chunks()

    def mark(self, name: str) -> None:
        """Bind ``name`` to the next instruction's index."""
        self.labels[name] = len(self.instructions)

    def emit(
        self, a: int | str, b: int | str, target: str | int, d: int | str = "ZERO"
    ) -> int:
        """Append one instruction; return its index."""
        self.instructions.append((a, b, target, d))
        return len(self.instructions) - 1

    def jump(self, target: str) -> None:
        """Emit an unconditional jump to ``target``."""
        self.emit("ZERO", "ZERO", target)

    def clear(self, dst: str) -> None:
        """Emit an instruction that zeroes the cell named ``dst``."""
        self.emit(dst, dst, "next", "ONE")

    def branch_positive(self, cell: str, positive: str, zero: str) -> None:
        """Branch on ``cell > 0`` and restore the reusable jump cell."""
        positive_trampoline, zero_trampoline = self.trampolines.branch_pair()
        at = len(self.instructions)
        # The jump cell is the ``c`` operand of the dispatch instruction
        # itself -- there is no indirect jump to hide it behind now.
        jump_cell = _cell(at + 1, _C_OPERAND)
        self.emit(jump_cell, "FOUR", "next", cell)
        # The trampolines are two instructions apart; their midpoint is
        # the value from which adding/subtracting FOUR selects either one.
        self.emit("ZERO", "ZERO", _cell(at + 3))
        self.mark(positive_trampoline)
        self.emit(jump_cell, "FOUR", "next")
        self.emit("ZERO", "ZERO", positive)
        self.mark(zero_trampoline)
        self.emit(jump_cell, "FOUR", "next", "ONE")
        self.emit("ZERO", "ZERO", zero)

    def read_inputs(self) -> None:
        """Read every input; essential ones extend the Horner index."""
        # Only essential reads extend the Horner index; ignored reads
        # reuse TMP.
        for weight in self.weights:
            self.clear("TMP")
            self.emit("TMP", -1, "next")
            if not weight:
                continue
            self.emit("TMP", "C48", "next", "ONE")
            self.emit("INDEX", "INDEX", "next")
            self.emit("INDEX", "TMP", "next")

    def select_chunk(self) -> None:
        """Walk INDEX down to zero, advancing the chunk pointer per chunk."""
        self.mark("select_test")
        self.branch_positive("INDEX", "select_step", "selected")
        self.mark("select_step")
        self.emit("INDEX", "ONE", "next", "ONE")
        self.emit("COUNT", "ONE", "next", "ONE")
        self.emit("OFFSET", "ONE", "next")
        self.branch_positive("COUNT", "select_test", "advance_chunk")
        self.mark("advance_chunk")
        self.load_operand_increment = self.emit(0, "ONE", "next")
        self.emit("COUNT", "N", "next")
        self.clear("OFFSET")
        self.jump("select_test")

    def divide_chunk(self) -> None:
        """Divide the selected chunk by two OFFSET+1 times; print the bit."""
        self.mark("selected")
        self.clear("TABLE")
        self.load_chunk = self.emit("TABLE", "CHUNK0", "next")
        self.clear("SHIFT")
        self.emit("SHIFT", "OFFSET", "next")
        self.emit("SHIFT", "ONE", "div_init")

        # The final remainder is precisely the indexed truth-table bit.
        self.mark("div_init")
        self.clear("Q")
        self.clear("R")
        self.mark("div_test")
        self.branch_positive("TABLE", "div_first", "division_complete")
        self.mark("div_first")
        self.emit("TABLE", "ONE", "next", "ONE")
        self.branch_positive("TABLE", "div_pair", "div_odd")
        self.mark("div_pair")
        self.emit("TABLE", "ONE", "next", "ONE")
        self.emit("Q", "ONE", "div_test")
        self.mark("div_odd")
        self.emit("R", "ONE", "division_complete")

        self.mark("division_complete")
        self.emit("SHIFT", "ONE", "next", "ONE")
        self.branch_positive("SHIFT", "divide_again", "output")
        self.mark("divide_again")
        self.clear("TABLE")
        self.emit("TABLE", "Q", "div_init")
        self.mark("output")
        self.emit("OUT", "R", "next")
        self.emit(-1, "OUT", -8)  # print, then halt on the special address

    def pack_chunks(self) -> str:
        """Pack the table into cells, resolve memory, and return the text."""
        # Pack m adjacent essential rows per cell. Each value and each cell
        # address have O(log T) digits, while there are O(T/log T) cells.
        truth_table, chunk_width = self.truth_table, self.chunk_width
        chunks = [
            int(truth_table[start : start + chunk_width][::-1], 2)
            for start in range(0, len(truth_table), chunk_width)
        ]

        self.values.update((f"CHUNK{i}", value) for i, value in enumerate(chunks))
        memory = _memory(self.instructions, self.values, self.labels)
        # Advancing this instruction's destination advances LOAD_CHUNK's b
        # operand through the contiguous chunk cells.
        memory[_cell(self.load_operand_increment)] = _cell(self.load_chunk, _B_OPERAND)
        return " ".join(map(str, memory))


def _packed_build(truth_table: str, weights: list[int]) -> str:
    """Decode packed essential rows while consuming every original input."""
    return _PackedBuilder(truth_table, weights).build()


def _addsubjump_ordered(
    truth_table: str,
    perm: tuple[int, ...],
    *,
    shared: bool = False,
) -> str:
    """Emit one input order's AddSubJump program; see :func:`addsubjump`.

    ``truth_table`` is already permuted, so row indices are in the permuted
    frame; ``perm`` surfaces only where a node names the *stream* input
    whose cell it tests.

    Cells are named by the input they hold (``B{i}`` for stream input ``i``),
    not by the allocating instruction index: the node-read build keyed names
    off ``len(instructions)``, which a reorder shifts.
    """
    n = _validate_truth_table(truth_table)

    instructions: list[_Instruction] = []
    values: dict[str, int] = {}
    # ``c`` is a literal destination, so a branch target is resolved into the
    # operand rather than into a cell the jump dereferences.  ``targets`` maps
    # a forward-reference name to the instruction index it will land on.
    targets: dict[str, int] = {}
    # Operand names in mention order, recorded at emit: re-scanning every
    # operand cost 3.5M ``isinstance`` calls on a six-input build
    # (2026-10-11; a whole one is now 1,168 calls).
    named: list[str] = []

    def emit(a: _Operand, b: _Operand, c: _Operand, d: int) -> int:
        idx = len(instructions)
        instructions.append((a, b, c, d))
        for v in (a, b):
            if isinstance(v, str):
                named.append(v)
        return idx

    # The entry jumps over these two instruction-width data blocks.  Their
    # fixed addresses hold the operands repeated throughout the tree:
    # D48=4, D49=5, U=6 and C48=8.  The adds target U, instruction 1's own
    # ``c`` operand, which nothing writes -- adding U to itself is a no-op.
    u_cell = _cell(1, _C_OPERAND)
    emit(u_cell, u_cell, _cell(3), _ADD)
    instructions += [(_ASCII_ZERO, _ASCII_ONE, 0, 0), (-_ASCII_ZERO, 0, 0, 0)]

    stored = stored_inputs(truth_table, perm)

    # The reads, in stream order.  An input no node tests is read into
    # write-only scratch: the contract is that every input is *consumed*,
    # not that every value is kept.
    if any(i not in stored for i in range(n)):
        values["DUMP"] = 0
    for i in range(n):
        if i not in stored:
            emit("DUMP", -1, "next", _ADD)  # read and discard
            continue
        bit = f"B{i}"
        values[bit] = 0
        emit(bit, -1, "next", _ADD)  # B += input byte (48/49)
        emit(bit, _cell(2, _A_OPERAND), "next", _ADD)  # B += -48
        emit(bit, bit, "next", _ADD)  # double
        emit(bit, bit, "next", _ADD)  # double -> {0, 4}

    # Rows split most significant first, so the span a node covers is the
    # contiguous ``truth_table[lo:hi]`` and its two halves are that slice cut
    # in two.  The fold test is O(1) on the span, so the tree is O(2**n).
    constant = constant_span_test(truth_table)

    # IDs retain depth, so each row visits a self-modified branch at most once.
    levels, children, _constants = _residual_ids(truth_table, n)
    root = levels[0][0]
    seen: dict[int, str] = {}

    def build(level: int, lo: int, hi: int, residual: int) -> None:
        if shared:
            if residual in seen:
                emit(u_cell, u_cell, seen[residual], _ADD)
                return
            label = f"R{residual}"
            seen[residual] = label
            targets[label] = len(instructions)
        if constant(lo, hi):
            # Every read already happened up front, so a folded leaf prints
            # and halts with nothing to drain.
            emit(-1, _cell(1, _A_OPERAND) + int(truth_table[lo]), -8, _ADD)
            return
        half = (hi - lo) // 2
        if perm[level] not in stored or (
            shared and children[residual][0] == children[residual][1]
        ):
            # Reads already happened; this residual does not depend on the bit.
            build(level + 1, lo, lo + half, children[residual][0])
            return
        base = len(instructions)
        bit = f"B{perm[level]}"
        # The jump cell is the goto's own ``c`` operand: with a literal
        # destination the only computed jump is a self-modifying one.  It
        # rests on the zero trampoline two slots on, and ``B`` (0 or 4) moves
        # it to the one trampoline.
        jump = _cell(base + 1, _C_OPERAND)
        emit(jump, bit, "next", _ADD)  # c of the goto += B, the hoisted bit
        # Goto: rests on the zero trampoline.
        emit(u_cell, u_cell, _cell(base + 2), _ADD)
        ztarget = f"Z{base}"
        otarget = f"O{base}"
        emit(u_cell, u_cell, ztarget, _ADD)  # zero trampoline
        emit(u_cell, u_cell, otarget, _ADD)  # one trampoline
        targets[ztarget] = len(instructions)
        build(level + 1, lo, lo + half, children[residual][0])
        targets[otarget] = len(instructions)
        build(level + 1, lo + half, hi, children[residual][1])

    build(0, 0, 2**n, root)

    return " ".join(map(str, _memory(instructions, values, targets, [*named, *values])))


LANGUAGE = Language(
    "AddSubJump",
    "addsubjump",
    category="register_based",
    boolean=addsubjump,
    contract=BooleanContract(
        input_shape="char_stream",
    ),
    wrap=wrap_grid,
    proof_execution=(execution, True, (6,)),
    proof_workspace=(workspace, False, (3, 5)),
)
