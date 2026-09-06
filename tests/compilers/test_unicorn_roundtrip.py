"""Execute every compiler's output as RISC-V machine code and check it.

The sweep in ``test_assembly_compilers`` checks that a compiler emits
*assembly*; the goldens there pin exactly which assembly.  Neither can see a
compiler whose output assembles, runs, and computes the wrong thing -- and
a golden is only as good as the day it was regenerated, since a deliberate
codegen change updates it by definition.  This module is the check that
survives that: it assembles each compiler's output and runs it under
unicorn, comparing what the program *printed* against a hand-chosen
expectation.

The cases are ``scripts/verify_riscv_unicorn.py``'s own ``COMPILER_CASES``,
imported rather than copied so the two cannot drift.  That script keeps
running them as part of ``scripts/verify.py``; this module makes the same
round-trip visible to pytest, which is what lets the mutation harness use
it as a kill test.  Measured on ``jaune``, the round-trip kills roughly a
quarter of the mutants that survive the pytest suite alone.

Marked ``unicorn`` rather than ``slow``: the mutation harness deselects slow
tests, and these are the only tests that can see a compiler emitting
working-but-wrong code, so folding them into ``slow`` would remove them from
the one run that most needs them.  ``just test-quick`` deselects this marker
by name instead.

Skipped whole when unicorn or the RISC-V cross-compiler is missing, the same
condition ``verify.py`` applies -- so the suite still passes on a machine
without the toolchain, and says why it was skipped rather than going quiet.
"""

import importlib
import shutil
import sys
from pathlib import Path

import pytest

# ``verify_riscv_unicorn`` imports ``riscv_elf_runner`` flatly, so scripts/
# has to lead sys.path for both to resolve.  Anchored to this file's parents
# rather than the working directory: the mutation harness runs these tests
# from a copied work directory, where a cwd-relative path would miss.
_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

_HAVE_UNICORN = importlib.util.find_spec("unicorn") is not None
_HAVE_GCC = (
    shutil.which("riscv64-elf-gcc") is not None
    or shutil.which("riscv64-linux-gnu-gcc") is not None
)

pytestmark = [
    pytest.mark.unicorn,
    pytest.mark.skipif(
        not (_HAVE_UNICORN and _HAVE_GCC),
        reason="needs unicorn and a RISC-V cross-compiler",
    ),
]


def _cases() -> list[tuple[str, str, str, str, str]]:
    """Return the shared compiler cases, normalised to a fixed-width tuple.

    Imported lazily so that collection on a machine without the toolchain
    costs nothing and cannot fail: the module-level import in
    ``verify_riscv_unicorn`` reaches ``riscv_elf_runner``, which imports
    unicorn.
    """
    if not (_HAVE_UNICORN and _HAVE_GCC):
        return []
    module = importlib.import_module("verify_riscv_unicorn")
    # The fifth element is optional in the source table -- only the
    # stdin-reading backends carry one -- so it is defaulted here rather
    # than at every use.
    return [
        (name, mod, source, expected, rest[0] if rest else "")
        for name, mod, source, expected, *rest in module.COMPILER_CASES
    ]


_CASES = _cases()


# The case's own name rides in the test id rather than as a parameter: it
# labels the case for a reader and is not something the test asserts on.
@pytest.mark.parametrize(
    ("module", "source", "expected", "stdin"),
    [case[1:] for case in _CASES],
    ids=[f"{name}-{i}" for i, (name, *_) in enumerate(_CASES)],
)
def test_compiled_output_runs_correctly(
    module: str, source: str, expected: str, stdin: str
) -> None:
    """Each compiler's output prints what the source program means."""
    from riscv_elf_runner import assemble_source, run_elf

    comp = importlib.import_module(f"esolangs.compilers.{module}").comp
    binary = assemble_source(comp(source))
    # latin-1 on both sides: the emulated program writes bytes, and UTF-8
    # would expand 0x80+ to multiple bytes that no single-byte output can
    # match.
    out, _ = run_elf(binary, stdin.encode("latin-1"))
    assert out == expected.encode("latin-1")


def test_every_registered_compiler_is_round_tripped() -> None:
    """No registered backend escapes the round-trip.

    The failing direction, matching ``check_compilers.py``: a new compiler
    that nobody adds a case for fails this test rather than being silently
    unverified.  ``verify_riscv_unicorn.main`` makes the same check, so this
    pins it for the pytest run too.
    """
    from esolangs.registry import COMPILERS

    covered = {module for _, module, *_ in _CASES}
    assert set(COMPILERS.values()) - covered == set()
