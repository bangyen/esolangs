"""Run every generated template through the shipped interpreter.

The prototype checks itself against its own simulator; this checks the
simulator against the real thing, and asserts the equal-length property that
keeps a program from leaking its inputs through ``len``.
"""

import pathlib
import sys

_HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(_HERE))
sys.path.insert(0, str(_HERE.parent / "src"))

from minifuck_boolean_prototype import emit_program  # noqa: E402
from minifuck_joint_sim import setter  # noqa: E402

from esolangs.interpreters.io import ScriptedIO  # noqa: E402
from esolangs.interpreters.tape_based.minifuck import _Machine  # noqa: E402

TABLES = ("0000", "1000", "1100", "1110", "1111")


def run(code: str, cap: int = 2_000_000) -> str:
    """Run `code` on the shipped interpreter and return what it printed."""
    io = ScriptedIO("")
    machine = _Machine(code, io)
    steps = 0
    while not machine.halted and steps < cap:
        machine.step()
        steps += 1
    return io.getvalue()


def instantiate(template: str, bits: list[int]) -> str:
    """Fill every `{Xi}` with the setter for that input bit."""
    for i, bit in enumerate(bits):
        template = template.replace("{X" + str(i) + "}", setter(bit))
    return template


def main() -> int:
    """Check each table end to end; return a shell exit status."""
    failures = 0
    for table in TABLES:
        template = emit_program(table)
        n = (len(table) - 1).bit_length()
        printed, lengths = [], set()
        for row in range(2**n):
            bits = [(row >> (n - 1 - k)) & 1 for k in range(n)]
            code = instantiate(template, bits)
            lengths.add(len(code))
            printed.append(run(code))
        ok = printed == list(table) and len(lengths) == 1
        failures += not ok
        print(
            f"{table}: printed {''.join(printed)!r} "
            f"lengths={lengths} {'OK' if ok else 'FAIL'}"
        )
    print("all tables verified" if not failures else f"{failures} failed")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
