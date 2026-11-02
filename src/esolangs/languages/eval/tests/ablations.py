"""Independent Eval lookup with restoring reversals as the ablation."""

from typing import Literal

from esolangs.generation.helpers import essential_inputs, permute_truth_table, read_at


def ablate(truth: str, rule: Literal["default", "orientation_carry"]) -> str:
    """Return a Gray-carried or restoring lookup with its proved stack cutoff."""
    n = len(truth).bit_length() - 1
    if len(set(truth)) == 1:
        return "$" * n + ("0" if truth[0] == "0" else "`") + "."
    table = permute_truth_table(truth, tuple(reversed(range(n))))
    used = essential_inputs(table, n)
    reduced = read_at(table, used, n)
    carry = rule == "default"
    dual = n >= 4 and 0 in used and len(reduced) >= 8 * n + (4 if carry else -20)

    def layout(bits: str) -> str:
        return "".join(bits[i ^ (i >> 1)] for i in range(len(bits))) if carry else bits

    if dual:
        half = len(reduced) // 2
        low, high = layout(reduced[:half]), layout(reduced[half:])
        out = ["".join("`" if b == "1" else "0" for b in low), "~"]
        previous = "0"
        for bit in high:
            out.append("0" if bit == "0" else "^" if previous == "1" else "0+")
            previous = bit
        out.extend(("~", "$" * (3 * n), "~;~?~", ";" * (n - 1)))
        start, remaining = 1, half
    else:
        out = [
            "$" * (2 * n),
            "".join("`" if b == "1" else "0" for b in layout(reduced)),
        ]
        start, remaining = 0, len(reduced)
    for level in range(start, n):
        if level not in used:
            out.append("~;~")
        else:
            remaining //= 2
            out.extend(("~=~?*" if carry else "~^=~?*", ";" * remaining))
            if not carry:
                out.append("~=~?*")
    return "".join(out) + "."
