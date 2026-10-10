"""Count forced divergence after recursively confined preserving prefixes."""

import sys
from collections import defaultdict
from functools import lru_cache
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _brainfuck_divergence import _append, _construct, _export

from tests.proofs._brainfuck_balanced import Matrix, patterns
from tests.proofs._brainfuck_count import automaton, minimize

# Earlier four atom fields, right/left confinement phase (0/1/broken),
# preserving-prefix phase (root/right1/right2/left1/left2/broken/blocked).
type State = tuple[bool, int, int, int, int, int, int, int]
type Loop = tuple[bool, bool, int, bool]  # read, first print, confinement bits, empty
EMPTY: State = (False, 0, 0, 0, 0, 0, 0, 0)
BOUND = (1377, 200)
SCALE = 10**8


def loop_types() -> list[Loop]:
    """Return empty and nonempty loop types; reads prohibit confinement."""
    return [(False, False, 3, True)] + [
        (read, printing, kind, False)
        for read in (False, True)
        for printing in (False, True)
        for kind in ([0] if read else range(4))
    ]


@lru_cache(maxsize=8192)
def _step(state: State, column: int) -> State | None:
    read, tail, first, count, right, left, prefix, balance = state
    loop = loop_types()[column - 6] if column >= 6 else None
    atom = ("M" if loop[1] else "L") if loop else (".", ",", "s", "s", "m", "m")[column]
    base = _append(
        (read, tail, first, count), atom, reads=loop[0] if loop else column == 1
    )
    if base is None:
        return None
    for direction in (1, 2):
        phase = right if direction == 1 else left
        if loop:
            if not (loop[2] & direction if phase == 0 else loop[2] == 3 and phase == 1):
                phase = 2
        elif column == 1:
            phase = 2
        elif column in (4, 5):
            opening = 5 if direction == 1 else 4
            phase = (
                1
                if column == opening and phase == 0
                else 0
                if column != opening and phase == 1
                else 2
            )
        if direction == 1:
            right = phase
        else:
            left = phase
    if prefix < 5:
        if loop:
            if prefix == 0:
                prefix = 6 if loop[3] and balance == 0 else 5
            elif not (
                loop[2] & (1 if prefix < 3 else 2) if prefix in (1, 3) else loop[2] == 3
            ):
                prefix = 5
        elif column == 1:
            prefix = 5
        elif column in (2, 3) and prefix == 0:
            balance += 1 if column == 3 else -1
            if abs(balance) > 1:
                prefix = 5
        elif column in (4, 5):
            movement = (
                {0: 3, 3: 4, 2: 1, 1: 0} if column == 4 else {0: 1, 1: 2, 4: 3, 3: 0}
            )
            prefix = movement.get(prefix, 5)
    return (*base, right, left, prefix, balance if prefix < 5 else 0)


def body_type(state: State) -> Loop | None:
    """Return the eligible body type; blocked prefixes cannot become loop bodies."""
    read, tail, first, count, right, left, prefix, _balance = state
    if (first == 2 and count == 1) or (not read and tail == 3) or prefix == 6:
        return None
    kind = (right == 0) + 2 * (left == 0)
    return read, first == 1, kind, count == 0


def states() -> list[State]:
    """Reconstruct all reachable atom states, aborting at 512 classes."""
    pending = [EMPTY]
    reached = {EMPTY}
    for state in pending:
        for column in range(6 + len(loop_types())):
            target = _step(state, column)
            if target is not None and target not in reached:
                reached.add(target)
                pending.append(target)
                if len(reached) > 512:
                    raise RuntimeError("preserving certificate class budget exceeded")
    return sorted(reached)


def typed_counts(limit: int) -> list[dict[State, int]]:
    """Return exact sequence coefficients before finite-factor intersection."""
    sequences = [{EMPTY: 1}]
    kinds = loop_types()
    for size in range(1, limit + 1):
        atoms = [(1, column, 1) for column in range(6)]
        for width in range(2, size + 1):
            bodies: defaultdict[Loop, int] = defaultdict(int)
            for state, count in sequences[width - 2].items():
                kind = body_type(state)
                if kind is not None:
                    bodies[kind] += count
            atoms.extend(
                (width, 6 + kinds.index(kind), count) for kind, count in bodies.items()
            )
        current: defaultdict[State, int] = defaultdict(int)
        for width, column, multiplicity in atoms:
            for state, count in sequences[size - width].items():
                target = _step(state, column)
                if target is not None:
                    current[target] += count * multiplicity
        sequences.append(dict(current))
    return sequences


