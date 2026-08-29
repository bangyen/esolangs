r"""Generate every affine two-input table by construction.

``affine_gen.py`` lands XOR and XNOR.  The remaining affine tables follow by
choosing, per input, whether its setter lands on the answer bit:

* an input embedded **at location 7** toggles the answer with its bit
  (``12`` flips location 7, ``21`` flips location 8 and is inert);
* an input embedded **anywhere past location 8** is inert either way, since
  ``byte()`` reads only locations 0-7 -- so the table ignores it.

So the reachable set is exactly ``answer = c XOR (subset of the inputs)``:
the eight affine functions, which for two inputs are const0, const1, b0,
b1, NOT b0, NOT b1, XOR and XNOR.  Each input is still embedded exactly once
whichever role it takes, and both instantiations of a setter are two
characters wide.
"""

from affine import instantiate, run
from affine_gen import PRE_ONE, PRE_ZERO, prologue, walk_and_print

NAMES = {
    ("0", "1", "1", "0"): "XOR", ("1", "0", "0", "1"): "XNOR",
    ("0", "0", "1", "1"): "b0", ("1", "1", "0", "0"): "NOT b0",
    ("0", "1", "0", "1"): "b1", ("1", "0", "1", "0"): "NOT b1",
    ("0", "0", "0", "0"): "const0", ("1", "1", "1", "1"): "const1",
}


def build(pre_value, live):
    """Assemble a template; ``live`` says which inputs touch the answer bit.

    A live input is embedded at location 7, where its setter toggles the
    answer.  An inert input is embedded two cells further right, past the
    byte, so it is placed exactly once but cannot affect the output.
    """
    parts = [prologue(pre_value)]
    inert = []
    for i in (0, 1):
        if i in live:
            parts.append("{X" + str(i) + "}")
        else:
            inert.append(i)
    if inert:
        # step right past the byte, embed the inert inputs, then step back
        parts.append("22")
        for i in inert:
            parts.append("{X" + str(i) + "}")
        parts.append("11")
    parts.append(walk_and_print())
    return "".join(parts)


def table_of(template):
    """Return the four printed characters, or None if a row misbehaves."""
    rows = []
    for r in range(4):
        bits = [(r >> 1) & 1, r & 1]
        out, halted = run(instantiate(template, bits))
        if not halted or out is None or len(out) != 1:
            return None
        rows.append(out)
    return tuple(rows)


def main():
    """Emit and verify a template for each affine table."""
    found = {}
    for pre in (PRE_ZERO, PRE_ONE):
        for live in ((0, 1), (0,), (1,), ()):
            tpl = build(pre, live)
            tbl = table_of(tpl)
            if tbl in NAMES and NAMES[tbl] not in found:
                found[NAMES[tbl]] = (tpl, tbl)
    print(f"affine tables constructed: {len(found)}/8\n")
    for name in ("const0", "const1", "b0", "NOT b0", "b1", "NOT b1",
                 "XOR", "XNOR"):
        if name in found:
            tpl, tbl = found[name]
            print(f"  {name:8} {''.join(tbl)}  {tpl!r}")
        else:
            print(f"  {name:8} -- not constructed")


if __name__ == "__main__":
    main()
