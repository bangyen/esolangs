r"""Every command shown in the docs is a claim; this runs them."""

from __future__ import annotations

import importlib
import pathlib
import re
import shutil
import subprocess
import sys

import pytest

from esolangs.cli import HELP, USAGE
from esolangs.registry import LANGUAGES

ROOT = pathlib.Path(__file__).parents[1]

# : ``<`` or ``>`` marks a.
# : ``> name.txt`` and is a.
_PLACEHOLDER = re.compile(r"<\w|\w>")
_LANGUAGES = {name.lower(): name for name in LANGUAGES}


def _documents() -> dict[str, str]:
    r"""Return every document that can contain a command."""
    found = {"README.md": (ROOT / "README.md").read_text(), "usage": USAGE}
    for name, text in HELP.items():
        found[f"{name} --help"] = text
    # Recursive: a doc moved into a.
    # sweep.
    # files sharing a name in.
    for doc in sorted((ROOT / "docs").rglob("*.md")):
        found[str(doc.relative_to(ROOT))] = doc.read_text()
    return found


def _commands(text: str) -> list[tuple[str, str | None]]:
    r"""Return the concrete commands in ``text``, with any stated output."""
    out: list[tuple[str, str | None]] = []
    for line in text.splitlines():
        command = line.strip().removeprefix("$ ").strip()
        expected: str | None = None
        if "->" in command:
            command, _, stated = command.partition("->")
            command, expected = command.strip(), stated.strip()
        if command.startswith("esolangs ") and not _PLACEHOLDER.search(command):
            out.append((command, expected))
    return out


def _language_in(command: str) -> str | None:
    r"""Return the language a command names, if any."""
    for token in re.findall(r'"[^"]+"|\S+', command):
        bare = token.strip('"')
        if bare.lower() in _LANGUAGES:
            return _LANGUAGES[bare.lower()]
    return None


@pytest.mark.slow
@pytest.mark.parametrize("where", sorted(_documents()))
def test_every_documented_command_runs(where: str, tmp_path: pathlib.Path) -> None:
    r"""Run one document's commands, in order, in a scratch directory."""
    commands = _commands(_documents()[where])
    if not commands:
        pytest.skip(f"{where} shows no concrete commands")
    work = tmp_path / "work"
    work.mkdir()
    produced: set[str] = set()
    failures = []
    for command, expected in commands:
        language = _language_in(command)
        # A file the example expects to.
        # line here created, is stood.
        for filename in re.findall(r"\b[\w.-]+\.txt\b", command):
            if filename not in produced and language is not None:
                (work / filename).write_text(
                    subprocess.run(
                        [
                            sys.executable,
                            "-m",
                            "esolangs",
                            "generate",
                            language,
                            "0110",
                        ],
                        capture_output=True,
                        text=True,
                        check=True,
                    ).stdout
                )
        stdin_text = ""
        if language is not None and "|" not in command:
            encoded = subprocess.run(
                [sys.executable, "-m", "esolangs", "encode", language, "10"],
                capture_output=True,
                text=True,
                check=False,
            )
            stdin_text = encoded.stdout if encoded.returncode == 0 else ""
        shell = command.replace("esolangs ", f"{sys.executable} -m esolangs ")
        result = subprocess.run(
            shell,
            shell=True,
            capture_output=True,
            text=True,
            timeout=120,
            cwd=work,
            input=stdin_text,
            check=False,
        )
        produced.update(re.findall(r">\s*([\w.-]+\.txt)", command))
        if result.returncode != 0:
            first = result.stderr.strip().splitlines()
            failures.append(
                f"{command}\n    rc={result.returncode} {first[0] if first else ''}"
            )
        elif expected is not None and result.stdout.strip() != expected:
            failures.append(
                f"{command}\n    says it prints {expected!r}, printed "
                f"{result.stdout.strip()!r}"
            )
    assert not failures, f"in {where}:\n" + "\n".join(failures)
    shutil.rmtree(work, ignore_errors=True)


def test_the_documents_really_do_contain_commands() -> None:
    r"""A parser that matched nothing would make every case above vacuous."""
    parsed = [c for text in _documents().values() for c in _commands(text)]
    assert len(parsed) >= 20, f"only {len(parsed)} documented commands found"
    # And at least one example.
    # arrow-checking half of the.
    assert [c for c in parsed if c[1] is not None]


# : A ``\`\`test_name\`\`\``.
_CITATION = re.compile(r"``(test_[a-z_0-9]+)``")

#: A test definition.
_DEFINITION = re.compile(r"^\s*def (test_[a-z_0-9]+)", re.M)

_ROOT = pathlib.Path(__file__).parents[1]


def test_every_test_a_docstring_names_still_exists() -> None:
    r"""A citation to a renamed or deleted test is worse than none."""
    cited: dict[str, list[str]] = {}
    for path in sorted((_ROOT / "src").rglob("*.py")):
        for name in _CITATION.findall(path.read_text()):
            cited.setdefault(name, []).append(str(path.relative_to(_ROOT)))
    defined = {
        name
        for path in (_ROOT / "tests").rglob("*.py")
        for name in _DEFINITION.findall(path.read_text())
    }
    missing = {name: where for name, where in cited.items() if name not in defined}
    assert not missing, "docstrings name tests that do not exist: " + "; ".join(
        f"{name} (in {', '.join(where)})" for name, where in sorted(missing.items())
    )
    # A regex that stopped matching.
    assert len(cited) >= 15, f"only {len(cited)} citations found"


# : A fully-qualified reference.
_QUALIFIED_REF = re.compile(
    r":(?:func|class|data|meth|attr|exc):`~?(esolangs\.[\w.]+)`"
)


def test_every_qualified_reference_resolves() -> None:
    r"""A ``:func:`esolangs.a.b.c`` pointing at nothing."""
    targets: dict[str, set[str]] = {}
    for path in sorted((_ROOT / "src").rglob("*.py")):
        for target in _QUALIFIED_REF.findall(path.read_text()):
            targets.setdefault(target, set()).add(str(path.relative_to(_ROOT)))

    def resolves(target: str) -> bool:
        parts = target.split(".")
        for split in range(len(parts) - 1, 0, -1):
            try:
                obj: object = importlib.import_module(".".join(parts[:split]))
            except ImportError:
                continue
            for name in parts[split:]:
                obj = getattr(obj, name, None)
                if obj is None:
                    break
            else:
                return True
        return False

    broken = {t: w for t, w in targets.items() if not resolves(t)}
    assert not broken, "references that resolve to nothing: " + "; ".join(
        f"{t} (in {', '.join(sorted(w))})" for t, w in sorted(broken.items())
    )
    # A regex that stopped matching.
    assert len(targets) >= 40, f"only {len(targets)} qualified references found"
