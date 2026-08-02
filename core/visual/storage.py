from pathlib import Path
from typing import Optional, Protocol, runtime_checkable


@runtime_checkable
class ScreenshotStorage(Protocol):
    """Port for persisting and loading screenshot/diff image bytes."""

    def save_snapshot(self, site_id: int, snapshot_id: int, data: bytes) -> str:
        """Persist raw screenshot bytes and return the relative path."""
        ...

    def load_snapshot(self, site_id: int, snapshot_id: int) -> Optional[bytes]:
        """Load raw screenshot bytes, or None if missing."""
        ...

    def save_diff(self, site_id: int, change_id: int, data: bytes) -> str:
        """Persist diff overlay bytes and return the relative path."""
        ...

    def load_diff(self, site_id: int, change_id: int) -> Optional[bytes]:
        """Load diff overlay bytes, or None if missing."""
        ...

    def exists(self, relative_path: str) -> bool:
        """Return True if the relative path exists under storage."""
        ...


class FileSystemScreenshotStorage:
    """Store screenshots under <project_root>/data/screenshots/{site_id}/..."""

    def __init__(self, base_dir: str = "."):
        self.base_dir = Path(base_dir).resolve()
        self.screenshots_dir = self.base_dir / "data" / "screenshots"

    def save_snapshot(self, site_id: int, snapshot_id: int, data: bytes) -> str:
        path = self._snapshot_path(site_id, snapshot_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path.relative_to(self.base_dir).as_posix()

    def load_snapshot(self, site_id: int, snapshot_id: int) -> Optional[bytes]:
        path = self._snapshot_path(site_id, snapshot_id)
        if not path.exists():
            return None
        return path.read_bytes()

    def save_diff(self, site_id: int, change_id: int, data: bytes) -> str:
        path = self._diff_path(site_id, change_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path.relative_to(self.base_dir).as_posix()

    def load_diff(self, site_id: int, change_id: int) -> Optional[bytes]:
        path = self._diff_path(site_id, change_id)
        if not path.exists():
            return None
        return path.read_bytes()

    def exists(self, relative_path: str) -> bool:
        target = (self.base_dir / relative_path).resolve()
        return target.exists() and target.is_relative_to(self.base_dir)

    def _snapshot_path(self, site_id: int, snapshot_id: int) -> Path:
        return self.screenshots_dir / str(site_id) / f"{snapshot_id}.png"

    def _diff_path(self, site_id: int, change_id: int) -> Path:
        return self.screenshots_dir / str(site_id) / "diffs" / f"{change_id}.png"
