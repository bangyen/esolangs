"""Build brainfuck Boolean programs with folded trees or affine streams."""

from collections.abc import Callable

from esolangs.generation.helpers import (
    _ASCII_ZERO,
    _validate_truth_table,
    constant_span_test,
    decision_tree_body,
    essential_inputs,
    in_input_order,
    move_text,
    subtree_ids,
)
from esolangs.generation.shared_block import ContinuationCost as _Cost
from esolangs.generation.shared_block import _repeated_blocks, repeated_block
from esolangs.generation.shared_flag import flag_tree_body, shared_flag_tree
from esolangs.generation.wrap import wrap_chars
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Language


def binary_bank(
    table: str, command_budget: int, *, remaining: int = 2
) -> tuple[str, int] | None:
    """Return a priced suffix bank after the standard identity-order reads."""
    n = _validate_truth_table(table)
    depth = n - remaining
    if remaining < 1 or depth < 2:
        return None
    start, result = 2 * (n - 1), 2 * n
    ids = subtree_ids(table)
    constant = constant_span_test(table)
    blocks = [(d, row) for d, row, _ in _repeated_blocks(table) if d == depth]
    if len(blocks) < 2:
        return None
    if remaining == 2:
        if len(blocks) > 14:
            raise ValueError("too many nonconstant two-input functions")
        planned_width = 4
        result_bit = 2
    else:
        planned_width = (len(blocks) + 1).bit_length()
        if planned_width > min(remaining + 2, depth):
            return None
        result_bit = min(remaining, planned_width - 1)
    completed_one = 1 << result_bit
    high_bit = 1 << (remaining + 1)
    flags = tuple(2 * (depth + i) + 1 for i in range(result_bit))
    kept = essential_inputs(table, n)
    # Standard reads overwrite the next kept cell for ignored inputs. Their
    # own cells before the last kept input remain zero, so [-] costs one step.
    unwritten = {2 * i for i in range(kept[-1]) if i not in kept}
    codes = [value for value in range(1, 1 << planned_width) if value != completed_one]
    # Reserve R's digit for completed one. All other digits use unread flags;
    # only a word exceeding that capacity needs the retired-input high bit.
    selected = {
        ids[depth][row >> remaining]: codes[i] for i, (_, row) in enumerate(blocks)
    }
    words = {
        codes[i]: table[row : row + (1 << remaining)]
        for i, (_, row) in enumerate(blocks)
    }
    out: list[str] = []
    pos = start
    count = 0
    targets: dict[int, tuple[int, int | None]] = {}

    def emit(code: str) -> None:
        nonlocal count
        out.append(code)
        count += len(code)

    def move(target: int) -> None:
        nonlocal pos
        emit(">" * (target - pos) if target >= pos else "<" * (pos - target))
        pos = target

    def clear(cell: int) -> int:
        move(cell)
        emit("[-]")
        return 1 if cell in unwritten else 3

    def inline(word: str) -> int:
        nonlocal pos
        # Each word is its own definition: defer its greatest repeat, so a
        # nested body shares like a top-level one.  Zero-constant elision
        # stays off -- its price is not the bank's price model.
        code, commands = flag_tree_body(
            word,
            tuple(range(depth, n)),
            pos,
            result,
            shared=repeated_block(word),
            fold_zero=False,
        )
        emit(code)
        pos = result
        return commands

    def pending_target(code: int, free: int | None = None) -> int:
        key = code * (n + 1) + (0 if free is None else free // 2 + 1)
        targets[key] = (code, free)
        return key

    def split[Branch](
        bit: int, one: Callable[[], Branch], zero: Callable[[], Branch]
    ) -> tuple[Branch, int, Branch, int]:
        """Emit both guarded arms and return their bodies and path overheads."""
        beginning = count
        flag = bit + 1
        move(flag)
        emit("+")
        move(bit)
        zero_entry = count - beginning + 1
        emit("[-")
        move(flag)
        emit("-")
        one_entry = count - beginning
        one_body = one()
        finish = count
        move(bit)
        emit("]")
        one_finish = count - finish
        zero_start = count
        move(flag)
        emit("[-")
        one_finish += count - zero_start - 1
        zero_entry += count - zero_start
        zero_body = zero()
        finish = count
        move(flag)
        emit("]")
        return one_body, one_entry + one_finish, zero_body, zero_entry + count - finish

    def node(i: int, lo: int, hi: int, free: int | None) -> _Cost:
        beginning = count
        key = ids[i][lo >> (n - i)]
        if i == depth:
            code = selected.get(key)
            if code is not None and (not (code & high_bit) or free is not None):
                cells = (*flags, result, free)
                for bit, cell in enumerate(cells):
                    if code & (1 << bit):
                        if cell is None:
                            raise ValueError("a high marker needs a retired input")
                        move(cell)
                        emit("+")
                return _Cost(
                    count - beginning,
                    target=pending_target(code, free if code & high_bit else None),
                )
            commands = inline(table[lo:hi])
            if constant(lo, hi):
                return _Cost(
                    commands,
                    target=pending_target(completed_one if table[lo] == "1" else 0),
                )
            return _Cost(
                commands,
                (
                    _Cost(0, target=pending_target(0)),
                    _Cost(0, target=pending_target(completed_one)),
                ),
            )
        if constant(lo, hi):
            if table[lo] == "1":
                move(result)
                emit("+")
            # Unvisited prefix bits must not masquerade as a high marker.
            adjustment = sum(clear(2 * level) - 3 for level in range(i, depth))
            return _Cost(
                count - beginning + adjustment,
                target=pending_target(completed_one if table[lo] == "1" else 0),
            )
        mid = (lo + hi) // 2
        zero_id, one_id = ids[i + 1][lo >> (n - i - 1)], ids[i + 1][mid >> (n - i - 1)]
        if zero_id == one_id:
            cleared = clear(2 * i)
            prefix = count - beginning + cleared - 3
            return _Cost(prefix, (node(i + 1, lo, mid, 2 * i),))
        # An active one guard still tests its cleared input when it closes.
        # Only a zero arm (whose one test has finished) or an ignored input
        # can hold the high marker. With neither available, keep this copy.
        one, one_cost, zero, zero_cost = split(
            2 * i,
            lambda: node(i + 1, mid, hi, free),
            lambda: node(i + 1, lo, mid, 2 * i),
        )
        return _Cost(0, (_Cost(one_cost, (one,)), _Cost(zero_cost, (zero,))))

    prefix = node(0, 0, len(table), None)
    labels = tuple(sorted({code for code, _ in targets.values()}))
    width = max(labels).bit_length()
    if width > depth:
        return None
    collector = 2 * (depth - 1) + 1
    # At most one retired input holds a high marker; every other prefix
    # input is zero. Collect it before reusing those cells as decoder bits.
    collector_base = 0
    for i in range(depth if width == remaining + 2 else 0):
        collector_base += abs(pos - 2 * i) + 1
        move(2 * i)
        emit("[-")
        move(collector)
        emit("+")
        move(2 * i)
        emit("]")
    scratch = tuple(2 * (depth - width + i) for i in range(width))
    metadata = (*flags, result, collector)[:width]
    transfer_base = 0
    transfer_active = []
    for source, target in zip(metadata, scratch, strict=True):
        transfer_base += abs(pos - source) + 1
        transfer_active.append(2 * abs(source - target) + 3)
        move(source)
        emit("[-")
        move(target)
        emit("+")
        move(source)
        emit("]")

    def decode(bit: int, labels: tuple[int, ...]) -> dict[int, int]:
        beginning = count
        if bit < 0:
            code = labels[0]
            if code == completed_one:
                move(result)
                emit("+")
            elif code != 0:
                return {code: inline(words[code])}
            return {code: count - beginning}
        groups = [
            tuple(code for code in labels if (code >> bit) & 1 == value)
            for value in (0, 1)
        ]
        cell = scratch[bit]
        if not groups[0] or not groups[1]:
            if groups[1]:
                move(cell)
                emit("-")
            flat = count - beginning
            return {
                label: flat + cost
                for label, cost in decode(bit - 1, groups[1] or groups[0]).items()
            }
        one, one_cost, zero, zero_cost = split(
            cell,
            lambda: decode(bit - 1, groups[1]),
            lambda: decode(bit - 1, groups[0]),
        )
        return {
            **{label: cost + one_cost for label, cost in one.items()},
            **{label: cost + zero_cost for label, cost in zero.items()},
        }

    decoder = decode(width - 1, labels)
    final_move = abs(result - pos)
    move(result)
    tails: dict[int | None, int] = {
        key: collector_base
        + (2 * abs(collector - free) + 3 if free is not None else 0)
        + transfer_base
        + sum(active for bit, active in enumerate(transfer_active) if code & (1 << bit))
        + decoder[code]
        + final_move
        for key, (code, free) in targets.items()
    }
    commands = prefix.evaluate(tails)
    # The body keeps every value binary and every address lies in 0..2n.
    # Adding ASCII 48 only to R therefore preserves the 2n+6 tape-bit cap.
    if commands > command_budget:
        return None
    return "".join(out), commands


def larger_suffix_bank(table: str, command_budget: int) -> tuple[str, int] | None:
    """Emit the eligible non-default level with greatest repeated-span saving."""
    n = _validate_truth_table(table)
    groups: dict[int, tuple[int, int]] = {}
    for depth, _, saving in _repeated_blocks(table):
        count, score = groups.get(depth, (0, 0))
        groups[depth] = count + 1, score + saving
    best: tuple[int, int] | None = None
    for depth, (count, score) in groups.items():
        remaining = n - depth
        width = (count + 1).bit_length()
        if remaining != 2 and count >= 2 and width <= min(remaining + 2, depth):
            candidate = score, remaining
            if best is None or candidate > best:
                best = candidate
    # One scan chooses a level; no bodies are generated for losing levels.
    # Its prefix and disjoint representative spans total O(T). Actual text
    # and commands still decide admission alongside the existing candidates.
    return (
        None if best is None else binary_bank(table, command_budget, remaining=best[1])
    )


__all__ = ["bf_tree", "brainfuck"]


def brainfuck(truth_table: str) -> str:
    """Return a program for a binary, MSB-first ``2**n`` truth table."""
    return bf_tree(truth_table)


_RIGHT, _LEFT = ">", "<"


def bf_tree(truth_table: str) -> str:
    """Return a compact program, consuming every input unconditionally.

    Tree bits use cells 2i, flags 2i+1; branches clear both, and one final print
    reads the result. Flags cut n=10 sparse from 2,646 to 754 chars;
    folding and shared output cut n=10 XOR from 77,939 to 18,495.  Equal
    sibling halves merge; repeated residuals use one unused flag per level
    and emit once in depth order, within the existing command bound.
    A bank can use several unused descendant flags instead: a same-level bank,
    or the union of the one-per-depth picks with the greatest bank, so blocks
    at several depths defer.
    Two-input banks also use four-bit labels, with a retired input holding
    the high bit; labels are consumed before their shared bodies execute.
    Affine tables also stream through three cells: n=16 parity falls from
    672,691 to 1,186 chars, with at most 66 commands per selected input.
    An ignored input before the last kept one is read bare into the next
    kept cell, whose read overwrites it: 1.9% smaller at n=8 with one ignored,
    6.7% with two. A trailing one keeps its subtract; left at 48/49 it breaks
    the Workspace bound, and ``,[-]`` the execution bound (289 > 251 steps).
    """
    tree = in_input_order(truth_table, _bf_ordered)
    affine = _affine_stream(truth_table)
    return min((tree, affine), key=len) if affine is not None else tree


def _affine_stream(table: str) -> str | None:
    """Stream an admitted affine table through one bit and a toggle scratch."""
    n = _validate_truth_table(table)
    bias = int(table[0])
    coefficients = [int(table[1 << (n - i - 1)]) ^ bias for i in range(n)]
    expected = [bias]
    for coefficient in reversed(coefficients):
        expected += [value ^ coefficient for value in expected]
    if any(str(value) != bit for value, bit in zip(expected, table, strict=True)):
        return None
    # Input, accumulator, scratch occupy cells 0, 1, 2. Each selected read
    # costs at most 66 commands; a trailing ignored read must leave a bit
    # rather than ASCII beside the final ASCII output to retain workspace.
    parts = [">+<" if bias else ""]
    commands = 3 * bias + 50
    for i, coefficient in enumerate(coefficients):
        if coefficient:
            parts.append("," + "-" * _ASCII_ZERO + "[->>+<[->-<]>[-<+>]<<]")
            commands += 66
        elif i == n - 1:
            parts.append("," + "-" * _ASCII_ZERO)
            commands += 49
        else:
            parts.append(",")
            commands += 1
    if commands > 69 * n + 44:
        return None
    parts.append(">" + "+" * _ASCII_ZERO + ".")
    return "".join(parts)


def _bf_ordered(
    truth_table: str, perm: tuple[int, ...], *, share: bool = True, bank: bool = True
) -> str:
    """Emit a permuted table; node i tests cell 2*perm[i], reads stay ordered."""
    n = _validate_truth_table(truth_table)

    # read bits b_i at cell 2i, leaving the flag cells (1, 3, ...) zero; an
    # ignored input is read into the next kept input's cell, which overwrites it
    kept = essential_inputs(truth_table, n)
    last = kept[-1] if kept else -1
    reads, pending = [], ""
    for i in range(n):
        if i in kept or i > last:
            reads.append(pending + "," + "-" * _ASCII_ZERO)
            pending = ""
        else:
            reads.append("")
            pending += ","
    cells = [(_RIGHT * 2).join(reads)]
    pos = 2 * max(n - 1, 0)
    header = cells[0]
    tree_start = pos

    # The tree itself.
    body, pos = decision_tree_body(truth_table, _RIGHT, _LEFT, perm, pos)
    cells.append(body)

    # A shared print pays the ASCII offset once rather than at every leaf.
    cells.append(move_text(pos, 2 * n, _RIGHT, _LEFT))
    cells.append("+" * _ASCII_ZERO)
    cells.append(".")
    plain = "".join(cells)
    if not share:
        return plain
    shared = shared_flag_tree(
        truth_table,
        perm,
        tree_start,
        2 * n,
        command_budget=69 * n + 44 - len(header) - _ASCII_ZERO - 1,
        bank=bank,
    )
    if shared is not None:
        body, commands = shared
        candidate = header + body + "+" * _ASCII_ZERO + "."
        if len(header) + commands + _ASCII_ZERO + 1 <= 69 * n + 44 and len(
            candidate
        ) < len(plain):
            plain = candidate
    if bank and perm == tuple(range(n)):
        binary = binary_bank(truth_table, 69 * n + 44 - len(header) - _ASCII_ZERO - 1)
        if binary is not None:
            body, _ = binary
            candidate = header + body + "+" * _ASCII_ZERO + "."
            if len(candidate) < len(plain):
                plain = candidate
        larger = larger_suffix_bank(
            truth_table, 69 * n + 44 - len(header) - _ASCII_ZERO - 1
        )
        if larger is not None:
            body, _ = larger
            candidate = header + body + "+" * _ASCII_ZERO + "."
            if len(candidate) < len(plain):
                plain = candidate
    return plain


LANGUAGE = Language(
    "brainfuck",
    "brainfuck",
    category="tape_based",
    weekly_mutation=("interpreter",),
    boolean=brainfuck,
    contract=BooleanContract(
        input_shape="char_stream",
    ),
    wrap=wrap_chars,
)
