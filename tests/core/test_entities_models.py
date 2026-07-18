from core.entities.models import Entity, CorrelatedEntity


def test_entity_requires_id_and_name():
    e = Entity(entity_id="prod-1", name="T-Shirt", value="19.99")
    assert e.entity_id == "prod-1"
    assert e.name == "T-Shirt"
    assert e.value == "19.99"


def test_correlated_entity_tracks_change():
    c = CorrelatedEntity(
        entity_id="prod-1",
        name="T-Shirt",
        old_value="19.99",
        new_value="17.99",
        changed=True,
        status="changed",
    )
    assert c.old_value == "19.99"
    assert c.new_value == "17.99"
    assert c.changed is True
