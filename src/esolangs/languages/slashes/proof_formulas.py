"""Written string peaks, including expanded sweep macros."""


def workspace_terms(_: int, program: str) -> dict[str, int]:
    """Measure the decoder, ignored input preamble and sweep layout."""
    from esolangs.languages.slashes.generator import (
        _DECODE,
        _IGNORE,
        _SWEEP,
        _SWEEP_DEF,
        _UNARY,
    )

    prefix, delimiter, data = program.partition(_DECODE)
    if not delimiter:
        return {"D": 0, "S": 0, "P": 0, "X": 0, "M": 0, "K": 0}
    slots, _separator, table = data.partition(">")
    size = len(table) // 2
    ignored = slots.count("X")
    preamble = len(_IGNORE) if ignored else 0
    body = prefix[preamble + len(_UNARY) :]
    macro = body.startswith(_SWEEP_DEF)
    count = len(body) - len(_SWEEP_DEF) if macro else len(body) // len(_SWEEP)
    return {"D": 1, "S": size, "P": preamble, "X": ignored, "M": int(macro), "K": count}
