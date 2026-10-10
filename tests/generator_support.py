"""Generator round-trip checks for the development suite."""

from itertools import pairwise

import esolangs
from esolangs._evaluate import _DEFAULT, _Default, _evaluate
from esolangs.interpreters.io import ScriptedIO
from esolangs.tools.helpers import TEMPLATE_CHAR, fill_runs
from tests.stdin_check import _validate_shape_for_evaluate
from tests.witness_tables import parity, row_bits


def evaluate_generated(
    language: str,
    table: str,
    timeout: float | _Default | None = _DEFAULT,
    width: int | None = None,
    *,
    isolated: bool = False,
) -> str:
    """Generate a table's program, then evaluate its observed answers."""
    inputs = _validate_shape_for_evaluate(table)
    program = esolangs.generate(language, table, width=width)
    return _evaluate(language, program, timeout, inputs=inputs, isolated=isolated)


def verify_generated(
    language: str,
    table: str,
    timeout: float | _Default | None = _DEFAULT,
    width: int | None = None,
    *,
    isolated: bool = False,
) -> bool:
    """Compare a generator's observed table with its requested table."""
    return (
        evaluate_generated(language, table, timeout, width, isolated=isolated) == table
    )


#: What a coverage failure for a new language says to do: ``check`` names
#: the file and the entry, so the messages need not repeat it.
CHECK = "`just check-language <name>` names the entry to add"


def assert_an_ignored_input_costs(name: str, n: int, cost: int) -> None:
    """An input the table ignores adds ``cost`` characters, read and dropped.

    Lifted at every position from an ``n``-input one-hot table.  A lookup
    indexed by the essential inputs still reads the ignored one; it used to
    grow as much as a real input, the table doubled over the bit.
    """
    from esolangs.registry import LANGUAGES

    inner = "".join(str(int(row.bit_count() == 1)) for row in range(2**n))
    build = LANGUAGES[name].boolean
    assert build is not None
    for at in (0, n // 2, n):
        low = n - at
        table = "".join(
            inner[row >> (low + 1) << low | row & ((1 << low) - 1)]
            for row in range(2 * len(inner))
        )
        assert len(build(table)) - len(build(inner)) == cost, at
    assert evaluate_generated(name, table, timeout=30) == table


def overruns(name: str, table: str) -> tuple[int, int]:
    """Return how many widths a layout overran, and by the worst margin."""
    counted = [
        max(len(line) for line in esolangs.generate(name, table, width=w).splitlines())
        - w
        for w in range(1, 124, 4)
    ]
    over = [margin for margin in counted if margin > 0]
    return len(over), max(over, default=0)


def assert_parity_at_most_doubles(generator, arities, slack=0):
    """A parity table's source at most doubles per input, plus ``slack``."""
    sizes = [len(generator(parity(n))) for n in arities]
    assert all(b <= 2 * a + slack for a, b in pairwise(sizes)), sizes


def run_filled(run, template: str, setters, row: int, n: int, char: str = "") -> str:
    """Fill ``template`` with row ``row``'s ``n`` bits, run it, return its output."""
    io = ScriptedIO("")
    run(fill_runs(template, char or TEMPLATE_CHAR, setters, row_bits(row, n)), io)
    return io.getvalue()


def run_lines(run, program: str, bits: str) -> tuple[str, int]:
    """Run a grid ``program`` on ``bits``; return its output and reads."""
    io = ScriptedIO(bits)
    run(program.splitlines(), io)
    return io.getvalue(), io.reads


def assert_constant_balanced_shape(language, language_id, table, legacy):
    """Check that a projected constant retains its legacy balanced shape."""
    from esolangs.tools.wrap import balance_program, balance_score

    assert balance_score(
        esolangs.generate(language, table, balance=True)
    ) <= balance_score(balance_program(legacy, language_id))


def assert_shared_program(
    language, table, plain, command_bound, workspace_bound, *, size=len, rows=None
):
    """Execute shared-program rows and check commands and written state."""
    from esolangs.debugger import make_vm
    from scripts.benchmark import WrittenState

    n = len(table).bit_length() - 1
    program = esolangs.generate(language, table)
    assert size(program) < size(plain)
    parameterized = esolangs.describe(language)["parameterized"]
    for row in range(len(table)) if rows is None else rows:
        expected = table[row]
        bits = [int(bit) for bit in format(row, f"0{n}b")]
        source = (
            esolangs.instantiate(language, program, bits) if parameterized else program
        )
        stdin = (
            ""
            if parameterized
            else esolangs.encode_inputs(language, bits, truth_table=table)
        )
        machine = make_vm(language, source, stdin=stdin)
        written = WrittenState(machine.snapshot())
        commands = 0
        while not machine.halted and commands <= command_bound:
            machine.step()
            written.sample(machine.snapshot())
            commands += 1
        assert machine.halted
        if machine.dumps_on_the_post_halt_step:
            machine.step()
            written.sample(machine.snapshot())
            commands += 1
        assert esolangs.read_answer(language, machine.output) == expected
        assert commands <= command_bound
        assert written.bits <= workspace_bound(program)
