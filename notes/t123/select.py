"""Search for a 123 selector: one embedded bit choosing between two outputs.

``param.py`` showed the naive splice loops -- the digit printers halt only as
whole programs, and embedding one leaves the pointer where the end-of-code
check restarts instead of halting.  So rather than splicing hand-built parts,
search over templates directly: a template is a string containing ``{X0}``,
instantiated with a same-width setter, and it succeeds when the two
instantiations print two *different* single characters and both halt.

That is the weakest useful form of input dependence: a one-input, two-valued
program built by substitution.  If even this is unreachable the parameterized
wall stands on a real obstruction; if it lands, the wall's output argument is
finished and a full generator is a matter of scaling.
"""

import itertools
import sys

from lib import run

# A same-width setter: '1' flips the bit under the pointer (and moves left);
# '3' below location 0 is a control-flow no-op of the same width, but at
# pos >= 0 it branches, so the neutral filler is chosen per placement.
SETTERS = (("1", "2"), ("1", "3"))


def instantiate(template, bit, setter):
    """Substitute ``{X0}`` with the one- or zero-setter."""
    return template.replace("{X0}", setter[bit])


def main():
    """Sweep templates for a one-input selector printing two distinct bytes."""
    max_len = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    for setter in SETTERS:
        print(f"=== setter one={setter[1]!r} zero={setter[0]!r} ===", flush=True)
        for length in range(1, max_len + 1):
            hits = []
            for body in itertools.product("123", repeat=length):
                # place {X0} at every position in the body
                for slot in range(length + 1):
                    tpl = "".join(body[:slot]) + "{X0}" + "".join(body[slot:])
                    outs = []
                    ok = True
                    for bit in (0, 1):
                        out, status = run(instantiate(tpl, bit, setter), "", limit=3000)
                        if status != "halt" or len(out) != 1:
                            ok = False
                            break
                        outs.append(out)
                    if ok and outs[0] != outs[1]:
                        hits.append((tpl, outs))
            if hits:
                print(
                    f"  length {length}: {len(hits)} selectors, e.g. {hits[:3]}",
                    flush=True,
                )
                return
            print(f"  length {length}: none", flush=True)


if __name__ == "__main__":
    main()
