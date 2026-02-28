"""Platform for light integration."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

import python_rako
from python_rako.exceptions import RakoBridgeError

from homeassistant.components.light import (
    ATTR_EFFECT,
    ColorMode,
    LightEntity,
    LightEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import DOMAIN
from .util import create_unique_id

if TYPE_CHECKING:
    from .bridge import RakoBridge
    from .model import RakoDomainEntryData

_LOGGER = logging.getLogger(__name__)

# Scene effects - no "Off" effect, that's handled by turn_off
SCENE_EFFECTS = ["Scene 1", "Scene 2", "Scene 3", "Scene 4"]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the config entry."""
    rako_domain_entry_data: RakoDomainEntryData = hass.data[DOMAIN][entry.unique_id]
    bridge = rako_domain_entry_data["rako_bridge_client"]

    light_entities: list[RakoRoomLight] = []
    session = async_get_clientsession(hass)

    bridge.level_cache, bridge.scene_cache = await bridge.get_cache_state()

    async for light in bridge.discover_lights(session):
        # Only create lights for room lights, not individual channels
        if isinstance(light, python_rako.RoomLight):
            light_entity = RakoRoomLight(bridge, light)
            light_entities.append(light_entity)

    async_add_entities(light_entities, True)


class RakoRoomLight(LightEntity, RestoreEntity):
    """Representation of a Rako Room as a Light with scene effects."""

    _attr_color_mode = ColorMode.ONOFF
    _attr_supported_color_modes = {ColorMode.ONOFF}
    _attr_supported_features = LightEntityFeature.EFFECT

    def __init__(self, bridge: RakoBridge, light: python_rako.RoomLight) -> None:
        """Initialize a RakoRoomLight."""
        self.bridge = bridge
        self._light = light
        self._current_scene = self.bridge.scene_cache.get(light.room_id, 0)
        self._last_scene = 1  # Default to Scene 1
        self._available = True
        self._attr_effect_list = SCENE_EFFECTS

    @property
    def name(self) -> str:
        """Return the display name of this light."""
        return self._light.room_title

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        await super().async_added_to_hass()

        # Restore last scene from previous state
        if (last_state := await self.async_get_last_state()) is not None:
            if last_state.attributes.get("last_scene"):
                self._last_scene = last_state.attributes["last_scene"]
                _LOGGER.debug(
                    "Restored last scene %d for %s",
                    self._last_scene,
                    self._light.room_title,
                )

        await self.bridge.register_for_state_updates(self)

    async def async_will_remove_from_hass(self) -> None:
        """Run when entity about to be removed from hass."""
        await self.bridge.deregister_for_state_updates(self)

    @property
    def unique_id(self) -> str:
        """Light's unique ID."""
        return create_unique_id(self.bridge.mac, self._light.room_id, 0)

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._available

    @property
    def is_on(self) -> bool:
        """Return True if light is on (scene > 0)."""
        return self._current_scene > 0

    @property
    def effect(self) -> str | None:
        """Return the current effect (scene name) or None if off."""
        if self._current_scene > 0:
            return SCENE_EFFECTS[self._current_scene - 1]
        return None

    @property
    def current_scene(self) -> int:
        """Return the current scene number (0-4)."""
        return self._current_scene

    @current_scene.setter
    def current_scene(self, value: int) -> None:
        """Set the current scene. Used when state is updated outside Home Assistant."""
        if 0 <= value <= 4:
            self._current_scene = value
            # Also update last_scene if non-zero
            if value > 0:
                self._last_scene = value
            self.async_write_ha_state()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        return {
            "last_scene": self._last_scene,
        }

    @property
    def should_poll(self) -> bool:
        """Entity pushes its state to HA."""
        return False

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this Rako Room."""
        return {
            "identifiers": {(DOMAIN, self.unique_id)},
            "name": self._light.room_title,
            "manufacturer": "Rako",
            "suggested_area": self._light.room_title,
            "via_device": (DOMAIN, self.bridge.mac),
        }

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the light."""
        # If effect is specified, use that scene; otherwise use last scene
        if ATTR_EFFECT in kwargs:
            effect_name = kwargs[ATTR_EFFECT]
            if effect_name not in SCENE_EFFECTS:
                _LOGGER.error("Invalid effect: %s", effect_name)
                return
            scene_number = SCENE_EFFECTS.index(effect_name) + 1
        else:
            # No effect specified, restore last scene
            scene_number = self._last_scene

        try:
            await asyncio.wait_for(
                self.bridge.set_room_scene(self._light.room_id, scene_number),
                timeout=3.0,
            )
            # Update local state immediately after successful command
            self._current_scene = scene_number
            self._last_scene = scene_number
            self._available = True
            self.async_write_ha_state()

        except TimeoutError:
            # Command was sent but response timed out - this is OK because the
            # state update will come via the listener task. Don't mark unavailable.
            _LOGGER.debug(
                "Scene command timed out waiting for response (room_id=%s, scene=%s), "
                "but state will be updated by listener",
                self._light.room_id,
                scene_number,
            )
            # Optimistically update state - listener will correct if needed
            self._current_scene = scene_number
            self._last_scene = scene_number
            self._available = True
            self.async_write_ha_state()

        except RakoBridgeError as e:
            # Actual bridge error - mark unavailable
            if self._available:
                _LOGGER.error(
                    "Bridge error while updating Rako Light (room_id=%s, scene=%s): %s",
                    self._light.room_id,
                    scene_number,
                    e,
                )
            self._available = False
            self.async_write_ha_state()
            return

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the light (set to scene 0)."""
        scene_number = 0

        try:
            await asyncio.wait_for(
                self.bridge.set_room_scene(self._light.room_id, scene_number),
                timeout=3.0,
            )
            # Update current scene but preserve last_scene
            self._current_scene = scene_number
            self._available = True
            self.async_write_ha_state()

        except TimeoutError:
            # Command was sent but response timed out - this is OK because the
            # state update will come via the listener task. Don't mark unavailable.
            _LOGGER.debug(
                "Scene off command timed out waiting for response (room_id=%s), "
                "but state will be updated by listener",
                self._light.room_id,
            )
            # Optimistically update state - listener will correct if needed
            self._current_scene = scene_number
            self._available = True
            self.async_write_ha_state()

        except RakoBridgeError as e:
            # Actual bridge error - mark unavailable
            if self._available:
                _LOGGER.error(
                    "Bridge error while turning off Rako Light (room_id=%s): %s",
                    self._light.room_id,
                    e,
                )
            self._available = False
            self.async_write_ha_state()
            return
