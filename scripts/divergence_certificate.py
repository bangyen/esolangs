"""Check a read-free nonzero-tail matrix supersolution with exact integers."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from balanced_certificate import Matrix, _product, _scale, _sum
from grammar_certificate import check_grammar

type State = tuple[bool, int, int, int]


def _next(state: State, column: int) -> State | None:
    read, suffix, first, count = state
    if column == 0:
        if suffix == 2:
            return None
    elif column in (2, 3):
        suffix = 3 if suffix in (1, 2) else 0
    elif column >= 6:
        suffix = 1 + column % 2
    else:
        suffix = 0
    if count == 0:
        first = 1 if column == 0 else 2 if column >= 6 else 3
    return read or column == 1 or column >= 8, suffix, first, min(2, count + 1)


def _states() -> list[State]:
    reached: set[State] = {(False, 0, 0, 0)}
    while True:
        image = {
            target
            for state in reached
            for column in range(10)
            if (target := _next(state, column)) is not None
        }
        if image <= reached:
            return sorted(reached)
        reached |= image


def check_certificate(
    rows: list[list[int]],
    classes: list[State],
    matrices: list[Matrix],
    scale: int,
    bound: tuple[int, int],
) -> None:
    """Verify the forward atom equations, independently of grouped construction."""
    size = len(rows)
    if not size or type(scale) is not int or scale <= 0:
        raise ValueError("invalid certificate scale or size")
    if len(bound) != 2 or any(type(value) is not int for value in bound):
        raise ValueError("invalid certificate bound")
    numerator, denominator = bound
    if not numerator > denominator > 0:
        raise ValueError("invalid certificate bound")
    if any(
        len(row) != 8
        or any(type(target) is not int or not -1 <= target < size for target in row)
        for row in rows
    ):
        raise ValueError("invalid DFA transition")
    if classes != _states() or len(matrices) != len(classes):
        raise ValueError("invalid atom classes")
    for matrix in matrices:
        if len(matrix) != size or any(
            type(end) is not int
            or not 0 <= end < size
            or type(value) is not int
            or value < 0
            for row in matrix
            for end, value in row.items()
        ):
            raise ValueError("invalid matrix entry")
    zero: Matrix = [{} for _ in rows]
    bodies = [[dict(row) for row in zero] for _ in range(4)]
    for (read, suffix, first, count), matrix in zip(classes, matrices, strict=True):
        if (first, count) == (2, 1) or (not read and suffix == 3):
            continue
        kind = 2 * read + (first == 1)
        bodies[kind] = _sum(bodies[kind], matrix)
    transitions = [
        [{row[column]: 1} if row[column] >= 0 else {} for row in rows]
        for column in range(8)
    ]
    loops = [
        _product(_product(transitions[6], body), transitions[7]) for body in bodies
    ]
    atoms = transitions[:6] + loops
    image = [[dict(row) for row in zero] for _ in classes]
    index = {state: position for position, state in enumerate(classes)}
    for state, prefix in zip(classes, matrices, strict=True):
        for column, atom in enumerate(atoms):
            target = _next(state, column)
            if target is None:
                continue
            multiplier = (
                numerator * denominator * scale if column < 6 else denominator**2
            )
            position = index[target]
            image[position] = _sum(
                image[position], _scale(_product(prefix, atom), multiplier)
            )
    starts = {0, *(row[6] for row in rows if row[6] >= 0)}
    identity = [
        {state: numerator**2 * scale**2} if state in starts else {}
        for state in range(size)
    ]
    image[index[False, 0, 0, 0]] = _sum(image[index[False, 0, 0, 0]], identity)
    divisor = numerator**2 * scale
    for state, polynomial, candidate in zip(classes, image, matrices, strict=True):
        if any(
            value > divisor * candidate[start].get(end, 0)
            for start, row in enumerate(polynomial)
            for end, value in row.items()
        ):
            raise ValueError(f"atom {state} supersolution inequality failed")


def main() -> None:
    """Check the exported matrices and their factor-DFA language."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("certificate", type=Path)
    data = json.loads(parser.parse_args().certificate.read_text())
    classes = [tuple(state) for state in data["classes"]]
    matrices = [
        [{int(end): value for end, value in row.items()} for row in matrix]
        for matrix in data["matrices"]
    ]
    check_certificate(
        data["rows"], classes, matrices, data["scale"], tuple(data["bound"])
    )
    pairs = check_grammar(data["rows"], ".,-+<>[]", data["factors"], [])
    print(
        f"exact nonzero-tail supersolution {data['bound']}; "
        f"grammar verified at {pairs} pairs"
    )


if __name__ == "__main__":
    main()
