"""Check an exported DFA spectral bound with integer arithmetic only."""

import argparse
import json
from pathlib import Path


def check_certificate(
    rows: list[list[int]], vector: list[int], bound: tuple[int, int], alphabet: str
) -> None:
    """Reject malformed data or a violated positive-vector upper bound."""
    numerator, denominator = bound
    if (
        not alphabet
        or len(set(alphabet)) != len(alphabet)
        or type(numerator) is not int
        or type(denominator) is not int
        or numerator <= 0
        or denominator <= 0
        or not rows
        or len(rows) != len(vector)
        or any(type(value) is not int or value <= 0 for value in vector)
    ):
        raise ValueError("invalid certificate dimensions, bound or vector")
    for index, (row, value) in enumerate(zip(rows, vector, strict=True)):
        if len(row) != len(alphabet) or any(
            type(target) is not int or not -1 <= target < len(rows) for target in row
        ):
            raise ValueError(f"invalid transition row {index}")
        image = sum(vector[target] for target in row if target >= 0)
        if denominator * image > numerator * value:
            raise ValueError(f"spectral inequality fails at row {index}")


def main() -> None:
    """Validate JSON without importing the DFA builder or numerical solvers."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("certificate", type=Path)
    args = parser.parse_args()
    data = json.loads(args.certificate.read_text())
    try:
        check_certificate(
            data["rows"], data["vector"], tuple(data["bound"]), data["alphabet"]
        )
    except (ValueError, KeyError, TypeError) as error:
        parser.exit(1, f"{error}\n")
    print(f"{len(data['rows'])} states: {data['bound'][0]}/{data['bound'][1]} verified")


if __name__ == "__main__":
    main()
