"""Check the measured local answer patterns for the 17-input packing experiment."""

from itertools import product
from pathlib import Path

# Each group shares a marker. A primary input's low two bits select its printer.
GROUPS = (
    (5133, 5134),
    (21516, 21517, 21518),
    (45089, 45113),
    (103436, 103437, 103438),
    (127032, 127033, 127034),
)


def group_choices(group: tuple[int, ...]) -> list[tuple[int, ...]]:
    """Give the eight physical pattern masks for each requested answer pattern."""
    inversions = [
        sum(((polarity >> (row % 4)) & 1) << i for i, row in enumerate(group))
        for polarity in range(8)
    ]
    return [
        tuple(1 << (requested ^ flip) for flip in inversions)
        for requested in range(1 << len(group))
    ]


def main() -> None:
    """Exhaust the requested answers on the five coupled columns."""
    lines = Path(__file__).with_name("selector-masks.txt").read_text().splitlines()
    masks = [tuple(int(word, 16) for word in line.split()) for line in lines]
    choices = [group_choices(group) for group in GROUPS]

    covered = 0
    for answers in product(*choices):
        if any(
            all(
                mask & column[flips]
                for mask, column in zip(lookup, answers, strict=True)
            )
            for lookup in masks
            for flips in range(8)
        ):
            covered += 1

    total = 1 << sum(map(len, GROUPS))
    print(f"{covered:,} of {total:,} selector assignments covered")
    if covered != total:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
