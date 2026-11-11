"""Literal-seed command/workspace maxima and bootstrap-layout ceilings."""

from esolangs.languages.taglate.interpreter import _tokens


def _bootstrap(program: str) -> tuple[int, int] | None:
    """Setup and total tokens for an empty-seed rebuild, otherwise no setup."""
    if not program or program.partition("\n")[0]:
        return None
    tokens = _tokens("".join(program.partition("\n")[2].splitlines()))
    return tokens.index("h"), len(tokens)


def execution_terms(_: int, program: str) -> dict[str, int]:
    """Count the commands before the first bootstrap read."""
    setup = _bootstrap(program)
    return {"B": setup[0] if setup else 0}


def workspace_terms(_: int, program: str) -> dict[str, int]:
    """Extract the bootstrap route, setup prefix and token count."""
    setup = _bootstrap(program)
    before, tokens = setup if setup else (0, 0)
    return {"C": int(setup is not None), "B": before, "R": tokens}
