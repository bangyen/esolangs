"""Grapheme's integer conversion and uninitialized-variable choices."""

from dataclasses import dataclass

from esolangs._dialects import UNSET_POLICIES

INTEGER_CONVERSIONS = ("between_letters", "after_each_letter")


@dataclass(frozen=True)
class GraphemeDialect:
    unset_variables: str = "error"
    integer_conversion: str = "between_letters"

    def __post_init__(self) -> None:
        if self.unset_variables not in UNSET_POLICIES:
            raise ValueError("unset_variables must be error or zero")
        if self.integer_conversion not in INTEGER_CONVERSIONS:
            raise ValueError(
                "integer_conversion must be between_letters or after_each_letter"
            )

    def finish_integer(self, value: int) -> int:
        return value * 10 if self.integer_conversion == "after_each_letter" else value


DEFAULT_GRAPHEME = GraphemeDialect()
