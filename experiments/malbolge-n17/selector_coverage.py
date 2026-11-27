"""Check the measured local answer patterns for the 17-input packing experiment."""

from functools import reduce
from itertools import product
from operator import and_
from pathlib import Path

# Each group shares a marker. The two spill inputs use slots 2 and 1.
GROUPS = (
    (7180, 7181, 7182),
    (7183, 39951),
    (45112, 45113, 45114),
    (63584, 63585, 63586, 82016, 82017, 82018),
    (127032, 127033, 127034),
)
SPILL_SLOTS = {7183: 2, 39951: 1}


def group_choices(group: tuple[int, ...], masks: tuple[int, ...]) -> list[int]:
    """For each requested pattern, mark every compatible lookup and polarity."""
    choices = [0] * (1 << len(group))
    for polarity in range(8):
        flip = sum(
            ((polarity >> SPILL_SLOTS.get(row, row % 4)) & 1) << i
            for i, row in enumerate(group)
        )
        for lookup, mask in enumerate(masks):
            setting = 1 << (8 * lookup + polarity)
            for requested in range(len(choices)):
                if mask & (1 << (requested ^ flip)):
                    choices[requested] |= setting
    return choices


def main() -> None:
    """Count assignments that admit the same setting in all five columns."""
    lines = Path(__file__).with_name("selector-masks.txt").read_text().splitlines()
    masks = [tuple(int(word, 16) for word in line.split()) for line in lines]
    choices = [
        group_choices(group, column)
        for group, column in zip(GROUPS, zip(*masks, strict=True), strict=True)
    ]
    covered = sum(bool(reduce(and_, assignment)) for assignment in product(*choices))
    total = 1 << sum(map(len, GROUPS))
    print(f"{covered:,} of {total:,} selector assignments covered")
    if covered != total:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
