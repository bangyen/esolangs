"""Language-specific generator execution helpers."""


def one_two_three_result(program: str) -> str:
    """Run a 123 program; return "0" if it halts and "1" if it loops."""
    from esolangs.interpreters.io import ScriptedIO
    from esolangs.languages.one_two_three.interpreter import _Machine
    from esolangs.vm import run_until_halt_or_cycle

    machine = _Machine(program, ScriptedIO(""))
    return "0" if run_until_halt_or_cycle(machine) else "1"
