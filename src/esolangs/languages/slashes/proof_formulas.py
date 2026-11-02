"""Written string peaks, including expanded sweep macros."""


def workspace(n: int, program: str) -> int:
    """Return the exact all-row written peak for a generated template."""
    from esolangs.languages.slashes.generator import (
        _DECODE,
        _IGNORE,
        _SWEEP,
        _SWEEP_DEF,
        _UNARY,
    )

    prefix, delimiter, data = program.partition(_DECODE)
    if not delimiter:
        return 16 * n + 32
    slots, _, table = data.partition(">")
    size = len(table) // 2
    m = size.bit_length() - 1
    ignored = slots.count("X")
    preamble = len(_IGNORE) if ignored else 0
    body = prefix[preamble + len(_UNARY) :]
    macro = body.startswith(_SWEEP_DEF)
    count = len(body) - len(_SWEEP_DEF) if macro else len(body) // len(_SWEEP)
    # Source, pattern and replacement peaks are counted separately. The
    # last row reaches the longest unary string and every macro expansion.
    growth = max(
        0,
        size - 15 - preamble - 2 * ignored,
        size - 1 - m - preamble - 2 * ignored + 17 * count - 48 if macro else 0,
    )
    return 8 * (len(program) + growth) + 32 + (144 if macro else 24)
