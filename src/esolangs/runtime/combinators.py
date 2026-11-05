"""Combinator terms, parenthesized parsing and persistent argument spines."""

from esolangs.runtime.source_hints import syntax_error

#: A symbol, or a function applied to an argument.
type Term = str | tuple[Term, Term]
#: Arguments in application order; the first argument is on top.
type Args = tuple[Term, Args] | None
#: The head symbol and its arguments.
type State = tuple[str, Args]


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


def unwind(term: Term, args: Args) -> State:
    """Return ``term`` applied to ``args`` as a head and its arguments."""
    while not isinstance(term, str):
        term, args = term[0], (term[1], args)
    return term, args


def count(args: Args, limit: int) -> int:
    """Return the argument count, stopping at ``limit``."""
    depth = 0
    while args is not None and depth < limit:
        depth, args = depth + 1, args[1]
    return depth


def stack(state: State) -> list[object]:
    """Return the head followed by its arguments in application order."""
    cells: list[object] = [state[0]]
    args = state[1]
    while args is not None:
        cells.append(args[0])
        args = args[1]
    return cells
