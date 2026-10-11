"""Language-specific generator execution helpers."""


def run_taglate(program: str, inputs: list[str]) -> str:
    import esolangs

    return esolangs.run("Taglate", program, stdin="".join(inputs))
