"""Generator round-trip checks for the development suite."""

import random
from itertools import pairwise
from math import isqrt

import esolangs
from esolangs.generation.helpers import TEMPLATE_CHAR, fill_runs
from esolangs.registry._certification import load as load_certification
from esolangs.runtime.io import ScriptedIO
from esolangs.vm import _capture_workspace
from tests.support.evaluation import _DEFAULT, _Default, _evaluate
from tests.support.event_io import ReadFirstIO
from tests.support.witness_tables import parity, row_bits


def assert_every_row(
    language: str, table: str, *, program: esolangs.Program | None = None
) -> None:
    """Check every row through the public I/O contract, generating when omitted."""
    n = len(table).bit_length() - 1
    if program is None:
        program = esolangs.generate(language, table)
    for row in range(len(table)):
        bits = [(row >> (n - 1 - i)) & 1 for i in range(n)]
        stdin = esolangs.encode_inputs(language, bits)
        got = esolangs.run(language, program, stdin=stdin, timeout=5)
        assert esolangs.read_answer(language, got) == table[row], (table, row)


def assert_native_rows(
    language, table, program, run, *, sentinel="7", token=False, count_whitespace=False
):
    """Check native answers, read-before-write ordering and the following record."""
    n = len(table).bit_length() - 1
    for row, expected in enumerate(table):
        stdin = esolangs.encode_inputs(language, row_bits(row, n))
        io = ReadFirstIO(
            stdin + sentinel, expected=len(stdin.rstrip()) if count_whitespace else n
        )
        run(program, io)
        got = io.getvalue()
        assert io.past_end == 0
        if token:
            assert io.input_token() == sentinel.strip()
        else:
            assert io.input_char() == ord(sentinel)
        assert esolangs.read_answer(language, got) == expected, (table, row)


def assert_proved_resource_cap(name: str) -> None:
    """Require a declared cap backed by a language-wide scaling obstruction."""
    from esolangs.registry import LANGUAGES
    from tests.proofs._roadmap import load

    lang = LANGUAGES[esolangs.resolve(name)]
    row = load().by_name().get(lang.name)
    assert row is not None
    assert row.totality == "Cap"
    assert row.output_size == "Language lower bound"
    assert lang.backend.restrictions


def probe_table(name: str, default: str = "0110") -> str:
    """Use a compact executable witness when a proved cap forbids the corpus."""
    from esolangs.registry import LANGUAGES

    lang = LANGUAGES[esolangs.resolve(name)]
    if load_certification(lang).benchmark_tables:
        assert_proved_resource_cap(name)
        return next(
            table
            for table in load_certification(lang).benchmark_tables
            if "0" in table and "1" in table
        )
    return default


def multiple_tables() -> list[str]:
    """A fixed corpus of 128-bit truth tables for residual-structure tests.

    Two structured tables plus six seeded random ones, so the medium-marked
    parametrized tests exercise repeated bands across identical inputs.
    """
    rng = random.Random(88417)
    a, b = "00010111", "01101001"
    four = (
        "0001011101101001",
        "0110100100010111",
        "1010110010001101",
        "1101001010010010",
    )
    return [
        a + b + b + a + a + b + a + b,
        "".join(four[(row // 4 + row % 4) % 4] for row in range(16)),
        *("".join(str(rng.randrange(2)) for _ in range(128)) for _ in range(6)),
    ]


def evaluate_generated(
    language: str,
    table: str,
    timeout: float | _Default | None = _DEFAULT,
    width: int | None = None,
    *,
    isolated: bool = False,
) -> str:
    """Generate a table's program, then evaluate its observed answers."""
    program = esolangs.generate(language, table, width=width)
    inputs = len(table).bit_length() - 1
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
    build = LANGUAGES[name].backend.generate
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


def assert_shared_program(
    language, table, plain, command_bound, workspace_bound, *, size=len, rows=None
):
    """Execute shared-program rows and check commands and written state."""
    from esolangs.debugger import make_vm

    n = len(table).bit_length() - 1
    program = esolangs.generate(language, table)
    assert plain is None or size(program) < size(plain)
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
        commands, written = measure_run(machine, limit=command_bound)
        assert machine.halted
        if machine.dumps_on_the_post_halt_step:
            machine.step()
            written.sample(_capture_workspace(machine))
            commands += 1
        assert esolangs.read_answer(language, machine.output) == expected
        assert commands <= command_bound
        assert written.bits <= workspace_bound(program)


def near_even_counts(size: int) -> set[int]:
    """Return ``size`` and the chunk counts near the divisors of ``size - 1``.

    Those are every count that splits ``size`` items near-evenly: O(sqrt size).
    """
    counts = {size}
    for divisor in range(1, isqrt(size - 1) + 1):
        counts.update((divisor + 1, (size - 1) // divisor + 1))
    return counts


def assert_constant_output(run, code, io, expected, reads, **run_kwargs):
    """Run a constant program; check output and reads without touching its sentinel."""
    run(code, io, **run_kwargs)
    assert io.getvalue() == expected
    assert io.reads == reads
    assert io.past_end == 0


def measure_run(machine, *, limit=None):
    """Return step count and sampled written state, stopping past ``limit``."""
    from scripts.benchmark import WrittenState

    written = WrittenState(_capture_workspace(machine))
    commands = 0
    while not machine.halted and (limit is None or commands <= limit):
        machine.step()
        written.sample(_capture_workspace(machine))
        commands += 1
    return commands, written
