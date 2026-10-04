"""Seeded image mutations exercise every raster interpreter through pixels."""

import os
import random
from contextlib import suppress
from io import BytesIO

import pytest
from PIL import Image, ImageEnhance, ImageFilter

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


@pytest.mark.parametrize(
    "operations",
    [
        ("brightness",),
        ("contrast",),
        ("grayscale",),
        ("blur",),
        ("sharpen",),
        ("crop",),
        ("jpeg",),
        ("bilinear",),
        ("bicubic",),
        ("bilinear", "jpeg"),
        ("jpeg", "bicubic"),
        ("blur", "contrast"),
        ("contrast", "blur"),
        ("brightness", "grayscale"),
        ("grayscale", "brightness"),
        ("crop", "blur", "sharpen"),
        ("blur", "sharpen", "crop"),
    ],
    ids=lambda operations: "-".join(operations),
)
@pytest.mark.parametrize("variant", range(2))
def test_filtered_images_have_only_documented_outcomes(
    raster_seed: tuple[str, Raster], operations: tuple[str, ...], variant: int
) -> None:
    language, seed = raster_seed
    rng = random.Random(sum(map(ord, language + "-".join(operations))) + variant)
    image = Image.open(BytesIO(seed.to_png())).convert("RGB")
    for operation in operations:
        if operation == "brightness":
            image = ImageEnhance.Brightness(image).enhance(rng.uniform(0.5, 1.5))
        elif operation == "contrast":
            image = ImageEnhance.Contrast(image).enhance(rng.uniform(0.5, 1.5))
        elif operation == "grayscale":
            image = image.convert("L").convert("RGB")
        elif operation == "blur":
            image = image.filter(ImageFilter.GaussianBlur(rng.uniform(0.25, 1.25)))
        elif operation == "sharpen":
            image = ImageEnhance.Sharpness(image).enhance(rng.uniform(1.5, 3.0))
        elif operation == "jpeg":
            compressed = BytesIO()
            image.save(
                compressed,
                format="JPEG",
                quality=rng.randint(25, 50) if variant == 0 else rng.randint(75, 95),
                subsampling=2 if variant == 0 else 0,
            )
            image = Image.open(BytesIO(compressed.getvalue())).convert("RGB")
        elif operation in ("bilinear", "bicubic"):
            factor = rng.uniform(0.5, 0.9) if variant == 0 else rng.uniform(1.1, 1.5)
            image = image.resize(
                (
                    max(1, round(image.width * factor)),
                    max(1, round(image.height * factor)),
                ),
                Image.Resampling.BILINEAR
                if operation == "bilinear"
                else Image.Resampling.BICUBIC,
            )
        elif operation == "crop":
            left = rng.randrange(image.width)
            top = rng.randrange(image.height)
            image = image.crop(
                (
                    left,
                    top,
                    rng.randrange(left + 1, image.width + 1),
                    rng.randrange(top + 1, image.height + 1),
                )
            )
        else:
            raise AssertionError(f"unknown image operation: {operation}")
    encoded = BytesIO()
    image.save(encoded, format="PNG")
    filtered = Raster.from_png(encoded.getvalue())
    with suppress(EsolangError):
        esolangs.run(language, filtered, "0\n1\n", timeout=0.5)


@pytest.mark.parametrize("scale", [2, 3])
def test_nearest_neighbor_scaling_preserves_output(
    raster_seed: tuple[str, Raster], scale: int
) -> None:
    language, seed = raster_seed
    image = Image.open(BytesIO(seed.to_png())).convert("RGB")
    image = image.resize(
        (image.width * scale, image.height * scale), Image.Resampling.NEAREST
    )
    encoded = BytesIO()
    image.save(encoded, format="PNG")
    enlarged = Raster.from_png(encoded.getvalue())
    for first, second in ((0, 0), (0, 1), (1, 0), (1, 1)):
        stdin = f"{first}\n{second}\n"
        expected = str(first ^ second)
        assert esolangs.run(language, seed, stdin, timeout=0.5) == expected
        assert (
            esolangs.run(language, enlarged, stdin, scale=scale, timeout=0.5)
            == expected
        )
