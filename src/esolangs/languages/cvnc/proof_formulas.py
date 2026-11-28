"""Source terms for CV(N)(C) workspace."""

from esolangs.languages.cvnc.interpreter import _prepare_source


def workspace_terms(_n: int, program: str) -> dict[str, int]:
    """Count commands and syllables, and identify the constant reader."""
    image = _prepare_source(program)
    return {
        "K": len(image.tokens),
        "S": len(image.starts),
        "C": int(image.tokens[0] == "s"),
    }
