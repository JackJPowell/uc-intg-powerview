"""
This module implements the Powerview communication of the Remote Two/3 integration driver.

"""

import asyncio
import logging
from asyncio import AbstractEventLoop
from enum import StrEnum

from aiopvapi.helpers.aiorequest import AioRequest
from aiopvapi.hub import Hub
from aiopvapi.resources.scene import Scene
from aiopvapi.resources.shade import BaseShade, ShadePosition
from aiopvapi.scene_members import SceneMembers
from aiopvapi.scenes import Scenes
from aiopvapi.shades import Shades
from const import PowerviewCoverInfo, PowerviewConfig, PowerviewSceneInfo
from ucapi import EntityTypes
from ucapi.button import Attributes as ButtonAttr
from ucapi.cover import Attributes as CoverAttr
from ucapi.media_player import Attributes as MediaAttr
from ucapi_framework import StatelessHTTPDevice, create_entity_id
from ucapi_framework.device import DeviceEvents

_LOG = logging.getLogger(__name__)


class PowerState(StrEnum):
    """Playback state for companion protocol."""

    OFF = "OFF"
    ON = "ON"
    STANDBY = "STANDBY"


class SmartHub(StatelessHTTPDevice):
    """Representing a Powerview Smart Hub Device."""

    def __init__(
        self,
        config: PowerviewConfig,
        loop: AbstractEventLoop | None = None,
        config_manager=None,
    ) -> None:
        """Create instance."""
        super().__init__(config, loop, config_manager)
        self._request: AioRequest = AioRequest(
            self._device_config.address, self._loop, timeout=10
        )
        self._powerview_smart_hub: Hub = Hub(self._request)
        self._cover_entry_point: Shades = Shades(self._request)
        self._scene_entry_point: Scenes = Scenes(self._request)
        self._scene_member_entry_point: SceneMembers = SceneMembers(self._request)
        self._state: PowerState = PowerState.OFF
        self._covers: list[PowerviewCoverInfo] = []
        self._scenes: list[PowerviewSceneInfo] = []
        self._raw_covers: list[BaseShade] = []
        self._raw_scenes: list[Scene] = []
        self.radio_operation_lock = asyncio.Lock()

    @property
    def device_config(self) -> PowerviewConfig:
        """Return the device configuration."""
        return self._device_config

    @property
    def identifier(self) -> str:
        """Return the device identifier."""
        return self._device_config.identifier

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
    def covers(self) -> list[PowerviewCoverInfo]:
        """Return the list of cover entities."""
        return self._covers

    @property
    def scenes(self) -> list[PowerviewSceneInfo]:
        """Return the list of scene entities."""
        return self._scenes

    def rebuild_request(self) -> None:
        """Rebuild the request object."""
        self._request = AioRequest(self._device_config.address, self._loop, timeout=10)
        self._powerview_smart_hub = Hub(self._request)
        self._cover_entry_point = Shades(self._request)
        self._scene_entry_point = Scenes(self._request)
        self._scene_member_entry_point = SceneMembers(self._request)

    async def verify_connection(self):
        try:
            await self._powerview_smart_hub.query_firmware()
        except asyncio.CancelledError as err:
            _LOG.error("[%s] Connection cancelled: %s", self.log_id, err)
            return False
        except Exception as err:  # pylint: disable=broad-exception-caught
            _LOG.error("[%s] Could not connect: %s", self.log_id, err)
            return False
        finally:
            _LOG.debug("[%s] Connect setup finished", self.log_id)

    async def connect(self) -> bool:
        """Establish connection to the Powerview device."""

        if self._powerview_smart_hub is None:
            self.rebuild_request()
        await super().connect()

        await self._update_covers()
        await self._update_scenes()
        return True

    async def disconnect(self) -> None:
        """Disconnect from the device."""
        self._powerview_smart_hub = None
        await super().disconnect()

    async def _update_covers(self) -> None:
        update = {}
        try:
            await self.get_covers()

            for cover_data in self._covers:
                update = {}
                update[CoverAttr.STATE] = (
                    "OPEN"
                    if cover_data.raw_shade.current_position.primary >= 5
                    else "CLOSED"
                )
                update[CoverAttr.POSITION] = (
                    cover_data.raw_shade.current_position.primary
                )

                self.events.emit(
                    DeviceEvents.UPDATE,
                    create_entity_id(
                        EntityTypes.COVER,
                        self.device_config.identifier,
                        cover_data.id,
                    ),
                    update,
                )

        except Exception:  # pylint: disable=broad-exception-caught
            _LOG.exception("[%s] App list: protocol error", self.log_id)

    async def _update_scenes(self) -> None:
        update = {}
        update[ButtonAttr.STATE] = self.state

        try:
            self._scenes = await self.get_scenes()

        except Exception:  # pylint: disable=broad-exception-caught
            _LOG.exception("[%s] App list: protocol error", self.log_id)

    async def get_covers(self) -> list[PowerviewCoverInfo]:
        """Return the list of cover entities."""
        self._raw_covers = await self._cover_entry_point.get_instances()

        # Wrap raw covers in PowerviewCoverInfo for consistent interface
        self._covers = [
            PowerviewCoverInfo(
                device_id=str(shade.id),
                type=str(getattr(shade, "type", "shade")),
                name=shade.name,
                position=shade.current_position.primary,
                raw_shade=shade,
            )
            for shade in self._raw_covers
        ]
        return self._covers

    async def get_scenes(self) -> list[PowerviewSceneInfo]:
        """Return the list of scene entities."""
        self._raw_scenes = await self._scene_entry_point.get_instances()

        # Wrap raw scenes in PowerviewSceneInfo for consistent interface
        self._scenes = [
            PowerviewSceneInfo(scene_id=str(scene.id), name=scene.name, raw_scene=scene)
            for scene in self._raw_scenes
        ]
        return self._scenes

    async def activate_scene(self, scene_id: str) -> None:
        """Activate a scene."""
        scene_data = next((s for s in self._scenes if s.id == scene_id), None)
        if scene_data is None:
            _LOG.error("[%s] Scene %s not found", self.log_id, scene_id)
            return
        try:
            async with self.radio_operation_lock:
                await scene_data.raw_scene.activate()
        except Exception as err:  # pylint: disable=broad-exception-caught
            _LOG.error(
                "[%s] Error activating scene %s: %s", self.log_id, scene_data.name, err
            )

    async def open_cover(self, cover_id: str, position: int = None) -> None:
        """Open a cover to a specific position."""
        state = "OPEN"
        cover_data = next((c for c in self._covers if c.id == cover_id), None)
        if cover_data is None:
            _LOG.error("[%s] Cover %s not found", self.log_id, cover_id)
            return

        try:
            if position is not None:
                raw_position = ShadePosition(position)
                async with self.radio_operation_lock:
                    await cover_data.raw_shade.move(raw_position)
                state = "OPEN" if position >= 5 else "CLOSED"
            else:
                async with self.radio_operation_lock:
                    await cover_data.raw_shade.open()

                state = "OPEN"
                self.events.emit(
                    DeviceEvents.UPDATE,
                    create_entity_id(
                        EntityTypes.COVER,
                        self._device_config.identifier,
                        cover_id,
                    ),
                    {CoverAttr.STATE: state, CoverAttr.POSITION: position},
                )
        except Exception as err:  # pylint: disable=broad-exception-caught
            _LOG.error("[%s] Error opening cover %s: %s", self.log_id, cover_id, err)

    async def close_cover(self, cover_id: str) -> None:
        """Close a cover."""
        cover_data = next((c for c in self._covers if c.id == cover_id), None)
        if cover_data is None:
            _LOG.error("[%s] Cover %s not found", self.log_id, cover_id)
            return

        try:
            async with self.radio_operation_lock:
                await cover_data.raw_shade.close()
            self.events.emit(
                DeviceEvents.UPDATE,
                create_entity_id(
                    EntityTypes.COVER,
                    self._device_config.identifier,
                    cover_id,
                ),
                {CoverAttr.STATE: "CLOSED", CoverAttr.POSITION: 0},
            )
        except Exception as err:  # pylint: disable=broad-exception-caught
            _LOG.error(
                "[%s] Error turning off cover %s: %s", self.log_id, cover_id, err
            )

    async def stop_cover(self, cover_id: str) -> None:
        """Stop a cover."""
        cover_data = next((c for c in self._covers if c.id == cover_id), None)
        if cover_data is None:
            _LOG.error("[%s] Cover %s not found", self.log_id, cover_id)
            return

        try:
            async with self.radio_operation_lock:
                await cover_data.raw_shade.stop()
            self.events.emit(
                DeviceEvents.UPDATE,
                create_entity_id(
                    EntityTypes.COVER,
                    self._device_config.identifier,
                    cover_id,
                ),
                {CoverAttr.STATE: "STOPPED"},
            )
        except Exception as err:  # pylint: disable=broad-exception-caught
            _LOG.error(
                "[%s] Error turning off cover %s: %s", self.log_id, cover_id, err
            )

    async def toggle_cover(self, cover_id: str) -> None:
        """Toggle a cover."""
        cover_data = next((c for c in self._covers if c.id == cover_id), None)
        if cover_data is None:
            _LOG.error("[%s] Cover %s not found", self.log_id, cover_id)
            return

        current_position = cover_data.raw_shade.current_position.primary
        try:
            if current_position == 0:
                async with self.radio_operation_lock:
                    await cover_data.raw_shade.open()
            else:
                async with self.radio_operation_lock:
                    await cover_data.raw_shade.close()
            self.events.emit(
                DeviceEvents.UPDATE,
                create_entity_id(
                    EntityTypes.COVER,
                    self._device_config.identifier,
                    cover_id,
                ),
                {
                    CoverAttr.STATE: "OPEN" if current_position >= 5 else "CLOSED",
                    CoverAttr.POSITION: 100 if current_position == 0 else 0,
                },
            )
        except Exception as err:  # pylint: disable=broad-exception-caught
            _LOG.error("[%s] Error toggling cover %s: %s", self.log_id, cover_id, err)
