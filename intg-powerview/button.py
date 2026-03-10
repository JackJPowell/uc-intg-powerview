"""
Button entity functions.

:license: Mozilla Public License Version 2.0, see LICENSE for more details.
"""

import logging
from typing import Any

import ucapi
from const import PowerviewConfig, PowerviewSceneInfo
from powerview import SmartHub
from ucapi import EntityTypes, button
from ucapi_framework import create_entity_id, ButtonEntity

_LOG = logging.getLogger(__name__)


class PowerviewButton(ButtonEntity):
    """Representation of a Powerview Button entity."""

    def __init__(
        self,
        config: PowerviewConfig,
        scene_info: PowerviewSceneInfo,
        device: SmartHub,
    ):
        """Initialize the class."""
        _LOG.debug("Powerview Button init")
        self._device = device
        self._scene_id = scene_info.scene_id

        super().__init__(
            create_entity_id(
                EntityTypes.BUTTON, config.identifier, scene_info.scene_id
            ),
            scene_info.name,
            cmd_handler=self.button_cmd_handler,
        )

        if device:
            self.subscribe_to_device(device)

    async def sync_state(self) -> None:
        """Sync button state from device to Remote."""
        if self._device is None:
            return
        attrs = self._device.get_button_attributes(self._scene_id)
        if attrs is not None:
            self.update(attrs, force=True)

    async def button_cmd_handler(
        self,
        entity: button.Button,
        cmd_id: str,
        params: dict[str, Any] | None,
        _: Any | None = None,
    ) -> ucapi.StatusCodes:
        """
        Button entity command handler.

        Called by the integration-API if a command is sent to a configured button entity.

        :param entity: button entity
        :param cmd_id: command
        :param params: optional command parameters
        :return: status code of the command. StatusCodes.OK if the command succeeded.
        """
        if self._device is None:
            return ucapi.StatusCodes.SERVICE_UNAVAILABLE

        _LOG.info(
            "Got %s command request: %s %s", entity.id, cmd_id, params if params else ""
        )

        try:
            match cmd_id:
                case button.Commands.PUSH:
                    await self._device.activate_scene(scene_id=self._scene_id)

        except Exception as ex:  # pylint: disable=broad-except
            _LOG.error("Error executing command %s: %s", cmd_id, ex)
            return ucapi.StatusCodes.BAD_REQUEST
        return ucapi.StatusCodes.OK
