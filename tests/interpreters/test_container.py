"""Unit tests for the Container interpreter."""

from esolangs.interpreters.io import IO
from esolangs.interpreters.other.container import run
from tests.raises import raises_message

HELLO_WORLD = [
    "A:",
    "+1 EXIT>=1",
    "",
    "PRINT:",
    "+1 PRINT<=0",
    "-1 PRINT>=1",
    "",
    "OUT:",
    "+72 A>=0",
    "-115 A>=2",
    "+93 A>=4",
    "-100 A>=6",
    "+103 A>=8",
    "-173 A>=10",
    "+114 A>=11",
    "+0 A>=12",
    "+99 A>=14",
    "-194 A>=16",
    "+205 A>=18",
    "-214 A>=20",
    "+106 A>=21",
    "+0 A>=22",
    "-59 A>=24",
    "",
    "EXIT=1:",
    "-1 A>=24",
]


class TestContainer:
    def test_the_malformed_program_message_reads_exactly(self) -> None:
        """``match=`` only looks for a substring, so pin the whole message."""
        with raises_message(ValueError, "rule line before any container declaration"):
            run(["+1 A>=0"], IO())


class TestPublicAPI:
    def test_run_returns_output_instead_of_exiting(self) -> None:
        """EXIT is a normal halt, so the public API returns the output.

        Container used to call ``sys.exit``, which escaped
        :func:`esolangs.run` as ``SystemExit`` and made the CLI print
        nothing at all.
        """
        import esolangs

        assert esolangs.run("Container", "\n".join(HELLO_WORLD)) == "Hello, world!"
