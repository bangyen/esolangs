"""Check an integer supersolution for balanced words with no sole-loop bodies."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from grammar_certificate import check_grammar

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
) -> None:
    """Check N >= A(I+N)+L(I+N), B >= I+A(I+N)+LN exactly."""
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
    for matrix in (nonempty, bodies):
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
    for row in rows:
        counts: dict[int, int] = {}
        for target in row[:6]:
            if target >= 0:
                counts[target] = counts.get(target, 0) + 1
        literals.append(counts)
    opening = [{row[6]: 1} if row[6] >= 0 else {} for row in rows]
    closing = [{row[7]: 1} if row[7] >= 0 else {} for row in rows]
    loops = _product(_product(opening, bodies), closing)
    atoms = _product(literals, _sum(identity, nonempty))
    common = _sum(
        _scale(atoms, numerator * denominator * scale),
        _scale(_product(loops, nonempty), denominator**2),
    )
    sequence_image = _sum(common, _scale(loops, denominator**2 * scale))
    body_image = _sum(common, _scale(identity, numerator**2 * scale))
    divisor = numerator**2 * scale
    for name, image, matrix in (
        ("sequence", sequence_image, nonempty),
        ("body", body_image, bodies),
    ):
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
        data["rows"], matrices[0], matrices[1], data["scale"], tuple(data["bound"])
    )
    pairs = check_grammar(data["rows"], ".,-+<>[]", data["factors"], [])
    print(
        f"exact balanced supersolution {data['bound']}; "
        f"grammar verified at {pairs} pairs"
    )


if __name__ == "__main__":
    main()
