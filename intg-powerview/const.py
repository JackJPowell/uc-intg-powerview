"""
This module implements the Powerview constants for the Remote Two/3 integration driver.
"""

from dataclasses import dataclass


@dataclass
class PowerviewCoverInfo:
    device_id: str
    type: str
    name: str


@dataclass
class PowerviewSceneInfo:
    scene_id: str
    name: str
