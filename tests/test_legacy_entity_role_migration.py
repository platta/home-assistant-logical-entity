"""PLAT-220: a YAML-declared logical entity whose logical_id matches a
pre-existing `entity_role`-platform registry entry (the pre-rename
integration) must adopt that entry's entity_id, not register a fresh,
differently-numbered one.

Covers the migration `_migrate_legacy_entity_role_entry`
(yaml_config.py) implements: DECISION — ChatGPT (PLAT-220,
2026-09-08T12:58 ET) required this with test coverage after Opus's
adjudication escalation identified the gap — without it, the entity
registry's (domain, platform, unique_id) key means a same-unique_id
record registers as a genuinely new entry once `platform` changes, orphans
the old one, and forces a collision-avoidance suffix (e.g.
`light.office_test_light_2`) onto the entity_id every automation, scene,
dashboard, and HomeKit binding actually references.
"""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from custom_components.logical_entity.const import DOMAIN
from custom_components.logical_entity.yaml_config import (
    LEGACY_ENTITY_ROLE_PLATFORM,
    async_reconcile_yaml_logical_entities,
)

from .conftest import create_source_entity


def _create_legacy_entity_role_entry(hass: HomeAssistant, domain: str, logical_id: str) -> str:
    """Simulate a registry entry left behind by the pre-PLAT-220
    `entity_role` integration: same domain/unique_id shape, old platform.
    Not loaded this session (no state set) — matching a real deployment
    where the old integration's code no longer exists to load it."""
    registry = er.async_get(hass)
    entry = registry.async_get_or_create(
        domain, LEGACY_ENTITY_ROLE_PLATFORM, logical_id, suggested_object_id=logical_id
    )
    return entry.entity_id


async def test_matching_legacy_entry_is_adopted_not_orphaned(hass: HomeAssistant) -> None:
    """The core case: office_test_light-shaped migration preserves entity_id."""
    legacy_entity_id = _create_legacy_entity_role_entry(hass, "light", "office_test_light")
    assert legacy_entity_id == "light.office_test_light"

    source = create_source_entity(hass, "light", "nanoleaf", state="on")
    await async_reconcile_yaml_logical_entities(
        hass,
        {
            DOMAIN: [
                {
                    "logical_id": "office_test_light",
                    "domain": "light",
                    "source": source,
                    "name": "Office Test Light",
                }
            ]
        },
    )
    await hass.async_block_till_done()

    # Same entity_id as the legacy entry, NOT light.office_test_light_2.
    state = hass.states.get("light.office_test_light")
    assert state is not None
    assert state.state == "on"
    assert hass.states.get("light.office_test_light_2") is None

    registry = er.async_get(hass)
    entry = registry.async_get(legacy_entity_id)
    assert entry is not None
    assert entry.platform == DOMAIN
    assert entry.unique_id == "office_test_light"
    # The legacy (domain, entity_role, logical_id) lookup no longer resolves
    # anything -- the entry itself moved, it wasn't duplicated.
    assert (
        registry.async_get_entity_id("light", LEGACY_ENTITY_ROLE_PLATFORM, "office_test_light")
        is None
    )


async def test_no_legacy_entry_creates_normally(hass: HomeAssistant) -> None:
    """Negative control: nothing to migrate -> ordinary first-time creation,
    no crash, no spurious registry entries."""
    source = create_source_entity(hass, "light", "nanoleaf", state="on")
    await async_reconcile_yaml_logical_entities(
        hass,
        {
            DOMAIN: [
                {
                    "logical_id": "brand_new_light",
                    "domain": "light",
                    "source": source,
                    "name": "Brand New Light",
                }
            ]
        },
    )
    await hass.async_block_till_done()

    state = hass.states.get("light.brand_new_light")
    assert state is not None
    assert state.state == "on"

    registry = er.async_get(hass)
    entry = registry.async_get("light.brand_new_light")
    assert entry is not None
    assert entry.platform == DOMAIN


async def test_migration_runs_once_not_reattempted_on_later_reconcile(hass: HomeAssistant) -> None:
    """A second reconcile of an already-migrated (now DOMAIN-platform)
    logical entity must rebind in place as usual, not re-attempt migration
    (which would be a no-op anyway, since the legacy-platform lookup no
    longer matches) or otherwise disturb its now-current registry entry."""
    _create_legacy_entity_role_entry(hass, "light", "office_test_light")
    source_a = create_source_entity(hass, "light", "nanoleaf", state="on")
    config = {
        DOMAIN: [
            {
                "logical_id": "office_test_light",
                "domain": "light",
                "source": source_a,
                "name": "Office Test Light",
            }
        ]
    }
    await async_reconcile_yaml_logical_entities(hass, config)
    await hass.async_block_till_done()

    registry = er.async_get(hass)
    unique_id_before = registry.async_get("light.office_test_light").unique_id

    source_b = create_source_entity(hass, "light", "hue", state="off")
    config[DOMAIN][0]["source"] = source_b
    await async_reconcile_yaml_logical_entities(hass, config)
    await hass.async_block_till_done()

    # Same entity, rebound in place -- not a second migration/creation.
    assert registry.async_get("light.office_test_light").unique_id == unique_id_before
    assert hass.states.get("light.office_test_light").state == "off"
    assert hass.states.get("light.office_test_light_2") is None


async def test_mismatched_logical_id_does_not_adopt_unrelated_legacy_entry(
    hass: HomeAssistant,
) -> None:
    """A legacy entry under a *different* unique_id must not be touched by
    an unrelated new declaration -- the lookup is keyed on the exact
    logical_id, not "any" legacy entity_role entry in the same domain."""
    unrelated_legacy_entity_id = _create_legacy_entity_role_entry(hass, "light", "some_other_light")

    source = create_source_entity(hass, "light", "nanoleaf", state="on")
    await async_reconcile_yaml_logical_entities(
        hass,
        {
            DOMAIN: [
                {
                    "logical_id": "office_test_light",
                    "domain": "light",
                    "source": source,
                    "name": "Office Test Light",
                }
            ]
        },
    )
    await hass.async_block_till_done()

    registry = er.async_get(hass)
    unrelated_entry = registry.async_get(unrelated_legacy_entity_id)
    assert unrelated_entry is not None
    assert unrelated_entry.platform == LEGACY_ENTITY_ROLE_PLATFORM

    new_entry = registry.async_get("light.office_test_light")
    assert new_entry is not None
    assert new_entry.platform == DOMAIN
    assert new_entry.entity_id != unrelated_legacy_entity_id
