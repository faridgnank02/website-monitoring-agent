from typing import Optional
from pydantic import BaseModel, ConfigDict


class Entity(BaseModel):
    model_config = ConfigDict(frozen=True)

    entity_id: str
    name: str
    value: str
    # FIXME: Temporary shim for AnalystAgent backward compatibility.
    # Remove once AnalystAgent uses correlate_entities() and CorrelatedEntity.
    old_value: Optional[str] = None
    unit: Optional[str] = None
    context: Optional[str] = None


class CorrelatedEntity(BaseModel):
    entity_id: str
    name: str
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    unit: Optional[str] = None
    changed: bool = False
    status: str = "unchanged"  # unchanged | changed | added | removed
