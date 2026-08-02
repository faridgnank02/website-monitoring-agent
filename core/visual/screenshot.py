from contextlib import AbstractContextManager
from io import BytesIO
from typing import Any, Callable, Optional, Protocol, runtime_checkable

from PIL import Image


@runtime_checkable
class ScreenshotProvider(Protocol):
    """Port for capturing a screenshot of a URL as PNG bytes."""

    def capture(self, url: str) -> bytes:
        """Capture a full-page screenshot and return PNG bytes."""
        ...


class ScreenshotError(Exception):
    """Raised when screenshot capture fails."""
    pass


class StaticScreenshotProvider:
    """Deterministic PNG provider for tests and CI."""

    def __init__(
        self,
        width: int = 1280,
        height: int = 720,
        color: Optional[tuple[int, int, int]] = None,
    ):
        self.width = width
        self.height = height
        self.color = color if color is not None else (100, 150, 200)

    def capture(self, url: str) -> bytes:
        image = Image.new("RGB", (self.width, self.height), self.color)
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        return buffer.getvalue()


# Playwright context manager factory: called with no args returns a context manager
# that yields a Playwright object.
PlaywrightContextFactory = Callable[[], AbstractContextManager[Any]]


class PlaywrightScreenshotProvider:
    """Full-page screenshot via Playwright/Chromium."""

    def __init__(
        self,
        viewport_width: int = 1280,
        viewport_height: int = 720,
        _sync_playwright: Optional[PlaywrightContextFactory] = None,
    ):
        self.viewport = {"width": viewport_width, "height": viewport_height}
        self._sync_playwright = _sync_playwright

    def capture(self, url: str) -> bytes:
        try:
            if self._sync_playwright is not None:
                cm = self._sync_playwright()
            else:
                from playwright.sync_api import sync_playwright
                cm = sync_playwright()
            with cm as playwright:
                return self._capture_with_playwright(playwright, url)
        except Exception as exc:
            raise ScreenshotError(f"Failed to capture screenshot of {url}: {exc}") from exc

    def _capture_with_playwright(self, playwright: Any, url: str) -> bytes:
        browser = playwright.chromium.launch()
        page = None
        try:
            page = browser.new_page(viewport=self.viewport)
            page.goto(url, wait_until="networkidle")
            return page.screenshot(full_page=True, type="png")
        finally:
            if page is not None:
                try:
                    page.close()
                except Exception:
                    pass
            try:
                browser.close()
            except Exception:
                pass
