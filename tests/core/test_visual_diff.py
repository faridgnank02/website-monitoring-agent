from io import BytesIO

import pytest
from PIL import Image, ImageDraw

from core.visual import VisualDiffEngine, VisualDiffError
from core.visual.diff import VisualDiffEngine as VisualDiffEngineFromModule
from core.visual.diff import VisualDiffError as VisualDiffErrorFromModule
from core.visual.screenshot import StaticScreenshotProvider


def test_visual_diff_engine_is_exported_publicly():
    assert VisualDiffEngine is VisualDiffEngineFromModule
    assert VisualDiffError is VisualDiffErrorFromModule


def test_identical_images_produce_no_diff():
    provider = StaticScreenshotProvider(width=20, height=20, color=(255, 255, 255))
    img = provider.capture("x")
    engine = VisualDiffEngine()
    result = engine.compare(img, img)
    assert result.changed is False
    assert result.diff_bytes is None
    assert result.diff_score == 0.0
    assert result.changed_regions == 0


def test_different_images_produce_diff():
    old = StaticScreenshotProvider(width=20, height=20, color=(255, 255, 255)).capture("x")
    new = StaticScreenshotProvider(width=20, height=20, color=(0, 0, 0)).capture("x")
    engine = VisualDiffEngine()
    result = engine.compare(old, new)
    assert result.changed is True
    assert result.diff_bytes is not None
    assert result.diff_score > 0.0
    assert result.changed_regions >= 1


def test_different_dimensions_are_padded_not_stretched():
    old = StaticScreenshotProvider(width=20, height=20, color=(255, 255, 255)).capture("x")
    new = Image.new("RGB", (20, 30), (255, 255, 255))
    # Add a black strip in the extra 10 rows at the bottom
    ImageDraw.Draw(new).rectangle((0, 20, 19, 29), fill=(0, 0, 0))
    new_bytes = BytesIO()
    new.save(new_bytes, format="PNG")
    engine = VisualDiffEngine()
    result = engine.compare(old, new_bytes.getvalue())
    # Only the padded area at the bottom should differ
    assert result.changed is True
    assert result.changed_regions >= 1


def test_multiple_regions_are_detected():
    # Create two 40x20 images: old is white, new has two black squares
    old = Image.new("RGB", (40, 20), (255, 255, 255))
    new = Image.new("RGB", (40, 20), (255, 255, 255))
    draw = ImageDraw.Draw(new)
    draw.rectangle((2, 2, 7, 7), fill=(0, 0, 0))
    draw.rectangle((25, 10, 32, 17), fill=(0, 0, 0))

    old_bytes = BytesIO()
    old.save(old_bytes, format="PNG")
    new_bytes = BytesIO()
    new.save(new_bytes, format="PNG")

    engine = VisualDiffEngine(min_region_size=2)
    result = engine.compare(old_bytes.getvalue(), new_bytes.getvalue())
    assert result.changed is True
    assert result.changed_regions == 2


def test_min_region_size_filters_small_changes():
    # Single 2x2 black square on white background
    old = Image.new("RGB", (20, 20), (255, 255, 255))
    new = Image.new("RGB", (20, 20), (255, 255, 255))
    draw = ImageDraw.Draw(new)
    draw.rectangle((5, 5, 6, 6), fill=(0, 0, 0))

    old_bytes = BytesIO()
    old.save(old_bytes, format="PNG")
    new_bytes = BytesIO()
    new.save(new_bytes, format="PNG")

    engine = VisualDiffEngine(min_region_size=10)
    result = engine.compare(old_bytes.getvalue(), new_bytes.getvalue())
    # Diff pixels exist but region is too small, so treated as unchanged
    assert result.changed is False
    assert result.changed_regions == 0
    assert result.diff_bytes is None


def test_invalid_image_bytes_raise_visual_diff_error():
    engine = VisualDiffEngine()
    with pytest.raises(VisualDiffError):
        engine.compare(b"not-an-image", b"not-an-image")
