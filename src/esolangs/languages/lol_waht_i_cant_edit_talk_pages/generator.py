"""lol waht i cant edit talk pages Boolean generator: a decision tree.

Each level reads the one variable ``x``, then a while-equal loop on ``1``
runs the one arm and ends in ``waht i got banned``; the zero arm follows
unguarded and runs only when that loop was skipped.  Leaves print through the
signature line ``0 --tommyaweosme``, needing no variable. An identity
node on the final input instead reads and prints ``x`` directly.

Size:
    O(T) lines; n=4 parity: 1222 chars

Decisions:
    A halt ends the one arm, where two guarded loops each ended in a bump:
    it drops the zero loop and both bumps ([ablations.halt_arm]).  One shared
    variable suffices: the zero arm tests nothing, so the one arm's reads
    cannot disturb it.
"""

from esolangs.generation.helpers import _validate_truth_table
from esolangs.generation.requests import GenerationRequest
from esolangs.runtime._program import Program

_READ = "im awesome tottaly but no x"


def _branch(zero: tuple[str, ...], one: tuple[str, ...]) -> tuple[str, ...]:
    """Drain an ignored selector, or terminate the one arm before the zero arm."""
    # The fold interns truth subtables, so identical children share one object.
    if zero is one:
        return (_READ, *zero)
    return (
        _READ,
        "JUST LET ME CHANGE 1 MESSAGE ON x {",
        *one,
        "waht i got banned",
        "}",
        *zero,
    )


def lol_waht_i_cant_edit_talk_pages(truth_table: str) -> str:
    """Build a program printing ``truth_table[row]`` for the inputs."""
    # Decision-module initialization cut cold constants to 0.80x throughput.
    if (
        isinstance(truth_table, str)
        and truth_table
        and truth_table.count(truth_table[0]) == len(truth_table)
    ):
        n = _validate_truth_table(truth_table)
        return "\n".join(["user:x", *([_READ] * n), f"{truth_table[0]} --tommyaweosme"])
    from esolangs.generation.decision import fold_subtables

    terminals = {
        "0": ("0 --tommyaweosme",),
        "1": ("1 --tommyaweosme",),
        "01": (_READ, "i hate u x"),
    }
    body = fold_subtables(truth_table, terminals, _branch)
    return "\n".join(("user:x", *body))


def lol_waht_i_cant_edit_talk_pages_request(request: GenerationRequest) -> Program:
    """Emit source through the declared generation request interface."""
    return lol_waht_i_cant_edit_talk_pages(request.table)
