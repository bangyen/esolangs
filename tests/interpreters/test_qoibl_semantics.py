"""Independent Qoibl AST evaluator and forward lexer; wiki revision 84835."""

import itertools
import random

import pytest

import esolangs
from esolangs.exceptions import HaltError, InputExhaustedError
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.register_based.qoibl import _Machine, run, tokenize
from tests.interpreters.views import view as vm_view


@pytest.mark.parametrize("suffix", ["w", "q", "t", "r", "qt"])
def test_incomplete_prefix_cannot_discard_output(suffix: str) -> None:
    with pytest.raises(ValueError, match="malformed Qoibl expression"):
        _Machine(f"tt y tt {suffix}", ScriptedIO())


@pytest.mark.parametrize("prefix", ["w", "q", "t", "r"])
def test_lone_prefix_does_not_invent_an_opcode(prefix: str) -> None:
    assert tokenize(prefix) == [[]]


@pytest.mark.parametrize("bits", ["ey", "eey", "yy"])
def test_trailing_r_borrows_the_preceding_bit(bits: str) -> None:
    assert tokenize(bits + "r") == [[bits[:-1], "yr"]]
    with pytest.raises(ValueError, match="malformed Qoibl comparison operator"):
        _Machine(bits + "r", ScriptedIO())


@pytest.mark.parametrize("operation", ["index", "division"])
def test_large_binary_operand_preserves_halt_diagnostic(operation: str) -> None:
    bits = "y" + "e" * 20000
    value = 1 << 20000
    digits = []
    while value:
        value, digit = divmod(value, 10)
        digits.append(chr(48 + digit))
    decimal = "".join(reversed(digits))
    source = f"qe {bits} qe" if operation == "index" else f"{bits} ry yy ry e"
    expected = (
        f"variable index {decimal} is outside 0..255"
        if operation == "index"
        else f"division by zero: {decimal} divided by 0"
    )
    machine = _Machine(source, ScriptedIO())
    with pytest.raises(HaltError) as raised:
        machine.step()
    assert str(raised.value) == expected
    assert vm_view(machine, "ip") == 1
    assert machine.var == {}


# The spec leaves association and failure atomicity open; these model the
# repository's right association and statement transaction boundary.
def lit(value):
    return ("literal", value)


def spelling(node):
    operation, *args = node
    if operation == "literal":
        return format(args[0], "b").translate(str.maketrans("01", "ey"))
    if operation == "input":
        return "et"
    if operation in ("tt", "qe"):
        return f"{operation} {spelling(args[0])} {operation}"
    if operation in ("we", "rr"):
        return (
            f"{operation} {spelling(args[0])} {operation} "
            f"{spelling(args[1])} {operation}"
        )
    marker, operator, left, right = args
    return f"{spelling(left)} {marker} {operator} {marker} {spelling(right)}"


class Parser:
    """Cursor-based precedence parser for whitespace-delimited valid programs."""

    def __init__(self, source):
        self.tokens = source.split() if isinstance(source, str) else source
        self.cursor = 0

    def take(self, expected=None):
        token = self.tokens[self.cursor]
        self.cursor += 1
        if expected is not None:
            assert token == expected, (token, expected)
        return token

    def expression(self, stop=None, minimum=0):
        token = self.take()
        if token == "et":
            node = ("input",)
        elif token in ("tt", "qe"):
            node = (token, self.expression(token))
            self.take(token)
        elif token in ("we", "rr"):
            left = self.expression(token)
            self.take(token)
            right = self.expression(token)
            self.take(token)
            node = (token, left, right)
        else:
            assert token, token
            assert all(char in "ey" for char in token), token
            value = 0
            for char in token:
                value = 2 * value + (char == "y")
            node = lit(value)
        while self.cursor < len(self.tokens):
            marker = self.tokens[self.cursor]
            precedence = {"yr": 1, "ry": 2}.get(marker, 0)
            if marker == stop or precedence == 0 or precedence < minimum:
                break
            self.take(marker)
            operator = self.take()
            assert operator in ("ee", "ey", "ye", "yy")
            self.take(marker)
            node = ("binary", marker, operator, node, self.expression(stop, precedence))
        return node

    def program(self):
        statements = []
        while self.cursor < len(self.tokens):
            statements.append(self.expression())
        return statements


