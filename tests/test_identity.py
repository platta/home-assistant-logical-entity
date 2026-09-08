"""Stable logical identity across reload/restart, for both configuration
sources (ticket item: "stable identity across reload/restart"; design §4).
"""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.logical_entity.const import (
    CONF_CAPABILITY_CONTRACT,
    CONF_DOMAIN,
    CONF_SOURCE,
    DOMAIN,
)
from custom_components.logical_entity.yaml_config import async_reconcile_yaml_logical_entities

from .conftest import create_source_entity, entity_id_for_logical_entity as get_entity_id_for_logical_entity


async def test_ui_owned_logical_entity_unique_id_is_the_config_entry_id(hass: HomeAssistant) -> None:
    """design §4: "UI-owned logical entity: the config entry ID" — the switch_as_x
    pattern."""
    source = create_source_entity(hass, "light", "nanoleaf", state="on")
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Kitchen Counter",
        data={CONF_DOMAIN: "light"},
        options={CONF_SOURCE: source, CONF_CAPABILITY_CONTRACT: {}, "hide_source": False},
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    logical_id = get_entity_id_for_logical_entity(hass, "light", entry.entry_id)
    assert er.async_get(hass).async_get(logical_id).unique_id == entry.entry_id


async def test_ui_owned_logical_entity_survives_unload_reload_with_same_identity(
    hass: HomeAssistant,
) -> None:
    """Simulates a config-entry reload (the same primitive an HA restart
    drives): unique_id is unchanged."""
    source = create_source_entity(hass, "light", "nanoleaf", state="on")
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Kitchen Counter",
        data={CONF_DOMAIN: "light"},
        options={CONF_SOURCE: source, CONF_CAPABILITY_CONTRACT: {}, "hide_source": False},
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    logical_id = get_entity_id_for_logical_entity(hass, "light", entry.entry_id)
    unique_id_before = er.async_get(hass).async_get(logical_id).unique_id

    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()

    assert get_entity_id_for_logical_entity(hass, "light", entry.entry_id) == logical_id
    assert er.async_get(hass).async_get(logical_id).unique_id == unique_id_before


async def test_yaml_owned_logical_entity_unique_id_is_the_declared_logical_id(hass: HomeAssistant) -> None:
    """design §4: "YAML-owned logical entity: an author-declared logical_id slug"."""
    source = create_source_entity(hass, "light", "nanoleaf", state="on")
    await async_reconcile_yaml_logical_entities(
        hass,
        {
            DOMAIN: [
                {
                    "logical_id": "kitchen_counter",
                    "domain": "light",
                    "source": source,
                    "name": "Kitchen Counter",
                }
            ]
        },
    )
    await hass.async_block_till_done()

    assert (
        er.async_get(hass).async_get("light.kitchen_counter").unique_id == "kitchen_counter"
    )


async def test_yaml_owned_logical_entity_identity_stable_across_simulated_restart(
    hass: HomeAssistant,
) -> None:
    """Simulates an HA restart for the declarative path: tear down every
    running logical entity (as unload-on-stop would) and re-apply the same file from
    a cold reconcile — unique_id/entity_id converge to the same values,
    since YAML-owned identity is author-declared and lives in the file
    itself (design §6.3: "bindings converge to Git with no dependence on
    .storage")."""
    source = create_source_entity(hass, "light", "nanoleaf", state="on")
    config = {
        DOMAIN: [
            {
                "logical_id": "kitchen_counter",
                "domain": "light",
                "source": source,
                "name": "Kitchen Counter",
            }
        ]
    }

    await async_reconcile_yaml_logical_entities(hass, config)
    await hass.async_block_till_done()
    unique_id_before = er.async_get(hass).async_get("light.kitchen_counter").unique_id

    await async_reconcile_yaml_logical_entities(hass, {DOMAIN: []})
    await hass.async_block_till_done()
    assert hass.states.get("light.kitchen_counter") is None

    await async_reconcile_yaml_logical_entities(hass, config)
    await hass.async_block_till_done()

    assert er.async_get(hass).async_get("light.kitchen_counter").unique_id == unique_id_before
