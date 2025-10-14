#!/usr/bin/env python3
"""
This module implements a Unfolded Circle integration driver for Powerview devices.

:copyright: (c) 2023-2024 by Unfolded Circle ApS.
:license: Mozilla Public License Version 2.0, see LICENSE for more details.
"""

import asyncio
import logging
import os
import sys
from typing import Any
import config
import setup
import ucapi
import ucapi.api as uc
from ucapi import EntityTypes
from button import PowerviewButton
from cover import PowerviewCover
from config import (
    PowerviewConfig,
    device_from_entity_id,
    entity_from_entity_id,
    create_entity_id,
    type_from_entity_id,
)
from const import PowerviewCoverInfo, PowerviewSceneInfo
import powerview

_LOG = logging.getLogger("driver")  # avoid having __main__ in log messages
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

_LOOP = asyncio.new_event_loop()
asyncio.set_event_loop(_LOOP)

# Global variables
api = uc.IntegrationAPI(_LOOP)
_configured_devices: dict[str, powerview.SmartHub] = {}


@api.listens_to(ucapi.Events.CONNECT)
async def on_r2_connect_cmd() -> None:
    """Connect all configured devices when the Remote Two sends the connect command."""
    _LOG.debug("Client connect command: connecting device(s)")
    await api.set_device_state(
        ucapi.DeviceStates.CONNECTED
    )  # just to make sure the device state is set
    for device in _configured_devices.values():
        await device.connect()


@api.listens_to(ucapi.Events.DISCONNECT)
async def on_r2_disconnect_cmd():
    """Disconnect all configured devices when the Remote Two/3 sends the disconnect command."""
    _LOG.debug("Client disconnect command: disconnecting device(s)")
    for device in _configured_devices.values():
        await device.disconnect()


@api.listens_to(ucapi.Events.ENTER_STANDBY)
async def on_r2_enter_standby() -> None:
    """
    Enter standby notification from Remote Two/3.

    Disconnect every on device instances.
    """
    _LOG.debug("Enter standby event: disconnecting device(s)")
    for device in _configured_devices.values():
        await device.disconnect()


@api.listens_to(ucapi.Events.SUBSCRIBE_ENTITIES)
async def on_subscribe_entities(entity_ids: list[str]) -> None:
    """
    Subscribe to given entities.

    :param entity_ids: entity identifiers.
    """
    _LOG.info("Subscribe request for %d entities", len(entity_ids))

    if entity_ids is not None and len(entity_ids) > 0:
        device_id = device_from_entity_id(entity_ids[0])
        if device_id not in _configured_devices:
            device_config = config.devices.get(device_id)
            if device_config:
                # Add and connect to the device, which will also register entities
                await _add_configured_device(device_config, connect=True)
            else:
                _LOG.error(
                    "Failed to subscribe entity %s: no instance found", device_id
                )
                return

        device = _configured_devices.get(device_id)
        if device and not device.is_connected:
            attempt = 0
            while attempt := attempt + 1 < 4:
                _LOG.debug(
                    "Device %s not connected, attempting to connect (%d/3)",
                    device_id,
                    attempt,
                )
                if await device.connect():
                    # After successful connection, register entities from the hub
                    await _register_available_entities_from_hub(device)
                    break
                else:
                    await device.disconnect()
                    await asyncio.sleep(0.5)

    for entity_id in entity_ids:
        device_id = device_from_entity_id(entity_id)
        device = _configured_devices[device_id]
        match type_from_entity_id(entity_id):
            case EntityTypes.BUTTON.value:
                entity = next(
                    (
                        scene
                        for scene in device.scenes
                        if scene.scene_id == entity_from_entity_id(entity_id)
                    ),
                    None,
                )

                if entity is not None:
                    update = {}
                    update["state"] = "AVAILABLE"
                    api.configured_entities.update_attributes(entity_id, update)
            case EntityTypes.COVER.value:
                entity = next(
                    (
                        cover
                        for cover in device.covers
                        if cover.device_id == entity_from_entity_id(entity_id)
                    ),
                    None,
                )
                if entity is not None:
                    update = {}
                    update["state"] = (
                        "OPEN"
                        if entity.raw_shade.current_position.primary >= 5
                        else "CLOSED"
                    )
                    update["position"] = entity.raw_shade.current_position.primary
                    api.configured_entities.update_attributes(entity_id, update)
        continue


