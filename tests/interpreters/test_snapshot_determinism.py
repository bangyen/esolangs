"""One program, run twice in one process, snapshots the same both times.

The cycle detector and the workspace ledger trust that equal states give
equal snapshots.  A snapshot built from ``id()`` breaks that quietly: Forbin
numbered scopes by their locals' ids, a binding freed the old mapping, and a
recycled id handed its serial to a new one, so 11 of 5,197 programs gave two
snapshot sequences.  Only the trace diff's large random corpus reached those
programs; samples and small tables did not, so this runs it, weekly.
"""

import pytest

from esolangs.registry import LANGUAGES
from esolangs.vm import make_vm
from tests.support.samples import SAMPLES
from tests.tooling.script_support import REPO_ROOT, load

tracediff = load(REPO_ROOT / "scripts" / "tracediff.py")

#: Steps traced per program, as the trace diff does.
_LIMIT = tracediff.LIMIT


def _programs(name: str) -> list[tuple[object, str]]:
    """The trace diff's corpus, plus the suite sample (a raster one included)."""
    return [SAMPLES[name], *tracediff.corpus(name)]


def _snapshots(name: str, program: object, stdin: str) -> list[object]:
    out: list[object] = []
    try:
        vm = make_vm(name, program, stdin=stdin)  # type: ignore[arg-type]
        for _ in range(_LIMIT):
            out.append(vm.snapshot())
            if vm.halted:
                break
            vm.step()
    except Exception as error:  # an error is part of the run
        out.append((type(error).__name__, str(error)))
    return out


@pytest.mark.slow
@pytest.mark.weekly
@pytest.mark.cost_evidence("Forbin's id()-keyed scope serials (cf5c8d203)")
@pytest.mark.parametrize("name", sorted(LANGUAGES))
def test_a_program_snapshots_the_same_on_a_second_run(name: str) -> None:
    held = []
    differ = []
    for program, stdin in _programs(name):
        first = _snapshots(name, program, stdin)
        # Keep garbage alive between runs, so the allocator hands out
        # different addresses the second time.
        held.append([object() for _ in range(64)])
        if _snapshots(name, program, stdin) != first:
            differ.append(program)
    assert not differ, f"{len(differ)} programs differ, e.g. {differ[0]!r:.200}"
