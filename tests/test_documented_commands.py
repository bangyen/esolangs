"""Every command shown in the docs is a claim; this runs them.

Four documented claims have been falsified by execution over this
package's QA history -- Fargo's input shape, a count of "four languages"
that was seven, Grapheme's truthiness rule, and the exception ``run``
promised for all sixty-nine.  Each was fixed where it was found.  This is
the same class caught at the source instead: a command that appears in the
README, in ``docs/``, or in any ``--help`` output has to work.

Only *concrete* commands run.  A line containing ``<`` or ``>`` in angle
form is a template (``esolangs run <language> <file>``) and is skipped, as
is anything that is not a command at all.
"""

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

#: ``<`` or ``>`` marks a placeholder, except in a shell redirect, which is
#: ``> name.txt`` and is a real part of a real command.
_PLACEHOLDER = re.compile(r"<\w|\w>")
_LANGUAGES = {name.lower(): name for name in LANGUAGES}


def _documents() -> dict[str, str]:
    """Return every document that can contain a command."""
    found = {"README.md": (ROOT / "README.md").read_text(), "usage": USAGE}
    for name, text in HELP.items():
        found[f"{name} --help"] = text
    for doc in sorted((ROOT / "docs").glob("*.md")):
        found[f"docs/{doc.name}"] = doc.read_text()
    return found


def _commands(text: str) -> list[tuple[str, str | None]]:
    """Return the concrete commands in ``text``, with any stated output.

    Some examples are written ``esolangs answer brainfuck 0110 10 -> 1``.
    The arrow is a claim about what the command prints, so it is parsed and
    checked rather than stripped: an example that says what it produces is
    the most falsifiable kind there is.
    """
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
    """Return the language a command names, if any."""
    for token in re.findall(r'"[^"]+"|\S+', command):
        bare = token.strip('"')
        if bare.lower() in _LANGUAGES:
            return _LANGUAGES[bare.lower()]
    return None


@pytest.mark.slow
@pytest.mark.parametrize("where", sorted(_documents()))
def test_every_documented_command_runs(where: str, tmp_path: pathlib.Path) -> None:
    """Run one document's commands, in order, in a scratch directory.

    In order and in one directory because the examples are sequences: a
    ``generate ... > prog.txt`` line sets up the ``run ... prog.txt`` line
    under it.  Getting that wrong is what made a hand-run of this report a
    false failure -- the setup file was regenerated from scratch between
    the two lines and arrived as an unfilled template.
    """
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
    """A parser that matched nothing would make every case above vacuous."""
    parsed = [c for text in _documents().values() for c in _commands(text)]
    assert len(parsed) >= 20, f"only {len(parsed)} documented commands found"
    # And at least one example states the output it produces, or the
    # arrow-checking half of the test above is dead code.
    assert [c for c in parsed if c[1] is not None]


#: A ``\`\`test_name\`\`\`` citation in the source.
_CITATION = re.compile(r"``(test_[a-z_0-9]+)``")

#: A test definition.
_DEFINITION = re.compile(r"^\s*def (test_[a-z_0-9]+)", re.M)

_ROOT = pathlib.Path(__file__).parents[1]


def test_every_test_a_docstring_names_still_exists() -> None:
    """A citation to a renamed or deleted test is worse than none.

    Twenty docstrings in ``src/`` back a claim by naming the test that
    proves it -- that a constant is derived rather than frozen, that a
    selection rule is pinned, that two structures cannot drift apart.  A
    reader who goes looking and finds nothing cannot tell whether the test
    moved or the claim stopped being true, and the *writer* gets no signal
    at all: renaming a test is a one-file change and the prose citing it
    lives somewhere else entirely.

    Three had already gone stale when this was written.  One was a rename
    the citation had not followed (``test_separation_law_is_least_mean``,
    backing the claim that Streetcode's separation laws are re-derived
    rather than frozen -- the most load-bearing of the three).  One named a
    test that is simply gone.  The third described a *deleted* test in the
    past tense, correctly, but spelled its name the same way a live
    citation is spelled, so it read like the other two.
    """
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
    assert len(cited) >= 15, f"only {len(cited)} citations found"


#: A fully-qualified reference into this package.
_QUALIFIED_REF = re.compile(
    r":(?:func|class|data|meth|attr|exc):`~?(esolangs\.[\w.]+)`"
)


def test_every_qualified_reference_resolves() -> None:
    """A ``:func:`esolangs.a.b.c`` pointing at nothing.

    Only the *fully qualified* references are checked.  A bare
    ``:class:`ScriptedIO`` is resolved by Sphinx against whatever the citing
    module imported, and reimplementing that here produced 460 accusations
    out of 510 -- a guard that cries wolf is worse than no guard, so it
    checks the subset it can judge exactly.  That subset is also the one
    most likely to rot, because it names a path that moves when code does.

    One was broken when this was written:
    ``esolangs.tools.boolean.examples.bio``, for a generator that lives at
    ``esolangs.tools.boolean.bio`` -- the reader is sent to the module that
    registers the examples rather than the one with the function in it.
    """
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
    assert len(targets) >= 40, f"only {len(targets)} qualified references found"
