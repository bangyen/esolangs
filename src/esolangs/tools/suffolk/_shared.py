"""Evaluate each distinct cofactor once using self-cancelling NOR writes."""

from esolangs.tools.helpers import essential_inputs, read_at, subtree_ids
from esolangs.tools.suffolk import _one, _read, _write


def _nor(target: int, *operands: int) -> str:
    """Write NOR of Boolean operands, cancelling the target's previous value."""
    return _read(target) + "".join(_read(cell) for cell in operands) + _write(target)


def shared_dag(table: str, inputs: int) -> str | None:
    """Return a reduced cofactor circuit within the existing workspace ledger."""
    used = essential_inputs(table, inputs)
    if not used:
        return None
    ids = subtree_ids(read_at(table, used, inputs))
    count = len(used)
    # Store complemented cofactors: false/true use the shared one/zero cells.
    slots = {0: 3, 1: 4}
    nodes: list[tuple[int, int, int, int]] = []
    for depth in range(count - 1, -1, -1):
        for index, state in enumerate(ids[depth]):
            if state in slots:
                continue
            zero, one = ids[depth + 1][2 * index : 2 * index + 2]
            if zero == one:
                slots[state] = slots[zero]
            else:
                target = 5 + count + len(nodes)
                slots[state] = target
                nodes.append((depth, slots[zero], slots[one], target))
    # Tape cells are binary except the shared byte/ASCII-offset cell
    # (six bits). The accumulator also needs six bits.
    # Pay any pointer growth above the lookup's three bits from its tape cap.
    tape_bits = 10 + count + len(nodes)
    pointer_bits = (4 + count + len(nodes)).bit_length()
    if tape_bits + pointer_bits > max(19, 4 * inputs - 1) + 3:
        return None
    # The ledger limits nodes to O(n): rendering costs O(n²), hence O(T).
    # Initial ! clears the previous print's accumulator on a repeated pass.
    # The first read is within 59 commands, preserving the L+151 EOF bound.
    out = [_write(0), _one(3)]
    positions = {original: i for i, original in enumerate(used)}
    for original in range(inputs):
        position = positions.get(original)
        if position is None:
            out.append(",!")
        else:
            out.append(_one(0) + _write(0) * 47 + ",!")
            out.append(_nor(1, 0) + _nor(5 + position, 1))
    for depth, zero, one, target in nodes:
        # For complemented children g0/g1, complement of the mux is
        # NOR(NOR(b,g0), NOR(not-b,g1)). Scratch cells are reused per node.
        out.append(
            _nor(0, 5 + depth)
            + _nor(1, 0, zero)
            + _nor(2, 5 + depth, one)
            + _nor(target, 1, 2)
        )
    out.append(
        _nor(1, slots[ids[0][0]])
        + _one(0)
        + _write(0) * 47
        + _read(0)
        + _read(3)
        + _read(1)
        + "."
    )
    return "".join(out)