@api.listens_to(ucapi.Events.UNSUBSCRIBE_ENTITIES)
async def on_unsubscribe_entities(entity_ids: list[str]) -> None:
    """On unsubscribe, we disconnect the objects and remove listeners for events."""
    _LOG.debug("Unsubscribe entities event: %s", entity_ids)
    for entity_id in entity_ids:
        device_id = device_from_entity_id(entity_id)
        if device_id is None:
            continue
        _configured_devices[device_id].events.remove_all_listeners()


async def on_device_connected(device_id: str):
    """Handle device connection."""
    _LOG.debug("Powerview device connected: %s", device_id)
    if str(device_id) not in _configured_devices:
        _LOG.warning("Powerview device %s is not configured", device_id)
        return

    await api.set_device_state(ucapi.DeviceStates.CONNECTED)


async def on_device_disconnected(device_id: str):
    """Handle device disconnection."""
    _LOG.debug("Powerview device disconnected: %s", device_id)

    for entity_id in _entities_from_device_id(device_id):
        configured_entity = api.configured_entities.get(entity_id)
        if configured_entity is None:
            continue

        if configured_entity.entity_type == ucapi.EntityTypes.COVER:
            api.configured_entities.update_attributes(
                entity_id,
                {ucapi.cover.Attributes.STATE: ucapi.cover.States.UNAVAILABLE},
            )
        elif configured_entity.entity_type == ucapi.EntityTypes.BUTTON:
            api.configured_entities.update_attributes(
                entity_id,
                {ucapi.button.Attributes.STATE: ucapi.button.States.UNAVAILABLE},
            )


async def on_device_connection_error(device_id: str, message):
    """Set entities of Powerview device to state UNAVAILABLE if device connection error occurred."""
    _LOG.error(message)

    for entity_id in _entities_from_device_id(device_id):
        configured_entity = api.configured_entities.get(entity_id)
        if configured_entity is None:
            continue

        if configured_entity.entity_type == ucapi.EntityTypes.COVER:
            api.configured_entities.update_attributes(
                entity_id,
                {ucapi.cover.Attributes.STATE: ucapi.cover.States.UNAVAILABLE},
            )
        elif configured_entity.entity_type == ucapi.EntityTypes.BUTTON:
            api.configured_entities.update_attributes(
                entity_id,
                {ucapi.button.Attributes.STATE: ucapi.button.States.UNAVAILABLE},
            )

    await api.set_device_state(ucapi.DeviceStates.ERROR)


# pylint: disable=too-many-branches,too-many-statements
async def on_device_update(entity_id: str, update: dict[str, Any] | None) -> None:
    """
    Update attributes of configured media-player entity if Device properties changed.

    :param entity_id: Device media-player entity identifier
    :param update: dictionary containing the updated properties or None
    """
    attributes = {}
    configured_entity = api.available_entities.get(entity_id)
    if configured_entity is None:
        return

    if isinstance(configured_entity, PowerviewCover):
        if "state" in update:
            attributes[ucapi.cover.Attributes.STATE] = update["state"]

        if "position" in update:
            attributes[ucapi.cover.Attributes.POSITION] = update["position"]

    elif configured_entity.entity_type == ucapi.EntityTypes.BUTTON:
        if "state" in update:
            attributes[ucapi.button.Attributes.STATE] = "AVAILABLE"

    if attributes:
        if api.configured_entities.contains(entity_id):
            api.configured_entities.update_attributes(entity_id, attributes)
        else:
            api.available_entities.update_attributes(entity_id, attributes)


async def _add_configured_device(
    device_config: PowerviewConfig, connect: bool = True
) -> None:
    """Add and optionally connect to a PowerView hub, then register its entities.

    :param device_config: The PowerView hub configuration
    :param connect: Whether to connect immediately (default True)
    """
    # the device should not yet be configured, but better be safe
    if device_config.identifier in _configured_devices:
        _LOG.info(
            "Updating existing device: %s",
            device_config.identifier,
        )
        device = _configured_devices[str(device_config.identifier)]
        await device.disconnect()

    _LOG.info(
        "Adding new device: %s (%s)",
        device_config.identifier,
        device_config.address,
    )
    device = powerview.SmartHub(device_config, loop=_LOOP)
    device.events.on(powerview.EVENTS.CONNECTED, on_device_connected)
    device.events.on(powerview.EVENTS.DISCONNECTED, on_device_disconnected)
    device.events.on(powerview.EVENTS.ERROR, on_device_connection_error)
    device.events.on(powerview.EVENTS.UPDATE, on_device_update)

    _configured_devices[str(device.identifier)] = device

    if connect:
        # Connect to the PowerView hub first
        _LOG.info(
            "Connecting to PowerView hub: %s",
            device_config.identifier,
        )
        connected = await device.connect()

        if connected:
            _LOG.info(
                "Successfully connected to PowerView hub: %s",
                device_config.identifier,
            )

            # Now that we're connected, register entities from the hub
            await _register_available_entities_from_hub(device)
        else:
            _LOG.error(
                "Failed to connect to PowerView hub: %s",
                device_config.identifier,
            )


