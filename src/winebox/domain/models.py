"""Domain models for WineBox."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional


class AppStatus(str, Enum):
    READY = "ready"
    DISABLED = "disabled"
    FAILED = "failed"


class PrefixOrigin(str, Enum):
    CREATED = "created"
    IMPORTED = "imported"


class PrefixStatus(str, Enum):
    READY = "ready"
    STAGING = "staging"
    CORRUPTED = "corrupted"


class MountMode(str, Enum):
    RO = "ro"
    RW = "rw"


@dataclass
class HostMount:
    host_path: Path
    sandbox_path: Path
    mode: MountMode = MountMode.RO


@dataclass
class SecurityProfile:
    id: str
    name: str
    is_builtin: bool = False
    display: bool = True
    audio: bool = True
    network: bool = True
    gpu: bool = True
    description: str = ""

    def to_policy(self, host_mounts: Optional[List[HostMount]] = None, env_vars: Optional[Dict[str, str]] = None) -> "SecurityPolicy":
        return SecurityPolicy(
            display=self.display,
            audio=self.audio,
            network=self.network,
            gpu=self.gpu,
            host_mounts=host_mounts or [],
            env_vars=env_vars or {},
        )


@dataclass
class SecurityPolicy:
    display: bool = True
    audio: bool = True
    network: bool = True
    gpu: bool = True
    host_mounts: List[HostMount] = field(default_factory=list)
    env_vars: Dict[str, str] = field(default_factory=dict)


@dataclass
class Application:
    id: str
    name: str
    prefix_id: str
    exe_path: str  # Path relative to prefix drive_c or absolute within sandbox
    runner_id: str = "system-wine"
    profile_id: str = "permissive"
    arguments: List[str] = field(default_factory=list)
    policy: SecurityPolicy = field(default_factory=SecurityPolicy)
    status: AppStatus = AppStatus.READY
    last_run_at: Optional[datetime] = None
    last_exit_code: Optional[int] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class Prefix:
    id: str
    name: str
    runner_id: str = "system-wine"
    default_profile_id: str = "permissive"
    origin: PrefixOrigin = PrefixOrigin.CREATED
    status: PrefixStatus = PrefixStatus.READY
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class Runner:
    id: str
    name: str
    wine_bin: Path
    wineserver_bin: Optional[Path] = None
    is_system: bool = True
