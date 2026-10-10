"""Packlang's literal-policy dialect."""

from dataclasses import dataclass

LITERAL_POLICIES = ("decimal", "binary_digits")


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
