"""Platform for select integration."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

import python_rako
from python_rako.exceptions import RakoBridgeError

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .util import create_unique_id

if TYPE_CHECKING:
    from .bridge import RakoBridge
    from .model import RakoDomainEntryData

_LOGGER = logging.getLogger(__name__)

# Scene number to option name mapping
SCENE_OPTIONS = ["Off", "Scene 1", "Scene 2", "Scene 3", "Scene 4"]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the config entry."""
    rako_domain_entry_data: RakoDomainEntryData = hass.data[DOMAIN][entry.unique_id]
    bridge = rako_domain_entry_data["rako_bridge_client"]

    scene_entities: list[RakoRoomScene] = []
    session = async_get_clientsession(hass)

    bridge.level_cache, bridge.scene_cache = await bridge.get_cache_state()

    async for light in bridge.discover_lights(session):
        # Only create scene selectors for room lights, not individual channels
        if isinstance(light, python_rako.RoomLight):
            scene_entity = RakoRoomScene(bridge, light)
            scene_entities.append(scene_entity)

    async_add_entities(scene_entities, True)


class RakoRoomScene(SelectEntity):
    """Representation of a Rako Room Scene selector."""

    def __init__(self, bridge: RakoBridge, light: python_rako.RoomLight) -> None:
        """Initialize a RakoRoomScene."""
        self.bridge = bridge
        self._light = light
        self._current_scene = self.bridge.scene_cache.get(light.room_id, 0)
        self._available = True
        self._attr_options = SCENE_OPTIONS

    @property
    def name(self) -> str:
        """Return the display name of this scene selector."""
        return f"{self._light.room_title} Scene"

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        await self.bridge.register_for_state_updates(self)

    async def async_will_remove_from_hass(self) -> None:
        """Run when entity about to be removed from hass."""
        await self.bridge.deregister_for_state_updates(self)

    @property
    def unique_id(self) -> str:
        """Scene selector's unique ID."""
        return create_unique_id(self.bridge.mac, self._light.room_id, 0)

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._available

    @property
    def current_option(self) -> str:
        """Return the current selected scene option."""
        return SCENE_OPTIONS[self._current_scene]

    @property
    def current_scene(self) -> int:
        """Return the current scene number (0-4)."""
        return self._current_scene

    @current_scene.setter
    def current_scene(self, value: int) -> None:
        """Set the current scene. Used when state is updated outside Home Assistant."""
        if 0 <= value <= 4:
            self._current_scene = value
            self.async_write_ha_state()

    @property
    def should_poll(self) -> bool:
        """Entity pushes its state to HA."""
        return False

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this Rako Scene selector."""
        return {
            "identifiers": {(DOMAIN, self.unique_id)},
            "name": self._light.room_title,
            "manufacturer": "Rako",
            "suggested_area": self._light.room_title,
            "via_device": (DOMAIN, self.bridge.mac),
        }

    async def async_select_option(self, option: str) -> None:
        """Change the selected scene."""
        if option not in SCENE_OPTIONS:
            _LOGGER.error("Invalid scene option: %s", option)
            return

        # Convert option name to scene number
        scene_number = SCENE_OPTIONS.index(option)

        try:
            await asyncio.wait_for(
                self.bridge.set_room_scene(self._light.room_id, scene_number),
                timeout=3.0,
            )
            # Update local state immediately after successful command
            self._current_scene = scene_number
            self._available = True
            self.async_write_ha_state()

        except (RakoBridgeError, asyncio.TimeoutError):
            if self._available:
                _LOGGER.error("An error occurred while updating the Rako Scene")
            self._available = False
            self.async_write_ha_state()
            return
