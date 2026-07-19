import pytest
from pydantic import ValidationError

from core.visual import VisualDiffResult
from core.visual.models import VisualDiffResult as VisualDiffResultFromModels


def test_visual_diff_result_is_exported_publicly():
    assert VisualDiffResult is VisualDiffResultFromModels


def test_visual_diff_result_with_required_fields():
    result = VisualDiffResult(changed=True, diff_score=0.5, changed_regions=3)
    assert result.changed is True
    assert result.diff_score == 0.5
    assert result.changed_regions == 3
    assert result.diff_bytes is None


def test_diff_bytes_round_trips():
    result = VisualDiffResult(changed=True, diff_score=0.1, changed_regions=1, diff_bytes=b"pngdata")
    assert result.changed is True
    assert result.diff_score == 0.1
    assert result.changed_regions == 1
    assert result.diff_bytes == b"pngdata"


@pytest.mark.parametrize("field", ["changed", "diff_score", "changed_regions"])
def test_required_fields(field):
    data = {"changed": True, "diff_score": 0.5, "changed_regions": 1}
    data.pop(field)
    with pytest.raises(ValidationError):
        VisualDiffResult(**data)


def test_boundary_values_are_accepted():
    VisualDiffResult(changed=True, diff_score=0.0, changed_regions=0)
    VisualDiffResult(changed=True, diff_score=1.0, changed_regions=0)


def test_diff_score_must_be_non_negative():
    with pytest.raises(ValidationError):
        VisualDiffResult(changed=True, diff_score=-0.1, changed_regions=1)


def test_diff_score_must_be_at_most_one():
    with pytest.raises(ValidationError):
        VisualDiffResult(changed=True, diff_score=1.1, changed_regions=1)


def test_changed_regions_must_be_non_negative():
    with pytest.raises(ValidationError):
        VisualDiffResult(changed=True, diff_score=0.5, changed_regions=-1)
