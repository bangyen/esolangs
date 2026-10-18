"""Executed command bounds."""


def _program_commands(p: str) -> int:
    """Each ``?`` read, three per comparison, less each guard's final ``loop?``."""
    guards = sum(
        "::" in line and line.rstrip().endswith("loop?") for line in p.splitlines()
    )
    return p.count("?") - guards + 3 * (p.count("==") + p.count("!="))


def execution(_: int, p: str) -> int:
    """The stated execution bound, evaluated for n and the program."""
    return _program_commands(p)
