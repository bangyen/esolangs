"""Normal forms for total, single-output Factor truth-table programs."""

ALPHABET = "><+-.,[]"
FORBIDDEN = frozenset({"+-", "-+", "><", "[]", "..", "+,", "-,"})


def normalize(code: str) -> str:
    """Preserve balanced code on inputs where it halts with exactly one output."""
    stack: list[str] = []
    for char in code:
        while stack and stack[-1] + char in FORBIDDEN:
            previous = stack.pop()
            if char == "," and previous in "+-":
                continue
            break
        else:
            stack.append(char)
    return "".join(stack)


def growth() -> float:
    """Return the Perron root of x^3 - 7x^2 - x + 2, bracketed in (7.10,7.11)."""
    lower, upper = 7.10, 7.11
    for _ in range(60):
        middle = (lower + upper) / 2
        if middle**3 - 7 * middle**2 - middle + 2 < 0:
            lower = middle
        else:
            upper = middle
    return (lower + upper) / 2
