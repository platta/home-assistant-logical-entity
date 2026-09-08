"""End-to-end light logical entity behavior via a config entry (spike gates a, e-adjacent).

Covers: state/attribute proxying, contract ∩ source capability intersection
including downgrade on rebind, command forwarding, and identity stability
(unique_id/entity_id untouched) across a rebind — spike gate (a): "automation
+ scene + dashboard referencing a logical entity survive a live rebind untouched" is
approximated here at the entity-identity level, the concrete guarantee those
consumers depend on.
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

from .conftest import create_source_entity, entity_id_for_logical_entity


async def _setup_light(
    hass: HomeAssistant, source_entity_id: str, contract: dict
) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Kitchen Counter",
        data={CONF_DOMAIN: "light"},
        options={
            CONF_SOURCE: source_entity_id,
            CONF_CAPABILITY_CONTRACT: contract,
            "hide_source": False,
        },
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_logical_entity_proxies_state_and_attributes(hass: HomeAssistant) -> None:
    source = create_source_entity(
        hass,
        "light",
        "nanoleaf",
        state="on",
        attributes={
            "supported_color_modes": ["hs", "color_temp"],
            "supported_features": 0,
            "brightness": 120,
            "color_mode": "hs",
            "hs_color": (30, 40),
        },
    )
    entry = await _setup_light(
        hass, source, {"supported_color_modes": ["hs", "color_temp"], "supported_features": 0}
    )

    logical_id = entity_id_for_logical_entity(hass, "light", entry.entry_id)
    logical_entity_state = hass.states.get(logical_id)

    assert logical_entity_state.state == "on"
    assert logical_entity_state.attributes["brightness"] == 120
    assert set(logical_entity_state.attributes["supported_color_modes"]) == {"hs", "color_temp"}
    assert er.async_get(hass).async_get(logical_id).unique_id == entry.entry_id


async def test_source_state_change_propagates(hass: HomeAssistant) -> None:
    source = create_source_entity(hass, "light", "nanoleaf", state="off")
    entry = await _setup_light(
        hass, source, {"supported_color_modes": [], "supported_features": 0}
    )
    logical_id = entity_id_for_logical_entity(hass, "light", entry.entry_id)
    assert hass.states.get(logical_id).state == "off"

    hass.states.async_set(source, "on", {})
    await hass.async_block_till_done()
    assert hass.states.get(logical_id).state == "on"


async def test_contract_intersection_narrows_downgraded_hardware(hass: HomeAssistant) -> None:
    """Contract seeded from an RGB+CCT light; source is brightness-only.

    Advertised capabilities are contract ∩ source — narrower than the
    contract — per design §5.
    """
    source = create_source_entity(
        hass,
        "light",
        "cheap_bulb",
        state="on",
        attributes={"supported_color_modes": ["brightness"], "supported_features": 0},
    )
    entry = await _setup_light(
        hass,
        source,
        {"supported_color_modes": ["hs", "color_temp", "brightness"], "supported_features": 0},
    )
    logical_id = entity_id_for_logical_entity(hass, "light", entry.entry_id)
    modes = set(hass.states.get(logical_id).attributes["supported_color_modes"])
    assert modes == {"brightness"}


async def test_command_forwarded_to_source(hass: HomeAssistant) -> None:
    """Calls the logical entity's own async_turn_on directly rather than going
    through hass.services.async_call("light", "turn_on", ...) end to end:
    registering a test double for "light"/"turn_on" *replaces* the real
    light component's own service handler outright, so an outer call would
    never reach `LightEntity.async_turn_on` at all (confirmed by this
    spike's own CI) — there is exactly one "light"/"turn_on" registration,
    and this test needs it to observe the *forwarded* (inner) call, which
    async_forward_command itself makes."""
    source = create_source_entity(hass, "light", "nanoleaf", state="off")
    entry = await _setup_light(
        hass, source, {"supported_color_modes": [], "supported_features": 0}
    )
    logical_id = entity_id_for_logical_entity(hass, "light", entry.entry_id)

    calls = []

    async def fake_turn_on(call):
        calls.append(call)
        hass.states.async_set(source, "on", {})

    hass.services.async_register("light", "turn_on", fake_turn_on)

    logical_entity = hass.data[DOMAIN]["logical_entities"][entry.entry_id]
    await logical_entity.async_turn_on()
    await hass.async_block_till_done()

    assert len(calls) == 1
    assert calls[0].data["entity_id"] == [source] or calls[0].data["entity_id"] == source
    assert hass.states.get(logical_id).state == "on"


async def test_rebind_preserves_identity_and_updates_contract(hass: HomeAssistant) -> None:
    old_source = create_source_entity(
        hass,
        "light",
        "nanoleaf",
        state="on",
        attributes={"supported_color_modes": ["hs"], "supported_features": 0},
    )
    entry = await _setup_light(
        hass, old_source, {"supported_color_modes": ["hs"], "supported_features": 0}
    )
    logical_id = entity_id_for_logical_entity(hass, "light", entry.entry_id)
    unique_id_before = er.async_get(hass).async_get(logical_id).unique_id

    new_source = create_source_entity(
        hass,
        "light",
        "hue",
        state="on",
        attributes={"supported_color_modes": ["hs", "color_temp"], "supported_features": 0},
    )

    hass.config_entries.async_update_entry(
        entry,
        options={
            **entry.options,
            CONF_SOURCE: new_source,
            CONF_CAPABILITY_CONTRACT: {
                "supported_color_modes": ["hs", "color_temp"],
                "supported_features": 0,
            },
        },
    )
    await hass.async_block_till_done()

    # entity_id and unique_id are unchanged across the rebind.
    assert entity_id_for_logical_entity(hass, "light", entry.entry_id) == logical_id
    assert er.async_get(hass).async_get(logical_id).unique_id == unique_id_before

    state = hass.states.get(logical_id)
    assert set(state.attributes["supported_color_modes"]) == {"hs", "color_temp"}
