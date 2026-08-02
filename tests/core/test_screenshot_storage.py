import tempfile
from pathlib import Path

from core.visual.storage import FileSystemScreenshotStorage


def test_save_and_load_snapshot():
    with tempfile.TemporaryDirectory() as tmp:
        storage = FileSystemScreenshotStorage(base_dir=tmp)
        path = storage.save_snapshot(site_id=1, snapshot_id=42, data=b"png")
        assert path == "data/screenshots/1/42.png"
        assert storage.exists(path) is True
        assert storage.load_snapshot(1, 42) == b"png"


def test_save_and_load_diff():
    with tempfile.TemporaryDirectory() as tmp:
        storage = FileSystemScreenshotStorage(base_dir=tmp)
        path = storage.save_diff(site_id=1, change_id=7, data=b"diff")
        assert path == "data/screenshots/1/diffs/7.png"
        assert storage.exists(path) is True
        assert storage.load_diff(1, 7) == b"diff"


def test_load_missing_returns_none():
    with tempfile.TemporaryDirectory() as tmp:
        storage = FileSystemScreenshotStorage(base_dir=tmp)
        assert storage.load_snapshot(1, 999) is None
        assert storage.load_diff(1, 999) is None
        assert storage.exists("data/screenshots/1/999.png") is False


def test_overwrite_existing_snapshot():
    with tempfile.TemporaryDirectory() as tmp:
        storage = FileSystemScreenshotStorage(base_dir=tmp)
        storage.save_snapshot(1, 1, b"first")
        storage.save_snapshot(1, 1, b"second")
        assert storage.load_snapshot(1, 1) == b"second"


def test_exists_rejects_out_of_bounds_file():
    with tempfile.TemporaryDirectory() as tmp:
        outside = Path(tmp).parent / "outside.txt"
        outside.write_text("secret")
        storage = FileSystemScreenshotStorage(base_dir=tmp)
        assert storage.exists("../outside.txt") is False
        assert storage.exists("data/screenshots/../../outside.txt") is False