class Reference:
    def __init__(self, statements, stdin="", variables=None):
        self.statements = statements
        self.stdin = stdin
        self.variables = dict(variables or {})
        self.ip = 0
        self.position = 0
        self.past_end = 0
        self.output = ""
        self.visits = 0

    @property
    def halted(self):
        return self.ip >= len(self.statements)

    def evaluate(self, node, variables):
        self.visits += 1
        if self.visits > 20000:
            raise RuntimeError("reference expression budget exhausted")
        operation, *args = node
        if operation == "literal":
            return args[0]
        if operation == "input":
            if self.position == len(self.stdin):
                self.past_end += 1
                raise InputExhaustedError(self.position, len(self.stdin), "character")
            char = self.stdin[self.position]
            self.position += 1
            return ord(char)
        if operation == "tt":
            value = self.evaluate(args[0], variables)
            self.output += chr(value)
            return 0
        if operation == "qe":
            index = self.evaluate(args[0], variables)
            self.address(index)
            return variables.get(index, 0)
        if operation == "we":
            index = self.evaluate(args[0], variables)
            value = self.evaluate(args[1], variables)
            self.address(index)
            variables[index] = value
            return 0
        if operation == "rr":
            while self.evaluate(args[0], variables):
                self.evaluate(args[1], variables)
            return 0
        marker, operator, left, right = args
        x = self.evaluate(left, variables)
        y = self.evaluate(right, variables)
        if marker == "yr":
            return int({"ee": x == y, "ey": x > y, "ye": x < y, "yy": x != y}[operator])
        if operator == "ee":
            return x + y
        if operator == "ey":
            return x - y
        if operator == "ye":
            return x * y
        if not y:
            raise HaltError(f"division by zero: {x} divided by {y}")
        return x // y

    @staticmethod
    def address(index):
        if not 0 <= index < 256:
            raise HaltError(f"variable index {index} is outside 0..255")

    def step(self):
        if self.halted:
            return
        statement = self.statements[self.ip]
        self.ip += 1
        staged = self.variables.copy()
        if statement is not None:
            self.evaluate(statement, staged)
        self.variables = staged


def inspect(machine):
    assert vm_view(machine, "memory") == [
        machine.var.get(index, 0) for index in range(256)
    ]
    assert vm_view(machine, "stack") == []
    assert machine.snapshot() == (
        vm_view(machine, "ip"),
        tuple(sorted(machine.var.items())),
        machine.io.position(),
    )
    return (
        vm_view(machine, "ip"),
        dict(machine.var),
        machine.io.position(),
        machine.io.past_end,
        machine.io.getvalue(),
        machine.halted,
    )


def expected_state(reference):
    return (
        reference.ip,
        reference.variables,
        reference.position,
        reference.past_end,
        reference.output,
        reference.halted,
    )


def compare(statements, stdin="", variables=None, source=None):
    if source is None:
        source = "\n".join(map(spelling, statements))
        assert Parser(source).program() == statements, source
    expected = Reference(statements, stdin, variables)
    actual = _Machine(source, ScriptedIO(stdin))
    actual.var = dict(variables or {})
    assert inspect(actual) == expected_state(expected)
    while not expected.halted:
        snapshot = actual.snapshot()
        original_hash = hash(snapshot)
        error = None
        try:
            expected.step()
        except (HaltError, InputExhaustedError, ValueError) as caught:
            error = caught
        # The model completes (or throws) first: never invoke an uncertified loop.
        if error is not None:
            with pytest.raises(type(error)) as caught:
                actual.step()
            assert str(caught.value) == str(error), source
        else:
            actual.step()
        assert inspect(actual) == expected_state(expected), source
        assert hash(snapshot) == original_hash
        if error is not None:
            return expected, error
    terminal = inspect(actual)
    actual.step()
    actual.step()
    assert inspect(actual) == terminal
    return expected, None


