"""Executed command and snapshot-bit bounds."""


def execution_terms(_: int, program: str) -> dict[str, int]:
    """Identify the direct constant program."""
    return {"C": int(program.startswith("Package : IO {\n  Char c;\n"))}
