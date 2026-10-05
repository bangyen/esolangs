import itertools

from esolangs.exceptions import HaltError
from esolangs.interpreters.other.packlang import (
    _advance,
    _Frame,
    _parse,
    _Parser,
    _strip_comments,
    _tokenize,
)
from tests.interpreters.packlang_expression_reference import (
    Expression,
    native_tree,
    tokens,
)


def scalar_cases():
    checks = 0
    for low, high, under, over in [
        (0, 255, 255, 0),
        (3, 7, 6, 4),
        (0, 1, 1, 0),
        (2, 2, 2, 2),
    ]:
        source = (
            f"Package {{ Integer({low},{high},{under},{over}) x; "
            "Integer main { 0; } } p;"
        )
        program = _parse(source)
        function = program.entry
        assert function is not None
        for value, opcode in itertools.product(
            [low - 1, low, low + 1, high - 1, high, high + 1],
            ["init", "incr", "decr", "read", "print", "val"],
        ):
            frame = _Frame(function, (("x", value),))
            if opcode in ("init", "incr", "decr"):
                stmt = (opcode, "x", None)
                expected = (
                    low if opcode == "init" else value + (1 if opcode == "incr" else -1)
                )
                if opcode != "init":
                    expected = (
                        under
                        if expected < low
                        else over
                        if expected > high
                        else expected
                    )
                store = (("x", expected),)
                output = None
                result = 0
            elif opcode == "read":
                stmt = (opcode, "x", None)
                store = (("x", 913),)
                output = None
                result = 0
            else:
                stmt = (opcode, ("var", "x"))
                store = frame.store
                output = chr(value % 256) if opcode == "print" else None
                result = value if opcode == "val" else 0
            observed, out, read = _advance(frame, program, 913, stmt)
            assert (observed.store, out, read, observed.pc, observed.result) == (
                store,
                output,
                False,
                1,
                result,
            ), (opcode, value)
            assert frame.store == (("x", value),)
            checks += 1
    return checks


def array_control_cases():
    checks = 0
    program = _parse("Package { Array(Integer(3,7,6,4),3) a; Integer main { 0; } } p;")
    function = program.entry
    assert function is not None
    for row, index, opcode in itertools.product(
        [(3, 3, 3), (7, 3, 6), (2, 8, 4)],
        range(-1, 5),
        ["init", "incr", "decr", "read"],
    ):
        original = tuple(row)
        frame = _Frame(function, (("a", original),))
        statement = (opcode, "a", ("lit", index))
        expected = list(row)
        if 0 <= index < 3:
            value = (
                3
                if opcode == "init"
                else 913
                if opcode == "read"
                else row[index] + (1 if opcode == "incr" else -1)
            )
            if opcode in ("incr", "decr"):
                value = 6 if value < 3 else 4 if value > 7 else value
            expected[index] = value
            updated, out, wants_read = _advance(frame, program, 913, statement)
            assert updated.store == (("a", tuple(expected)),)
            assert out is None
            assert not wants_read
        else:
            try:
                _advance(frame, program, 913, statement)
            except HaltError:
                pass
            else:
                raise AssertionError((row, index, opcode))
        assert frame.store == (("a", original),)
        checks += 1
    for left, right in itertools.product([0, 1, 3, 255, 256, 913], repeat=2):
        expressions = [
            (("xor", ("lit", left), ("lit", right)), left ^ right),
            (("not", ("xor", ("lit", left), ("lit", right))), int(left == right)),
            (("not", ("not", ("lit", left))), int(left != 0)),
        ]
        for expression, answer in expressions:
            frame = _Frame(function, (("a", (3, 4, 5)),), pc=2)
            updated, out, read = _advance(frame, program, None, ("jz", expression, 19))
            assert updated.pc == (3 if answer else 19)
            assert (updated.store, out, read) == (frame.store, None, False)
            checks += 1
    return checks


