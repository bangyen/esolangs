"""Jaune tape, exhausted-input and unresolved-target choices."""

from dataclasses import dataclass

from esolangs._brainfuck import BrainfuckDialect

UNDEFINED_TARGETS = ("error", "halt", "ignore")


@dataclass(frozen=True)
class JauneDialect(BrainfuckDialect):
    cell_modulus: int | None = None
    undefined_targets: str = "error"

    def __post_init__(self) -> None:
        super().__post_init__()
        if self.undefined_targets not in UNDEFINED_TARGETS:
            raise ValueError("undefined_targets must be error, halt or ignore")


DEFAULT_JAUNE = JauneDialect()
