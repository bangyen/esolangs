"""Cut a language's entries out of data files and documents.

The fixture-and-prose phase of ``remove_language``: rows keyed by the
language go from the JSON timing snapshot, and its bullets and table
rows go from the documents, name prefix and all.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from pathlib import Path

ROOT = Path(__file__).parents[2]


def _drop_json(path: Path, prune: Callable[[object], object]) -> None:
    """Rewrite ``path`` through ``prune``, keeping its indent and escaping."""
    text = path.read_text(encoding="utf-8")
    second = text.split("\n", 2)[1] if "\n" in text else ""
    indent = len(second) - len(second.lstrip())
    pruned = prune(json.loads(text))
    out = json.dumps(pruned, indent=indent, ensure_ascii=text.isascii())
    if text.endswith("\n"):
        out += "\n"
    path.write_text(out, encoding="utf-8")


def _drop_bullets(path: Path, name: str) -> None:
    """Drop each ``- name ...`` or ``- [name](...) ...`` bullet from ``path``.

    Its indented lines go with it, ``- **name:**`` counts too, and a blank
    line that only separated the bullet from the next goes as well.
    """
    text = path.read_text(encoding="utf-8")
    token = re.escape(name)
    label = rf"(?:\[{token}\]\([^\n]*?\)|\*\*{token}:?\*\*|{token})"
    bullet = (
        rf"(?im)^- {label}(?=\s|:|['\u2019]s\b|$).*(?:\n|$)"
        r"(?:  .*(?:\n|$)|\n(?=(?:\n)*  ))*"
    )

    def cut(match: re.Match[str]) -> str:
        before = text[: match.start()]
        if before.endswith("\n\n") and text.startswith("\n", match.end()):
            return "\0"  # marks the separator below for removal
        return ""

    text = re.sub(bullet, cut, text).replace("\0\n", "")
    path.write_text(text, encoding="utf-8")


def _drop_doc_entries(path: Path, name: str) -> None:
    """Drop language-owned bullets and rows whose first cell names it."""
    _drop_bullets(path, name)
    token = re.escape(name)
    label = rf"(?:\[{token}\]\([^\n]*?\)|\*\*{token}\*\*|{token})"
    row = rf"(?im)^\|\s*{label}\s*\|.*(?:\n|$)"
    text = path.read_text(encoding="utf-8")
    path.write_text(re.sub(row, "", text), encoding="utf-8")


def _stale_timing(key: str, names: set[str], gone_paths: set[str]) -> bool:
    """Whether a recorded pytest node ID names a deleted test or language.

    A shared test carries the language as one of its parametrize ids
    (``...[Suffolk-one_hot]``, ``...[1-Line]``); a language's own test carries
    its file path.  ``Piet`` must not take ``Piet++``'s rows: only a whole
    ``-``-delimited component counts.

    ``gone_paths`` holds directories as well as files -- the doomed set
    carries a package's ``tests`` directory, not each file in it -- so
    a node ID is stale when its file is a doomed path or lies under
    one.  The ``/`` boundary keeps a sibling such as ``tests2`` alive.
    """
    file = key.split("::", 1)[0]
    if any(file == gone or file.startswith(gone + "/") for gone in gone_paths):
        return True
    match = re.search(r"\[([^\]]*)\]", key)
    if match is None:
        return False
    param = match.group(1)
    return any(
        param == n
        or param.startswith(n + "-")
        or param.endswith("-" + n)
        or f"-{n}-" in param
        for n in names
    )


def _drop_from_series(path: Path, name: str, tail: str) -> None:
    """Drop ``name`` from the prose list ``A, B, C and D <tail>`` in ``path``.

    Whitespace, line breaks included, is kept where it fell, so the wrapped
    paragraph stays wrapped; the last two items keep their ``and``.
    """
    text = path.read_text(encoding="utf-8")
    flat = " ".join(text.split())
    match = re.search(rf"([\w,\-~/ ()]+?) {tail}", flat)
    if not match:
        return
    items = [p.strip() for p in re.split(r",| and ", match.group(1)) if p.strip()]
    if name not in items:
        return
    sep = r"\s+"
    region = re.search(re.escape(match.group(1)).replace(r"\ ", sep) + sep + tail, text)
    assert region, tail
    part = region.group()
    word = re.escape(name).replace(r"\ ", sep)
    if items[-1] == name:
        # "Y, X and Name tail" becomes "Y and X tail".
        pattern = rf",(\s+)([^,]+?)\s+and\s+{word}(\s+{tail.split()[0]})"
        part, n = re.subn(pattern, r" and\1\2\3", part, count=1)
        if not n:  # only two items: "X and Name tail"
            part = re.sub(rf"\s+and\s+{word}(?=\s+{tail.split()[0]})", "", part)
    elif items[-2] == name:
        part = re.sub(rf",?(\s+){word}\s+and(\s+)", r"\1and\2", part, count=1)
        part = part.replace(" and\nand", " and")  # never two ``and``s
    else:
        part = re.sub(
            rf"([ \t]?)(?<![\w~/]){word},[ \t]*(\n?)",
            lambda m: m.group(2) or m.group(1),
            part,
            count=1,
        )
    text = text[: region.start()] + part + text[region.end() :]
    path.write_text(text, encoding="utf-8")


def _prune_fixtures(names: set[str], paths: set[str]) -> None:
    """Drop the language's rows from the fixtures still keyed by language.

    Size baselines and catalogue entries need no pruning: they live in
    the removed package's own ``language.toml`` and die with it.
    """
    # The root snapshot keeps one duration per pytest node ID; drop the
    # removed language's parametrized rows and its own deleted test files.
    # The ``collected`` dates beside the durations are not the language's.
    timings = ROOT / "snapshot.json"

    def drop_timings(node: object) -> object:
        if not isinstance(node, dict):
            return node
        durations = node.get("durations")
        if not isinstance(durations, dict):
            return node
        return {
            **node,
            "durations": {
                key: value
                for key, value in durations.items()
                if not _stale_timing(str(key), names, paths)
            },
        }

    if timings.is_file():
        _drop_json(timings, drop_timings)
