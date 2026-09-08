"""Declarative (YAML) configuration path — spike gate (d).

Covers: create via YAML, reload without HA restart, rebind-in-place on
reload, a syntax-valid file with one bad record degrading only that logical entity
(design §10.1 R7), and logical entity removal via YAML.

The unparseable-file / top-level-schema-invalid "last-known-good" path is
handled one layer up, in __init__.py's reload service handler: when
homeassistant.helpers.reload.async_integration_yaml_config returns None,
async_reconcile_yaml_logical_entities is never called at all, so every currently
running logical entity is left exactly as it was. That contract is what this module's
async_reconcile_yaml_logical_entities relies on — it only ever receives an
already-syntactically-valid config and is responsible solely for per-record
validity (schema_invalid, duplicate_logical_id, unresolvable source) within it.
"""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er, issue_registry as ir

from custom_components.logical_entity.const import DOMAIN, ISSUE_YAML_RECORD_INVALID
from custom_components.logical_entity.yaml_config import async_reconcile_yaml_logical_entities

from .conftest import create_source_entity


async def test_yaml_logical_entity_created_and_reads_source_state(hass: HomeAssistant) -> None:
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

    state = hass.states.get("light.kitchen_counter")
    assert state is not None
    assert state.state == "on"


async def test_yaml_reload_rebinds_in_place_without_restart(hass: HomeAssistant) -> None:
    source_a = create_source_entity(hass, "light", "nanoleaf", state="on")
    await async_reconcile_yaml_logical_entities(
        hass,
        {
            DOMAIN: [
                {
                    "logical_id": "kitchen_counter",
                    "domain": "light",
                    "source": source_a,
                    "name": "Kitchen Counter",
                }
            ]
        },
    )
    await hass.async_block_till_done()
    entity_id = "light.kitchen_counter"
    unique_id_before = er.async_get(hass).async_get(entity_id).unique_id

    source_b = create_source_entity(hass, "light", "hue", state="off")
    await async_reconcile_yaml_logical_entities(
        hass,
        {
            DOMAIN: [
                {
                    "logical_id": "kitchen_counter",
                    "domain": "light",
                    "source": source_b,
                    "name": "Kitchen Counter",
                }
            ]
        },
    )
    await hass.async_block_till_done()

    # Same entity_id/unique_id — reload updated the running logical entity in place
    # rather than unloading and recreating it (design §10.2 #4's "candidate
    # refinement", adopted here as the implemented behavior for this spike).
    assert er.async_get(hass).async_get(entity_id).unique_id == unique_id_before
    assert hass.states.get(entity_id).state == "off"


async def test_yaml_removal_removes_the_logical_entity(hass: HomeAssistant) -> None:
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
    assert hass.states.get("light.kitchen_counter") is not None

    await async_reconcile_yaml_logical_entities(hass, {DOMAIN: []})
    await hass.async_block_till_done()
    assert hass.states.get("light.kitchen_counter") is None


async def test_bad_record_degrades_only_that_logical_entity(hass: HomeAssistant) -> None:
    """A syntax-valid file with one bad record: the good logical entity still
    reconciles, the bad one is skipped and flagged, not the whole file
    rejected (design §10.1 R7)."""
    good_source = create_source_entity(hass, "light", "nanoleaf", state="on")
    await async_reconcile_yaml_logical_entities(
        hass,
        {
            DOMAIN: [
                {
                    "logical_id": "kitchen_counter",
                    "domain": "light",
                    "source": good_source,
                    "name": "Kitchen Counter",
                },
                {
                    "logical_id": "broken",
                    "domain": "light",
                    "source": "light.does_not_exist",
                    "name": "Broken Logical Entity",
                },
            ]
        },
    )
    await hass.async_block_till_done()

    assert hass.states.get("light.kitchen_counter") is not None
    assert hass.states.get("light.broken") is None

    issue = ir.async_get(hass).async_get_issue(DOMAIN, f"{ISSUE_YAML_RECORD_INVALID}_broken")
    assert issue is not None


