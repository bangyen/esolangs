"""Forbin cases derived from bit permutations, products and bytes."""

import itertools


def output(values):
    bits = list(values)
    return "out " + ",".join(map(str, [0] * (8 - len(bits)) + bits)) + ";"


def names_output(names):
    return "out " + ",".join(["0"] * (8 - len(names)) + list(names)) + ";"


def finite_cases():
    cases = []

    def check(family, code, expected, stdin=""):
        cases.append(
            {
                "family": family,
                "source": code,
                "input": stdin,
                "expected_bytes": expected,
            }
        )

    for n in range(2, 6):
        names = list("abcde"[:n])
        for bits in itertools.product([0, 1], repeat=n):
            for shift in range(n):
                indexes = list(range(shift, n)) + list(range(shift))
                code = (
                    "main{"
                    + ",".join(names)
                    + "="
                    + ",".join(map(str, bits))
                    + ";"
                    + ",".join(names)
                    + "="
                    + ",".join(names[i] for i in indexes)
                    + ";"
                    + names_output(names)
                    + "}"
                )
                check(
                    "parallel_assignment",
                    code,
                    [sum((bits[i] << n - j - 1 for j, i in enumerate(indexes)))],
                )
    for n in range(1, 6):
        names = list("abcde"[:n])
        for bits in itertools.product([0, 1], repeat=n):
            for selected in range(n):
                literal = (
                    "(" + ",".join(names) + " @ {return " + names[selected] + ";})"
                )
                code = (
                    "main{f="
                    + literal
                    + ";x=(f "
                    + ",".join(map(str, bits))
                    + ");"
                    + names_output(["x"])
                    + "}"
                )
                check("anonymous_parameters", code, [bits[selected]])
    for n in range(2, 5):
        names = list("abcd"[:n])
        for pattern in itertools.product(["0", "1", "*"], repeat=n):
            choices = [(0, 1) if value == "*" else (int(value),) for value in pattern]
            expected = [
                sum((value << n - i - 1 for i, value in enumerate(row)))
                for row in itertools.product(*choices)
            ]
            for form in ["short", "group"]:
                pat = ",".join(pattern)
                if form == "group":
                    pat = "(" + pat + ")"
                code = (
                    "main{"
                    + ",".join(names)
                    + "=0;for ("
                    + ",".join(names)
                    + "):("
                    + pat
                    + "){"
                    + names_output(names)
                    + "}}"
                )
                check("wildcard_" + form, code, expected)
    for low, high in itertools.product([0, 1], repeat=2):
        for initial in [0, 1]:
            code = (
                "main{i=0;x="
                + str(initial)
                + ";for i:"
                + str(low)
                + ".."
                + str(high)
                + "{x=!x;"
                + names_output(["i", "x"])
                + "}}"
            )
            value = initial
            expected = []
            for index in range(low, high + 1):
                value = 1 - value
                expected.append(2 * index + value)
            check("inclusive_range", code, expected)
    for byte in range(256):
        code = "main{a,b,c,d,e,f,g,h=(in 0);" + names_output("abcdefgh") + "}"
        check("msb_byte_reads", code, [byte], chr(byte))
    for byte in range(256):
        code = "main{{" + output(map(int, format(byte, "08b"))) + "}0;}"
        check("bare_literal_call", code, [byte])
    return cases


def global_cases():
    cases = []
    for n in range(1, 7):
        names = list("abcdef"[:n])
        for bits in itertools.product([0, 1], repeat=n):
            declarations = ",".join(names) + "=" + ",".join(map(str, bits)) + ";"
            emit = "out " + ",".join(["0"] * (8 - n) + names) + ";"
            value = sum((bit << n - index - 1 for index, bit in enumerate(bits)))
            variants = [
                (declarations + "main{" + emit + "}", value),
                (
                    declarations
                    + "main{"
                    + names[0]
                    + "=!"
                    + names[0]
                    + ";"
                    + emit
                    + "}",
                    value ^ 1 << n - 1,
                ),
                (declarations + "emit_byte{" + emit + "}main{emit_byte 0;}", value),
            ]
            for code, expected in variants:
                cases.append({"code": code, "expected_byte": expected})
    for byte in range(256):
        code = "a,b,c,d,e,f,g,h=(in 0);main{out a,b,c,d,e,f,g,h;}"
        cases.append({"code": code, "input_byte": byte, "expected_byte": byte})
    for byte in range(256):
        bit = byte & 1
        code = "x=(f 0);main{out 0,0,0,0,0,0,0,x;}f{return " + str(bit) + ";}"
        cases.append({"code": code, "expected_byte": bit})
    return cases