def expressions():
    atoms = [lit(value) for value in (0, 1, 2, 3, 7, 48, 255, 256, 0x10FFFF, 0x110000)]
    atoms += [
        ("input",),
        ("qe", lit(0)),
        ("qe", lit(255)),
        ("qe", lit(2)),
        ("qe", ("input",)),
        ("qe", ("qe", lit(1))),
    ]
    yield from atoms
    for marker, operator, left, right in itertools.product(
        ("yr", "ry"), ("ee", "ey", "ye", "yy"), atoms[:8], atoms[:8]
    ):
        yield ("binary", marker, operator, left, right)
    for operators in itertools.product(("ee", "ey", "ye", "yy"), repeat=2):
        yield (
            "binary",
            "ry",
            operators[0],
            lit(7),
            ("binary", "ry", operators[1], lit(3), lit(2)),
        )
    for operator in ("ee", "ey", "ye", "yy"):
        yield (
            "binary",
            "yr",
            operator,
            ("binary", "ry", "ey", lit(1), lit(7)),
            ("binary", "ry", "ey", lit(3), lit(9)),
        )
        yield ("binary", "ry", operator, ("input",), ("input",))
        yield ("binary", "ry", operator, ("qe", ("input",)), ("input",))
    yield ("binary", "ry", "yy", ("qe", lit(1)), lit(4))


@pytest.mark.medium
def test_independent_expression_and_statement_effects():
    variables = {0: 13, 1: -7, 65: 3, 255: 97}
    for expr in expressions():
        for stdin in ("", "\x00\x02", "AB"):
            for statement in (expr, ("tt", expr), ("we", lit(2), expr)):
                compare([statement], stdin, variables)
    for index in (0, 1, 255, 256, 1 << 80):
        for value in (0, 97, 1 << 100):
            compare([("we", lit(index), lit(value)), ("tt", ("qe", lit(index)))])
    for stdin in ("", "\x01", "\x01A", "\u0100A"):
        compare([("we", ("input",), ("input",))], stdin)
        compare([("we", ("input",), ("tt", ("input",)))], stdin)
    compare([("tt", ("tt", lit(65)))])
    compare([("tt", ("we", lit(1), lit(65))), ("tt", ("qe", lit(1)))])
    # Assignment inside a failing print/division must roll back variables.
    compare([("tt", ("binary", "ry", "ee", lit(0x110000), ("we", lit(1), lit(65))))])
    compare([("binary", "ry", "yy", lit(7), ("we", lit(1), ("tt", lit(65))))])


@pytest.mark.medium
def test_finite_loops_and_failed_statement_rollback():
    for count in range(8):
        statements = [
            ("we", lit(0), lit(count)),
            (
                "rr",
                ("qe", lit(0)),
                ("we", lit(0), ("binary", "ry", "ey", ("qe", lit(0)), lit(1))),
            ),
            ("tt", ("qe", lit(0))),
        ]
        compare(statements)
    for stdin in ("\x00", "\x01\x02\x00", "AB\x00", "AB", ""):
        compare([("rr", ("input",), ("tt", lit(65)))], stdin)
    for stdin in ("AB", "A\x00", ""):
        # The first loop iteration writes; the later EOF rolls that write back.
        compare([("rr", ("input",), ("we", lit(1), ("input",)))], stdin)