def expression_cases():
    expressions = [
        "0",
        "001",
        "255",
        "913",
        "x",
        "a(0)",
        "a(length)",
        "f()",
        "f(1,2)",
        "(x ^ 0)",
        "!x",
        "!!x",
        "!x ^ 1",
        "!(x ^ 1)",
    ]
    expressions += [
        left + " ^ " + right
        for left, right in itertools.product(expressions[:10], repeat=2)
    ]
    checks = 0
    for expression in expressions:
        expected = native_tree(Expression(expression).parse())
        for decorated in [
            expression,
            "% before\n" + expression,
            expression + " % trailing",
            "%$ block \n arbitrary? % " + expression,
        ]:
            words = tokens(decorated)
            assert words == _tokenize(_strip_comments(decorated))
            parser = _Parser(words)
            actual = parser.expression()
            assert parser.peek() is None, (decorated, actual, expected)
            assert actual == expected, (decorated, actual, expected)
            checks += 1
    for expression in [
        "",
        ")",
        "(",
        "!",
        "1 ^",
        "f(,)",
        "f(1,)",
        "f(1",
        "a(length,1)",
        "1 2",
        "1 @ 2",
    ]:
        try:
            Expression(expression).parse()
        except ValueError:
            pass
        else:
            raise AssertionError(expression)
        try:
            parser = _Parser(_tokenize(_strip_comments(expression)))
            parser.expression()
            if parser.peek() is not None:
                raise ValueError("trailing token")
        except ValueError:
            pass
        else:
            raise AssertionError(expression)
        checks += 1
    return checks


def render(node):
    if node[0] == "number":
        return str(node[1])
    if node[0] == "invert":
        return "!(" + render(node[1]) + ")"
    if node[0] == "xor":
        return "(" + render(node[1]) + " ^ " + render(node[2]) + ")"
    return node[0] + "(" + render(node[1]) + ")"


def evaluate(node, output):
    if node[0] == "number":
        return node[1]
    if node[0] == "invert":
        return int(evaluate(node[1], output) == 0)
    if node[0] == "xor":
        return evaluate(node[1], output) ^ evaluate(node[2], output)
    argument = evaluate(node[1], output)
    output.append(chr(argument % 256))
    return argument ^ 1 if node[0] == "flip" else int(argument == 0)


def expression(rng, depth):
    if depth == 0:
        return ["number", rng.choice([0, 1, 65, 255, 256, 913])]
    kind = rng.choice(["number", "invert", "xor", "flip", "zero"])
    if kind == "number":
        return expression(rng, 0)
    if kind == "xor":
        return [kind, expression(rng, depth - 1), expression(rng, depth - 1)]
    return [kind, expression(rng, depth - 1)]


PORT_PROGRAMS = [
    (
        "Package : IO { Integer f { Char x; charGet(x); charPut(x); x"
        "; } Integer main { charPut(f()); } } p;"
    ),
    (
        "Package : IO { Array(Char,2) a; Integer index { charPut(73);"
        " 1; } Integer main { charGet(a(index())); charPut(a(1)); } }"
        " p;"
    ),
    (
        "Package : IO { Integer recurse : Integer x { If x Then { DEC"
        "R x; recurse(x); } x; } Integer main { charPut(recurse(6)); "
        "} } p;"
    ),
    (
        "Package : IO { Integer x; Integer tick : Integer v { INCR v;"
        " charPut(v); v; } Integer main { While x ^ 5 Do { charPut(ti"
        "ck(x)); INCR x; } } } p;"
    ),
    (
        "Package { Integer f { 65; } Integer main { charPut(f()); } }"
        " first; Package { Integer f { 66; } } second;"
    ),
    (
        "Dependency { Integer f { 65; } } base; Dependency : base { I"
        "nteger g { f(); } } middle; Package : middle,IO { Integer ma"
        "in { charPut(g()); } } last;"
    ),
    (
        "Package : IO { Array(Integer(3,7,6,4),3) a; Integer main { I"
        "NCR a(0); DECR a(2); INIT a; charPut(a(0)); charPut(a(2)); c"
        "harPut(a(length)); } } p;"
    ),
    (
        "Package : IO { Integer main { Pointer(Char) x; String empty;"
        " charGet(x); charPut(x); charPut(empty(length)); } } p;"
    ),
    (
        "Package : IO { Integer(3,7,6,4) x; Integer main { INIT x; DE"
        "CR x; charPut(x); INCR x; INCR x; charPut(x); } } p;"
    ),
]
