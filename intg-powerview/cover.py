"""
Cover entity functions.

:license: Mozilla Public License Version 2.0, see LICENSE for more details.
"""

import logging
from typing import Any
import ucapi
from powerview import SmartHub
from ucapi import Cover, cover, EntityTypes
from const import PowerviewCoverInfo, PowerviewDevice
from ucapi_framework import create_entity_id

_LOG = logging.getLogger(__name__)


class PowerviewCover(Cover):
    """Representation of a Powerview Cover entity."""

    def __init__(
        self, config: PowerviewDevice, cover_info: PowerviewCoverInfo, device: SmartHub
    ):
        """Initialize the class."""
        _LOG.debug("Powerview Cover init")
        entity_id = create_entity_id(
            EntityTypes.COVER, config.identifier, cover_info.device_id
        )
        self.config = config
        self.device: SmartHub = device
        state = "UNKNOWN"
        current_position = 0
        self._cover_id = cover_info.device_id

        if self.device and self.device.covers is not None:
            this_cover = next(
                (c for c in self.device.covers if c.id == cover_info.device_id),
                None,
            )
        else:
            this_cover = cover_info

        if this_cover is not None:
            current_position = this_cover.raw_shade.current_position.primary
            state = "OPEN" if current_position >= 5 else "CLOSED"

        super().__init__(
            entity_id,
            cover_info.name,
            features=[
                cover.Features.OPEN,
                cover.Features.CLOSE,
                cover.Features.STOP,
                cover.Features.POSITION,
            ],
            attributes={
                cover.Attributes.STATE: state,
                cover.Attributes.POSITION: 100 if current_position == 0 else 0,
            },
            device_class=cover.DeviceClasses.SHADE,
            cmd_handler=self.cover_cmd_handler,
        )

    async def cover_cmd_handler(
        self, entity: Cover, cmd_id: str, params: dict[str, Any] | None
    ) -> ucapi.StatusCodes:
        """
        Cover entity command handler.

        Called by the integration-API if a command is sent to a configured cover entity.

        :param entity: cover entity
        :param cmd_id: command
        :param params: optional command parameters
        :return: status code of the command. StatusCodes.OK if the command succeeded.
        """
        _LOG.info(
            "Got %s command request: %s %s", entity.id, cmd_id, params if params else ""
        )

        try:
            match cmd_id:
                case cover.Commands.OPEN:
                    await self.device.open_cover(cover_id=self._cover_id)
                case cover.Commands.CLOSE:
                    await self.device.close_cover(cover_id=self._cover_id)
                case cover.Commands.STOP:
                    await self.device.stop_cover(cover_id=self._cover_id)
                case cover.Commands.POSITION:
                    if params and "position" in params:
                        position = params["position"]
                        await self.device.open_cover(
                            cover_id=self._cover_id, position=position
                        )
        except Exception as ex:  # pylint: disable=broad-except
            _LOG.error("Error executing command %s: %s", cmd_id, ex)
            return ucapi.StatusCodes.BAD_REQUEST
        return ucapi.StatusCodes.OK
