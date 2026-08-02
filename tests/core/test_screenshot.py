from contextlib import contextmanager
from io import BytesIO
from unittest.mock import MagicMock, call

import pytest
from PIL import Image

from core.visual.screenshot import (
    PlaywrightScreenshotProvider,
    ScreenshotError,
    ScreenshotProvider,
    StaticScreenshotProvider,
)


def test_static_provider_returns_png_bytes():
    provider = StaticScreenshotProvider(width=100, height=50, color=(255, 0, 0))
    data = provider.capture("https://example.com")
    assert data.startswith(b"\x89PNG")


def test_static_provider_can_produce_different_images():
    red = StaticScreenshotProvider(width=10, height=10, color=(255, 0, 0))
    blue = StaticScreenshotProvider(width=10, height=10, color=(0, 0, 255))
    assert red.capture("x") != blue.capture("x")


def test_static_provider_preserves_black_color():
    black = StaticScreenshotProvider(width=10, height=10, color=(0, 0, 0))
    data = black.capture("x")
    with Image.open(BytesIO(data)) as image:
        assert image.getpixel((0, 0)) == (0, 0, 0)


def test_playwright_provider_delegates_to_browser():
    mock_playwright = MagicMock()
    mock_browser = MagicMock()
    mock_page = MagicMock()
    mock_playwright.chromium.launch.return_value = mock_browser
    mock_browser.new_page.return_value = mock_page
    mock_page.screenshot.return_value = b"fakepng"

    @contextmanager
    def mock_sync_playwright():
        yield mock_playwright

    provider = PlaywrightScreenshotProvider(_sync_playwright=mock_sync_playwright)
    result = provider.capture("https://example.com")

    assert result == b"fakepng"
    mock_page.goto.assert_called_once_with("https://example.com", wait_until="networkidle")
    mock_page.screenshot.assert_called_once_with(full_page=True, type="png")
    mock_browser.assert_has_calls([call.new_page().close(), call.close()])


def test_playwright_provider_closes_browser_on_error():
    mock_playwright = MagicMock()
    mock_browser = MagicMock()
    mock_page = MagicMock()
    mock_playwright.chromium.launch.return_value = mock_browser
    mock_browser.new_page.return_value = mock_page
    mock_page.goto.side_effect = RuntimeError("network error")

    @contextmanager
    def mock_sync_playwright():
        yield mock_playwright

    provider = PlaywrightScreenshotProvider(_sync_playwright=mock_sync_playwright)
    with pytest.raises(ScreenshotError):
        provider.capture("https://example.com")

    mock_browser.assert_has_calls([call.new_page().close(), call.close()])


def test_screenshot_provider_is_runtime_checkable():
    assert isinstance(StaticScreenshotProvider(), ScreenshotProvider)
