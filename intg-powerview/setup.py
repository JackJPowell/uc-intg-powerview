#!/usr/bin/env python3

"""Module that includes all functions needed for the setup and reconfiguration process"""

import logging
from ipaddress import ip_address
from typing import Any

from aiopvapi.helpers.aiorequest import AioRequest
from aiopvapi.hub import Hub
from const import PowerviewDevice
from ucapi import IntegrationSetupError, RequestUserInput, SetupError
from ucapi_framework import BaseSetupFlow

_LOG = logging.getLogger(__name__)

_MANUAL_INPUT_SCHEMA = RequestUserInput(
    {"en": "Hunter Douglas Powerview Setup"},
    [
        {
            "id": "info",
            "label": {
                "en": "Setup your Hunter Douglas Powerview Device",
            },
            "field": {
                "label": {
                    "value": {
                        "en": (
                            "Please supply the IP address of your Hunter Douglas Powerview Device."
                        ),
                    }
                }
            },
        },
        {
            "field": {"text": {"value": ""}},
            "id": "address",
            "label": {
                "en": "IP Address",
            },
        },
    ],
)


class PowerviewSetupFlow(BaseSetupFlow[PowerviewDevice]):
    """
    Setup flow for PowerView integration.

    Handles PowerView device configuration through SSDP discovery or manual entry.
    """

    def get_manual_entry_form(self) -> RequestUserInput:
        """
        Return the manual entry form for device setup.

        :return: RequestUserInput with form fields for manual configuration
        """
        return _MANUAL_INPUT_SCHEMA

    async def query_device(
        self, input_values: dict[str, Any]
    ) -> PowerviewDevice | SetupError | RequestUserInput:
        address = input_values["address"]

        if address != "":
            # Check if input is a valid ipv4 or ipv6 address
            try:
                ip_address(address)
            except ValueError:
                _LOG.error("The entered ip address %s is not valid", address)
                return _MANUAL_INPUT_SCHEMA

            _LOG.info("Entered ip address: %s", address)

            try:
                request = AioRequest(address)
                hub = Hub(request)
                try:
                    await hub.query_firmware()
                    _LOG.info("Successfully connected to PowerView hub")
                    _LOG.info("Hub Name: %s", hub.hub_name)
                    _LOG.info("Model: %s", hub.model)
                    _LOG.info("Serial: %s", hub.serial_number)
                except Exception as ex:  # pylint: disable=broad-exception-caught
                    _LOG.error("Unable to query the Powerview Device: %s", ex)
                    return SetupError(IntegrationSetupError.NOT_FOUND)

                return PowerviewDevice(
                    identifier=hub.serial_number,
                    address=address,
                    name=hub.hub_name,
                    model=hub.model,
                )

            except Exception as ex:  # pylint: disable=broad-exception-caught
                _LOG.error("Unable to connect at IP: %s. Exception: %s", address, ex)
                _LOG.info(
                    "Please check if you entered the correct ip of the Powerview hub"
                )
                return SetupError(IntegrationSetupError.CONNECTION_REFUSED)
        else:
            _LOG.info("No ip address entered")
            return _MANUAL_INPUT_SCHEMA