def matrix_image(
    rows: list[list[int]],
    classes: list[State],
    matrices: list[Matrix],
    scale: int,
    bound: tuple[int, int],
) -> list[Matrix]:
    """Return the exact upward-rounded image using grouped opening destinations."""
    numerator, denominator = bound
    divisor = numerator**2 * scale
    index = {state: position for position, state in enumerate(classes)}
    kinds = loop_types()
    opening = {row[6] for row in rows if row[6] >= 0}
    loops: list[dict[int, dict[int, int]]] = [
        {start: {} for start in opening} for _ in kinds
    ]
    for state, matrix in zip(classes, matrices, strict=True):
        kind = body_type(state)
        if kind is None:
            continue
        loop = loops[kinds.index(kind)]
        for start in opening:
            output = loop[start]
            for end, value in matrix[start].items():
                target = rows[end][7]
                if target >= 0:
                    output[target] = output.get(target, 0) + value
    # Many loop types induce the same atom transition. Add their kernels
    # before multiplying, rather than repeating the sparse product.
    combined: dict[tuple[int, ...], dict[int, dict[int, int]]] = {}
    transitions = []
    for state in classes:
        groups: defaultdict[int, list[int]] = defaultdict(list)
        for column in range(len(loops)):
            target_state = _step(state, column + 6)
            if target_state is not None:
                groups[index[target_state]].append(column)
        edges = []
        for target, columns in groups.items():
            key = tuple(columns)
            if key not in combined:
                kernel: dict[int, dict[int, int]] = {start: {} for start in opening}
                for column in columns:
                    for start, row in loops[column].items():
                        output = kernel[start]
                        for end, value in row.items():
                            output[end] = output.get(end, 0) + value
                combined[key] = kernel
            edges.append((target, combined[key]))
        transitions.append(edges)
    image: list[Matrix] = [[{} for _ in rows] for _ in classes]
    literal_scale = numerator * denominator * scale
    loop_scale = denominator**2
    for start in sorted({0, *opening}):
        for state, matrix, edges in zip(classes, matrices, transitions, strict=True):
            source = matrix[start]
            if not source:
                continue
            for column in range(6):
                target_state = _step(state, column)
                if target_state is None:
                    continue
                output = image[index[target_state]][start]
                for end, value in source.items():
                    target = rows[end][column]
                    if target >= 0:
                        output[target] = output.get(target, 0) + literal_scale * value
            group: dict[int, int] = {}
            for end, value in source.items():
                target = rows[end][6]
                if target >= 0:
                    group[target] = group.get(target, 0) + value
            for target, loop in edges:
                output = image[target][start]
                for middle, left in group.items():
                    weighted_left = loop_scale * left
                    for end, right in loop[middle].items():
                        output[end] = output.get(end, 0) + weighted_left * right
    image[index[EMPTY]] = [
        {state: numerator**2 * scale**2} if state in {0, *opening} else {}
        for state in range(len(rows))
    ]
    return [
        [
            {end: (value + divisor - 1) // divisor for end, value in row.items()}
            for row in matrix
        ]
        for matrix in image
    ]


@lru_cache(maxsize=1)
def certificate() -> tuple[list[list[int]], list[State], list[Matrix]]:
    """Reconstruct the prefix certificate under the standing construction caps."""
    from _preserving_kernel import construct
    from preserving_certificate import check_certificate

    rows = minimize(automaton(patterns(), []))
    if len(rows) > 256:
        raise RuntimeError("preserving certificate DFA budget exceeded")
    classes = states()
    index = {state: position for position, state in enumerate(classes)}
    kinds = loop_types()
    edges = [
        [
            index[target] if (target := _step(state, column)) is not None else -1
            for column in range(6 + len(kinds))
        ]
        for state in classes
    ]
    types = [
        kinds.index(kind) if (kind := body_type(state)) is not None else -1
        for state in classes
    ]
    native = construct(rows, edges, types, len(kinds), SCALE, BOUND)
    if native is not None:
        check_certificate(rows, classes, native, SCALE, BOUND)
        return rows, classes, native
    return (
        rows,
        classes,
        _construct(
            rows, classes, SCALE, BOUND, matrix_image, "preserving", supersolution=True
        ),
    )


def main() -> None:
    """Rebuild, independently check and optionally export the prefix certificate."""
    from preserving_certificate import check_certificate

    _export(certificate, check_certificate, SCALE, BOUND, "preserving-prefix")


if __name__ == "__main__":
    main()
