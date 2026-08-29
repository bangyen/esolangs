"""Build an inverted table: gate -> silent halt -> reset -> unconditional emit.

``silenthalt.py`` confirms an out-of-range pop in byte mode raises HaltError
with no output.  The inversion works by putting an *emitter* after the gate:
rows whose gate fires die on the HaltError and print nothing, while rows
whose gate does not fire fall through and reach the emitter.  That turns any
reachable monotone gate into its complement.

``probe.go`` reports both a HaltError and a clean finish as ``"halt"``,
which hides exactly the distinction the gadget needs, so this module runs
the machine directly and reports the two separately.
"""

from tts_interp import State

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import ScriptedIO

BIG = 0x10FFFF + 2


def run_detail(source, inp, limit=800):
    """Return (output, outcome) with outcome in halt/died/loop."""
    io_obj = ScriptedIO(inp)
    state = State(io=io_obj)
    state.code = source.split()
    steps = 0
    try:
        while not state.halted and steps < limit:
            state.step()
            steps += 1
    except HaltError:
        return io_obj.getvalue(), "died"
    except Exception as exc:
        return io_obj.getvalue(), f"exc:{type(exc).__name__}"
    return io_obj.getvalue(), "halt" if state.halted else "loop"


def table(source, sep=""):
    """Return the four-row emission table (1 = printed something)."""
    out = []
    for b0 in "01":
        for b1 in "01":
            text, _ = run_detail(source, f"{b0}{sep}{b1}")
            out.append(1 if text else 0)
    return tuple(out)


def main():
    """Show the gate dying silently, then invert it with a trailing emitter."""
    print("--- does an out-of-range pop actually stop the program? ---")
    for src in (f"o v{BIG} v9999999", "o v49 @ v50"):
        for inp in ("00", "11"):
            print(f"  {src!r:18} on {inp!r}: {run_detail(src, inp)}")

    print("\n--- gate then emitter: the complement of the gate ---")
    emitter = "O v2 v99"
    for gate in (f"o v{BIG} @ v99", f"o v{BIG} @ v999"):
        src = f"{gate} {emitter}"
        print(f"  {src!r}")
        print(f"     table {table(src)}")


if __name__ == "__main__":
    main()
