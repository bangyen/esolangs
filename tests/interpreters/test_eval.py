"""Public Eval output routing contract."""

from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.stack_based.eval import run


def test_output_goes_to_the_supplied_io() -> None:
    """``run`` writes through its ``io`` argument, not a fresh default one.

    ``run_and_capture`` redirects stdout and passes a plain ``IO``, so a
    machine built with the *default* ``IO`` prints to the same redirected
    stream and looks identical.  Handing in a ``ScriptedIO`` separates
    them: it collects what the program prints, and stays empty if the
    argument was dropped on the way through.
    """
    scripted = ScriptedIO("")
    run("0+.", scripted)
    assert scripted.getvalue() == "1"
