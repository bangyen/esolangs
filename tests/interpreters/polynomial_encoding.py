"""Prime-ordered Polynomial factors expanded by integer convolution."""


def primes(count):
    result = []
    number = 2
    while len(result) < count:
        if all(number % divisor for divisor in range(2, int(number**0.5) + 1)):
            result.append(number)
        number += 1
    return result


def encode(instructions):
    coefficients = [1]
    for prime, instruction in zip(primes(len(instructions)), instructions, strict=True):
        if len(instruction) == 1:
            factor = [-(prime ** instruction[0]), 1]
        else:
            real, operator = instruction
            factor = [real * real + prime ** (2 * operator), -2 * real, 1]
        product = [0] * (len(coefficients) + len(factor) - 1)
        for i, left in enumerate(coefficients):
            for j, right in enumerate(factor):
                product[i + j] += left * right
        coefficients = product
    terms = []
    for degree in range(len(coefficients) - 1, -1, -1):
        value = coefficients[degree]
        if value:
            terms.append(f"{value:+d}" + (f"x^{degree}" if degree else ""))
    return "f(x) = " + " ".join(terms).lstrip("+")
