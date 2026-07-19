from typing import Optional
from core.entities.models import Entity, CorrelatedEntity


def correlate_entities(old: list[Entity], new: list[Entity]) -> list[CorrelatedEntity]:
    old_by_id = {e.entity_id: e for e in old}
    new_by_id = {e.entity_id: e for e in new}

    results: list[CorrelatedEntity] = []
    seen_ids = set()

    for entity_id in new_by_id:
        new_entity = new_by_id[entity_id]
        old_entity = old_by_id.get(entity_id)
        if old_entity is None:
            results.append(CorrelatedEntity(
                entity_id=entity_id,
                name=new_entity.name,
                new_value=new_entity.value,
                unit=new_entity.unit,
                changed=True,
                status="added",
            ))
        else:
            changed = old_entity.value != new_entity.value
            results.append(CorrelatedEntity(
                entity_id=entity_id,
                name=new_entity.name,
                old_value=old_entity.value,
                new_value=new_entity.value,
                unit=new_entity.unit,
                changed=changed,
                status="changed" if changed else "unchanged",
            ))
        seen_ids.add(entity_id)

    for entity_id in old_by_id:
        if entity_id in seen_ids:
            continue
        old_entity = old_by_id[entity_id]
        results.append(CorrelatedEntity(
            entity_id=entity_id,
            name=old_entity.name,
            old_value=old_entity.value,
            unit=old_entity.unit,
            changed=True,
            status="removed",
        ))

    return results
