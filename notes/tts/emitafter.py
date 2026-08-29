r"""Inspect what a surviving row leaves and which emitter fires on it.

An earlier gate+emitter sweep reached only the constants, which means the emitter is
not behaving as a fresh start: the gate's own drain has already reshaped the
stack, so appending words continues an existing computation rather than
beginning a new one.

This inspects the post-gate stack per row instead of guessing emitters.
"""

from tts_interp import State

from esolangs.interpreters.io import ScriptedIO

GATE = "o v98 @ v0 v99"


def stack_after(source, inp, limit=800):
    """Return (stack, output, outcome) after running ``source``."""
    from esolangs.exceptions import HaltError

    io_obj = ScriptedIO(inp)
    state = State(io=io_obj)
    state.code = source.split()
    steps = 0
    try:
        while not state.halted and steps < limit:
            state.step()
            steps += 1
    except HaltError:
        return list(state.stk), io_obj.getvalue(), "died"
    return list(state.stk), io_obj.getvalue(), "halt"


def main():
    """Show the per-row post-gate state, and the word counter that resets."""
    print(f"gate = {GATE!r}")
    for a in "01":
        for b in "01":
            stk, out, outcome = stack_after(GATE, a + b)
            print(f"  {a}{b}: stack={stk} out={out!r} {outcome}")

    print("\n--- the 15-word reset clears the stack; where is the counter? ---")
    for n in (1, 2, 3):
        pad = " ".join(["#"] * n)
        src = f"{GATE} {pad}"
        outs = [stack_after(src, f"{a}{b}")[2] for a in "01" for b in "01"]
        print(f"  +{n} pad words -> {outs}")


if __name__ == "__main__":
    main()
