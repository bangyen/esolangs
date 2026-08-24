"""Verify the committed esolangs-wiki spec hashes.

``docs/wiki-specs.json`` maps each language to the sha256 of its wiki page's
raw wikitext (the ``?action=raw`` source) and of the raw wikitext of its
talk page, where authors sometimes clarify an underspecified spec.  Each
hash is the fingerprint of the material the interpreter was verified
against: a mismatch means the page (or its discussion) changed since the
interpreter was last checked, so it deserves a re-read.  The raw wikitext
is hashed rather than the rendered HTML so navigation and template
boilerplate do not pollute the hash.

A hash is recorded only after the interpreter has been audited against that
revision of the spec and its talk page; run ``--update`` only after
re-verifying every reported change.  A main-page change is always worth
re-verifying; a talk-page change is usually discussion churn, but can carry
a spec clarification, so it is reported separately.
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


def fetch(title: str) -> tuple[str, str]:
    """Return the raw wikitext of ``title`` and the title it resolves to.

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
        return text, title
    raise RuntimeError(f"redirect loop while fetching {title!r}")


def page_hash(text: str) -> str:
    """sha256 of the raw wikitext, the fingerprint of one spec revision."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def spec_texts(name: str) -> tuple[str, str]:
    """Return the raw wikitext of the page and talk page for ``name``.

    A language with no talk page hashes the empty string for ``talk``.
    """
    page, resolved = fetch(page_title(name))
    try:
        talk, _ = fetch("Talk:" + resolved)
    except urllib.error.HTTPError as e:
        if e.code != 404:
            raise
        talk = ""
    return page, talk


def spec_hash(page: str, talk: str) -> dict[str, str]:
    """Build the ``{"page", "talk"}`` sha256 fingerprints of a spec revision."""
    return {"page": page_hash(page), "talk": page_hash(talk)}


def main() -> int:
    """Compare the committed spec hashes against the live wiki pages."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--update", action="store_true")
    args = parser.parse_args()

    # json.loads returns Any; the committed file is written by --update
    # below, so every value is a {"page", "talk"} mapping.
    recorded: dict[str, dict[str, str | None]] = (
        json.loads(HASHES.read_text()) if HASHES.exists() else {}
    )
    current: dict[str, dict[str, str]] = {}
    unverified: list[str] = []
    page_changed: list[str] = []
    talk_changed: list[str] = []
    for name in sorted(LANGUAGES):
        try:
            page, talk = spec_texts(name)
        except urllib.error.URLError as e:
            print(f"fetch error for {name}: {e}")
            return 1
        h = spec_hash(page, talk)
        current[name] = h
        if name not in recorded:
            unverified.append(name)
        else:
            old = recorded[name]
            if old.get("page") != h["page"]:
                page_changed.append(name)
            if old.get("talk") != h["talk"]:
                talk_changed.append(name)

    stale = [name for name in recorded if name not in LANGUAGES]

    if args.update:
        HASHES.write_text(json.dumps(current, indent=2, sort_keys=True) + "\n")
        print(f"wrote {HASHES} ({len(current)} languages)")
        return 0

    if unverified:
        print("no recorded hash (audit before recording): " + ", ".join(unverified))
    if page_changed:
        label = "wiki page changed (re-verify the interpreter): "
        print(label + ", ".join(page_changed))
    if talk_changed:
        label = "wiki talk page changed (re-read the discussion): "
        print(label + ", ".join(talk_changed))
    if stale:
        print("recorded but not a registered language (stale): " + ", ".join(stale))
    if not (unverified or page_changed or talk_changed or stale):
        print("all wiki-spec hashes match")
    return 0 if not (unverified or page_changed or talk_changed or stale) else 1


if __name__ == "__main__":
    sys.exit(main())
