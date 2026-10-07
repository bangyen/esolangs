"""Documented commands, links and the README example execute as written."""

from __future__ import annotations

import importlib
import pathlib
import re
import shutil
import subprocess
import sys
from functools import cache
from urllib.parse import unquote

import pytest

from esolangs import generate, run
from esolangs.cli import HELP, USAGE
from esolangs.registry import LANGUAGES

ROOT = pathlib.Path(__file__).parents[1]

#: ``<`` or ``>`` marks a placeholder, except in a shell redirect, which is
#: ``> name.txt`` and is a real part of a real command.
_PLACEHOLDER = re.compile(r"<\w|\w>")
_LANGUAGES = {name.lower(): name for name in LANGUAGES}


def _documents() -> dict[str, str]:
    """Return every document that can contain a command."""
    found = {"README.md": (ROOT / "README.md").read_text(), "usage": USAGE}
    for name, text in HELP.items():
        found[f"{name} --help"] = text
    # Recursive: a doc moved into a subfolder must not silently leave this
    # sweep.  The key is the path relative to ROOT, not the bare name, so two
    # files sharing a name in different folders cannot collide into one entry.
    for doc in sorted((ROOT / "docs").rglob("*.md")):
        found[str(doc.relative_to(ROOT))] = doc.read_text()
    return found


def _logical_lines(text: str) -> list[str]:
    """Join backslash-continued lines, as the shell would."""
    lines: list[str] = []
    pending = ""
    for raw in text.splitlines():
        line = raw.rstrip()
        if line.endswith("\\"):
            pending += line[:-1].rstrip() + " "
            continue
        lines.append(pending + line)
        pending = ""
    if pending:
        lines.append(pending)
    return lines


def _commands(text: str) -> list[tuple[str, str | None]]:
    """Return the concrete commands in ``text``, with any stated output."""
    out: list[tuple[str, str | None]] = []
    for line in _logical_lines(text):
        command = line.strip().removeprefix("$ ").strip()
        expected: str | None = None
        if "->" in command:
            command, _, stated = command.partition("->")
            command, expected = command.strip(), stated.strip()
        if command.startswith("esolangs ") and not _PLACEHOLDER.search(command):
            out.append((command, expected))
    return out


def _language_in(command: str) -> str | None:
    """Return the language a command names, if any."""
    for token in re.findall(r'"[^"]+"|\S+', command):
        bare = token.strip('"')
        if bare.lower() in _LANGUAGES:
            return _LANGUAGES[bare.lower()]
    return None


@cache
def _setup_command(*args: str) -> subprocess.CompletedProcess[str]:
    """Reuse identical fixture generation and input encoding across documents."""
    return subprocess.run(
        [sys.executable, "-m", "esolangs", *args],
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.mark.slow
@pytest.mark.parametrize("where", sorted(_documents()))
def test_every_documented_command_runs(where: str, tmp_path: pathlib.Path) -> None:
    """Run one document's commands, in order, in a scratch directory."""
    commands = _commands(_documents()[where])
    if not commands:
        pytest.skip(f"{where} shows no concrete commands")
    work = tmp_path / "work"
    work.mkdir()
    produced: set[str] = set()
    failures = []
    for command, expected in commands:
        language = _language_in(command)
        # A file the example expects to exist already, and which no earlier
        # line here created, is stood up so the command has something real.
        for filename in re.findall(r"\b[\w.-]+\.txt\b", command):
            if filename not in produced and language is not None:
                generated = _setup_command("generate", language, "0110")
                generated.check_returncode()
                (work / filename).write_text(generated.stdout)
        stdin_text = ""
        if language is not None and "|" not in command:
            encoded = _setup_command("encode", language, "10")
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
    """A parser that matched nothing would make every case above vacuous."""
    parsed = [c for text in _documents().values() for c in _commands(text)]
    assert len(parsed) >= 20, f"only {len(parsed)} documented commands found"
    # And at least one example states the output it produces, or the
    # arrow-checking half of the test above is dead code.
    assert [c for c in parsed if c[1] is not None]


def test_the_usage_guide_names_every_command() -> None:
    """A command reachable only from ``--help`` is one a reader does not find."""
    text = (ROOT / "docs" / "usage.md").read_text()
    missing = [command for command in HELP if f"`{command}`" not in text]
    assert not missing, f"docs/usage.md never names: {', '.join(sorted(missing))}"


#: A ``\`\`test_name\`\`\`` citation in the source.
_CITATION = re.compile(r"``(test_[a-z_0-9]+)``")

#: A test definition.
_DEFINITION = re.compile(r"^\s*def (test_[a-z_0-9]+)", re.M)

_ROOT = pathlib.Path(__file__).parents[1]


def test_every_test_a_docstring_names_still_exists() -> None:
    """A citation to a renamed or deleted test is worse than none."""
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
    # A regex that stopped matching would make the check above vacuous.
    assert len(cited) >= 5, f"only {len(cited)} citations found"


#: A fully-qualified reference into this package.
_QUALIFIED_REF = re.compile(
    r":(?:func|class|data|meth|attr|exc):`~?(esolangs\.[\w.]+)`"
)


def test_every_qualified_reference_resolves() -> None:
    """A ``:func:`esolangs.a.b.c`` pointing at nothing."""
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
    # A regex that stopped matching would make the check above vacuous.
    assert len(targets) >= 30, f"only {len(targets)} qualified references found"


_LINK = re.compile(r"(?<!!)\[[^]]*\]\(([^ )]+)(?:\s+[^)]*)?\)")
_DOCUMENTS = (
    ROOT / "README.md",
    *sorted((ROOT / "docs").rglob("*.md")),
    *sorted((ROOT / "src" / "esolangs" / "examples").glob("*.md")),
)


def test_every_local_markdown_link_resolves() -> None:
    """Check shipped documentation, including package example guides."""
    missing: list[str] = []
    for document in _DOCUMENTS:
        for target in _LINK.findall(document.read_text(encoding="utf-8")):
            path, _, _fragment = unquote(target).partition("#")
            if not path or "://" in path or path.startswith("mailto:"):
                continue
            if not (document.parent / path).exists():
                missing.append(f"{document.relative_to(ROOT)} -> {target}")
    assert not missing, "broken local Markdown links:\n" + "\n".join(missing)


_README = pathlib.Path(__file__).resolve().parents[1] / "README.md"

_LANGUAGE = "Sophie"
_TABLE = "0110"  # XOR


def _readme_program() -> str:
    """Return the first fenced block under the Examples heading."""
    text = _README.read_text(encoding="utf-8")
    body = text[text.index("## Examples") :]
    match = re.search(r"```\n(.*?)\n```", body, re.DOTALL)
    assert match is not None, "no fenced program under ## Examples"
    return match.group(1)


def test_readme_program_is_what_the_generator_emits() -> None:
    assert _readme_program() == generate(_LANGUAGE, _TABLE)


def test_readme_program_computes_xor_on_every_row() -> None:
    """All four rows, not just one: a program that printed a constant
    would pass a single-row check."""
    program = _readme_program()
    for row, expected in enumerate(_TABLE):
        stdin = "".join(f"{bit}" for bit in format(row, "02b"))
        assert run(_LANGUAGE, program, stdin=stdin) == expected


def test_readme_states_the_real_length() -> None:
    """The prose says 51 characters; the program has to be that long."""
    program = _readme_program()
    body = _README.read_text(encoding="utf-8")
    assert f"emits {len(program)} characters" in body
