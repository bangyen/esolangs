"""Seeded image mutations exercise every raster interpreter through pixels."""

import os
import random
from contextlib import suppress

import pytest

import esolangs
from esolangs.exceptions import EsolangError
from esolangs.raster import Raster
from esolangs.registry import LANGUAGES, SourceKind

RASTER_LANGUAGES = sorted(
    name for name, lang in LANGUAGES.items() if lang.source_kind is SourceKind.RASTER
)
pytestmark = [
    pytest.mark.medium,
    pytest.mark.skipif(os.name != "posix", reason="bounded raster fuzz uses SIGALRM"),
]


@pytest.fixture(
    scope="module",
    params=[
        (language, balanced)
        for language in RASTER_LANGUAGES
        for balanced in (False, True)
    ],
)
def raster_seed(request: pytest.FixtureRequest) -> tuple[str, Raster]:
    language, balanced = request.param
    source = esolangs.generate(language, "0110", balance=balanced)
    seed = Raster.from_png(source.to_png())
    assert esolangs.evaluate(language, seed, inputs=2) == "0110"
    return language, seed


@pytest.mark.parametrize("variant", range(4))
def test_mutated_images_have_only_documented_outcomes(
    raster_seed: tuple[str, Raster], variant: int
) -> None:
    language, seed = raster_seed
    rng = random.Random(sum(map(ord, language)) + variant)
    palette = sorted({pixel for row in seed.rows for pixel in row})
    palette.extend(((0, 0, 0), (255, 255, 255), (17, 83, 149)))
    rows = [list(row) for row in seed.rows]
    if variant % 2:
        ink = [
            (y, x)
            for y, row in enumerate(rows)
            for x, pixel in enumerate(row)
            if pixel != (255, 255, 255)
        ]
        y, x = rng.choice(ink)
    else:
        y, x = rng.randrange(len(rows)), rng.randrange(len(rows[0]))
    original = rows[y][x]
    rows[y][x] = rng.choice([pixel for pixel in palette if pixel != original])
    image = Raster(rows)
    with suppress(EsolangError):
        esolangs.run(language, image, "0\n1\n", timeout=0.5)


@pytest.mark.parametrize("language", RASTER_LANGUAGES)
def test_random_small_images_have_only_documented_outcomes(language: str) -> None:
    rng = random.Random(sum(map(ord, language)) + 1)
    palette = ((0, 0, 0), (255, 255, 255), (255, 192, 192), (0, 0, 255))
    for _ in range(16):
        width, height = rng.randrange(1, 9), rng.randrange(1, 9)
        image = Raster(
            tuple(
                tuple(rng.choice(palette) for _ in range(width)) for _ in range(height)
            )
        )
        with suppress(EsolangError):
            esolangs.run(language, image, "0\n1\n", timeout=0.1)
