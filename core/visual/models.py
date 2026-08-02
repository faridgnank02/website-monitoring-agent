from typing import Optional
from pydantic import BaseModel, Field


class VisualDiffResult(BaseModel):
    """Result of comparing two screenshots.

    Fields:
        changed: True if any pixels differ above the threshold.
        diff_score: Ratio of changed pixels (0.0 to 1.0).
        changed_regions: Number of bounding boxes drawn around changed areas.
        diff_bytes: PNG bytes of the highlighted diff overlay, or None if unchanged.
    """

    changed: bool
    diff_score: float = Field(..., ge=0.0, le=1.0)
    changed_regions: int = Field(..., ge=0)
    diff_bytes: Optional[bytes] = None
