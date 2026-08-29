r"""Show how @ delivers input and what one read leaves on the stack.

``two_input.py`` found nothing, which is a harness question before it is a
language question: ``@`` calls ``io.input_str()`` and extends the stack with
*every* character's byte code, so one ``@`` consumes a whole line and a
second one hits EOF.  Two bits therefore arrive from a single read.
"""

from probe import go
from tts_interp import State


def stack_after(source, inp):
    """Return the stack left by ``source`` on ``inp`` (no drain interference)."""
    from esolangs.interpreters.io import ScriptedIO

    io_obj = ScriptedIO(inp)
    state = State(io=io_obj)
    state.code = source.split()
    steps = 0
    while not state.halted and steps < 50:
        state.step()
        steps += 1
    return list(state.stk), io_obj.getvalue()


def main():
    """Show what one @ leaves for one- and two-character inputs."""
    print("--- one @ reads the whole line ---")
    for inp in ("0", "1", "00", "01", "10", "11"):
        stk, out = stack_after("@", inp)
        print(f"  input {inp!r:5} -> stack {stk} out {out!r}")

    print("\n--- so a two-bit program reads once; does the sum gate? ---")
    for src in ("o v49 @ v50", "o v97 @ v99", "o v98 @ v99"):
        rows = [go(src, b0 + b1)[0] for b0 in "01" for b1 in "01"]
        print(f"  {src!r:14} -> {rows}")


if __name__ == "__main__":
    main()
