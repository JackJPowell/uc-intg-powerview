#!/usr/bin/env python3
"""
This module implements a Unfolded Circle integration driver for Powerview devices.

:copyright: (c) 2023-2024 by Unfolded Circle ApS.
:license: Mozilla Public License Version 2.0, see LICENSE for more details.
"""

import asyncio
import logging
import os

from button import PowerviewButton
from const import PowerviewDevice
from cover import PowerviewCover
from discover import PowerviewDiscovery
from powerview import SmartHub
from setup import PowerviewSetupFlow
from ucapi import EntityTypes
from ucapi.button import Attributes as ButtonAttr
from ucapi.cover import Attributes as CoverAttr
from ucapi_framework import BaseDeviceManager, BaseIntegrationDriver, get_config_path

_LOG = logging.getLogger("driver")


class PowerviewIntegrationDriver(BaseIntegrationDriver[SmartHub, PowerviewDevice]):
    """PowerView Integration Driver"""

    async def refresh_entity_state(self, entity_id):
        """
        Refresh the state of a configured entity by querying the device.
        """
        device_id = self.device_from_entity_id(entity_id)
        device = self._configured_devices[device_id]
        match self.entity_type_from_entity_id(entity_id):
            case EntityTypes.BUTTON.value:
                entity = next(
                    (
                        scene
                        for scene in device.scenes
                        if scene.scene_id == self.entity_from_entity_id(entity_id)
                    ),
                    None,
                )

                if entity is not None:
                    update = {}
                    update[ButtonAttr.STATE] = "AVAILABLE"
                    self.api.configured_entities.update_attributes(entity_id, update)
            case EntityTypes.COVER.value:
                entity = next(
                    (
                        cover
                        for cover in device.covers
                        if cover.device_id == self.entity_from_entity_id(entity_id)
                    ),
                    None,
                )
                if entity is not None:
                    update = {}
                    update[CoverAttr.STATE] = (
                        "OPEN"
                        if entity.raw_shade.current_position.primary >= 5
                        else "CLOSED"
                    )
                    update[CoverAttr.POSITION] = (
                        entity.raw_shade.current_position.primary
                    )
                    self.api.configured_entities.update_attributes(entity_id, update)

    async def async_register_available_entities(
        self, device_config: PowerviewDevice, device: SmartHub
    ) -> bool:
        """
        Register entities by querying the PowerView hub for its devices.

        This is called after the hub is connected and retrieves the actual
        devices from the PowerView network rather than from stored config.

        :param device: The connected SmartHub instance
        :return: True if entities were registered successfully
        """
        _LOG.info(
            "Registering available entities from PowerView hub: %s",
            device.identifier,
        )

        try:
            # Get covers from the hub (this queries the PowerView network)
            if not device.covers:
                await device.get_covers()
            _LOG.info("Found %d covers on PowerView network", len(device.covers))

            # Get scenes from the hub (this queries the PowerView network)
            if not device.scenes:
                await device.get_scenes()
            _LOG.info("Found %d scenes on PowerView network", len(device.scenes))

            entities = []

            # Create cover entities from what the hub reports
            for cover in device.covers:
                _LOG.debug(
                    "Registering cover: %s (id %s)",
                    cover.name,
                    cover.id,
                )
                # Determine cover type based on available information
                cover_entity = PowerviewCover(device.device_config, cover, device)
                entities.append(cover_entity)

            # Create scene/button entities from what the hub reports
            for scene in device.scenes:
                _LOG.debug(
                    "Registering scene: %s (id %s)",
                    scene.name,
                    scene.id,
                )
                button_entity = PowerviewButton(device.device_config, scene, device)
                entities.append(button_entity)

            # Register all entities with the API
            for entity in entities:
                if self.api.available_entities.contains(entity.id):
                    _LOG.debug("Removing existing entity: %s", entity.id)
                    self.api.available_entities.remove(entity.id)
                _LOG.debug("Adding entity: %s", entity.id)
                self.api.available_entities.add(entity)

            _LOG.info(
                "Successfully registered %d entities from PowerView hub",
                len(entities),
            )
            return True

        except Exception as ex:  # pylint: disable=broad-exception-caught
            _LOG.error("Error registering entities from hub: %s", ex)
            return False


async def main():
    """Start the Remote Two/3 integration driver."""
    logging.basicConfig()

    level = os.getenv("UC_LOG_LEVEL", "DEBUG").upper()
    logging.getLogger("bridge").setLevel(level)
    logging.getLogger("driver").setLevel(level)
    logging.getLogger("discover").setLevel(level)
    logging.getLogger("setup").setLevel(level)

    loop = asyncio.get_running_loop()

    driver = PowerviewIntegrationDriver(
        loop=loop,
        device_class=SmartHub,
        entity_classes=[PowerviewCover, PowerviewButton],
        require_connection_before_registry=True,
    )
    # Initialize configuration manager with device callbacks
    driver.config = BaseDeviceManager(
        get_config_path(driver.api.config_dir_path),
        driver.on_device_added,
        driver.on_device_removed,
        device_class=PowerviewDevice,
    )

    # Connect to all configured PowerView hubs
    for device_config in list(driver.config.all()):
        await driver.async_add_configured_device(device_config)

    discovery = PowerviewDiscovery(service_type="_powerview._tcp.local.", timeout=2)

    setup_handler = PowerviewSetupFlow.create_handler(driver.config, discovery)

    await driver.api.init("driver.json", setup_handler)

    await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())
