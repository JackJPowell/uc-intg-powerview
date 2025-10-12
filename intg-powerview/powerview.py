"""
This module implements the Powerview communication of the Remote Two/3 integration driver.

"""

import asyncio
import logging
from asyncio import AbstractEventLoop
from enum import StrEnum, IntEnum
from typing import Any, ParamSpec, TypeVar

from aiopvapi.helpers.aiorequest import AioRequest
from aiopvapi.hub import Hub
from aiopvapi.shades import Shades
from aiopvapi.scene_members import SceneMembers
from aiopvapi.scenes import Scenes
from aiopvapi.resources.shade import BaseShade, ShadePosition
from aiopvapi.resources.scene import Scene
from pyee.asyncio import AsyncIOEventEmitter
from ucapi.media_player import Attributes as MediaAttr
from ucapi import EntityTypes
from config import PowerviewConfig, create_entity_id
from const import PowerviewCoverInfo, PowerviewSceneInfo

_LOG = logging.getLogger(__name__)


class EVENTS(IntEnum):
    """Internal driver events."""

    CONNECTING = 0
    CONNECTED = 1
    DISCONNECTED = 2
    PAIRED = 3
    ERROR = 4
    UPDATE = 5


_PowerviewDeviceT = TypeVar("_PowerviewDeviceT", bound="PowerviewConfig")
_P = ParamSpec("_P")


class PowerState(StrEnum):
    """Playback state for companion protocol."""

    OFF = "OFF"
    ON = "ON"
    STANDBY = "STANDBY"


