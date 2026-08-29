r"""Check the claim that every death is either input-independent or noisy.

Under emission-vs-silence, inverting a gate needs a death that prints
nothing.  A death happens when a popped value leaves the byte-mode range,
and the argument is that such a death can never be both silent and
input-gated:

* a *silent* death must happen on the very first pop, since any deeper pop
  prints the values above the killer on its way down -- and a printing death
  is an emission, so it does not invert anything;
* the first pop's condition is ``sum(tail) / 2 > front`` with ``front`` the
  killer.  A killer that dies immediately has ``front <= 0``, so the
  condition is ``sum(tail) / 2 > 0``, which holds whenever the tail carries
  any positive value -- and once input has landed the tail always does.
  So a depth-1 kill fires on every row, input-independently.

This checks both halves against the interpreter.
"""

from invert import run_detail

NL = chr(10)


def main():
    """Test that depth-1 kills are unconditional and deeper kills print."""
    print("--- depth-1 kill: front 0, fires on every row? ---")
    for src in ("o v0 @ v99", "o v0 @ @ v99", "o v0 @ v1"):
        outs = [run_detail(src, f"{a}{NL}{b}") for a in "01" for b in "01"]
        print(f"  {src!r:16} -> outcomes {[o[1] for o in outs]} "
              f"outputs {[o[0] for o in outs]}")

    print("\n--- deeper kill: does it print on the way down? ---")
    for src in ("o v98 @ v0 v99", "o v97 @ v0 v99"):
        outs = [run_detail(src, f"{a}{b}") for a in "01" for b in "01"]
        for (out, outcome), row in zip(
                outs, ("00", "01", "10", "11"), strict=True):
            if outcome == "died":
                print(f"  {src!r} row {row}: died having printed {out!r}")


if __name__ == "__main__":
    main()
