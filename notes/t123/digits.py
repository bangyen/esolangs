r"""Search for a one-input 123 selector whose two outputs are '0' and '1'.

``select.py`` found selectors at length 7 (``113{X0}1213`` prints ``'@'`` /
``'\\x80'``), so ``3`` genuinely selects between two independent outputs on an
embedded bit.  A boolean generator needs the two outputs to be the ASCII
digits, which is a strictly harder target: the digit printers found by
``witness.py`` are 14 and 28 commands, so the templates here must be long
enough to build 48 and 49, not merely to differ.
"""

import itertools
import sys

from lib import run

SETTER = {0: "1", 1: "2"}


def search(max_len, want=("0", "1")):
    """Sweep templates for one whose instantiations print ``want``."""
    for length in range(1, max_len + 1):
        hits = []
        for body in itertools.product("123", repeat=length):
            base = "".join(body)
            for slot in range(length + 1):
                tpl = base[:slot] + "{X0}" + base[slot:]
                outs = []
                ok = True
                for bit in (0, 1):
                    code = tpl.replace("{X0}", SETTER[bit])
                    out, status = run(code, "", limit=3000)
                    if status != "halt" or len(out) != 1:
                        ok = False
                        break
                    outs.append(out)
                if ok and tuple(outs) in (want, want[::-1]):
                    hits.append((tpl, outs))
        print(
            f"  length {length}: {len(hits)} digit-selectors"
            + (f", e.g. {hits[:3]}" if hits else ""),
            flush=True,
        )
        if hits:
            return hits
    return []


def main():
    """Run the digit-selector sweep."""
    max_len = int(sys.argv[1]) if len(sys.argv) > 1 else 14
    search(max_len)


if __name__ == "__main__":
    main()
