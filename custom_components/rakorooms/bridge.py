"""Module representing a Rako Bridge."""

from __future__ import annotations

import asyncio
from asyncio import Task
import contextlib
import logging

from python_rako.bridge import Bridge
from python_rako.helpers import get_dg_listener
from python_rako.model import ChannelStatusMessage, SceneStatusMessage, StatusMessage

from homeassistant.core import HomeAssistant

from custom_components.rakorooms.fan import RakoFan

from .const import DOMAIN
from .select import RakoRoomScene
from .model import RakoDomainEntryData
from .util import create_unique_id

_LOGGER = logging.getLogger(__name__)


class RakoBridge(Bridge):
    """Represents a Rako Bridge."""

    def __init__(
        self,
        host: str,
        port: int,
        name: str,
        mac: str,
        entry_id: str,
        hass: HomeAssistant,
    ) -> None:
        """Init subclass of python_rako Bridge."""
        super().__init__(host, port, name, mac)
        self.entry_id = entry_id
        self.hass = hass

    @property
    def _scene_map(self) -> dict[str, RakoRoomScene]:
        rako_domain_entry_data: RakoDomainEntryData = self.hass.data[DOMAIN][self.mac]
        return rako_domain_entry_data["rako_scene_map"]

    @property
    def _fan_map(self) -> dict[str, RakoFan]:
        rako_domain_entry_data: RakoDomainEntryData = self.hass.data[DOMAIN][self.mac]
        return rako_domain_entry_data.get("rako_fan_map", {})

    @property
    def _entity_map(self) -> dict[str, any]:
        """Return combined map of all listening entities."""
        entity_map = {}
        entity_map.update(self._scene_map)
        entity_map.update(self._fan_map)
        return entity_map

    @property
    def _listener_task(self) -> Task | None:
        rako_domain_entry_data: RakoDomainEntryData = self.hass.data[DOMAIN][self.mac]
        return rako_domain_entry_data["rako_listener_task"]

    @_listener_task.setter
    def _listener_task(self, task: Task) -> None:
        rako_domain_entry_data: RakoDomainEntryData = self.hass.data[DOMAIN][self.mac]
        rako_domain_entry_data["rako_listener_task"] = task

    def get_listening_entity(self, entity_unique_id: str):
        """Return any listening entity (scene or fan)."""
        entity_map = self._entity_map
        return entity_map.get(entity_unique_id)

    def _add_listening_scene(self, scene: RakoRoomScene) -> None:
        scene_map = self._scene_map
        scene_map[scene.unique_id] = scene

    def _remove_listening_scene(self, scene: RakoRoomScene) -> None:
        scene_map = self._scene_map
        if scene.unique_id in scene_map:
            del scene_map[scene.unique_id]

    def _add_listening_fan(self, fan) -> None:
        fan_map = self._fan_map
        fan_map[fan.unique_id] = fan

    def _remove_listening_fan(self, fan) -> None:
        fan_map = self._fan_map
        if fan.unique_id in fan_map:
            del fan_map[fan.unique_id]

    async def listen_for_state_updates(self) -> None:
        """Background task to listen for state updates."""
        self._listener_task: Task = asyncio.create_task(
            listen_for_state_updates(self), name=f"rako_{self.mac}_listener_task"
        )

    async def stop_listening_for_state_updates(self) -> None:
        """Background task to stop listening for state updates."""
        if listener_task := self._listener_task:
            listener_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await listener_task

    async def register_for_state_updates(self, entity) -> None:
        """Register an entity to listen for state updates."""
        if hasattr(entity, "select_option"):  # Scene select entity
            self._add_listening_scene(entity)
        elif hasattr(entity, "percentage"):  # Fan entity
            self._add_listening_fan(entity)
        else:
            _LOGGER.warning("Unknown entity type: %s", entity)
            return

        if len(self._entity_map) == 1:
            await self.listen_for_state_updates()

    async def deregister_for_state_updates(self, entity) -> None:
        """Deregister an entity to listen for state updates."""
        if hasattr(entity, "select_option"):  # Scene select entity
            self._remove_listening_scene(entity)
        elif hasattr(entity, "percentage"):  # Fan entity
            self._remove_listening_fan(entity)

        if not self._entity_map:
            await self.stop_listening_for_state_updates()


def _state_update(bridge: RakoBridge, status_message: StatusMessage) -> None:
    """Process state updates from the bridge."""

    if isinstance(status_message, SceneStatusMessage):
        # Scene changed - update scene select entity
        scene_unique_id = create_unique_id(
            bridge.mac, status_message.room, 0  # channel_id=0 for rooms
        )
        scene_entity = bridge.get_listening_entity(scene_unique_id)

        if scene_entity and hasattr(scene_entity, 'current_scene'):
            scene_entity.current_scene = status_message.scene
            _LOGGER.debug("Updated scene %s to scene %d", scene_unique_id, status_message.scene)

    elif isinstance(status_message, ChannelStatusMessage):
        # Channel brightness changed - only fans use this now
        entity_unique_id = create_unique_id(
            bridge.mac, status_message.room, status_message.channel
        )
        entity = bridge.get_listening_entity(entity_unique_id)

        if entity and hasattr(entity, 'percentage'):
            # It's a fan entity
            percentage = int((status_message.brightness / 255) * 100) if status_message.brightness > 0 else 0
            entity.percentage = percentage
            _LOGGER.debug("Updated fan %s to %d%%", entity_unique_id, percentage)
    else:
        _LOGGER.debug("Unhandled message type: %s", status_message)


async def listen_for_state_updates(bridge: RakoBridge) -> None:
    """Listen for state updates worker method."""
    async with get_dg_listener(bridge.port) as listener:
        while True:
            message = await bridge.next_pushed_message(listener)
            if message and isinstance(message, StatusMessage):
                _state_update(bridge, message)
