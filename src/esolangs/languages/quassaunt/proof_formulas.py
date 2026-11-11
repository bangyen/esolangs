"""Executed-word and snapshot-bit bounds for the shared store loop."""

from esolangs.generation.decision import residual_count_bound


def node_cap(n: int) -> int:
    """The most distinct residuals, including constants at each input depth."""
    return residual_count_bound(n) + (1 << min(1, n))


def execution_terms(_: int, program: str) -> dict[str, int]:
    """Mark the shared-store route and count concatenations."""
    return {"C": int("%%Store" in program), "Q": program.split().count("%%Concatenate")}


def workspace_terms(n: int, program: str) -> dict[str, int]:
    """Measure raw frame words and reconstruct store keys and bodies."""
    raw = program.split()
    chars = sum(map(len, raw))
    if "%%Store" not in program:
        return {"C": 0, "R": chars, "W": len(raw), "B": 0, "A": 0, "H": 0, "K": 0}
    words: list[str] = []
    for word in raw:
        if word == "%%Concatenate":
            right, left = words.pop(), words.pop()
            words.append(left + right[2:])
        else:
            words.append(word)
    # Five helper-store words, 2n fillers, three dummy words, then triples
    # and the seven-word initial call. Cuts reconstruct this same layout.
    helper = len(words[1]) - 2
    triples = words[8 + 2 * n : -7]
    names = [len(triples[i]) - 2 for i in range(0, len(triples), 3)]
    bodies = [len(triples[i]) - 2 for i in range(1, len(triples), 3)]
    return {
        "C": 1,
        "R": chars,
        "W": len(raw),
        "B": sum(bodies),
        "A": sum(names),
        "H": helper,
        "K": max(names),
    }