class SmartHub:
    """Representing a Powerview Smart Hub Device."""

    def __init__(
        self, config: PowerviewConfig, loop: AbstractEventLoop | None = None
    ) -> None:
        """Create instance."""
        self._loop: AbstractEventLoop = loop or asyncio.get_running_loop()
        self.events = AsyncIOEventEmitter(self._loop)
        self._config: PowerviewConfig | None = config
        self._request: AioRequest = AioRequest(
            self._config.address, self._loop, timeout=10
        )
        self._powerview_smart_hub: Hub = Hub(self._request)
        self._cover_entry_point: Shades = Shades(self._request)
        self._scene_entry_point: Scenes = Scenes(self._request)
        self._scene_member_entry_point: SceneMembers = SceneMembers(self._request)
        self._connection_attempts: int = 0
        self._state: PowerState = PowerState.OFF
        self._features: dict = {}
        self._covers: list[BaseShade] = []
        self._scenes: list[Scene] = []
        self.radio_operation_lock = asyncio.Lock()

    @property
    def device_config(self) -> PowerviewConfig:
        """Return the device configuration."""
        return self._config

    @property
    def identifier(self) -> str:
        """Return the device identifier."""
        return self._config.identifier

    @property
    def log_id(self) -> str:
        """Return a log identifier."""
        return self.device_config.identifier

    @property
    def name(self) -> str:
        """Return the device name."""
        return self.device_config.name

    @property
    def address(self) -> str | None:
        """Return the optional device address."""
        return self.device_config.address

    @property
    def state(self) -> PowerState | None:
        """Return the device state."""
        return self._state

    @property
    def is_connected(self) -> bool:
        """Return if the device is connected."""
        return self._powerview_smart_hub is not None

    @property
    def attributes(self) -> dict[str, any]:
        """Return the device attributes."""
        updated_data = {
            MediaAttr.STATE: self.state,
        }
        return updated_data

    @property
    def covers(self) -> list[Any]:
        """Return the list of cover entities."""
        return self._covers

    @property
    def scenes(self) -> list[Any]:
        """Return the list of scene entities."""
        return self._scenes

    def rebuild_request(self) -> None:
        """Rebuild the request object."""
        self._request = AioRequest(self._config.address, self._loop, timeout=10)
        self._powerview_smart_hub = Hub(self._request)
        self._cover_entry_point = Shades(self._request)
        self._scene_entry_point = Scenes(self._request)
        self._scene_member_entry_point = SceneMembers(self._request)

    async def connect(self) -> bool:
        """Establish connection to the Powerview device."""

        if self._powerview_smart_hub is None:
            self.rebuild_request()

        _LOG.debug("[%s] Connecting to device", self.log_id)
        self.events.emit(EVENTS.CONNECTING, self.device_config.identifier)

        try:
            await self._powerview_smart_hub.query_firmware()
            self._state = PowerState.ON
            _LOG.info("[%s] Connected to device", self.log_id)
        except asyncio.CancelledError as err:
            _LOG.error("[%s] Connection cancelled: %s", self.log_id, err)
            return False
        except Exception as err:  # pylint: disable=broad-exception-caught
            _LOG.error("[%s] Could not connect: %s", self.log_id, err)
            return False
        finally:
            _LOG.debug("[%s] Connect setup finished", self.log_id)

        self.events.emit(EVENTS.CONNECTED, self.device_config.identifier)
        _LOG.debug("[%s] Connected", self.log_id)

        await self._update_covers()
        await self._update_scenes()
        return True

    async def disconnect(self) -> None:
        """Disconnect from the device."""
        _LOG.debug("[%s] Disconnecting from device", self.log_id)
        self._powerview_smart_hub = None
        self._state = PowerState.OFF
        self.events.emit(EVENTS.DISCONNECTED, self.device_config.identifier)

    async def _update_covers(self) -> None:
        update = {}
        try:
            await self.get_covers()

            for entity in self._covers:
                update = {}
                update["state"] = (
                    "OPEN" if entity.current_position.primary > 0 else "CLOSED"
                )
                update["position"] = entity.current_position.primary

                self.events.emit(
                    EVENTS.UPDATE,
                    create_entity_id(
                        self.device_config.identifier,
                        entity.id,
                        EntityTypes.COVER,
                    ),
                    update,
                )

        except Exception:  # pylint: disable=broad-exception-caught
            _LOG.exception("[%s] App list: protocol error", self.log_id)

    async def _update_scenes(self) -> None:
        update = {}
        update["state"] = self.state

        try:
            self._scenes = await self.get_scenes()

        except Exception:  # pylint: disable=broad-exception-caught
            _LOG.exception("[%s] App list: protocol error", self.log_id)

    async def get_covers(self) -> list[Any]:
        """Return the list of cover entities."""

        self._covers = await self._cover_entry_point.get_instances()
        return self._covers

    async def get_scenes(self) -> list[Any]:
        """Return the list of scene entities."""
        self._scenes = await self._scene_member_entry_point.get_instances()
        return self._scenes

    async def activate_scene(self, scene_id: str) -> None:
        """Activate a scene."""
        scene: Scene = next((s for s in self._scenes if s.id == scene_id), None)
        if scene is None:
            _LOG.error("[%s] Scene %s not found", self.log_id, scene_id)
            return
        try:
            async with self.radio_operation_lock:
                await scene.activate()
            self.events.emit(
                EVENTS.UPDATE,
                create_entity_id(
                    self.device_config.identifier,
                    "0",
                    EntityTypes.MEDIA_PLAYER,
                ),
                {"source": scene.name},
            )
        except Exception as err:  # pylint: disable=broad-exception-caught
            _LOG.error(
                "[%s] Error activating scene %s: %s", self.log_id, scene.name, err
            )

    async def open_cover(self, cover_id: str, position: int = None) -> None:
        """Open a cover to a specific position."""
        cover: BaseShade = next((c for c in self._covers if c.id == cover_id), None)
        try:
            if position is not None:
                raw_position = ShadePosition(position)
                async with self.radio_operation_lock:
                    await cover.move(raw_position)
            else:
                async with self.radio_operation_lock:
                    await cover.open()
                self.events.emit(
                    EVENTS.UPDATE,
                    create_entity_id(
                        self._config.identifier,
                        cover_id,
                        EntityTypes.COVER,
                    ),
                    {"state": "OPEN", "position": position},
                )
        except Exception as err:  # pylint: disable=broad-exception-caught
            _LOG.error("[%s] Error opening cover %s: %s", self.log_id, cover_id, err)

    async def close_cover(self, cover_id: str) -> None:
        """Close a cover."""
        cover: BaseShade = next((c for c in self._covers if c.id == cover_id), None)
        try:
            async with self.radio_operation_lock:
                await cover.close()
            self.events.emit(
                EVENTS.UPDATE,
                create_entity_id(
                    self._config.identifier,
                    cover_id,
                    EntityTypes.COVER,
                ),
                {"state": "CLOSED", "position": 0},
            )
        except Exception as err:  # pylint: disable=broad-exception-caught
            _LOG.error(
                "[%s] Error turning off cover %s: %s", self.log_id, cover_id, err
            )

    async def stop_cover(self, cover_id: str) -> None:
        """Stop a cover."""
        cover: BaseShade = next((c for c in self._covers if c.id == cover_id), None)
        try:
            async with self.radio_operation_lock:
                await cover.stop()
            self.events.emit(
                EVENTS.UPDATE,
                create_entity_id(
                    self._config.identifier,
                    cover_id,
                    EntityTypes.COVER,
                ),
                {"state": "STOPPED"},
            )
        except Exception as err:  # pylint: disable=broad-exception-caught
            _LOG.error(
                "[%s] Error turning off cover %s: %s", self.log_id, cover_id, err
            )

    async def toggle_cover(self, cover_id: str) -> None:
        """Toggle a cover."""
        cover: BaseShade = next((c for c in self._covers if c.id == cover_id), None)
        current_position = cover.current_position.primary
        try:
            if current_position == 0:
                async with self.radio_operation_lock:
                    await cover.open()
            else:
                async with self.radio_operation_lock:
                    await cover.close()
            self.events.emit(
                EVENTS.UPDATE,
                create_entity_id(
                    self._config.identifier,
                    cover_id,
                    EntityTypes.COVER,
                ),
                {
                    "state": "OPEN" if current_position == 0 else "CLOSED",
                    "position": 100 if current_position == 0 else 0,
                },
            )
        except Exception as err:  # pylint: disable=broad-exception-caught
            _LOG.error("[%s] Error toggling cover %s: %s", self.log_id, cover_id, err)
