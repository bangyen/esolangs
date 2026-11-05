"""Left-associated combinator terms with parenthesized grouping."""

from esolangs.runtime.source_hints import syntax_error

#: A symbol, or a function applied to an argument.
type Term = str | tuple[Term, Term]


def parse(code: str, symbols: str, language: str, hint: str) -> Term:
    """Return the one expression ``code`` spells, left-associated."""
    groups: list[list[Term]] = [[]]
    for char in code:
        if char.isspace():
            continue
        if char == "(":
            groups.append([])
        elif char == ")":
            if len(groups) == 1:
                raise syntax_error(
                    f"a {language} ')' has no matching '('", "balance the parentheses"
                )
            items = groups.pop()
            if not items:
                raise syntax_error(
                    f"{language} parentheses must enclose an expression",
                    "remove the empty () or put a combinator inside",
                )
            groups[-1].append(_applied(items))
        elif char in symbols:
            groups[-1].append(char)
        else:
            raise syntax_error(
                f"{char!r} is not a {language} combinator",
                hint,
            )
    if len(groups) > 1:
        raise syntax_error(
            f"a {language} '(' has no matching ')'", "balance the parentheses"
        )
    if not groups[0]:
        raise syntax_error(
            f"a {language} program needs at least one combinator",
            "write at least one combinator, for example K",
        )
    return _applied(groups[0])


def _applied(items: list[Term]) -> Term:
    """Return ``items`` applied left to right."""
    term = items[0]
    for item in items[1:]:
        term = (term, item)
    return term
