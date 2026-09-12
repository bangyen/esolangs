"""Z3 proofs for bounded Brainfuck loop templates."""

import z3


def test_affine_transfer_loop_invariant() -> None:
    """The accepted transfer template clears its counter and adds to targets."""
    counter, initial, first, first_initial, second, second_initial, a, b, iteration = (
        z3.Ints(
            "counter initial first first_initial second second_initial a b iteration"
        )
    )
    invariant = z3.And(
        counter == initial - iteration,
        first == first_initial + iteration * a,
        second == second_initial + iteration * b,
        iteration >= 0,
        iteration <= initial,
    )

    base = z3.Solver()
    base.add(
        initial >= 0,
        first_initial >= 0,
        second_initial >= 0,
        a >= 0,
        b >= 0,
        counter == initial,
        first == first_initial,
        second == second_initial,
    )
    base.add(z3.Not(z3.substitute(invariant, (iteration, z3.IntVal(0)))))
    assert base.check() == z3.unsat

    step_case = z3.Solver()
    step_case.add(
        initial >= 0,
        first_initial >= 0,
        second_initial >= 0,
        a >= 0,
        b >= 0,
        invariant,
        iteration < initial,
    )
    next_invariant = z3.substitute(
        invariant,
        (counter, counter - 1),
        (first, first + a),
        (second, second + b),
        (iteration, iteration + 1),
    )
    step_case.add(z3.Not(next_invariant))
    assert step_case.check() == z3.unsat


def test_affine_transfer_stays_in_a_byte_when_its_postcondition_does() -> None:
    """A bounded affine transfer needs no wraparound gadget."""
    counter, first, second, a, b, first_base, second_base, iteration = z3.Ints(
        "counter first second a b first_base second_base iteration"
    )
    solver = z3.Solver()
    solver.add(
        counter >= 0,
        first == first_base + iteration * a,
        second == second_base + iteration * b,
        a >= 0,
        b >= 0,
        first_base >= 0,
        second_base >= 0,
        iteration >= 0,
        iteration <= counter,
        counter * a + first_base <= 255,
        counter * b + second_base <= 255,
    )
    solver.add(z3.Or(first < 0, first > 255, second < 0, second > 255))
    assert solver.check() == z3.unsat
