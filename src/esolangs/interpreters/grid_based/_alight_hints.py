"""Repair guidance for alight source errors."""

from enum import StrEnum

from esolangs.interpreters.source_hints import syntax_error


class Hint(StrEnum):
    """Accepted grammar at each rejected source boundary."""

    SCANNED_LITERAL = (
        "close double-quoted strings and follow each single quote "
        "with its literal character"
    )
    OPERAND = "provide an operand after the operator"
    CHARACTER_LITERAL = "follow ' with one character, for example 'A"
    STRING_LITERAL = "close the string with a double quote"
    OPERAND_KIND = (
        "use a number, variable, quoted literal, list or function call as the operand"
    )
    NUMBER = "write a decimal number with at most one decimal point, for example 1.5"
    ARGUMENTS = (
        "separate list elements or call arguments with commas and "
        "close the list or call"
    )
    PROGRAM = "provide a grid containing begin"
    ENTRY = "put a begin command at the entry point"
    EXPRESSION = "keep one complete expression after the command"
    COMMAND = "start the command with a keyword or a function name"
    ASSIGNMENT = "write set <variable> <expression> with no trailing operands"
    VARIABLE_OPERANDS = "give var, inp or out exactly one variable name"
    VARIABLE_NAME = "use an alphanumeric name that is not a reserved keyword"
    RETURN_VALUE = "give end at most one complete return expression"

    def error(self, message: str) -> ValueError:
        """Attach this grammar hint to the rejected source diagnostic."""
        return syntax_error(message, self)
