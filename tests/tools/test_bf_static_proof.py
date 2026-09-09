"""Z3 proofs for bounded Brainfuck loop templates."""

import z3


def test_multiply_loop_invariant() -> None:
    """``[>+...+<-]`` clears its counter and adds ``counter * step``."""
    counter, initial, target, initial_target, step, iteration = z3.Ints(
        "counter initial target initial_target step iteration"
    )
    invariant = z3.And(
        counter == initial - iteration,
        target == initial_target + iteration * step,
        iteration >= 0,
        iteration <= initial,
    )

    base = z3.Solver()
    base.add(
        initial >= 0,
        initial_target >= 0,
        step >= 0,
        counter == initial,
        target == initial_target,
    )
    base.add(z3.Not(z3.substitute(invariant, (iteration, z3.IntVal(0)))))
    assert base.check() == z3.unsat

    step_case = z3.Solver()
    step_case.add(
        initial >= 0,
        initial_target >= 0,
        step >= 0,
        invariant,
        iteration < initial,
    )
    next_invariant = z3.substitute(
        invariant,
        (counter, counter - 1),
        (target, target + step),
        (iteration, iteration + 1),
    )
    step_case.add(z3.Not(next_invariant))
    assert step_case.check() == z3.unsat


def test_multiply_loop_stays_in_a_byte_when_its_postcondition_does() -> None:
    """A bounded clear-and-multiply template needs no wraparound gadget."""
    counter, target, step, remainder, iteration = z3.Ints(
        "counter target step remainder iteration"
    )
    solver = z3.Solver()
    solver.add(
        counter >= 0,
        target == iteration * step,
        step >= 0,
        remainder >= 0,
        iteration >= 0,
        iteration <= counter,
        counter * step + remainder <= 255,
    )
    solver.add(z3.Or(target < 0, target > 255, target + remainder > 255))
    assert solver.check() == z3.unsat
