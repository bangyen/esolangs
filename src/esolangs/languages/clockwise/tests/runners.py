"""Language-specific generator execution helpers."""


def run_clockwise(program: str, inputs: list[str] | list[int]) -> str:
    import esolangs

    # Clockwise loads the complete character stream (7 bits per char).
    return esolangs.run("Clockwise", program, stdin="".join(map(str, inputs)))
