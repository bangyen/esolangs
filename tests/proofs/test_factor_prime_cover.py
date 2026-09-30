"""Complete prime windows cannot be skipped by Factor's greedy encoder."""

import importlib
import itertools

import pytest

from esolangs.factor_primes import prime_segments
from esolangs.tools.factor import _BF_RESIDUE, _spans


def _complete(primes: list[int], start: int, width: int) -> bool:
    return set(range(1, 11)) <= {p % 11 for p in primes if start < p <= start + width}


@pytest.mark.medium
def test_complete_windows_cover_greedy_streams(monkeypatch: pytest.MonkeyPatch) -> None:
    factor_module = importlib.import_module("esolangs.tools.factor")
    monkeypatch.setattr(factor_module, "_FACTOR_PRIME_CHUNK", 256)
    streams = [
        [p for _length, p in _spans("".join(word))]
        for length in range(1, 4)
        for word in itertools.product(_BF_RESIDUE, repeat=length)
    ]
    primes = next(prime_segments(4096))[2]
    stop = max(stream[-1] for stream in streams)
    positive = 0
    for width in (8, 32, 128, 512):
        assert stop + width < primes[-1]
        complete = {n for n in range(1, stop) if _complete(primes, n, width)}
        for stream in streams:
            end = stream[-1]
            good = {n for n in complete if (end + 1) // 2 <= n < end}
            assert all(any(n < p <= n + width for p in stream) for n in good)
            assert len(good) <= len(stream) * width
            positive += len(good)
    assert positive > 0


def test_delayed_prime_can_skip_a_complete_window() -> None:
    primes = next(prime_segments(4096))[2]
    delayed = max(p for p in primes if p % 11 == 1)
    start, width = delayed // 2, 512
    assert _complete(primes, start, width)
    assert delayed > start + width
