"""Prove a factor witness equals the emitted polynomial before decoding it."""

from math import isqrt

from tests.interpreters.polynomial_parser import power_encoding, terms


def product_coefficients(factors):
    bound = 1
    degree = 0
    for factor in factors:
        bound *= sum(abs(c) for c in factor)
        degree += len(factor) - 1
    shift = bound.bit_length() + 2
    base = 1 << shift
    values = []
    for factor in factors:
        value = 0
        for coefficient in factor:
            value = value * base + coefficient
        values.append(value)
    while len(values) > 1:
        values = [
            values[i] * values[i + 1] if i + 1 < len(values) else values[i]
            for i in range(0, len(values), 2)
        ]
    packed = values[0] if values else 1
    result = {}

    def unpack(number, count, offset):
        if count == 1:
            assert abs(number) < base // 2
            if number:
                result[offset] = number
            return
        middle = count // 2
        bits = middle * shift
        unit = 1 << bits
        lower = number & (unit - 1)
        upper = number >> bits
        if lower >= unit // 2:
            lower -= unit
            upper += 1
        unpack(lower, middle, offset)
        unpack(upper, count - middle, offset + middle)

    unpack(packed, degree + 1, 0)
    return result


def decode(source, factors):
    assert product_coefficients(factors) == {
        p: c for p, c in terms(source).items() if c
    }
    encoded = []
    for factor in factors:
        assert factor[0] == 1
        if len(factor) == 2:
            real = -factor[1]
            imag = 0
        else:
            assert len(factor) == 3
            assert factor[1] % 2 == 0
            real = -factor[1] // 2
            square = factor[2] - real * real
            imag = isqrt(square)
            assert imag * imag == square
            assert imag > 0
        matched = power_encoding(imag, 6) if imag else power_encoding(real, 8)
        if matched is None:
            continue
        prime, operator = matched
        if imag and real == 0 and operator not in (1, 2):
            continue
        encoded.append((prime, imag, real, (real, operator) if imag else (operator,)))
    return tuple(item[3] for item in sorted(encoded, key=lambda item: item[:3]))


def generate_with_witness(table):
    import importlib

    module = importlib.import_module("esolangs.tools.polynomial")
    original = module.__dict__["_polynomial_assemble"]
    witnesses = {}

    def record(instructions):
        source = original(instructions)
        witnesses[source] = module.__dict__["_polynomial_factors"](instructions)
        return source

    module.__dict__["_polynomial_assemble"] = record
    try:
        source = module.polynomial(table)
    finally:
        module.__dict__["_polynomial_assemble"] = original
    return source, witnesses[source]
