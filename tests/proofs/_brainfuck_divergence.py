"""Count balanced words with unrestricted nonzero-tail divergence removed."""

from collections import defaultdict
from functools import lru_cache
from time import monotonic

from tests.proofs._brainfuck_balanced import SCALE, Matrix, patterns
from tests.proofs._brainfuck_count import automaton, minimize

# State: any read, last-loop suffix (none/plain/print-first/one sign),
# first atom (empty/print/loop/other), atom count capped at two.
type State = tuple[bool, int, int, int]
type Counts = dict[State, int]
EMPTY: State = (False, 0, 0, 0)
BOUND = (689, 100)


def _append(state: State, atom: str, *, reads: bool) -> State | None:
    read, tail, first, count = state
    if atom == "." and tail == 2:
        return None
    if atom in ("L", "M"):
        tail = 1 if atom == "L" else 2
    elif atom == "s":
        tail = 3 if tail in (1, 2) else 0
    elif atom != ".":
        tail = 0
    if not count:
        first = 1 if atom == "." else 2 if atom in ("L", "M") else 3
    return read or reads, tail, first, min(count + 1, 2)


def typed_counts(limit: int) -> tuple[list[Counts], list[dict[tuple[bool, bool], int]]]:
    """Return sequence and loop-body coefficients; no finite factors are removed."""
    sequences: list[Counts] = [{EMPTY: 1}]
    bodies: list[dict[tuple[bool, bool], int]] = [{(False, False): 1}]
    for size in range(1, limit + 1):
        current: defaultdict[State, int] = defaultdict(int)
        atoms = [(1, ".", False, 1), (1, ",", True, 1)]
        atoms.extend([(1, "s", False, 2), (1, "m", False, 2)])
        for width in range(2, size + 1):
            for (read, printing), multiplicity in bodies[width - 2].items():
                atoms.append((width, "M" if printing else "L", read, multiplicity))
        for width, atom, read, multiplicity in atoms:
            for state, count in sequences[size - width].items():
                target = _append(state, atom, reads=read)
                if target is not None:
                    current[target] += count * multiplicity
        sequences.append(dict(current))
        body: defaultdict[tuple[bool, bool], int] = defaultdict(int)
        for (read, tail, first, count), value in current.items():
            if first == 2 and count == 1:
                continue
            if not read and tail == 3:
                continue
            body[read, first == 1] += value
        bodies.append(dict(body))
    return sequences, bodies


def states() -> list[State]:
    """Return the reachable atom states, reconstructed without a stored table."""
    reached = {EMPTY}
    pending = [EMPTY]
    for state in pending:
        for atom, reads in (
            (".", False),
            (",", True),
            ("s", False),
            ("m", False),
            ("L", False),
            ("M", False),
            ("L", True),
            ("M", True),
        ):
            target = _append(state, atom, reads=reads)
            if target is not None and target not in reached:
                reached.add(target)
                pending.append(target)
    return sorted(reached)


def matrix_image(
    rows: list[list[int]],
    classes: list[State],
    matrices: list[Matrix],
    scale: int,
    bound: tuple[int, int],
) -> list[Matrix]:
    """Return the upward-rounded polynomial image, grouping bracket destinations."""
    numerator, denominator = bound
    divisor = numerator**2 * scale
    index = {state: position for position, state in enumerate(classes)}
    opening = sorted({row[6] for row in rows if row[6] >= 0})
    # Loop matrices depend only on the destination of `[`, and end at a `]` target.
    loops: dict[tuple[bool, bool], dict[int, dict[int, int]]] = {
        (read, printing): {start: {} for start in opening}
        for read in (False, True)
        for printing in (False, True)
    }
    for state, matrix in zip(classes, matrices, strict=True):
        read, tail, first, count = state
        if (first == 2 and count == 1) or (not read and tail == 3):
            continue
        for start in opening:
            output = loops[read, first == 1][start]
            for end, value in matrix[start].items():
                target = rows[end][7]
                if target >= 0:
                    output[target] = output.get(target, 0) + value
    image: list[Matrix] = [[{} for _ in rows] for _ in classes]
    literal_scale = numerator * denominator * scale
    loop_scale = denominator**2
    starts = {0, *opening}
    for start in sorted(starts):
        groups: dict[tuple[bool, int], dict[int, int]] = {}
        for state, matrix in zip(classes, matrices, strict=True):
            read, _, first, count = state
            source = matrix[start]
            for column, atom in enumerate((".", ",", "s", "s", "m", "m")):
                target_state = _append(state, atom, reads=column == 1)
                if target_state is None:
                    continue
                output = image[index[target_state]][start]
                for end, value in source.items():
                    target = rows[end][column]
                    if target >= 0:
                        output[target] = output.get(target, 0) + literal_scale * value
            if count:
                group = groups.setdefault((read, first), {})
                for end, value in source.items():
                    target = rows[end][6]
                    if target >= 0:
                        group[target] = group.get(target, 0) + value
        for (read, printing), loop in loops.items():
            tail = 2 if printing else 1
            begin = rows[start][6]
            if begin >= 0:
                output = image[index[read, tail, 2, 1]][start]
                for end, value in loop[begin].items():
                    output[end] = output.get(end, 0) + loop_scale * scale * value
            for (prefix_read, first), group in groups.items():
                output = image[index[prefix_read or read, tail, first, 2]][start]
                for middle, left in group.items():
                    for end, right in loop[middle].items():
                        output[end] = output.get(end, 0) + loop_scale * left * right
    image[index[EMPTY]] = [
        {state: numerator**2 * scale**2} if state in starts else {}
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
    """Rebuild the capped nonzero-tail supersolution; abort without relaxing it."""
    rows = minimize(automaton(patterns(), []))
    classes = states()
    if len(rows) > 256 or len(classes) > 32:
        raise RuntimeError("divergence certificate state budget exceeded")
    matrices: list[Matrix] = [[{} for _ in rows] for _ in classes]
    starts = {0, *(row[6] for row in rows if row[6] >= 0)}
    matrices[classes.index(EMPTY)] = [
        {state: SCALE} if state in starts else {} for state in range(len(rows))
    ]
    started = monotonic()
    for _ in range(1500):
        image = matrix_image(rows, classes, matrices, SCALE, BOUND)
        if image == matrices:
            return rows, classes, matrices
        if any(
            value > 100 * SCALE
            for matrix in image
            for row in matrix
            for value in row.values()
        ):
            raise RuntimeError("divergence certificate value budget exceeded")
        if monotonic() - started > 120:
            raise RuntimeError("divergence certificate time budget exceeded")
        matrices = image
    raise RuntimeError("divergence certificate iteration budget exceeded")


if __name__ == "__main__":
    import argparse
    import json
    from pathlib import Path

    from scripts.divergence_certificate import check_certificate

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--export", type=Path)
    args = parser.parse_args()
    rows, classes, matrices = certificate()
    check_certificate(rows, classes, matrices, SCALE, BOUND)
    if args.export:
        args.export.write_text(
            json.dumps(
                {
                    "rows": rows,
                    "classes": classes,
                    "matrices": matrices,
                    "scale": SCALE,
                    "bound": BOUND,
                    "factors": sorted(patterns()),
                }
            )
        )
    constant = sum(sum(matrix[0].values()) for matrix in matrices)
    print(f"exact nonzero-tail upper certificate {BOUND}: K={constant}/{SCALE}")