def test_snapshot_distinguishes_cursor_stored_zero_variables_and_input():
    machine = _Machine("et e", ScriptedIO("A"))
    snapshots = {machine.snapshot()}
    for state in (
        ({}, 1),
        ({0: 0}, 0),
        ({0: 1}, 0),
        ({255: 1}, 0),
        ({0: 1, 255: 2}, 0),
    ):
        machine.var, machine.ind = state
        snapshots.add(machine.snapshot())
    machine.var, machine.ind = {}, 0
    machine.io.input_char()
    snapshots.add(machine.snapshot())
    assert len(snapshots) == 7


@pytest.mark.parametrize(
    "source",
    [
        "tt y qe",
        "qe y tt",
        "we y we y tt",
        "rr e rr y tt",
        "tt e yr ee ry y tt",
        "tt e ry ee yr y tt",
        "qe y ry ee ry y qe",
        "we",
        "qe",
        "tt",
        "rr",
        "e ry ee",
        "e yr yy",
        "e ry e ry y",
        "e yr e yr y",
        "we e qe",
    ],
)
def test_malformed_markers_rejected_before_effects(source):
    marker = (
        "comparison operator"
        if "yr" in source
        else "arithmetic operator"
        if "ry" in source
        else "expression"
    )
    with pytest.raises(ValueError, match="malformed Qoibl") as caught:
        _Machine(source, ScriptedIO("A"))
    assert str(caught.value) == "malformed Qoibl " + marker


def word_readings(word):
    """Forward lexing: a literal's final bit may begin an overlapping opcode."""
    pending = [(0, [])]
    while pending:
        index, tokens = pending.pop()
        if index == len(word):
            yield tokens
            continue
        alternatives = []
        pair = word[index : index + 2]
        if pair in ("we", "qe", "tt", "rr", "ry") or (index == 0 and pair == "yr"):
            alternatives.append((index + 2, [*tokens, pair]))
        if word[index] in "ey":
            end = index
            while end < len(word) and word[end] in "ey":
                end += 1
            literal = word[index:end]
            alternatives.append((end, [*tokens, literal]))
            marker = {("e", "t"): "et", ("y", "r"): "yr"}.get(
                (literal[-1], word[end : end + 1])
            )
            if marker is not None:
                head = tokens + ([literal[:-1]] if len(literal) > 1 else [])
                alternatives.append((end + 1, [*head, marker]))
        pending.extend(reversed(alternatives))


def manual_tokens(source):
    cleaned = "".join(
        char for char in source if char in "ewqtry" or char.isspace()
    ).strip()
    if not cleaned:
        return []
    alternatives = [list(word_readings(word)) for word in cleaned.split()]
    first = None
    for readings in itertools.product(*alternatives):
        tokens = list(itertools.chain.from_iterable(readings))
        if first is None:
            first = tokens
        parser = Parser(tokens)
        statements = []
        try:
            while parser.cursor < len(tokens):
                start = parser.cursor
                parser.expression()
                statements.append(tokens[start : parser.cursor])
        except (AssertionError, IndexError):
            continue
        return statements
    if first is not None:
        return [first]
    if any(char in "ey" for char in cleaned) or any(
        marker in cleaned for marker in ("tt", "rr")
    ):
        raise ValueError("malformed Qoibl expression")
    return [[]]


def lexical_corpus():
    for length in range(5):
        for characters in itertools.product("ewqtry ", repeat=length):
            yield "".join(characters)
    yield from (
        "ttettt",
        "rrttetttrr",
        "qeeqeyreeyryyeeey",
        "et et",
        "eet",
        "e yr",
        "ey et",
        "y ttyytt",
        "tt",
        "we",
        "qe",
        "\nrr",
        "tt! yeeyeee? tt",
        "tt y tt tt ye tt",
        "eyr ",
        "eeyr",
        "yyr",
        "e\n\nr\n",
        "qt y\nqrt\nrt",
        "\u2003et\u00a0y",
        "tt y tt w",
        "tt y tt q",
        "tt y tt r",
        "tt y tt qt",
    )


