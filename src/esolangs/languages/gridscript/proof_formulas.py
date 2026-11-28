"""GridScript's arity-dependent tree workspace terms."""

from esolangs.languages.gridscript.generator import _height_name


def workspace_terms(n: int, _: str) -> dict[str, int]:
    """Count the wide tree's one-bit inputs with their variable names."""
    return {"V": sum(8 * len(_height_name(height)) + 1 for height in range(1, n + 1))}
