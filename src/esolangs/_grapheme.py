"""Grapheme's conflicting integer-conversion rules."""

from dataclasses import dataclass

INTEGER_CONVERSIONS = ("between_letters", "after_each_letter")


@dataclass(frozen=True)
class GraphemeDialect:
    integer_conversion: str = "between_letters"

    def __post_init__(self) -> None:
        if self.integer_conversion not in INTEGER_CONVERSIONS:
            raise ValueError(
                "integer_conversion must be between_letters or after_each_letter"
            )

    def finish_integer(self, value: int) -> int:
        return value * 10 if self.integer_conversion == "after_each_letter" else value


DEFAULT_GRAPHEME = GraphemeDialect()
