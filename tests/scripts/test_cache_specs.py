"""Offline coverage for the spec cache's request and artifact contracts."""

import hashlib
import json
from pathlib import Path
from urllib.error import URLError

import pytest

from scripts import cache_specs
from scripts.cache_specs import _Text, _write_atomic


def _artifacts(directory: Path, url: str) -> tuple[Path, Path]:
    key = hashlib.sha256(url.encode()).hexdigest()
    return directory / f"{key}.html", directory / f"{key}.txt"


def _write_cache(directory: Path, url: str, raw: bytes, text: bytes) -> None:
    raw_path, text_path = _artifacts(directory, url)
    raw_path.write_bytes(raw)
    text_path.write_bytes(text)
    (directory / "manifest.json").write_text(
        json.dumps(
            {
                url: {
                    "sha256": hashlib.sha256(raw).hexdigest(),
                    "text_sha256": hashlib.sha256(text).hexdigest(),
                    "html": raw_path.name,
                    "text": text_path.name,
                }
            }
        )
    )


def test_cache_reuses_only_hash_valid_artifacts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    url = "https://example.test/spec"
    raw, text = b"<p>spec</p>", b"spec"
    _write_cache(tmp_path, url, raw, text)
    calls: list[str] = []
    monkeypatch.setattr(
        cache_specs, "fetch", lambda address, _timeout: calls.append(address)
    )

    assert cache_specs.cache_specs({url: ["Example"]}, tmp_path) == 0
    assert calls == []

    _, text_path = _artifacts(tmp_path, url)
    text_path.write_bytes(b"tampered")
    monkeypatch.setattr(
        cache_specs,
        "fetch",
        lambda address, _timeout: (calls.append(address) or raw, address, "utf-8"),
    )
    assert cache_specs.cache_specs({url: ["Example"]}, tmp_path) == 0
    assert calls == [url]
    entry = json.loads((tmp_path / "manifest.json").read_text())[url]
    assert (tmp_path / entry["text"]).read_bytes() == b"\nspec\n"


def test_request_spacing_includes_failed_requests(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    urls = {"https://example.test/fail": ["A"], "https://example.test/ok": ["B"]}
    now = [10.0]
    sleeps: list[float] = []
    requests: list[float] = []

    def sleep(seconds: float) -> None:
        sleeps.append(seconds)
        now[0] += seconds

    def fetch(url: str, _timeout: float) -> tuple[bytes, str, str]:
        requests.append(now[0])
        now[0] += 2
        if url.endswith("fail"):
            raise URLError("offline")
        return b"<p>ok</p>", url, "utf-8"

    monkeypatch.setattr(cache_specs.time, "monotonic", lambda: now[0])
    monkeypatch.setattr(cache_specs.time, "sleep", sleep)
    monkeypatch.setattr(cache_specs, "fetch", fetch)
    assert cache_specs.cache_specs(urls, tmp_path, delay=5) == 1
    assert requests == [10.0, 17.0]
    assert sleeps == [5.0]
    manifest = json.loads((tmp_path / "manifest.json").read_text())
    assert manifest["https://example.test/fail"]["error"] == str(URLError("offline"))
    assert (
        manifest["https://example.test/ok"]["sha256"]
        == hashlib.sha256(b"<p>ok</p>").hexdigest()
    )


def test_refresh_failure_keeps_previous_files_and_records_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    url = "https://example.test/spec"
    raw, text = b"<pre>old</pre>", b"old"
    _write_cache(tmp_path, url, raw, text)
    monkeypatch.setattr(
        cache_specs,
        "fetch",
        lambda _address, _timeout: (_ for _ in ()).throw(URLError("offline")),
    )

    assert cache_specs.cache_specs({url: ["Example"]}, tmp_path, refresh=True) == 1
    raw_path, text_path = _artifacts(tmp_path, url)
    assert raw_path.read_bytes() == raw
    assert text_path.read_bytes() == text
    entry = json.loads((tmp_path / "manifest.json").read_text())[url]
    assert entry["sha256"] == hashlib.sha256(raw).hexdigest()
    assert entry["error"] == str(URLError("offline"))
    assert "last_attempt" in entry


def test_text_extraction_omits_scripts_and_styles_and_preserves_preformatted_text() -> (
    None
):
    parser = _Text()
    parser.feed(
        "<h1>Title</h1><script>secret</script><style>hidden</style>"
        "<p>A &amp; B</p><pre> x\n  y\n</pre>"
    )
    assert "".join(parser.parts) == "\nTitle\n\nA & B\n\n x\n  y\n\n"


def test_cli_deduplicates_urls_and_validates_options(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    captured: list[tuple[dict[str, list[str]], dict[str, object]]] = []
    monkeypatch.setattr(cache_specs, "resolve", lambda name: name.lower())
    monkeypatch.setattr(
        cache_specs, "wiki_url", lambda name: f"https://example.test/{name}"
    )
    monkeypatch.setattr(
        cache_specs,
        "cache_specs",
        lambda sources, _directory, **kwargs: captured.append((sources, kwargs)) or 0,
    )

    assert (
        cache_specs.main(
            [
                "ONE",
                "one",
                "--url",
                "https://example.test/one",
                "--cache-dir",
                str(tmp_path),
            ]
        )
        == 0
    )
    assert captured == [
        (
            {"https://example.test/one": ["one", "one", "https://example.test/one"]},
            {"delay": 5, "timeout": 30, "refresh": False},
        )
    ]
    with pytest.raises(SystemExit):
        cache_specs.main(["--delay", "4", "--cache-dir", str(tmp_path)])
    for option, value in (("--timeout", "0"), ("--timeout", "nan"), ("--delay", "inf")):
        with pytest.raises(SystemExit):
            cache_specs.main([option, value, "--cache-dir", str(tmp_path)])
    with pytest.raises(SystemExit):
        cache_specs.main(["--url", "file:///etc/passwd", "--cache-dir", str(tmp_path)])


def test_refresh_write_failure_preserves_previous_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    url = "https://example.test/spec"
    _write_cache(tmp_path, url, b"<p>old</p>", b"old")
    monkeypatch.setattr(
        cache_specs,
        "fetch",
        lambda address, _timeout: (b"<p>new</p>", address, "utf-8"),
    )
    write = _write_atomic

    def fail_text(path: Path, content: bytes) -> None:
        if path.suffix == ".txt":
            raise OSError("disk full")
        write(path, content)

    monkeypatch.setattr(cache_specs, "_write_atomic", fail_text)
    assert cache_specs.cache_specs({url: ["Example"]}, tmp_path, refresh=True) == 1
    raw, text = _artifacts(tmp_path, url)
    assert raw.read_bytes() == b"<p>old</p>"
    assert text.read_bytes() == b"old"
    entry = json.loads((tmp_path / "manifest.json").read_text())[url]
    assert entry["html"] == raw.name
    assert entry["text"] == text.name
    assert entry["error"] == "disk full"
