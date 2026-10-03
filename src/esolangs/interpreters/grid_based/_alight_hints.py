"""Repair guidance for alight source errors."""

from enum import StrEnum

from esolangs.exceptions import HaltError
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

    BOOLEAN_GUARD = "make the guard evaluate to true or false"
    OPERAND_TYPES = "use operand types supported by this operator"
    DIVISOR = "ensure the divisor is nonzero before dividing"
    REPEAT_COUNT = "use a nonnegative whole-number list repeat count"
    NUMERIC_INDEX = "use a numeric list index of the form 0.5 + k"
    INDEX_FORM = "use list indices 0.5, 1.5, 2.5 and so on"
    BUILTIN_LIST = "pass a list as the first argument"
    AT_ARGUMENTS = "pass a list as the first argument"
    INDEXED_WRITE = "use an index inside the list before replacing an element"
    ELEMENT_TYPE = "store a list element of the same type as the existing elements"
    GRID_PATH = "keep the execution path on the grid or terminate it with end"
    VARIABLE_REFERENCE = (
        "declare the variable before reading or assigning it; check its spelling"
    )
    CHARACTER_OUTPUT = "use a whole-number character code between 0 and 1114111"
    FUNCTION_REFERENCE = "define the function before calling it; check its spelling"
    CALL_ARITY = "pass the number of arguments declared by the function"
    BUILTIN_NUMBER = "pass exactly one numeric argument"
    LEN_ARGUMENTS = "pass a list as the first argument"
    PADDING_COUNT = "use a nonnegative whole-number padding count"
    VARIABLE_DECLARATION = (
        "choose a fresh variable name or assign to the existing variable"
    )

    def error(self, message: str) -> ValueError:
        """Attach this grammar hint to the rejected source diagnostic."""
        return syntax_error(message, self)

    def halt(self, message: str) -> HaltError:
        """Attach this operand hint to an invalid operation."""
        return HaltError(message, hint=self)
