"""Executed-word and snapshot-bit bounds for the shared store loop."""

from esolangs.generation.decision import residual_count_bound


def node_cap(n: int) -> int:
    """The most distinct residuals, including constants at each input depth."""
    return residual_count_bound(n) + (1 << min(1, n))


def execution(n: int, program: str) -> int:
    """Startup, 23 words per stored triple, then one n-level dispatch path."""
    extra = 2 * program.split().count("%%Concatenate")
    if "%%Store" not in program:
        return n + 2 + extra
    # D <= N+1 includes [], and C chains save seven words versus branches.
    # Exact path: 40+15n+26D-7C; the full-diagram witness has C=0.
    return 26 * node_cap(n) + 15 * n + 66 + extra


def workspace(n: int, program: str) -> int:
    """Exact component peaks; cuts alter the raw frame, not assembled payloads."""
    raw = program.split()
    if "%%Store" not in program:
        return (
            8 * sum(map(len, raw))
            + 8 * (n + 1)
            + (n + 1).bit_length()
            + 1
            + n.bit_length()
        )
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
    a, b, k = sum(names), sum(bodies), max(names)
    # Stack: dummy, all triples and helper. Globals: every definition plus
    # helper, dummy and error name. Local d holds the longest key. Raw words
    # dominate frame peaks, including every literal/Concatenate introduced by cuts.
    return (
        8 * (sum(map(len, raw)) + 26 + 2 * b + 3 * a + 2 * helper + k)
        + 10
        + (len(raw) - 1).bit_length()
        + n.bit_length()
    )
