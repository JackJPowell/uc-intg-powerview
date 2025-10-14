"""
This module implements the Powerview constants for the Remote Two/3 integration driver.
"""

from dataclasses import dataclass
from aiopvapi.resources.shade import BaseShade
from aiopvapi.resources.scene import Scene


@dataclass
class PowerviewCoverInfo:
    device_id: str
    type: str
    name: str
    id: str = None  # Alias for device_id for consistency
    position: int = 0  # Position of the shade (0-100)
    raw_shade: BaseShade | None = (
        None  # Store the raw BaseShade object for API operations
    )

    def __post_init__(self):
        """Ensure id is set to device_id if not provided."""
        if self.id is None:
            self.id = self.device_id


@dataclass
class PowerviewSceneInfo:
    scene_id: str
    name: str
    id: str = None  # Alias for scene_id for consistency
    raw_scene: Scene | None = None  # Store the raw Scene object for API operations

    def __post_init__(self):
        """Ensure id is set to scene_id if not provided."""
        if self.id is None:
            self.id = self.scene_id
