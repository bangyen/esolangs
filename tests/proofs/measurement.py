"""Run resource witnesses and measure native commands and written state."""

import esolangs
from esolangs.debugger import make_vm
from esolangs.vm import _capture_workspace
from scripts.benchmark import WrittenState
from tests.proofs._witnesses import (
    _WITNESSES,
    _befunge_worst,
    _bfstack_worst,
    _bfstack_ws_worst,
    _laserfuck_worst,
    _malbolge_stub,
    _seeded,
    _streetcode_worst,
)
from tests.proofs.deep.execution import _dense, run_to_answer
from tests.support.witness_tables import parity as _parity
from tests.support.witness_tables import row_bits


def _unary_tables(n: int) -> tuple[str, ...]:
    """Every table a nine-command source admits: constants and single inputs.

    Constant 0 is n commands, constant 1 n + 3, input i alone n + 2 if last
    else n + 4, one more negated; two or more essential inputs need 4n - 2 or
    more (AND 5n - 2, n = 2 only).
    """
    width = 1 << n

    def single(i: int, flip: int) -> str:
        return "".join(str((r >> (n - 1 - i) & 1) ^ flip) for r in range(width))

    shapes = {"0" * width: n, "1" * width: n + 3}
    for i in range(n):
        for flip in (0, 1):
            shapes[single(i, flip)] = n + (2 if i == n - 1 else 4) + flip
    tables = [table for table, commands in shapes.items() if commands <= 9]
    return (*tables, *(("0001",) if n == 2 else ()))


def tables(name: str, n: int) -> tuple[str, ...]:
    """Structured and random tables, with named worst-case witnesses."""
    width = 1 << n
    if name == "Unary":
        return _unary_tables(n)
    if name == "Circuit Diagram" and n >= 8:
        # Parity reaches 2n+1 at n=8; dense tables exercise pool admission
        # and constants use only their clock gate.
        return (_seeded(n, 1), _parity(n), "1" * width)
    if name == "Streetcode":
        # A tree's execution worst, one zero at the last entry; the shared
        # worst, parity below five and above it the flat street's longest
        # fill (:func:`_streetcode_worst`).
        return ("1" * (width - 1) + "0", _streetcode_worst(n))
    if name == "Malbolge":
        # Straight-line code: all 10 tables tie at every n measured; the
        # all-zeros or alternating label reaches the longest stub.
        return (_dense(n), _malbolge_stub(n), "0" * width)
    if name == "Befunge":
        # Straight-line code over the inputs that matter; parity has all, and
        # the longest scaling text needs a layout parity misses at n = 11, 12.
        return (_parity(n), _befunge_worst(n))
    if name == "LaserFuck" and n >= 5:
        # Retain prior extremes and include the shifted tape's exact witness.
        return (_parity(n), _dense(n), "0" * width, "1" * width, *_laserfuck_worst(n))
    if name == "BFStack" and n >= 10:
        # Lower arities sweep the generic families; this named witness reaches
        # the one-arm chain bound without repeating them.
        return (_bfstack_worst(n), _bfstack_ws_worst(n))
    if name == "Algebraic Programming Language" and n >= 8:
        # Lower arities sweep the full corpus; retain shared, dense and inline
        # program shapes for the larger frame/serial bounds.
        return (_parity(n), _dense(n), "0" * width, "1" * width)
    tables = (
        _parity(n),
        _seeded(n, 1),
        "0" * width,
        "1" * width,
        "0" * (width - 1) + "1",
        "10" * (width // 2),
        "1" * (width - 1) + "0",
        "1" + "0" * (width - 2) + "1",
        "01" * (width // 2),
    )
    if name == "BFStack" and n >= 8:
        tables += (_bfstack_worst(n),)
    if name == "BFStack" and n >= 9:
        tables += (_bfstack_ws_worst(n),)
    if name == "AddSubJump":
        # The packed decoder's worst now that the tree takes the lone zero:
        # ones but rows 8 mod 9 and the last, reaching it at n = 6.
        tables += (
            "".join("0" if r % 9 == 8 or r == width - 1 else "1" for r in range(width)),
        )
    if name == "Bitdeque":
        tables += ("10" + "01" * (width // 2 - 1),)
    if name in {"ArrowQueue", "EGL", "Minsky Swap", "ROTfuck"}:
        # Their worst, exhaustive through n=3: a lone zero, second to last.
        # ROTfuck's was NAND's, and Minsky Swap's and EGL's parity, until
        # symmetric tables took the count.
        tables += ("1" * (width - 2) + "01",)
    if name in _WITNESSES:
        tables += _WITNESSES[name](n)
    if name == "Fargo" and n == 6:
        # 322 commands: shared names run their bodies per reference, past 5T + 1.
        tables += ("1000001000110001000001001111000100000100010100000110010000011000",)
    if name == "Unsquare" and n >= 8:
        # One leaf of 12- and 14-cell runs (12a + 14b = S, 3 a cell); the
        # others alternate, so every input stays essential.
        leaf = 2 ** (n - max(0, (n - 3) // 2))
        b = (leaf // 2) % 6
        a = (leaf // 2 - 7 * b) // 6
        runs = [*[12] * a, *[14] * b]
        head = "".join(str(i % 2) * c for i, c in enumerate(runs))
        tables += (head + "01" * (leaf // 2) * (width // leaf - 1),)
    if name == "Packlang" and n >= 3:
        # The most zeros a 128-row fill block may punch, in every block;
        # zeros are isolated, since a run of ones would be a shorter loop.
        block = min(width, 128)
        zeros = (block - 4) // 2
        tail = block - 2 * (zeros - 1)
        # The odd tail zero keeps every input essential.
        head = "10" * (zeros - 1) + "11" + "0" + "1" * (tail - 3)
        # Swap pair j of 16-row block j, so no two blocks are equal: equal
        # ones alias at a smaller block (n=7: 311 steps, not 1205).
        cells = list(head)
        for j in range(block // 16 - 1):
            at = 16 * j + 2 * j % 16
            cells[at], cells[at + 1] = cells[at + 1], cells[at]
        tables += ("".join(cells) * (width // block),)
    return tuple(dict.fromkeys(tables))


def measure(
    name: str,
    table: str,
    *,
    written: bool = False,
    program: esolangs.Program | None = None,
) -> tuple[int, int]:
    """Most commands and optional written-state bits over halting rows."""
    facts = esolangs.describe(name)
    halts = None
    if facts["answer_mode"] == "termination":
        halts = str(list(facts["answer_encoding"]).index("halts"))
    n = len(table).bit_length() - 1
    if program is None:
        program = esolangs.generate(name, table)
    worst_steps = worst_bits = 0
    for row in range(len(table)):
        if halts is not None and table[row] != halts:
            continue
        bits = row_bits(row, n)
        if facts["parameterized"]:
            source, stdin = esolangs.instantiate(name, program, bits), ""
        else:
            source, stdin = (
                program,
                esolangs.encode_inputs(name, bits, truth_table=table),
            )
        machine = make_vm(name, source, stdin=stdin)
        state = WrittenState(_capture_workspace(machine)) if written else None
        steps = run_to_answer(
            machine, sample=state.sample if state is not None else None
        )
        assert steps is not None  # no cap
        worst_steps = max(worst_steps, steps)
        if state is not None:
            worst_bits = max(worst_bits, state.bits)
    return worst_steps, worst_bits
