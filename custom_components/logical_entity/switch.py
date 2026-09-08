"""Switch platform for Logical Entity (design §9.2)."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import (
    CONF_CAPABILITY_CONTRACT,
    CONF_DEVICE_CLASS,
    CONF_HIDE_SOURCE,
    CONF_LOGICAL_ID,
    CONF_NAME,
    CONF_SOURCE,
    DEFAULT_HIDE_SOURCE,
    DOMAIN_SWITCH,
)
from .entity import LogicalEntity
from .helpers import async_resolve_source_ref


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    async_add_entities([LogicalEntitySwitch.from_config_entry(hass, entry)])


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    if discovery_info is None:
        return
    async_add_entities(
        [
            LogicalEntitySwitch.from_yaml_record(hass, record)
            for record in discovery_info["logical_entities"]
        ]
    )


class LogicalEntitySwitch(LogicalEntity, SwitchEntity):
    """A logical switch/outlet proxying a bound source switch entity.

    The device_class (design §9.2: e.g. "outlet") is declared by the logical
    entity and independent of what the currently bound hardware reports, so
    a swap cannot flip the icon/semantics.
    """

    @classmethod
    def from_config_entry(cls, hass: HomeAssistant, entry: ConfigEntry) -> "LogicalEntitySwitch":
        source_ref = entry.options.get(CONF_SOURCE)
        resolved = async_resolve_source_ref(hass, source_ref) if source_ref else None
        entity = cls(
            logical_id=entry.entry_id,
            domain=DOMAIN_SWITCH,
            name=entry.title,
            source_entity_id=resolved,
            contract=entry.options.get(CONF_CAPABILITY_CONTRACT, {}),
            source_ref=source_ref,
            hide_source=entry.options.get(CONF_HIDE_SOURCE, DEFAULT_HIDE_SOURCE),
        )
        entity._attr_device_class = entry.options.get(CONF_DEVICE_CLASS)
        return entity

    @classmethod
    def from_yaml_record(cls, hass: HomeAssistant, record: dict[str, Any]) -> "LogicalEntitySwitch":
        source_ref = record.get(CONF_SOURCE)
        resolved = async_resolve_source_ref(hass, source_ref) if source_ref else None
        entity = cls(
            logical_id=record[CONF_LOGICAL_ID],
            domain=DOMAIN_SWITCH,
            # LOGICAL_ENTITY_SCHEMA now requires a non-blank `name`
            # (PLAT-150) — no logical_id fallback needed or wanted; a
            # name-less record never reaches here (see yaml_config.py's
            # module docstring).
            name=record[CONF_NAME],
            source_entity_id=resolved,
            contract=record.get(CONF_CAPABILITY_CONTRACT, {}),
            source_ref=source_ref,
            hide_source=record.get(CONF_HIDE_SOURCE, DEFAULT_HIDE_SOURCE),
            # Pin first-creation entity_id to logical_id, independent of the
            # now-independent `name` — see LogicalEntity.suggested_object_id.
            object_id=record[CONF_LOGICAL_ID],
        )
        entity._attr_device_class = record.get(CONF_DEVICE_CLASS)
        return entity

    @property
    def is_on(self) -> bool | None:
        if self.source_state is None:
            return None
        return self.source_state.state == "on"

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.async_forward_command("turn_on", kwargs)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.async_forward_command("turn_off", kwargs)
