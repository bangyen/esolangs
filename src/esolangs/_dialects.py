"""Explicit specification choices shared by interpreters and generators."""

from dataclasses import dataclass

EXPRESSION_SYNTAXES = ("infix", "postfix")
LITERAL_POLICIES = ("decimal", "binary_digits")


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
