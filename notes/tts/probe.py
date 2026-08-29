"""Probe The Temporary Stack's output claim from docs/walls.md.

The walls entry says an input-dependent ``'0'``/``'1'`` is impossible: the
auto-drain prints ``front - 1`` for the oldest element when
``sum(rest) / 2 > front``, so printing 48/49 needs the input to select a
49/50 constant, but "the only value-to-length conversion -- the front element
popping -- requires ``front < input / 2 < 24``, so the front is at most 24
and prints garbage".

Two things that argument does not address, and which this probes:

* ``v`` pushes an *arbitrary* integer parsed from the word's digits, so a
  49 or 50 constant does not have to be built by conversion at all.
* ``o``/``O`` select byte mode, where the drain prints ``chr(n)`` rather
  than the number, so the printed character and the stack value are
  different questions.
"""


from tts_interp import State


def go(source, inp="", limit=2000):
    """Run ``source``; return (output, status)."""
    from esolangs.interpreters.io import ScriptedIO

    out_io = ScriptedIO(inp)
    state = State(io=out_io)
    state.code = source.split()
    steps = 0
    try:
        while not state.halted and steps < limit:
            state.step()
            steps += 1
    except Exception as exc:
        return out_io.getvalue(), f"exc:{type(exc).__name__}"
    if not state.halted:
        return out_io.getvalue(), "loop"
    return out_io.getvalue(), "halt"


def main():
    """Try to print a bare '0' and a bare '1' at all."""
    print("--- numeric mode: can the drain print 0 or 1? ---")
    for src in ("v1 v99", "v2 v99", "v1 v9 v9", "v2 v9 v9"):
        print(f"  {src!r:16} -> {go(src)}")

    print("--- byte mode: does O make the drain print chr(n)? ---")
    for src in ("O v49 v999", "O v50 v999", "O v49 v9 v9 v9"):
        print(f"  {src!r:18} -> {go(src)}")


if __name__ == "__main__":
    main()
