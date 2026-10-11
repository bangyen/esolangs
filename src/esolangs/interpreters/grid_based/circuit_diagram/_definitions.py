"""Circuit Diagram function-definition parsing."""

import re
from collections.abc import Collection

from esolangs.interpreters.grid_based.circuit_diagram._hints import Hint
from esolangs.interpreters.source_hints import syntax_error

_DEFINITION_HEADER = re.compile(r"\s*\{([A-Za-z]+|[<>%])\s*")


def split_definitions(
    code: list[str], reserved: Collection[str], ignored: Collection[str]
) -> tuple[list[str], dict[str, tuple[str, ...]]]:
    """Return the main grid and the named function bodies declared around it."""
    main: list[str] = []
    definitions: dict[str, tuple[str, ...]] = {}
    position = 0
    while position < len(code):
        line = code[position].rstrip("\n")
        header = _DEFINITION_HEADER.fullmatch(line)
        if header is None:
            if line.strip() == "}":
                raise syntax_error(
                    f"unmatched function terminator at line {position + 1}",
                    Hint.FUNCTION_HEADER,
                )
            main.append(code[position])
            position += 1
            continue
        name = header.group(1)
        body: list[str] = []
        position += 1
        while position < len(code) and code[position].strip() != "}":
            body.append(code[position])
            position += 1
        if position == len(code):
            raise syntax_error(
                f"unterminated function {name!r}",
                Hint.FUNCTION_END,
            )
        if name in definitions:
            raise syntax_error(f"duplicate function {name!r}", Hint.FUNCTION_NAME)
        if name in reserved:
            raise syntax_error(
                f"function name {name!r} is reserved",
                Hint.RESERVED_NAME,
            )
        if name not in ignored:
            definitions[name] = tuple(body)
        position += 1
    return main, definitions
