"""ASCII monomials and exact Gaussian factorization, independent of peels."""

from math import isqrt

import sympy as sp


def decimal(text):
    parts = [
        (int(text[start : start + 9]), len(text[start : start + 9]))
        for start in range(0, len(text), 9)
    ]
    while len(parts) > 1:
        combined = []
        for index in range(0, len(parts) - 1, 2):
            left, lwidth = parts[index]
            right, rwidth = parts[index + 1]
            combined.append((left * 10**rwidth + right, lwidth + rwidth))
        if len(parts) % 2:
            combined.append(parts[-1])
        parts = combined
    return parts[0][0]


def terms(source):
    text = "".join(source.split())
    if not text.startswith("f(x)="):
        raise ValueError("polynomial prefix")
    text = text[5:]
    cursor = 0
    result = {}
    if not text:
        raise ValueError("empty polynomial")
    while cursor < len(text):
        sign = 1
        if text[cursor] in "+-":
            sign = -1 if text[cursor] == "-" else 1
            cursor += 1
        begin = cursor
        while cursor < len(text) and "0" <= text[cursor] <= "9":
            cursor += 1
        coefficient = decimal(text[begin:cursor]) if cursor > begin else None
        if cursor < len(text) and text[cursor] == "x":
            cursor += 1
            degree = 1
            coefficient = 1 if coefficient is None else coefficient
            if cursor < len(text) and text[cursor] == "^":
                cursor += 1
                begin = cursor
                while cursor < len(text) and "0" <= text[cursor] <= "9":
                    cursor += 1
                if begin == cursor:
                    raise ValueError("missing exponent")
                degree = decimal(text[begin:cursor])
        else:
            if coefficient is None:
                raise ValueError("missing term")
            degree = 0
        result[degree] = sign * coefficient
        if cursor < len(text) and text[cursor] not in "+-":
            raise ValueError("term separator")
    return result


def power_encoding(number, maximum):
    if number < 2:
        return None
    for exponent in range(1, maximum + 1):
        low, high = 1, 1 << ((number.bit_length() + exponent - 1) // exponent)
        while low <= high:
            middle = (low + high) // 2
            value = middle**exponent
            if value < number:
                low = middle + 1
            elif value > number:
                high = middle - 1
            else:
                if all(middle % divisor for divisor in range(2, isqrt(middle) + 1)):
                    return middle, exponent
                break
    return None


def parse(source):
    coefficients = terms(source)
    x = sp.Symbol("x")
    poly = sp.Poly.from_dict(
        {(degree,): value for degree, value in coefficients.items()},
        (x,),
        domain=sp.QQ_I,
    )
    if poly.is_zero:
        raise ValueError("zero polynomial has no finite root program")
    _, factors = sp.factor_list(poly)
    encoded = []
    for factor, multiplicity in factors:
        if factor.degree() != 1:
            continue
        a, b = factor.all_coeffs()
        root = sp.expand(-b / a)
        real, imag = root.as_real_imag()
        if not real.is_Integer or not imag.is_Integer or imag < 0:
            continue
        real, imag = int(real), int(imag)
        matched = power_encoding(imag, 6) if imag else power_encoding(real, 8)
        if matched is None:
            continue
        prime, operator = matched
        if imag and real == 0 and operator not in (1, 2):
            continue
        instruction = (real, operator) if imag else (operator,)
        encoded.extend([(prime, imag, real, instruction)] * multiplicity)
    return tuple(item[3] for item in sorted(encoded, key=lambda item: item[:3]))
