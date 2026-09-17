"""The Minifuck suites' shared harness: run a program, fill a template."""

from esolangs.tools.helpers import TEMPLATE_CHAR, runs
from esolangs.tools.minifuck_sim import PAIR


def run_count(template: str, n: int) -> int:
    """How many input runs ``template`` carries, expecting ``n``.

    The k-th run *is* input k, so this is what the text can still show
    about the embedding: a run short, a run over, or a fill character in
    the program proper refuses (a ``ValueError`` from :func:`runs`).
    """
    return len(runs(template, TEMPLATE_CHAR, (PAIR,) * n))


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