async def _register_available_entities_from_hub(device: powerview.SmartHub) -> bool:
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
        if device.covers is None:
            covers = await device.get_covers()
        _LOG.info("Found %d covers on PowerView network", len(device.covers))

        # Get scenes from the hub (this queries the PowerView network)
        if device.scenes is None:
            scenes = await device.get_scenes()
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
            cover_entity = PowerviewCover(
                device.device_config, cover, get_configured_device
            )
            entities.append(cover_entity)

        # Create scene/button entities from what the hub reports
        for scene in device.scenes:
            _LOG.debug(
                "Registering scene: %s (id %s)",
                scene.name,
                scene.id,
            )
            button_entity = PowerviewButton(
                device.device_config, scene, get_configured_device
            )
            entities.append(button_entity)

        # Register all entities with the API
        for entity in entities:
            if api.available_entities.contains(entity.id):
                _LOG.debug("Removing existing entity: %s", entity.id)
                api.available_entities.remove(entity.id)
            _LOG.debug("Adding entity: %s", entity.id)
            api.available_entities.add(entity)

        _LOG.info(
            "Successfully registered %d entities from PowerView hub",
            len(entities),
        )
        return True

    except Exception as ex:  # pylint: disable=broad-exception-caught
        _LOG.error("Error registering entities from hub: %s", ex)
        return False


def _entities_from_device_id(device_id: str) -> list[str]:
    """
    Return all associated entity identifiers of the given device.

    :param device_id: the device identifier
    :return: list of entity identifiers
    """
    # Get from configured device instance
    entities = []
    device = _configured_devices.get(device_id)
    if device:
        # Get entities from the live device instance
        entities.extend(
            create_entity_id(device.identifier, str(scene.id), EntityTypes.BUTTON)
            for scene in device.scenes
        )
        entities.extend(
            create_entity_id(device.identifier, str(cover.id), EntityTypes.COVER)
            for cover in device.covers
        )
    return entities


def on_device_added(device: PowerviewConfig) -> None:
    """Handle a newly added device in the configuration."""
    _LOG.debug("New device added: %s", device)
    # Schedule the async device addition
    _LOOP.create_task(_add_configured_device(device, connect=True))


def on_device_removed(device: PowerviewConfig | None) -> None:
    """Handle a removed device in the configuration."""
    if device is None:
        _LOG.debug(
            "Configuration cleared, disconnecting & removing all configured device instances"
        )
        for device in _configured_devices.values():
            device.events.remove_all_listeners()
        _configured_devices.clear()
        api.configured_entities.clear()
        api.available_entities.clear()
    else:
        if device.identifier in _configured_devices:
            _LOG.debug("Disconnecting from removed device %s", device.identifier)
            device = _configured_devices.pop(device.identifier)
            device.events.remove_all_listeners()
            entity_id = device.identifier
            api.configured_entities.remove(entity_id)
            api.available_entities.remove(entity_id)


def get_configured_device(device_id: str) -> powerview.SmartHub | None:
    """Return the configured device instance for the given device identifier."""
    return _configured_devices.get(str(device_id))


async def main():
    """Start the Remote Two/3 integration driver."""
    logging.basicConfig()

    level = os.getenv("UC_LOG_LEVEL", "DEBUG").upper()
    logging.getLogger("bridge").setLevel(level)
    logging.getLogger("driver").setLevel(level)
    logging.getLogger("config").setLevel(level)
    logging.getLogger("discover").setLevel(level)
    logging.getLogger("setup").setLevel(level)

    config.devices = config.Devices(
        api.config_dir_path, on_device_added, on_device_removed
    )

    # Connect to all configured PowerView hubs
    for device_config in config.devices.all():
        _LOG.info("Initializing PowerView hub: %s", device_config.identifier)
        await _add_configured_device(device_config, connect=True)

    await api.init("driver.json", setup.driver_setup_handler)


if __name__ == "__main__":
    _LOOP.run_until_complete(main())
    _LOOP.run_forever()
