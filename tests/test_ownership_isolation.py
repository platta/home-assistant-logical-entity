"""UI-vs-YAML ownership isolation (design §6.1, PLAT-128 carry-forward
item 5): "A logical entity is owned by exactly one source... UI-owned logical entities are
ignored by YAML reconciliation entirely." The spike implemented this by
construction (the two sources never share a logical_id/entry_id namespace, and
`async_reconcile_yaml_logical_entities` only ever touches `DATA_YAML_LOGICAL_ENTITIES`) but shipped
with no dedicated regression test proving it (design §10.2 #24/spike gate f:
"the UI-vs-YAML cross-ownership rule... has no dedicated test — see §4").
"""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from custom_components.logical_entity.const import (
    CONF_CAPABILITY_CONTRACT,
    CONF_DOMAIN,
    CONF_SOURCE,
    DOMAIN,
)
from custom_components.logical_entity.yaml_config import async_reconcile_yaml_logical_entities
from pytest_homeassistant_custom_component.common import MockConfigEntry

from .conftest import create_source_entity, entity_id_for_logical_entity


async def _create_ui_logical_entity(hass: HomeAssistant, source: str) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="UI Logical Entity",
        data={CONF_DOMAIN: "light"},
        options={CONF_SOURCE: source, CONF_CAPABILITY_CONTRACT: {}, "hide_source": False},
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_yaml_reconcile_to_empty_does_not_remove_ui_owned_logical_entity(
    hass: HomeAssistant,
) -> None:
    ui_source = create_source_entity(hass, "light", "ui_source", state="on")
    entry = await _create_ui_logical_entity(hass, ui_source)
    ui_logical_id = entity_id_for_logical_entity(hass, "light", entry.entry_id)

    # An empty YAML file must remove only YAML-owned logical entities (none here) —
    # never touch a UI-owned logical entity, which YAML reconciliation should not even
    # be aware of.
    await async_reconcile_yaml_logical_entities(hass, {DOMAIN: []})
    await hass.async_block_till_done()

    assert hass.states.get(ui_logical_id) is not None
    assert hass.states.get(ui_logical_id).state == "on"


async def test_yaml_reconcile_with_records_does_not_touch_unrelated_ui_owned_logical_entity(
    hass: HomeAssistant,
) -> None:
    ui_source = create_source_entity(hass, "light", "ui_source", state="on")
    entry = await _create_ui_logical_entity(hass, ui_source)
    ui_logical_id = entity_id_for_logical_entity(hass, "light", entry.entry_id)

    yaml_source = create_source_entity(hass, "light", "yaml_source", state="off")
    await async_reconcile_yaml_logical_entities(
        hass,
        {
            DOMAIN: [
                {
                    "logical_id": "kitchen_counter",
                    "domain": "light",
                    "source": yaml_source,
                    "name": "Kitchen Counter",
                }
            ]
        },
    )
    await hass.async_block_till_done()

    # Both logical entities exist independently, each still bound to its own source —
    # reconciling the YAML file neither rebinds nor removes the UI logical entity.
    assert hass.states.get(ui_logical_id).state == "on"
    assert hass.states.get("light.kitchen_counter").state == "off"
    logical_ids = {e.entity_id for e in er.async_get(hass).entities.values() if e.platform == DOMAIN}
    assert logical_ids == {ui_logical_id, "light.kitchen_counter"}


async def test_removing_ui_owned_logical_entity_does_not_affect_yaml_owned_logical_entity(
    hass: HomeAssistant,
) -> None:
    yaml_source = create_source_entity(hass, "light", "yaml_source", state="on")
    await async_reconcile_yaml_logical_entities(
        hass,
        {
            DOMAIN: [
                {
                    "logical_id": "kitchen_counter",
                    "domain": "light",
                    "source": yaml_source,
                    "name": "Kitchen Counter",
                }
            ]
        },
    )
    await hass.async_block_till_done()

    ui_source = create_source_entity(hass, "light", "ui_source", state="on")
    entry = await _create_ui_logical_entity(hass, ui_source)

    assert await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("light.kitchen_counter") is not None
    assert hass.states.get("light.kitchen_counter").state == "on"


async def test_ui_and_yaml_logical_entities_have_independent_identity_namespaces(
    hass: HomeAssistant,
) -> None:
    """design §4: a UI logical entity's identity is its config entry ID; a YAML logical entity's
    is its author-declared logical_id. Creating one never allocates or
    interferes with the other's identity space."""
    yaml_source = create_source_entity(hass, "light", "yaml_source", state="on")
    await async_reconcile_yaml_logical_entities(
        hass,
        {
            DOMAIN: [
                {
                    "logical_id": "kitchen_counter",
                    "domain": "light",
                    "source": yaml_source,
                    "name": "Kitchen Counter",
                }
            ]
        },
    )
    await hass.async_block_till_done()

    ui_source = create_source_entity(hass, "light", "ui_source", state="on")
    entry = await _create_ui_logical_entity(hass, ui_source)
    ui_logical_id = entity_id_for_logical_entity(hass, "light", entry.entry_id)

    registry = er.async_get(hass)
    assert registry.async_get("light.kitchen_counter").unique_id == "kitchen_counter"
    assert registry.async_get(ui_logical_id).unique_id == entry.entry_id
    assert entry.entry_id != "kitchen_counter"
