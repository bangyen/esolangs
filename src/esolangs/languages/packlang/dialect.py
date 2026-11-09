"""Packlang's literal-policy dialect."""

from dataclasses import dataclass

from esolangs.runtime.memory import parse_integer

LITERAL_POLICIES = ("decimal", "binary_digits")


@dataclass(frozen=True)
class PacklangLiterals:
    """Parse and emit literals under one declared policy."""

    policy: str = "decimal"

    def __post_init__(self) -> None:
        """Reject undeclared literal policies."""
        if self.policy not in LITERAL_POLICIES:
            raise ValueError("literal_policy must be decimal or binary_digits")

    def parse(self, text: str) -> int:
        """Return the literal value under this policy."""
        if self.policy == "binary_digits" and set(text) <= {"0", "1"}:
            return int(text, 2)
        return parse_integer(text)

    def emit(self, value: int) -> str:
        """Return a literal spelling under this policy."""
        return format(value, "b") if self.policy == "binary_digits" else str(value)
