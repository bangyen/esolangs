"""The Minifuck suites' shared harness: run a program, fill a template."""


class _MinifuckCase:
    """Input-by-substitution boolean generator for Minifuck.

    Minifuck's only read is ``.`` pulling a byte when the eight-cell pool is
    zero, which a boolean program cannot use without destroying the pool it
    is about to print -- so the inputs are embedded instead.  The generator
    simulates every row as it emits and raises rather than returning a
    program it has not seen print the table, so these tests are checking the
    *interpreter* agrees with that simulation.

    Split out of TestParameterizedMinifuck when that class became four, so
    the four do not each carry a copy of the harness.
    """

    def run_minifuck(self, prog: str) -> str:
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.minifuck import run

        io_ = ScriptedIO("")
        run(prog, io_)
        return io_.getvalue()

    def instantiate(self, tpl: str, bits: list[int]) -> str:
        """Fill the template the way the example harness does."""
        from tests.tools.fills import _fill_minifuck

        return _fill_minifuck(tpl, bits)


def _all_derived_plans(derived_plans, staged_arities, n: int) -> dict:
    """Every staging the enumeration places at ``n``, in one pass.

    ``_derived_plans`` is asked for the tables it should look for, so a test
    that wants the whole arity has to name them.  The arity guard is checked
    *first*: naming every table means ``2 ** (2 ** n)`` of them, which is
    unbuildable past four inputs, and the guard is what the unstaged arities
    are being tested for anyway.
    """
    if n not in staged_arities:
        return derived_plans(n, ())
    every = tuple(format(v, f"0{2**n}b") for v in range(2 ** (2**n)))
    return derived_plans(n, every)
