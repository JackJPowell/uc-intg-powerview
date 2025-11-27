"""Discovery module for Hunter Douglas PowerView devices using mDNS/Zeroconf."""

from typing import Any

from ucapi_framework.discovery import MDNSDiscovery, DiscoveredDevice
from zeroconf import IPVersion


class PowerViewDiscovery(MDNSDiscovery):
    """mDNS discovery for Hunter Douglas PowerView hubs."""

    def __init__(self, timeout: int = 5):
        """
        Initialize PowerView discovery.

        :param timeout: Discovery timeout in seconds
        """
        super().__init__(service_type="_powerview._tcp.local.", timeout=timeout)

    def parse_mdns_service(self, service_info: Any) -> DiscoveredDevice | None:
        """
        Parse mDNS service info into DiscoveredDevice.

        :param service_info: mDNS service info object from zeroconf
        :return: DiscoveredDevice or None if parsing fails
        """
        if not service_info.parsed_addresses():
            return None

        # Get the first IPv4 address
        addresses = service_info.parsed_addresses(version=IPVersion.V4Only)[0]
        address = addresses[0] if addresses else None

        if not address:
            return None

        # Extract name from service info (remove service suffix)
        name = service_info.name
        if name.endswith("._powerview._tcp.local."):
            name = name.replace("._powerview._tcp.local.", "")

        return DiscoveredDevice(
            identifier=name,
            name=name,
            address=address,
            extra_data={
                "port": service_info.port,
                "server": service_info.server,
                "properties": dict(service_info.properties)
                if service_info.properties
                else {},
            },
        )
