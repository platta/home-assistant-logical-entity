"""Empty declarative `logical_entity:` configuration (PLAT-144).

Live PLAT-143 validation found that a valid empty YAML declaration —
`logical_entity: []` reached via an `!include` whose target file was empty —
was rejected at HA startup as though it were a single, entirely blank logical entity
record (`required key 'logical_id'/'domain'/'source' not provided`).

Root cause: `homeassistant.util.yaml.loader._include_yaml` substitutes an
empty *dict* (`NodeDictClass()`), not an empty list, whenever an included
file's content parses to `None` (empty file, or a file containing only
comments — exactly the fresh GitOps-install/bootstrap state design intends
to support). `cv.ensure_list` then wraps that single empty dict into
`[{}]`, and `LOGICAL_ENTITY_SCHEMA` correctly rejects that lone blank record. A bare
`logical_entity:` key with no value hits the same path directly, since it
parses to `None` before `!include` is even involved.

`yaml_config._ensure_logical_entity_records` (composed into `LOGICAL_ENTITY_LIST_SCHEMA`, and
from there into `CONFIG_SCHEMA`) closes this: `None` and `{}` are both
normalized to "zero declared logical entities" ahead of `cv.ensure_list`'s generic
single-item wrap, while every other case (a real list, or a genuine
non-empty single-record dict) is unaffected.
"""

from __future__ import annotations

import pytest
import voluptuous as vol
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from custom_components.logical_entity import CONFIG_SCHEMA
from custom_components.logical_entity.const import DOMAIN
from custom_components.logical_entity.yaml_config import (
    LOGICAL_ENTITY_LIST_SCHEMA,
    async_reconcile_yaml_logical_entities,
)

from .conftest import create_source_entity

# --- LOGICAL_ENTITY_LIST_SCHEMA: unit-level coverage of the normalizer itself -------


def test_logical_entity_list_schema_treats_none_as_zero_records() -> None:
    """A bare `logical_entity:` key with no value (`None`) — zero logical entities."""
    assert LOGICAL_ENTITY_LIST_SCHEMA(None) == []


def test_logical_entity_list_schema_treats_empty_dict_as_zero_records() -> None:
    """The `!include`-of-an-empty-file shape (`{}`) — zero logical entities, the exact
    production failure this issue reports."""
    assert LOGICAL_ENTITY_LIST_SCHEMA({}) == []


def test_logical_entity_list_schema_accepts_empty_list_unchanged() -> None:
    """A real empty list — `logical_entity: []`, or an `!include` resolving to
    a file whose content is literally `[]` — was never broken; confirm it
    still passes through unchanged."""
    assert LOGICAL_ENTITY_LIST_SCHEMA([]) == []


def test_logical_entity_list_schema_still_wraps_nonempty_single_record_shorthand() -> None:
    """Negative control: a genuine single-record dict (not empty) must
    still be treated as one record via the standard ensure_list shorthand,
    not silently dropped by the empty-value fast path."""
    record = {
        "logical_id": "kitchen_counter",
        "domain": "light",
        "source": "light.x",
        "name": "Kitchen Counter",
    }
    validated = LOGICAL_ENTITY_LIST_SCHEMA(record)
    assert len(validated) == 1
    assert validated[0]["logical_id"] == "kitchen_counter"


def test_logical_entity_list_schema_still_rejects_a_genuinely_incomplete_record() -> None:
    """Negative control: an actually-incomplete record (missing required
    keys, but not the empty-dict sentinel) must still fail loudly — the fix
    narrowly targets the empty-value case, not per-record validation."""
    with pytest.raises(vol.Invalid):
        LOGICAL_ENTITY_LIST_SCHEMA({"logical_id": "kitchen_counter"})


# --- CONFIG_SCHEMA: the actual top-level schema HA validates against ------


@pytest.mark.parametrize("empty_value", [None, {}, []])
def test_config_schema_accepts_every_empty_shape(empty_value) -> None:
    validated = CONFIG_SCHEMA({DOMAIN: empty_value})
    assert validated[DOMAIN] == []


# --- End-to-end: HA setup with an empty declaration ------------------------


async def test_setup_with_none_starts_clean_with_zero_logical_entities(hass: HomeAssistant) -> None:
    """`logical_entity:` with no value must not fail component setup."""
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: None})
    await hass.async_block_till_done()

    logical_entities = [
        e for e in hass.states.async_all() if e.entity_id.startswith(("light.", "switch.", "binary_sensor."))
    ]
    assert logical_entities == []


async def test_setup_with_include_style_empty_dict_starts_clean(hass: HomeAssistant) -> None:
    """The exact shape `!include` produces for an empty/comment-only file —
    an empty dict — must not fail component setup either."""
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
    await hass.async_block_till_done()
    assert hass.states.async_all() == []


async def test_setup_with_empty_list_starts_clean(hass: HomeAssistant) -> None:
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: []})
    await hass.async_block_till_done()
    assert hass.states.async_all() == []


async def test_later_valid_declaration_still_creates_logical_entities_normally(
    hass: HomeAssistant,
) -> None:
    """A fresh/bootstrap install starts with zero logical entities, then a later,
    genuinely populated declaration must still create logical entities normally —
    the empty-input fix must not regress the ordinary populated path."""
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: []})
    await hass.async_block_till_done()

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
