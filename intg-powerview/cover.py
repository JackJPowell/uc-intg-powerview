"""
Cover entity functions.

:license: Mozilla Public License Version 2.0, see LICENSE for more details.
"""

import logging
from typing import Any

import ucapi
from const import PowerviewCoverInfo, PowerviewConfig
from powerview import SmartHub
from ucapi import EntityTypes, cover
from ucapi_framework import create_entity_id, CoverEntity

_LOG = logging.getLogger(__name__)


class PowerviewCover(CoverEntity):
    """Representation of a Powerview Cover entity."""

    def __init__(
        self, config: PowerviewConfig, cover_info: PowerviewCoverInfo, device: SmartHub
    ):
        """Initialize the class."""
        _LOG.debug("Powerview Cover init")
        self._device = device
        self._cover_id = cover_info.device_id

        super().__init__(
            create_entity_id(
                EntityTypes.COVER, config.identifier, cover_info.device_id
            ),
            cover_info.name,
            features=[
                cover.Features.OPEN,
                cover.Features.CLOSE,
                cover.Features.STOP,
                cover.Features.POSITION,
            ],
            attributes={
                cover.Attributes.STATE: cover.States.UNKNOWN,
                cover.Attributes.POSITION: 0,
            },
            device_class=cover.DeviceClasses.SHADE,
            cmd_handler=self.cover_cmd_handler,
        )

        if device:
            self.subscribe_to_device(device)

    async def sync_state(self) -> None:
        """Sync cover state from device to Remote."""
        if self._device is None:
            return
        attrs = self._device.get_cover_attributes(self._cover_id)
        if attrs is not None:
            self.update(attrs)

    async def cover_cmd_handler(
        self,
        entity: cover.Cover,
        cmd_id: str,
        params: dict[str, Any] | None,
        _: Any | None = None,
    ) -> ucapi.StatusCodes:
        """
        Cover entity command handler.

        Called by the integration-API if a command is sent to a configured cover entity.

        :param entity: cover entity
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
                case cover.Commands.OPEN:
                    await self._device.open_cover(cover_id=self._cover_id)
                case cover.Commands.CLOSE:
                    await self._device.close_cover(cover_id=self._cover_id)
                case cover.Commands.STOP:
                    await self._device.stop_cover(cover_id=self._cover_id)
                case cover.Commands.POSITION:
                    if params and "position" in params:
                        await self._device.open_cover(
                            cover_id=self._cover_id, position=params["position"]
                        )

        except Exception as ex:  # pylint: disable=broad-except
            _LOG.error("Error executing command %s: %s", cmd_id, ex)
            return ucapi.StatusCodes.BAD_REQUEST
        return ucapi.StatusCodes.OK
