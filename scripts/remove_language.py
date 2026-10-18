"""``new_language.py remove``: delete a language and every entry naming it.

The inverse of ``start``/``check``/``finish``: it deletes what ``check`` asks
for, cuts the language's entries out of the shared tables it knows, keeps a
module the remaining source still imports (minus its ``LANGUAGE``),
regenerates, and lists the mentions left in prose.
"""

from __future__ import annotations

import ast
import importlib
import shutil
import subprocess
import sys
import types
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from removal_mentions import drop_owned_comments, mention_edit
else:
    _mentions = importlib.import_module(
        f"{__package__ + '.' if __package__ else ''}removal_mentions"
    )
    mention_edit = _mentions.mention_edit
    drop_owned_comments = _mentions.drop_owned_comments

ROOT = Path(__file__).parents[1]
# scripts/ holds the sibling `removal` package, like `verify` and `docs`.
if str(Path(__file__).parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).parent))

from removal import documents as _documents  # noqa: E402
from removal import entries as _entries  # noqa: E402
from removal import ownership as _ownership  # noqa: E402
from removal.documents import (  # noqa: E402, F401
    _drop_bullets,
    _drop_doc_entries,
    _drop_from_series,
    _drop_json,
    _prune_fixtures,
    _stale_timing,
)
from removal.entries import (  # noqa: E402, F401
    _container_items,
    _drop_dead_code,
    _drop_entries,
    _drop_inline_items,
    _drop_matching_items,
    _inline_items,
    _names_used,
    _outermost,
    _str_value,
    _top_level_name,
    _whole_statement,
)
from removal.ownership import (  # noqa: E402, F401
    _EDITED,
    _dead_test_files,
    _declaring_module,
    _drop_language_statement,
    _gone,
    _gone_modules,
    _import_names,
    _import_users,
    _imported,
    _is_test,
    _module_of,
    _module_path,
    _orphans,
    _owned_evidence,
    _owned_module_paths,
    _owned_scripts,
    _owner_id,
    _python_files,
    _within,
)

#: The phase modules whose ``ROOT`` follows this module's.
_PHASE_MODULES = (_documents, _entries, _ownership)


class _RootModule(types.ModuleType):
    """A module type that forwards ``ROOT`` assignments to the phases.

    Tests point ``remove_language.ROOT`` at a fixture tree; the phase
    modules read their own ``ROOT``, so an assignment here must reach
    them too or the phases would keep working on the real tree.
    """

    def __setattr__(self, name: str, value: Any) -> None:
        super().__setattr__(name, value)
        if name == "ROOT":
            for module in _PHASE_MODULES:
                module.ROOT = value  # type: ignore[attr-defined]


sys.modules[__name__].__class__ = _RootModule

#: Where a language's own test and script files live.

_TREES = ("tests", "scripts")


def tests_attr(module: str, attr: str) -> Any:
    """Read ``attr`` from ``tests.<module>``, which needs the repo on the path."""
    sys.path.insert(0, str(ROOT))
    try:
        return getattr(importlib.import_module(f"tests.{module}"), attr)
    finally:
        sys.path.remove(str(ROOT))


def _mention_edit(mention: str, name: str | None = None) -> str:
    """Classify a raw hit from this checkout."""
    return mention_edit(ROOT, mention, name)


