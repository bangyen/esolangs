"""Explicit specification choices shared by interpreters and generators."""

from dataclasses import dataclass

INDEX_BASES = (0, 1)
EXPRESSION_SYNTAXES = ("infix", "postfix")
LITERAL_POLICIES = ("decimal", "binary_digits")
UNSET_POLICIES = ("error", "zero")
UNKNOWN_POLICIES = ("ignore", "error")
TAPE_BOUNDARIES = ("error", "wrap", "clamp")
SCHEDULINGS = ("creation", "reverse")
DEQUE_CURSORS = ("pointer", "shared")


def index_base(value: int) -> int:
    """Validate zero- or one-based indexing."""
    if type(value) is not int or value not in INDEX_BASES:
        raise ValueError("index_base must be 0 or 1")
    return value


def expression_syntax(value: str) -> str:
    """Validate Alight expression notation."""
    if value not in EXPRESSION_SYNTAXES:
        raise ValueError("expression_syntax must be infix or postfix")
    return value


@dataclass(frozen=True)
class PacklangLiterals:
    policy: str = "decimal"

    def __post_init__(self) -> None:
        if self.policy not in LITERAL_POLICIES:
            raise ValueError("literal_policy must be decimal or binary_digits")

    def parse(self, text: str) -> int:
        return int(
            text,
            2 if self.policy == "binary_digits" and set(text) <= {"0", "1"} else 10,
        )

    def emit(self, value: int) -> str:
        return format(value, "b") if self.policy == "binary_digits" else str(value)


@dataclass(frozen=True)
class FalseDialect:
    pick_base: int = 0
    unset_variables: str = "error"
    unknown_commands: str = "ignore"

    def __post_init__(self) -> None:
        index_base(self.pick_base)
        if self.unset_variables not in UNSET_POLICIES:
            raise ValueError("unset_variables must be error or zero")
        if self.unknown_commands not in UNKNOWN_POLICIES:
            raise ValueError("unknown_commands must be ignore or error")


@dataclass(frozen=True)
class LineDialect:
    cell_modulus: int | None = None
    tape_size: int | None = None
    boundary: str = "error"

    def __post_init__(self) -> None:
        for name, value, minimum in (
            ("cell_modulus", self.cell_modulus, 2),
            ("tape_size", self.tape_size, 1),
        ):
            if value is not None and (type(value) is not int or value < minimum):
                raise ValueError(f"{name} must be at least {minimum}")
        if self.boundary not in TAPE_BOUNDARIES:
            raise ValueError("boundary must be error, wrap or clamp")
        if self.tape_size is None and self.boundary != "error":
            raise ValueError("wrap and clamp require tape_size")

    def cell(self, value: int) -> int:
        return value if self.cell_modulus is None else value % self.cell_modulus

    def pointer(self, value: int) -> int:
        if self.tape_size is None or 0 <= value < self.tape_size:
            return value
        if self.boundary == "wrap":
            return value % self.tape_size
        if self.boundary == "clamp":
            return min(max(value, 0), self.tape_size - 1)
        from esolangs.exceptions import HaltError

        raise HaltError("Line pointer left the finite tape")


@dataclass(frozen=True)
class FlowchartDialect:
    scheduling: str = "creation"
    deque_cursor: str = "pointer"

    def __post_init__(self) -> None:
        if self.scheduling not in SCHEDULINGS:
            raise ValueError("scheduling must be creation or reverse")
        if self.deque_cursor not in DEQUE_CURSORS:
            raise ValueError("deque_cursor must be pointer or shared")


DEFAULT_FALSE = FalseDialect()
DEFAULT_LINE = LineDialect()
