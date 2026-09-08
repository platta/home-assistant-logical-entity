"""Light platform for Logical Entity (design §9.1)."""

from __future__ import annotations

from typing import Any

from homeassistant.components.light import ColorMode, LightEntity, LightEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import (
    CONF_CAPABILITY_CONTRACT,
    CONF_HIDE_SOURCE,
    CONF_LOGICAL_ID,
    CONF_NAME,
    CONF_SOURCE,
    DEFAULT_HIDE_SOURCE,
    DOMAIN_LIGHT,
)
from .entity import LogicalEntity
from .helpers import async_resolve_source_ref


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    async_add_entities([LogicalEntityLight.from_config_entry(hass, entry)])


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
            LogicalEntityLight.from_yaml_record(hass, record)
            for record in discovery_info["logical_entities"]
        ]
    )


class LogicalEntityLight(LogicalEntity, LightEntity):
    """A logical light proxying a bound source light entity."""

    @classmethod
    def from_config_entry(cls, hass: HomeAssistant, entry: ConfigEntry) -> "LogicalEntityLight":
        source_ref = entry.options.get(CONF_SOURCE)
        resolved = async_resolve_source_ref(hass, source_ref) if source_ref else None
        return cls(
            logical_id=entry.entry_id,
            domain=DOMAIN_LIGHT,
            name=entry.title,
            source_entity_id=resolved,
            contract=entry.options.get(CONF_CAPABILITY_CONTRACT, {}),
            source_ref=source_ref,
            hide_source=entry.options.get(CONF_HIDE_SOURCE, DEFAULT_HIDE_SOURCE),
        )

    @classmethod
    def from_yaml_record(cls, hass: HomeAssistant, record: dict[str, Any]) -> "LogicalEntityLight":
        source_ref = record.get(CONF_SOURCE)
        resolved = async_resolve_source_ref(hass, source_ref) if source_ref else None
        return cls(
            logical_id=record[CONF_LOGICAL_ID],
            domain=DOMAIN_LIGHT,
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

    @property
    def is_on(self) -> bool | None:
        if self.source_state is None:
            return None
        return self.source_state.state == "on"

    @property
    def supported_color_modes(self) -> set[str] | None:
        source_modes = (
            self.source_state.attributes.get("supported_color_modes")
            if self.source_state
            else None
        )
        modes = self.contract_intersect_iterable("supported_color_modes", source_modes)
        return set(modes) if modes else {ColorMode.ONOFF}

    @property
    def color_mode(self) -> str | None:
        if self.source_state is None:
            return None
        mode = self.source_state.attributes.get("color_mode")
        allowed = self.supported_color_modes
        if mode in allowed:
            return mode
        return next(iter(allowed), None)

    @property
    def brightness(self) -> int | None:
        return self._passthrough_attr("brightness")

    @property
    def color_temp_kelvin(self) -> int | None:
        return self._passthrough_attr("color_temp_kelvin")

    @property
    def hs_color(self) -> tuple[float, float] | None:
        return self._passthrough_attr("hs_color")

    @property
    def rgb_color(self) -> tuple[int, int, int] | None:
        return self._passthrough_attr("rgb_color")

    @property
    def rgbw_color(self) -> tuple[int, int, int, int] | None:
        return self._passthrough_attr("rgbw_color")

    @property
    def effect(self) -> str | None:
        return self._passthrough_attr("effect")

    @property
    def effect_list(self) -> list[str] | None:
        return self._passthrough_attr("effect_list")

    @property
    def supported_features(self) -> LightEntityFeature:
        # Must be a real LightEntityFeature flag, not a plain int: HA's
        # capability_attributes tests membership with `in`, which requires
        # an actual IntFlag instance — confirmed by this spike's own CI
        # (TypeError: argument of type 'int' is not a container or
        # iterable, raised from homeassistant/components/light/__init__.py
        # on the HA dev branch).
        source_features = (
            self.source_state.attributes.get("supported_features")
            if self.source_state
            else None
        )
        return LightEntityFeature(
            self.contract_intersect_bitmask("supported_features", source_features)
        )

    def _passthrough_attr(self, key: str) -> Any:
        if self.source_state is None:
            return None
        return self.source_state.attributes.get(key)

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.async_forward_command("turn_on", kwargs)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.async_forward_command("turn_off", kwargs)
