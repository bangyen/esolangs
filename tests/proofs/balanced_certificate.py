"""Check an integer supersolution for balanced words with no sole-loop bodies."""

import argparse
import json
from pathlib import Path

from tests.proofs.grammar_certificate import check_grammar

type Matrix = list[dict[int, int]]


def _sum(left: Matrix, right: Matrix) -> Matrix:
    result = [dict(row) for row in left]
    for row, other in zip(result, right, strict=True):
        for end, value in other.items():
            row[end] = row.get(end, 0) + value
    return result


def _product(left: Matrix, right: Matrix) -> Matrix:
    result: Matrix = []
    for row in left:
        image: dict[int, int] = {}
        for middle, value in row.items():
            for end, other in right[middle].items():
                image[end] = image.get(end, 0) + value * other
        result.append(image)
    return result


def _scale(matrix: Matrix, multiplier: int) -> Matrix:
    return [{end: value * multiplier for end, value in row.items()} for row in matrix]


def check_certificate(
    rows: list[list[int]],
    nonempty: Matrix,
    bodies: Matrix,
    scale: int,
    bound: tuple[int, int],
    *,
    nonprint: Matrix | None = None,
) -> None:
    """Check the sole-loop supersolution, optionally excluding print rotation."""
    size = len(rows)
    numerator, denominator = bound
    if not size or not isinstance(scale, int) or scale <= 0:
        raise ValueError("invalid certificate scale or size")
    if (
        not all(isinstance(value, int) for value in bound)
        or not numerator > denominator > 0
    ):
        raise ValueError("invalid certificate bound")
    if any(
        len(row) != 8
        or any(not isinstance(target, int) or not -1 <= target < size for target in row)
        for row in rows
    ):
        raise ValueError("invalid DFA transition")
    matrices = [nonempty, bodies] + ([nonprint] if nonprint is not None else [])
    for matrix in matrices:
        if len(matrix) != size or any(
            not isinstance(end, int)
            or not 0 <= end < size
            or not isinstance(value, int)
            or value < 0
            for row in matrix
            for end, value in row.items()
        ):
            raise ValueError("invalid matrix entry")
    identity = [{state: scale} for state in range(size)]
    literals: Matrix = []
    other_literals: Matrix = []
    for row in rows:
        counts: dict[int, int] = {}
        other: dict[int, int] = {}
        for column, target in enumerate(row[:6]):
            if target >= 0:
                counts[target] = counts.get(target, 0) + 1
                if column:
                    other[target] = other.get(target, 0) + 1
        literals.append(counts)
        other_literals.append(other)
    opening = [{row[6]: 1} if row[6] >= 0 else {} for row in rows]
    closing = [{row[7]: 1} if row[7] >= 0 else {} for row in rows]
    loops = _product(_product(opening, bodies), closing)
    sequences = _sum(identity, nonempty)
    atoms = _product(literals, sequences)
    order = numerator if nonprint is not None else 1
    common = _scale(_product(loops, nonempty), denominator**2 * order)
    tails = _scale(loops, denominator**2 * order * scale)
    body_atoms = atoms
    if nonprint is not None:
        printing = [{row[0]: 1} if row[0] >= 0 else {} for row in rows]
        print_loops = _product(
            _product(_product(opening, printing), sequences), closing
        )
        common = _sum(common, _scale(_product(print_loops, nonprint), denominator**3))
        tails = _sum(tails, _scale(print_loops, denominator**3 * scale))
        body_atoms = _product(other_literals, sequences)
    atom_scale = numerator * denominator * order * scale
    sequence_image = _sum(_sum(common, _scale(atoms, atom_scale)), tails)
    body_common = _sum(common, _scale(body_atoms, atom_scale))
    body_image = _sum(body_common, _scale(identity, numerator**2 * order * scale))
    images = [("sequence", sequence_image, nonempty), ("body", body_image, bodies)]
    if nonprint is not None:
        images.append(("nonprint", _sum(body_common, tails), nonprint))
    divisor = numerator**2 * order * scale
    for name, image, matrix in images:
        if any(
            value > divisor * matrix[state].get(end, 0)
            for state, row in enumerate(image)
            for end, value in row.items()
        ):
            raise ValueError(f"{name} supersolution inequality failed")


def main() -> None:
    """Check the algebraic inequalities and the exported forbidden factors."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("certificate", type=Path)
    args = parser.parse_args()
    data = json.loads(args.certificate.read_text())
    matrices = [
        [{int(end): value for end, value in row.items()} for row in data[key]]
        for key in ("nonempty", "bodies")
    ]
    check_certificate(
        data["rows"],
        matrices[0],
        matrices[1],
        data["scale"],
        tuple(data["bound"]),
        nonprint=(
            [
                {int(end): value for end, value in row.items()}
                for row in data["nonprint"]
            ]
            if "nonprint" in data
            else None
        ),
    )
    pairs = check_grammar(data["rows"], ".,-+<>[]", data["factors"], [])
    print(
        f"exact balanced supersolution {data['bound']}; "
        f"grammar verified at {pairs} pairs"
    )


if __name__ == "__main__":
    main()
