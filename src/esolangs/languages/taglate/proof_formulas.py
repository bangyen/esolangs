"""Literal-seed command/workspace maxima and bootstrap-layout ceilings."""

from esolangs.languages.taglate.interpreter import _tokens


def _literal(n: int) -> tuple[int, int]:
    """Static tokens and peak queue bits before normalization."""
    if n == 1:
        return 10, 34
    # Tokenize each gy/gz as one command.
    tokens = 5 * (1 << n) // 2 + 12 * n * n + 7 * n + 13
    # Seed ghosts/leaf pairs plus six bits for each physical input read.
    queue = 7 * (1 << n) // 4 + 17 * n + 20
    return tokens, queue


def _bootstrap(program: str) -> tuple[int, int] | None:
    """Setup and total tokens for an empty-seed rebuild, otherwise no setup."""
    if not program or program.partition("\n")[0]:
        return None
    tokens = _tokens("".join(program.partition("\n")[2].splitlines()))
    return tokens.index("h"), len(tokens)


def execution_terms(_: int, program: str) -> dict[str, int]:
    """Count the commands before the bootstrap halt marker."""
    setup = _bootstrap(program)
    return {"B": setup[0] if setup else 0}


def workspace(n: int, program: str) -> int:
    """Queue, token cursor and input peaks; URL rebuilding uses seven-bit cells."""
    tokens, queue = _literal(n)
    setup = _bootstrap(program)
    if setup:
        before, tokens = setup
        # The final URL's selector has M e/f commands, so M<=before.
        # The optional affine -1 rebuild peaks at 28 bits before input.
        queue = max(queue, 7 * before, 28)
    return queue + tokens.bit_length() + n.bit_length()
