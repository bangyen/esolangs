"""Independent arithmetic decoding; Factor wiki revision 138367."""

import itertools
import math
import random
import sys

import pytest

from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.tape_based.factor import _Machine, decode
from tests.interpreters.test_brainfuck_semantics import reference


def factors(number):
    result = {}
    divisor = 2
    while number > 1 and divisor * divisor <= number:
        while number % divisor == 0:
            result[divisor] = result.get(divisor, 0) + 1
            number //= divisor
        divisor += 1
    if number > 1:
        result[number] = result.get(number, 0) + 1
    return result


def decoded(number):
    commands = " ><+-.,[]"
    return "".join(
        commands[prime % 11] * exponent
        for prime, exponent in factors(number).items()
        if 1 <= prime % 11 <= 8
    )


def parsed(source):
    number = 0
    for char in source:
        if "0" <= char <= "9":
            number = 10 * number + ord(char) - ord("0")
    return number


def compare(source, stdin, cap):
    code = decoded(parsed(source))
    try:
        expected = reference(code, stdin, cap)
    except ValueError:
        with pytest.raises(ValueError, match="unmatched"):
            _Machine(source, ScriptedIO(stdin))
        return
    io = ScriptedIO(stdin)
    actual = _Machine(source, io)
    assert actual.bf.code == code
    error = None
    for _ in range(cap):
        if actual.halted:
            break
        before = actual.snapshot()
        fingerprint = hash(before)
        try:
            actual.step()
        except EOFError:
            error = "EOFError"
            break
        assert hash(before) == fingerprint
    assert (
        io.getvalue(),
        actual.tape,
        actual.ptr,
        actual.ip,
        io.position(),
        actual.halted,
        error,
    ) == expected
    assert actual.memory == list(actual.tape)
    assert actual.input_position() == io.position()
    assert actual.stack == []
    view = actual.memory
    view.append(99)
    assert actual.memory == list(actual.tape)
    assert actual.snapshot() == (actual.ip, actual.ptr, actual.tape, io.position())
    if actual.halted:
        before = actual.snapshot()
        actual.step()
        actual.step()
        assert actual.snapshot() == before


@pytest.mark.medium
@pytest.mark.parametrize("cap", [0, 1, 2, 7, 80])
@pytest.mark.parametrize("stdin", ["", "AB", "\x00\u0101\U0001f600\xff"])
def test_integer_and_commented_source_execution(cap, stdin):
    for number in range(2049):
        compare(str(number), stdin, cap)
    for source in ("", "words", "\u0661\uff12", "H1i5!", "-15", "1 5", "0", "00015"):
        compare(source, stdin, cap)


@pytest.mark.medium
@pytest.mark.parametrize("batch", range(8))
def test_independent_factorization_of_prime_powers_and_products(batch):
    from esolangs.interpreters.tape_based.factor import _factorint

    primes = [number for number in range(2, 100) if factors(number) == {number: 1}]
    for number in range(batch * 512, (batch + 1) * 512):
        assert _factorint(number) == factors(number)
        assert decode(number) == decoded(number)
    for index, powers in enumerate(itertools.product(range(4), repeat=5)):
        if index % 8 != batch:
            continue
        number = math.prod(p**e for p, e in zip(primes[-5:], powers, strict=True))
        expected = {p: e for p, e in zip(primes[-5:], powers, strict=True) if e}
        assert _factorint(number) == expected
        assert decode(number) == decoded(number)


@pytest.mark.medium
@pytest.mark.parametrize("seed", range(4))
def test_seeded_encoded_command_runs(seed):
    randomizer = random.Random(790 + seed)
    primes = [n for n in range(2, 150) if factors(n) == {n: 1}]
    for _ in range(100):
        number = math.prod(p ** randomizer.randrange(4) for p in primes)
        for cap in (0, 1, 7, 80):
            compare(str(number), "\u0101AB\x00", cap)