@pytest.mark.medium
def test_forward_lexical_oracle_and_exact_load_errors():
    for source in lexical_corpus():
        try:
            expected = manual_tokens(source)
        except ValueError as error:
            error_message = str(error)
        else:
            error_message = None
        if error_message is not None:
            with pytest.raises(
                ValueError, match="malformed Qoibl expression"
            ) as caught:
                _Machine(source, ScriptedIO())
            assert str(caught.value) == error_message
            continue
        assert tokenize(source) == expected, source
        if not expected or expected == [[]]:
            machine = _Machine(source, ScriptedIO())
            if expected:
                machine.step()
            assert machine.halted
        else:
            try:
                parser = Parser(expected[0])
                parser.expression()
                assert parser.cursor == len(expected[0])
            except (AssertionError, IndexError):
                marker = (
                    "comparison operator"
                    if "yr" in expected[0]
                    else "arithmetic operator"
                    if "ry" in expected[0]
                    else "expression"
                )
                with pytest.raises(ValueError, match="malformed Qoibl") as caught:
                    _Machine(source, ScriptedIO())
                assert str(caught.value) == "malformed Qoibl " + marker


WIKI_PROGRAMS = {
    "hello": "\n".join(
        "tt " + spelling(lit(ord(char))) + " tt" for char in "Hello, world!\n"
    ),
    "adder": (
        "we e we yyeeee we\n"
        "we y we et ry ey ry qe e qe we\n"
        "we ye we et ry ey ry qe e qe we\n"
        "we y we qe y qe ry ee ry qe ye qe we\n"
        "we y we qe y qe ry ee ry qe e qe we\n"
        "tt qe y qe tt"
    ),
    "truth": (
        "we e we et we\nrr qe e qe yr ee yr yyeeey rr tt yyeeey tt rr\ntt yyeeee tt"
    ),
    "cat": "rr e yr ee yr e rr tt et tt rr",
}


@pytest.mark.medium
def test_wiki_programs_spacing_execution_and_public_runner():
    for name, original in WIKI_PROGRAMS.items():
        statements = Parser(original).program()
        tokens = [line.split() for line in original.splitlines()]
        for source in (
            original,
            original.replace(" ", ""),
            original.replace(" ", "").replace("\n", ""),
        ):
            assert tokenize(source) == tokens
            if name == "truth":
                inputs = ("0",)
            elif name == "cat":
                inputs = ("", "A\n\u0101\x00")
            elif name == "adder":
                inputs = tuple(
                    f"{a}{b}" for a in range(5) for b in range(6) if a + b < 10
                )
            else:
                inputs = ("",)
            for stdin in inputs:
                reference, error = compare(statements, stdin, source=source)
                if name == "cat":
                    assert isinstance(error, InputExhaustedError)
                    assert reference.output == stdin
                    continue
                assert error is None
                output = (
                    "Hello, world!\n"
                    if name == "hello"
                    else "0"
                    if name == "truth"
                    else str(sum(map(int, stdin)))
                )
                assert reference.output == output
                io = ScriptedIO(stdin)
                run(source, io)
                assert io.getvalue() == output
                line_io = ScriptedIO(stdin)
                run(source.splitlines(), line_io)
                assert line_io.getvalue() == output
                assert esolangs.run("Qoibl", source, stdin) == output


def generated_result(table, n, row, source, statements):
    stdin = format(row, f"0{n}b")
    reference, error = compare(statements, stdin, source=source)
    assert error is None
    assert reference.output == table[row]
    assert reference.position == n
    assert reference.past_end == 0


