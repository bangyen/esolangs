"""Language-specific generator execution helpers."""


def run_jaune(program: str, inputs: list[str]) -> str:
    from esolangs.languages.jaune.interpreter import run
    from esolangs.runtime.io import ScriptedIO

    io = ScriptedIO("\n".join(inputs) + "\n")
    run(program, io)
    return io.getvalue()