async def test_record_becoming_valid_clears_its_issue(hass: HomeAssistant) -> None:
    await async_reconcile_yaml_logical_entities(
        hass,
        {
            DOMAIN: [
                {
                    "logical_id": "broken",
                    "domain": "light",
                    "source": "light.does_not_exist",
                    "name": "Broken Logical Entity",
                }
            ]
        },
    )
    await hass.async_block_till_done()
    assert (
        ir.async_get(hass).async_get_issue(DOMAIN, f"{ISSUE_YAML_RECORD_INVALID}_broken")
        is not None
    )

    fixed_source = create_source_entity(hass, "light", "hue", state="on")
    await async_reconcile_yaml_logical_entities(
        hass,
        {
            DOMAIN: [
                {
                    "logical_id": "broken",
                    "domain": "light",
                    "source": fixed_source,
                    "name": "Broken Logical Entity",
                }
            ]
        },
    )
    await hass.async_block_till_done()

    assert hass.states.get("light.broken") is not None
    assert (
        ir.async_get(hass).async_get_issue(DOMAIN, f"{ISSUE_YAML_RECORD_INVALID}_broken") is None
    )


async def test_existing_logical_entity_becoming_invalid_preserves_last_known_good(
    hass: HomeAssistant,
) -> None:
    """DECISION — ChatGPT (PLAT-126, 2026-09-02T12:14 ET): an existing YAML
    logical entity whose new record is *present but invalid* must keep its prior
    running binding/state and be flagged — not be deleted the way a logical entity
    genuinely omitted from the file is (design §10.1 R7's last-known-good
    contract). See test_yaml_removal_removes_the_logical_entity above for that
    separate, still-correct omitted-logical entity case."""
    good_source = create_source_entity(hass, "light", "nanoleaf", state="on")
    await async_reconcile_yaml_logical_entities(
        hass,
        {
            DOMAIN: [
                {
                    "logical_id": "kitchen_counter",
                    "domain": "light",
                    "source": good_source,
                    "name": "Kitchen Counter",
                }
            ]
        },
    )
    await hass.async_block_till_done()
    entity_id = "light.kitchen_counter"
    unique_id_before = er.async_get(hass).async_get(entity_id).unique_id

    # logical_id "kitchen_counter" is still declared, but this record is
    # invalid (unresolvable source).
    await async_reconcile_yaml_logical_entities(
        hass,
        {
            DOMAIN: [
                {
                    "logical_id": "kitchen_counter",
                    "domain": "light",
                    "source": "light.does_not_exist",
                    "name": "Kitchen Counter",
                }
            ]
        },
    )
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "on"  # still bound to the prior, good source
    assert er.async_get(hass).async_get(entity_id).unique_id == unique_id_before
    issue = ir.async_get(hass).async_get_issue(
        DOMAIN, f"{ISSUE_YAML_RECORD_INVALID}_kitchen_counter"
    )
    assert issue is not None

    # A corrected record updates/rebinds cleanly.
    replacement_source = create_source_entity(hass, "light", "hue", state="off")
    await async_reconcile_yaml_logical_entities(
        hass,
        {
            DOMAIN: [
                {
                    "logical_id": "kitchen_counter",
                    "domain": "light",
                    "source": replacement_source,
                    "name": "Kitchen Counter",
                }
            ]
        },
    )
    await hass.async_block_till_done()

    assert er.async_get(hass).async_get(entity_id).unique_id == unique_id_before
    assert hass.states.get(entity_id).state == "off"
    assert (
        ir.async_get(hass).async_get_issue(DOMAIN, f"{ISSUE_YAML_RECORD_INVALID}_kitchen_counter")
        is None
    )


async def test_duplicate_logical_id_only_first_record_accepted(hass: HomeAssistant) -> None:
    source = create_source_entity(hass, "light", "nanoleaf", state="on")
    await async_reconcile_yaml_logical_entities(
        hass,
        {
            DOMAIN: [
                {"logical_id": "dup", "domain": "light", "source": source, "name": "Dup Logical Entity"},
                {"logical_id": "dup", "domain": "light", "source": source, "name": "Dup Logical Entity"},
            ]
        },
    )
    await hass.async_block_till_done()

    # Count logical entities specifically, not every light-domain entity — the
    # source itself is also in "light" (this spike's own CI caught the
    # ambiguity: len(async_entity_ids("light")) == 2 here, source + logical entity).
    logical_entities = [e for e in er.async_get(hass).entities.values() if e.platform == DOMAIN]
    assert len(logical_entities) == 1
