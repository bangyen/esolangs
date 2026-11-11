"""Execution facts from emitted source."""


def execution_terms(n: int, program: str) -> dict[str, int]:
    """Identify the constant ring and its last reflection."""
    constant = program.startswith(" }}" + "," * n + "}-#/)")
    return {"C": int(constant), "X": int(program.partition("\n")[0].endswith("+x"))}
