"""Language-specific generator execution helpers."""


def run_jaune(program: str, inputs: list[str]) -> str:
    from esolangs.interpreters.io import ScriptedIO
    from esolangs.languages.jaune.interpreter import run

    io = ScriptedIO("\n".join(inputs) + "\n")
    run(program, io)
    return io.getvalue()
