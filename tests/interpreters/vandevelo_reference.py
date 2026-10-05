"""Statement evaluator for the finite and direct-self-loop audit domain."""

import re


class LoopError(Exception):
    pass


def reference(source, values):
    store = {"Nil": False}
    consumed = []

    def expression(text):
        # Boolean equality and inequality are associative parity operations;
        # evaluating accesses left to right preserves repeated lazy input reads.
        pieces = re.split(r"(==|!=)", text.strip())

        def access(token):
            name = token.strip().removesuffix("?")
            if name == "Inp":
                if len(consumed) == len(values):
                    raise EOFError
                value = values[len(consumed)]
                consumed.append(value)
                return value not in {"", "0", " "}
            binding = store[name]
            if isinstance(binding, bool):
                return binding
            value, negate = binding
            if value.strip() == name + "?" and not negate:
                raise LoopError
            return expression(value) != negate

        result = access(pieces[0])
        for operator, token in zip(pieces[1::2], pieces[2::2], strict=True):
            other = access(token)
            result = (result == other) if operator == "==" else (result != other)
        return result

    error = None
    try:
        for line in source.splitlines():
            line = line.partition("--")[0].strip()
            if not line:
                continue
            assignment = re.fullmatch(r"(\S+)\s*(~!>|-!>|~>|->)\s*(.+)", line)
            if assignment:
                name, arrow, value = assignment.groups()
                store[name] = (
                    expression(value) != ("!" in arrow)
                    if arrow[0] == "~"
                    else (value, "!" in arrow)
                )
            else:
                for part in line.split("::"):
                    if not expression(part):
                        break
    except (KeyError, EOFError, LoopError) as exc:
        error = (
            "undefined"
            if isinstance(exc, KeyError)
            else "cycle"
            if isinstance(exc, LoopError)
            else "eof"
        )
    return store, len(consumed), error
