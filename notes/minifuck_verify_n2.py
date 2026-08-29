"""Verify every generated n=2 template on the shipped interpreter.

The generator checks itself against its own simulator; this checks the
simulator against the real thing, and asserts the equal-length property that
keeps a program from leaking its inputs through ``len``.
"""

import pathlib
import sys

_HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(_HERE))
sys.path.insert(0, str(_HERE.parent / "src"))

from minifuck_combined import build  # noqa: E402
from minifuck_joint_sim import setter  # noqa: E402

from esolangs.interpreters.io import ScriptedIO  # noqa: E402
from esolangs.interpreters.tape_based.minifuck import _Machine  # noqa: E402


def run(code, cap=5_000_000):
    """Run `code` on the shipped interpreter and return what it printed."""
    io = ScriptedIO("")
    machine = _Machine(code, io)
    steps = 0
    while not machine.halted and steps < cap:
        machine.step()
        steps += 1
    return io.getvalue()


def instantiate(template, bits):
    """Fill every `{Xi}` with the setter for that input bit."""
    for i, bit in enumerate(bits):
        template = template.replace("{X" + str(i) + "}", setter(bit))
    return template


def main():
    """Generate and verify all 16 two-input tables; return an exit status."""
    failures = []
    for t in range(16):
        table = f"{t:04b}"
        try:
            template = build(table)
        except ValueError:
            failures.append((table, "not generated"))
            print(f"{table}: NOT GENERATED")
            continue
        printed, lengths = [], set()
        for row in range(4):
            bits = [(row >> (1 - k)) & 1 for k in range(2)]
            code = instantiate(template, bits)
            lengths.add(len(code))
            printed.append(run(code))
        ok = printed == list(table) and len(lengths) == 1
        if not ok:
            failures.append((table, f"{''.join(printed)} lengths={lengths}"))
        print(
            f"{table}: printed {''.join(printed)!r} lengths={lengths} "
            f"{'OK' if ok else 'FAIL'}"
        )
    print(
        f"\n{16 - len(failures)}/16 verified on the real interpreter"
        if not failures
        else f"\n{16 - len(failures)}/16 verified; failures: {failures}"
    )
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
