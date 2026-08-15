"""Verify the committed esolangs-wiki spec hashes.

``docs/wiki-specs.json`` maps each language to the sha256 of its wiki page's
raw wikitext (the ``?action=raw`` source).  The hash is the fingerprint of
the spec the interpreter was verified against: a mismatch means the wiki
page changed since the interpreter was last checked, so it deserves a
re-read.  The raw wikitext is hashed rather than the rendered HTML so
navigation and template boilerplate do not pollute the hash.

A hash is recorded only after the interpreter has been audited against that
revision of the spec; run ``--update`` only after re-verifying every
reported change.

Usage:
    PYTHONPATH=src python scripts/verify_wiki_specs.py [--update]
"""

import argparse
import hashlib
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from esolangs.registry import LANGUAGES

ROOT = Path(__file__).resolve().parent.parent
HASHES = ROOT / "docs" / "wiki-specs.json"
API = "https://esolangs.org/w/index.php"
_HEADERS = {"User-Agent": "esolangs-repo wiki-spec verification"}


def page_title(name: str) -> str:
    """Return the esolangs wiki page title for a language's display name."""
    return name.replace(" ", "_")


def fetch(title: str) -> str:
    """Return the raw wikitext of the page ``title``, following redirects.

    ``action=raw`` on a redirect returns the ``#REDIRECT [[target]]`` stub
    rather than following it, so this resolves the target and refetches.
    """
    for _ in range(5):
        url = API + "?" + urllib.parse.urlencode({"title": title, "action": "raw"})
        req = urllib.request.Request(url, headers=_HEADERS)
        with urllib.request.urlopen(req, timeout=30) as resp:
            text = resp.read().decode("utf-8")
        m = re.match(r"#REDIRECT \[\[([^]]+)\]\]", text)
        if m:
            title = m.group(1).strip()
            continue
        return text
    raise RuntimeError(f"redirect loop while fetching {title!r}")


def page_hash(text: str) -> str:
    """sha256 of the raw wikitext, the fingerprint of one spec revision."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def main() -> int:
    """Compare the committed spec hashes against the live wiki pages."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--update", action="store_true")
    args = parser.parse_args()

    recorded: dict[str, str] = json.loads(HASHES.read_text()) if HASHES.exists() else {}
    current: dict[str, str] = {}
    changed: list[str] = []
    unverified: list[str] = []
    for name in sorted(LANGUAGES):
        try:
            text = fetch(page_title(name))
        except urllib.error.URLError as e:
            print(f"fetch error for {name}: {e}")
            return 1
        h = page_hash(text)
        current[name] = h
        if name not in recorded:
            unverified.append(name)
        elif recorded[name] != h:
            changed.append(name)

    stale = [name for name in recorded if name not in LANGUAGES]

    if args.update:
        HASHES.write_text(json.dumps(current, indent=2, sort_keys=True) + "\n")
        print(f"wrote {HASHES} ({len(current)} languages)")
        return 0

    if unverified:
        print("no recorded hash (audit before recording): " + ", ".join(unverified))
    if changed:
        print("wiki page changed (re-verify the interpreter): " + ", ".join(changed))
    if stale:
        print("recorded but not a registered language (stale): " + ", ".join(stale))
    if not (unverified or changed or stale):
        print("all wiki-spec hashes match")
    return 0 if not (unverified or changed or stale) else 1


if __name__ == "__main__":
    sys.exit(main())