def remove(name: str) -> list[str]:
    """Delete ``name`` everywhere ``check`` looks; return the leftover mentions."""
    from esolangs.registry import LANGUAGES, example_stems

    reference = tests_attr("api.test_language_coupling", "REFERENCE")
    if name == reference:
        raise ValueError(
            f"{reference} is the reference language: shared tests, the example "
            "commands and scripts/docs/generate.py spell it out, so it is not "
            "removable"
        )
    lang = LANGUAGES[name]
    module = lang.interpreter or ""
    gen = lang.boolean.__name__ if lang.boolean else lang.id
    stem = example_stems().get(lang.id, "")
    declaring = _declaring_module(lang)
    own_modules, module_paths = _owned_module_paths(lang)
    files = _python_files()
    users = _imported([f for f in files if f not in _EDITED])
    doomed: set[Path] = {
        *module_paths,
        ROOT / "src/esolangs/languages" / lang.id / "tests",
        # The package's language-owned data file: not a module, and the
        # suffix sweep below would leave it (and its entries) behind.
        ROOT / "src/esolangs/languages" / lang.id / "language.toml",
        *(
            path
            for path in (ROOT / "src/esolangs/languages" / lang.id).iterdir()
            if path.suffix in {".txt", ".png", ".gz"}
        ),
        *_owned_scripts(lang),
    }
    doomed |= _owned_evidence(name)
    doomed |= _dead_test_files(doomed, _gone_modules(doomed), users)
    doomed |= _orphans(doomed, users)
    doomed, kept = _settle_kept(doomed, users)
    _delete(doomed)
    for path in module_paths - doomed:
        if declaring and path == _module_path(declaring):
            _drop_language_statement(path / "__init__.py" if path.is_dir() else path)
    keys = {name, module, lang.id, gen, stem} - {""}
    # ``Path("src/esolangs/languages/inject/tests/test_inject.py")`` in a support list.
    paths = {str(p.relative_to(ROOT)) for p in doomed}
    # A deleted test module too: ``tests/support/samples.py`` borrows Inject's program.
    gone_modules = _gone_modules(doomed)
    modules = {m for m in own_modules if _module_path(m) is None} | gone_modules
    # Names each surviving file reads.  A helper another file still names is
    # kept even when it reads a name this removal deletes: ``sbleq_variant``
    # serves every S*bleq variant, not just the one going.
    surviving = [f for f in files if not _within(f, doomed) and (ROOT / f).is_file()]
    used_by_file = {
        f: _names_used(ast.parse((ROOT / f).read_text(encoding="utf-8")))
        for f in surviving
    }

    def external_for(relative: str) -> set[str]:
        names: set[str] = set()
        for other, used in used_by_file.items():
            if other != relative:
                names |= used
        return names

    for relative in _EDITED:
        _drop_entries(ROOT / relative, keys | paths, modules, external_for(relative))
        _drop_inline_items(ROOT / relative, keys)

    _prune_fixtures({name, lang.id, *lang.aliases}, paths)
    tracked = subprocess.run(
        ["git", "ls-files"], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.splitlines()
    for relative in tracked:
        path = ROOT / relative
        if path.is_file() and (
            path.suffix in {".py", ".toml", ".yaml", ".yml"} or path.name == "justfile"
        ):
            drop_owned_comments(path, name)
    documents = [ROOT / "README.md", ROOT / "docs/proofs/index.md"]
    documents += sorted((ROOT / "docs").glob("*.md"))
    for path in documents:
        if path.is_file() and path.name != "CHANGELOG.md":
            _drop_doc_entries(path, name)
    _drop_from_series(ROOT / "docs/proofs/index.md", name, "keeps? no tree route")
    # A cut entry can leave its import unused; the linter knows which.
    shared = ["src/esolangs/generation/wrap.py"]
    touched = [
        *[str(p.relative_to(ROOT)) for p in module_paths - doomed],
        *_EDITED,
        *shared,
    ]
    ruff = Path(sys.executable).parent / "ruff"
    subprocess.run(
        [str(ruff), "check", "--fix", "--select", "F401,I", "-q", *touched],
        cwd=ROOT,
        check=False,
        capture_output=True,
    )
    # Dead code the language left in the shared modules: its wrapper in
    # ``wrap.py``.  The unused imports are gone, so a top-level name nothing
    # reads is dead.
    from esolangs.generation import wrap

    # A token wrapper is an instance with no ``__name__``: name it by identity.
    wrapper = (
        next(
            (n for n, v in vars(wrap).items() if v is lang.wrap),
            getattr(lang.wrap, "__name__", None),
        )
        if lang.wrap
        else None
    )
    exclusive = False
    if wrapper is not None and not any(
        other is not lang and other.wrap is lang.wrap for other in LANGUAGES.values()
    ):
        exclusive = not any(
            wrapper in used
            for relative, used in used_by_file.items()
            if relative.startswith("src/")
            and relative != "src/esolangs/generation/wrap.py"
        )
    for relative in shared:
        _drop_dead_code(ROOT / relative, external_for(relative))
    subprocess.run(
        [str(ruff), "format", "-q", *touched],
        cwd=ROOT,
        check=False,
        capture_output=True,
    )
    for target in ("docs", "examples"):
        subprocess.run(
            [sys.executable, "scripts/docs/generate.py", target],
            cwd=ROOT,
            check=True,
            stdout=subprocess.DEVNULL,
        )
    # An import of a deleted module fails wherever it runs.
    broken = sorted(
        f"{user}: imports {imported}, which is gone"
        for imported, importers in users.items()
        if _gone(imported, gone_modules)
        for user in importers
        if not _within(user, doomed)
    )
    survived = sorted(
        f"{path}: still present after its language went"
        for path in paths
        if (ROOT / path).exists()
    )
    # Prose and comments name a language by its display name and aliases; the
    # id and module are ordinary words (``line``, ``back``) far too often to
    # grep bare, so they count only inside quotes or a dotted module path.
    shadowed = any(other != name and other.startswith(name) for other in LANGUAGES)
    tokens = {name, *lang.aliases}
    if name.isdigit() or shadowed:
        tokens.discard(name)
    if exclusive and wrapper is not None:
        # The wrapper's own name is not the language's; surface the tests that
        # still name it (``WRAPPERS[...] is _bio``) so the hand edit is found.
        tokens.add(wrapper)
    patterns = list(tokens)
    patterns += [
        f"{quote}{token}{quote}"
        for token in {name, lang.id, *lang.aliases}
        for quote in ('"', "'", "`")
    ]
    if module:
        patterns.append(f"esolangs.languages.{module}.interpreter")
    if declaring:
        patterns.append(declaring)
    return kept + survived + broken + _leftover_mentions(name, patterns)


def _settle_kept(
    doomed: set[Path], users: dict[str, set[str]]
) -> tuple[set[Path], list[str]]:
    """Spare each ``src`` module surviving source imports; return why each stays.

    The module stays, minus its ``LANGUAGE``: the shared helper outlives the
    language that defined it.  Sparing one can spare what it imports, so this
    repeats until nothing changes.
    """

    def live(user: str, gone: set[Path]) -> bool:
        return (
            user.startswith("src/") and not _is_test(user) and not _within(user, gone)
        )

    kept: list[str] = []
    while True:
        needed = {
            path
            for path in doomed
            if path.is_relative_to(ROOT / "src")
            and path.suffix != ".txt"
            and any(live(user, doomed) for user in _import_users(path, users))
        }
        if not needed:
            return doomed, kept
        doomed = doomed - needed
        for path in sorted(needed):
            importers = sorted(
                user
                for user in _import_users(path, users)
                if live(user, doomed | {path})
            )
            shown = path.relative_to(ROOT)
            kept.append(f"{shown}: kept, still imported by {', '.join(importers)}")


def _delete(doomed: set[Path]) -> None:
    """Remove ``doomed`` from the index and the disk."""
    # ``git rm``, not unlink: tests read ``git ls-files``, which would still
    # list a file deleted only from disk.
    subprocess.run(
        ["git", "rm", "-q", "-r", "--ignore-unmatch", *map(str, sorted(doomed))],
        cwd=ROOT,
        check=True,
    )
    # ``git rm`` skips a file never committed: a language removed before its
    # first commit would otherwise stay registered.
    for path in doomed:
        if path.is_file():
            path.unlink()
        elif path.is_dir():
            shutil.rmtree(path)


def _leftover_mentions(name: str, patterns: list[str]) -> list[str]:
    """Return each tracked line still naming a pattern, labelled with its edit."""
    args: list[str] = []
    for pattern in dict.fromkeys(patterns):
        args += ["-e", pattern]
    grep = subprocess.run(
        ["git", "grep", "-n", "-I", "-F", "-w", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    # The tool's own examples name languages (``Piet++``, ``[1-Line]``), and
    # the changelog records that they existed; neither is coupling to edit,
    # so leave both out of the report.  Label what each remaining mention
    # needs: the tool cannot rewrite prose or a runnable example without
    # inventing a claim, so the edit stays with the caller.
    return [
        f"[{_mention_edit(line, name)}] {line}"
        for line in grep.stdout.splitlines()
        if not line.startswith(
            ("scripts/remove_language.py:", "scripts/removal/", "docs/CHANGELOG.md:")
        )
    ]
