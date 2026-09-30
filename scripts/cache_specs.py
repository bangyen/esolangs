"""Cache registry specs: uv run python scripts/cache_specs.py [LANGUAGE ...]."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import time
from datetime import UTC, datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

from esolangs.registry import LANGUAGES, resolve, wiki_url

ROOT = Path(__file__).resolve().parents[1]


class _Text(HTMLParser):
    """Extract readable text while preserving preformatted diagrams."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.hidden = 0

    def handle_starttag(self, tag: str, _attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style"}:
            self.hidden += 1
        if tag in {"p", "div", "pre", "br", "tr", "li", "h1", "h2", "h3"}:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style"}:
            self.hidden = max(0, self.hidden - 1)
        if tag in {"p", "div", "pre", "tr", "li", "h1", "h2", "h3"}:
            self.parts.append("\n")
        if tag in {"td", "th"}:
            self.parts.append("\t")

    def handle_data(self, data: str) -> None:
        if not self.hidden:
            self.parts.append(data)


def fetch(url: str, timeout: float) -> tuple[bytes, str, str]:
    """Return the response bytes, final URL, and declared encoding."""
    request = Request(url, headers={"User-Agent": "esolangs-spec-cache/1.0"})
    with urlopen(request, timeout=timeout) as response:
        return (
            response.read(),
            response.url,
            response.headers.get_content_charset() or "utf-8",
        )


def _write_atomic(path: Path, content: bytes) -> None:
    """Replace a file only after its new contents have been written."""
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(content)
    temporary.replace(path)


def cache_specs(
    sources: dict[str, list[str]],
    directory: Path,
    *,
    delay: float = 5,
    timeout: float = 30,
    refresh: bool = False,
) -> int:
    """Cache unique URLs; record failures and return their count."""
    directory.mkdir(parents=True, exist_ok=True)
    manifest_path = directory / "manifest.json"
    entries: dict[str, dict[str, object]] = (
        json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    )
    last_request: float | None = None
    failures = 0
    for url, names in sources.items():
        key = hashlib.sha256(url.encode()).hexdigest()
        old = entries.get(url, {})
        raw_path = directory / str(old.get("html", f"{key}.html"))
        text_path = directory / str(old.get("text", f"{key}.txt"))
        valid = (
            raw_path.exists()
            and text_path.exists()
            and hashlib.sha256(raw_path.read_bytes()).hexdigest() == old.get("sha256")
            and hashlib.sha256(text_path.read_bytes()).hexdigest()
            == old.get("text_sha256")
        )
        if valid and not refresh:
            print(f"cached: {', '.join(names)}", flush=True)
            continue
        if last_request is not None:
            time.sleep(max(0, delay - (time.monotonic() - last_request)))
        attempted = datetime.now(UTC).isoformat()
        try:
            raw, final_url, encoding = fetch(url, timeout)
            parser = _Text()
            parser.feed(raw.decode(encoding, errors="replace"))
            rendered = "".join(parser.parts).encode("utf-8")
            raw_hash = hashlib.sha256(raw).hexdigest()
            text_hash = hashlib.sha256(rendered).hexdigest()
            # Immutable snapshots keep a failed refresh from replacing old evidence.
            raw_path = directory / f"{key}-{raw_hash}.html"
            text_path = directory / f"{key}-{text_hash}.txt"
            _write_atomic(raw_path, raw)
            _write_atomic(text_path, rendered)
            entries[url] = {
                "languages": names,
                "fetched_at": attempted,
                "final_url": final_url,
                "sha256": raw_hash,
                "html": raw_path.name,
                "text_sha256": text_hash,
                "text": text_path.name,
            }
            print(f"fetched: {', '.join(names)}", flush=True)
        except (URLError, OSError, TimeoutError, LookupError) as error:
            failures += 1
            entries[url] = {
                **old,
                "languages": names,
                "last_attempt": attempted,
                "error": str(error),
            }
            print(f"failed: {url}: {error}", flush=True)
        finally:
            # Wait after completion as well as after a failed request.
            last_request = time.monotonic()
            _write_atomic(
                manifest_path,
                (json.dumps(entries, indent=2, sort_keys=True) + "\n").encode(),
            )
    return failures


def main(argv: list[str] | None = None) -> int:
    """Fetch missing specs, or refresh explicitly; fail on request errors."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("languages", nargs="*")
    parser.add_argument(
        "--url", action="append", default=[], help="additional spec URL"
    )
    parser.add_argument("--cache-dir", type=Path, default=ROOT / "notes" / "spec-cache")
    parser.add_argument("--delay", type=float, default=5)
    parser.add_argument("--timeout", type=float, default=30)
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args(argv)
    if (
        not math.isfinite(args.delay)
        or args.delay < 5
        or not math.isfinite(args.timeout)
        or args.timeout <= 0
    ):
        parser.error("delay must be at least 5 seconds and timeout must be positive")
    names = (
        [resolve(name) for name in args.languages]
        if args.languages
        else ([] if args.url else sorted(LANGUAGES))
    )
    sources: dict[str, list[str]] = {}
    for name in names:
        sources.setdefault(wiki_url(name), []).append(name)
    for url in args.url:
        if not url.startswith(("https://", "http://")):
            parser.error("spec URLs must use HTTP or HTTPS")
        sources.setdefault(url, []).append(url)
    return int(
        bool(
            cache_specs(
                sources,
                args.cache_dir,
                delay=args.delay,
                timeout=args.timeout,
                refresh=args.refresh,
            )
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
