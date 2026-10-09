"""Count balanced words with unrestricted nonzero-tail divergence removed."""

import sys
from collections import defaultdict
from collections.abc import Callable
from functools import lru_cache
from pathlib import Path
from time import monotonic

sys.path.insert(0, str(Path(__file__).resolve().parent))

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


def _construct[StateT](
    rows: list[list[int]],
    classes: list[StateT],
    scale: int,
    bound: tuple[int, int],
    update: Callable[
        [list[list[int]], list[StateT], list[Matrix], int, tuple[int, int]],
        list[Matrix],
    ],
    name: str,
    *,
    supersolution: bool = False,
) -> list[Matrix]:
    """Iterate a positive system under the shared value, time and update caps."""
    matrices: list[Matrix] = [[{} for _ in rows] for _ in classes]
    starts = {0, *(row[6] for row in rows if row[6] >= 0)}
    matrices[0] = [
        {state: scale} if state in starts else {} for state in range(len(rows))
    ]
    started = monotonic()
    for iteration in range(1500):
        image = update(rows, classes, matrices, scale, bound)
        if image == matrices:
            return matrices
        if supersolution and iteration % 20 == 19:
            # A small upward rounding may certify domination before exact
            # fixed-point iteration settles. The checker still evaluates F.
            candidate = [
                [
                    {end: (value * 10001 + 9999) // 10000 for end, value in row.items()}
                    for row in matrix
                ]
                for matrix in image
            ]
            if any(
                value > 100 * scale
                for matrix in candidate
                for row in matrix
                for value in row.values()
            ):
                matrices = image
                continue
            tested = update(rows, classes, candidate, scale, bound)
            if all(
                value <= upper.get(end, 0)
                for matrix, bounds in zip(tested, candidate, strict=True)
                for row, upper in zip(matrix, bounds, strict=True)
                for end, value in row.items()
            ):
                return candidate
        if any(
            value > 100 * scale
            for matrix in image
            for row in matrix
            for value in row.values()
        ):
            raise RuntimeError(f"{name} certificate value budget exceeded")
        if monotonic() - started > 120:
            raise RuntimeError(f"{name} certificate time budget exceeded")
        matrices = image
    raise RuntimeError(f"{name} certificate iteration budget exceeded")


@lru_cache(maxsize=1)
def certificate() -> tuple[list[list[int]], list[State], list[Matrix]]:
    """Rebuild the capped nonzero-tail supersolution; abort without relaxing it."""
    rows = minimize(automaton(patterns(), []))
    classes = states()
    if len(rows) > 256 or len(classes) > 32:
        raise RuntimeError("divergence certificate state budget exceeded")
    return (
        rows,
        classes,
        _construct(rows, classes, SCALE, BOUND, matrix_image, "divergence"),
    )


def _export[StateT](
    factory: Callable[[], tuple[list[list[int]], list[StateT], list[Matrix]]],
    check: Callable[
        [list[list[int]], list[StateT], list[Matrix], int, tuple[int, int]], None
    ],
    scale: int,
    bound: tuple[int, int],
    name: str,
) -> None:
    """Parse export arguments, rebuild and independently check a named certificate."""
    import argparse
    import json

    parser = argparse.ArgumentParser(
        description=f"Rebuild and check the {name} certificate."
    )
    parser.add_argument("--export", type=Path)
    args = parser.parse_args()
    rows, classes, matrices = factory()
    check(rows, classes, matrices, scale, bound)
    if args.export:
        args.export.write_text(
            json.dumps(
                {
                    "rows": rows,
                    "classes": classes,
                    "matrices": matrices,
                    "scale": scale,
                    "bound": bound,
                    "factors": sorted(patterns()),
                }
            )
        )
    constant = sum(sum(matrix[0].values()) for matrix in matrices)
    print(f"exact {name} upper certificate {bound}: K={constant}/{scale}")


if __name__ == "__main__":
    from divergence_certificate import check_certificate

    _export(certificate, check_certificate, SCALE, BOUND, "nonzero-tail")
