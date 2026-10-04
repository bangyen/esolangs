"""Independent bit-string evaluator for the supported INTERCAL scalar core."""

from dataclasses import dataclass


class InvalidError(Exception):
    pass


@dataclass(frozen=True)
class Value:
    bits: str

    @property
    def number(self):
        return int(self.bits, 2)


def value(number, width=16):
    if not 0 <= number < 2**width:
        raise InvalidError("operand range")
    return Value(format(number, f"0{width}b"))


def unary(operand, op):
    a = operand.bits
    b = a[-1:] + a[:-1]
    logic = {
        "&": lambda x, y: x == "1" and y == "1",
        "V": lambda x, y: x == "1" or y == "1",
        "?": lambda x, y: x != y,
    }[op]
    return Value(
        "".join("1" if logic(x, y) else "0" for x, y in zip(a, b, strict=True))
    )


def binary(left, right, op):
    if op == "$":
        if left.number > 65535 or right.number > 65535:
            raise InvalidError("mingle range")
        a = format(left.number, "016b")
        b = format(right.number, "016b")
        return Value("".join(x + y for x, y in zip(a, b, strict=True)))
    selected = "".join(
        x
        for x, y in zip(left.bits.zfill(32), right.bits.zfill(32), strict=True)
        if y == "1"
    )
    # C-INTERCAL determines select's width from the right operand's type.
    return Value(selected.zfill(len(right.bits)))


def expression(source, variables=None):
    variables = {} if variables is None else variables
    tokens = []
    cursor = 0
    while cursor < len(source):
        char = source[cursor]
        if char.isspace():
            cursor += 1
            continue
        if char.isascii() and char.isdigit():
            end = cursor + 1
            while end < len(source) and source[end].isascii() and source[end].isdigit():
                end += 1
            tokens.append(source[cursor:end])
            cursor = end
        elif char in ".#":
            tokens.append(char)
            cursor += 1
            if cursor < len(source) and source[cursor] in "&V?":
                tokens.append(source[cursor])
                cursor += 1
            end = cursor
            while end < len(source) and source[end].isascii() and source[end].isdigit():
                end += 1
            if end == cursor:
                raise InvalidError("split operand")
            tokens.append(source[cursor:end])
            cursor = end
        elif char in "'\"&V?$~":
            tokens.append(char)
            cursor += 1
        else:
            raise InvalidError("token")
    cursor = 0

    def take():
        nonlocal cursor
        if cursor == len(tokens):
            raise InvalidError("truncated")
        result = tokens[cursor]
        cursor += 1
        return result

    def parse():
        nonlocal cursor
        first = take()
        if first in (".", "#"):
            op = take()
            if op in "&V?":
                number = take()
            else:
                number = op
                op = None
            if not number.isascii() or not number.isdigit():
                raise InvalidError("operand")
            number = int(number)
            if first == ".":
                if not 1 <= number <= 65535:
                    raise InvalidError("variable range")
                number = variables.get(number, 0)
            result = value(number)
            return unary(result, op) if op else result
        if first not in ("'", '"'):
            raise InvalidError("group")
        op = (
            tokens[cursor] if cursor < len(tokens) and tokens[cursor] in "&V?" else None
        )
        if op:
            cursor += 1
        result = parse()
        if cursor < len(tokens) and tokens[cursor] in "$~":
            operation = take()
            right = parse()
            result = binary(result, right, operation)
        if take() != first:
            raise InvalidError("unbalanced")
        return unary(result, op) if op else result

    result = parse()
    if cursor != len(tokens):
        raise InvalidError("trailing")
    return result.number, len(result.bits)
