"""Normal forms for total, single-output Factor truth-table programs."""

ALPHABET = "><+-.,[]"
FORBIDDEN = frozenset({"+-", "-+", "><", "<>", "[]", "..", "+,", "-,"})


def normalize(code: str) -> str:
    """Preserve balanced code on inputs where it halts with exactly one output."""
    # Both singleton update loops clear a wrapping byte; brackets keep the
    # replaced command's run rank and exponent unchanged.
    code = code.replace("[+]", "[-]")
    stack: list[str] = []
    for char in code:
        while stack and stack[-1] + char in FORBIDDEN:
            previous = stack.pop()
            if char == "," and previous in "+-":
                continue
            break
        else:
            stack.append(char)
    return "".join(stack).replace("[+]", "[-]")


def growth() -> float:
    """Return the Perron root of x^3 - 7x^2 + 1, bracketed in (6.97,6.98)."""
    lower, upper = 6.97, 6.98
    for _ in range(60):
        middle = (lower + upper) / 2
        if middle**3 - 7 * middle**2 + 1 < 0:
            lower = middle
        else:
            upper = middle
    return (lower + upper) / 2


def prefix_normalize(code: str) -> str:
    """Preserve the first Boolean output; subsequent behavior may change."""

    def prune(word: str) -> str:
        def sequence(offset: int) -> tuple[str, int]:
            parts: list[str] = []
            active = True
            previous_loop = False
            while offset < len(word) and word[offset] != "]":
                char = word[offset]
                offset += 1
                if char == "[":
                    body, offset = sequence(offset)
                    if active and not previous_loop:
                        parts.append("[" + body + "]")
                    previous_loop = True
                elif active and char == ".":
                    if not previous_loop:
                        parts.append(char)
                        active = False
                elif active:
                    parts.append(char)
                    previous_loop = False
            return "".join(parts), offset + 1

        return sequence(0)[0]

    # Initially the original word is total and has exactly one output.
    word = normalize(code)
    while True:
        reduced = prune(word)
        # Pruning leaves no adjacent dots, so the single-output rewrite is safe.
        reduced = normalize(reduced)
        if reduced == word:
            return word
        word = reduced


def prefix_growth() -> float:
    """Return the clearing-loop normal form's Perron root in (5.94,5.95)."""
    lower, upper = 5.94, 5.95
    for _ in range(60):
        middle = (lower + upper) / 2
        if middle**4 - 5 * middle**3 - 5 * middle**2 - 4 * middle + 1 < 0:
            lower = middle
        else:
            upper = middle
    return (lower + upper) / 2