def generated_row(code, machine, stdin, answer):
    expected = reference(code, stdin, 100_000)
    assert expected[5]
    assert expected[6] is None
    assert expected[0] == answer
    assert expected[4] == len(stdin)
    io = ScriptedIO(stdin)
    machine.io = io
    machine.bf.io = io
    # Constructing once per integer avoids repeated factorization per row.
    from esolangs.interpreters.tape_based.brainfuck import _Machine as BFMachine

    machine.state = BFMachine(code, io)
    for _ in range(100_000):
        if machine.halted:
            break
        machine.step()
    assert (
        io.getvalue(),
        machine.tape,
        machine.ptr,
        machine.ip,
        io.position(),
        machine.halted,
        None,
    ) == expected


@pytest.mark.medium
@pytest.mark.parametrize("n", [1, 2, 3])
def test_generated_all_small_tables(n):
    from esolangs import generate

    for value in range(1 << (1 << n)):
        table = format(value, f"0{1 << n}b")
        before = sys.get_int_max_str_digits()
        program = generate("Factor", table)
        assert sys.get_int_max_str_digits() == before
        code = decoded(parsed(program))
        machine = _Machine(program, ScriptedIO())
        assert machine.bf.code == code
        for row, answer in enumerate(table):
            generated_row(code, machine, format(row, f"0{n}b"), answer)


@pytest.mark.medium
@pytest.mark.parametrize("n", [4, 5, 7, 11])
def test_generated_larger_tables(n):
    from esolangs import generate

    tables = ["0" * (2**n - 1) + "1"]
    if n <= 5:
        tables.extend(["0" * 2**n, "1" * 2**n])
    if n <= 7:
        tables.append("".join(str(row.bit_count() & 1) for row in range(2**n)))
        randomizer = random.Random(680 + n)
        tables.extend(
            "".join(randomizer.choice("01") for _ in range(2**n)) for _ in range(3)
        )
    for table in tables:
        before = sys.get_int_max_str_digits()
        program = generate("Factor", table)
        assert sys.get_int_max_str_digits() == before
        code = decoded(parsed(program))
        machine = _Machine(program, ScriptedIO())
        assert machine.bf.code == code
        for row in sorted({0, 1, 2 ** (n - 1), 2**n - 2, 2**n - 1}):
            generated_row(code, machine, format(row, f"0{n}b"), table[row])


@pytest.mark.medium
@pytest.mark.parametrize("width", [1, 2, 7, 40, 20000])
def test_segmented_primes_match_independent_dense_sieve(width):
    from esolangs.factor_primes import prime_segments

    limit = 60_002
    sieve = [True] * limit
    sieve[0] = sieve[1] = False
    for divisor in range(2, math.isqrt(limit - 1) + 1):
        if sieve[divisor]:
            for composite in range(divisor * divisor, limit, divisor):
                sieve[composite] = False
    previous = 2
    for start, stop, primes in prime_segments(width):
        assert start == previous
        assert stop - start >= width
        if stop > limit:
            break
        assert primes == [n for n in range(start, stop) if sieve[n]]
        previous = stop


@pytest.mark.medium
def test_published_program_positive_controls():
    cat = "310861643"
    truth = (
        "233915737501853959241591127266540514014498928384925170744745"
        "371936977107366667491950094954248611898080571424768"
    )
    assert decoded(parsed(cat)) == ",[.,]"
    for source, stdin, output in [(cat, "hello\x00", "hello"), (truth, "0", "0")]:
        compare(source, stdin, 3000)
        expected = reference(decoded(parsed(source)), stdin, 3000)
        assert expected[0] == output
        assert expected[5]
    compare(cat, "h\ni", 3000)
    compare(truth, "1", 3000)
    assert not reference(decoded(parsed(truth)), "1", 3000)[5]


@pytest.mark.parametrize("exponent", [0, 1, 63, 64, 65, 255, 256, 257, 511, 512])
def test_exponent_and_byte_boundaries(exponent):
    number = 3**exponent * 5
    code = decoded(number)
    assert code == "+" * exponent + "."
    compare(str(number), "", exponent + 3)
    assert reference(code, "", exponent + 3)[0] == chr(exponent & 255)
