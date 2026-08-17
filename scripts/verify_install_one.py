"""Verify the single-interpreter installer end to end.

``scripts/install_one.sh`` downloads ``bundle_one.py`` from a base URL and
runs it, which fetches the interpreter plus the shared modules over HTTP and
inlines them into one runnable file.  The unit tests exercise the bundler
against the local checkout, but not the HTTP fetch or the shell wrapper, so
this script serves the repository over a local HTTP server and runs the real
installer against it for a few representative languages.

It is called from CI's ``lint`` job and from ``verify.py`` locally.

Usage:
    python scripts/verify_install_one.py

Requires: curl and python3 on PATH (the installer's own requirements).
"""

import shutil
import subprocess
import sys
import tempfile
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "scripts" / "install_one.sh"

# A language with no dependencies beyond io/exceptions, one with a transitive
# interpreter import, and one that shares the bracket helper.
_LANGUAGES = ("brainfuck", "Factor", "3D Brainfuck")

# (program file contents, expected stdout) per language, run through the
# bundled file.  The programs come from the interpreter unit tests so the
# bundled file must reproduce exactly what the package produces.
_PROGRAMS = {
    "brainfuck": ("++++++++[>++++++++<-]>.", "@"),
    "Factor": ("21666143160021789415877957258569906604219402892572113", "A"),
    "3D Brainfuck": ("+" * 72 + ".", "H"),
}


def _serve() -> ThreadingHTTPServer:
    """Serve the repository root over HTTP on a random localhost port."""

    class _QuietHandler(SimpleHTTPRequestHandler):
        """A handler that does not log each request to stderr."""

        def log_message(self, _format: str, *args: object) -> None:
            pass

    handler = _QuietHandler
    handler.directory = str(ROOT)
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def _install(base: str, language: str, workdir: Path) -> subprocess.CompletedProcess:
    """Run the installer against ``base`` in ``workdir``."""
    env = {"ESOLANGS_BASE": base}
    return subprocess.run(
        ["sh", str(INSTALLER), language],
        cwd=workdir,
        env=env,
        capture_output=True,
        text=True,
    )


def _run_bundle(workdir: Path, program: str) -> str:
    """Run the bundled file (named by the canonical id) on ``program``."""
    bundle = next(workdir.glob("esolangs_*.py"))
    prog = workdir / "prog.txt"
    prog.write_text(program)
    result = subprocess.run(
        [sys.executable, str(bundle), str(prog)],
        capture_output=True,
        text=True,
    )
    return result.stdout


def main() -> int:
    """Install and run a bundled interpreter for each sample language."""
    if shutil.which("curl") is None:
        print("[skip] install-one check: curl not installed")
        return 0
    failures = 0
    server = _serve()
    try:
        base = f"http://127.0.0.1:{server.server_port}"
        for language in _LANGUAGES:
            with tempfile.TemporaryDirectory() as tmp:
                workdir = Path(tmp)
                result = _install(base, language, workdir)
                if result.returncode != 0:
                    print(f"{language}: installer failed: {result.stderr.strip()}")
                    failures += 1
                    continue
                program, expected = _PROGRAMS[language]
                out = _run_bundle(workdir, program)
                if out == expected:
                    print(f"{language}: bundled file runs correctly")
                else:
                    print(f"{language}: bundled output {out!r} != {expected!r}")
                    failures += 1
    finally:
        server.shutdown()
    if failures:
        print(f"install-one check: {failures} failure(s)")
        return 1
    print("install-one check: all languages bundled and ran correctly")
    return 0


if __name__ == "__main__":
    sys.exit(main())