@pytest.mark.medium
@pytest.mark.parametrize(
    ("n", "batch"), [(1, 0), (2, 0), *((3, batch) for batch in range(16))]
)
@pytest.mark.parametrize("width", [None, 1, 2, 3, 6, 13, 80])
def test_every_small_generated_table_against_mutable_model(n, batch, width):
    for value in range(16 * batch, min(16 * (batch + 1), 1 << (1 << n))):
        table = format(value, f"0{1 << n}b")
        source = esolangs.generate("Qoibl", table, width=width)
        if width is not None:
            assert max(map(len, source.splitlines())) <= max(2, width)
        statements = Parser(source).program()
        for row in range(1 << n):
            generated_result(table, n, row, source, statements)


@pytest.mark.medium
@pytest.mark.parametrize("n", [4, 5, 6, 7, 8, 9, 10, 12])
def test_larger_generated_tables_and_wide_row_indices(n):
    rng = random.Random(20260930 + n)
    tables = [
        "1" + "0" * ((1 << n) - 1),
        "0" * ((1 << n) - 1) + "1",
        "0" * (1 << n),
        "1" * (1 << n),
        "".join(str(row.bit_count() & 1) for row in range(1 << n)),
        format(rng.getrandbits(1 << n), f"0{1 << n}b"),
    ]
    for table in tables:
        source = esolangs.generate("Qoibl", table)
        statements = Parser(source).program()
        rows = (
            range(1 << n)
            if n <= 6
            else sorted(
                {
                    row
                    for row in (
                        0,
                        1,
                        127,
                        128,
                        255,
                        (1 << n) // 2 - 1,
                        (1 << n) // 2,
                        (1 << n) - 2,
                        (1 << n) - 1,
                    )
                    if row < (1 << n)
                }
            )
        )
        for row in rows:
            generated_result(table, n, row, source, statements)


@pytest.mark.medium
@pytest.mark.parametrize("n", [5, 8])
@pytest.mark.parametrize("width", [1, 3, 13])
def test_historical_narrow_horner_samples(n, width):
    rng = random.Random(20260930 + n)
    for table in (
        "".join(str(row.bit_count() & 1) for row in range(1 << n)),
        format(rng.getrandbits(1 << n), f"0{1 << n}b"),
    ):
        source = esolangs.generate("Qoibl", table, width=width)
        assert max(map(len, source.splitlines())) <= max(2, width)
        statements = Parser(source).program()
        for row in rng.sample(range(1 << n), 4):
            generated_result(table, n, row, source, statements)


@pytest.mark.medium
def test_exact_generated_size_rule_has_executed_positive_controls():
    for n in range(1, 13):
        table = "".join(str(row.bit_count() & 1) for row in range(1 << n))
        source = esolangs.generate("Qoibl", table)
        packed = sum(int(bit) << row for row, bit in enumerate(table))
        assert len(source) == 64 * n + 65 + max(1, packed.bit_length())
        statements = Parser(source).program()
        for row in (0, 1, (1 << n) - 1):
            generated_result(table, n, row, source, statements)


def test_wiki_truth_machine_repeated_output_has_a_bounded_port_control():
    class PortLimitError(Exception):
        pass

    class LimitedIO(ScriptedIO):
        def _write(self, value):
            if len(self.getvalue()) == 8:
                raise PortLimitError
            super()._write(value)

    class LimitedReference(Reference):
        def evaluate(self, node, variables):
            if node[0] == "tt" and len(self.output) == 8:
                raise PortLimitError
            return super().evaluate(node, variables)

    source = WIKI_PROGRAMS["truth"]
    for stdin in ("0", "1"):
        reference = LimitedReference(Parser(source).program(), stdin)
        actual = _Machine(source, LimitedIO(stdin))
        if stdin == "1":
            reference.step()
            actual.step()
            with pytest.raises(PortLimitError):
                reference.step()
            with pytest.raises(PortLimitError):
                actual.step()
            assert reference.output == "1" * 8
            assert reference.ip == 2
            assert reference.variables == {0: 49}
        else:
            while not reference.halted:
                reference.step()
                actual.step()
            assert reference.output == "0"
        assert inspect(actual) == expected_state(reference)
