"""Security policy validation and host path constraints."""

import os
from pathlib import Path
from typing import List, Set
from winebox.common.exceptions import PolicyValidationError
from winebox.domain.models import HostMount, SecurityPolicy


class PolicyValidator:
    """Validates security policies against prohibited host paths and configurations."""

    # Prohibited host paths that should NEVER be mounted directly into sandboxes
    RESTRICTED_PREFIXES: Set[Path] = {
        Path("/"),
        Path("/root"),
        Path("/etc"),
        Path("/sys"),
        Path("/boot"),
        Path("/var"),
        Path("/media"),
        Path("/mnt"),
    }

    # Critical sandbox paths that must NEVER be shadowed by custom host mounts
    RESTRICTED_SANDBOX_PREFIXES: Set[Path] = {
        Path("/proc"),
        Path("/dev"),
        Path("/sys"),
        Path("/app/runner"),
        Path("/usr"),
        Path("/lib"),
        Path("/lib64"),
        Path("/bin"),
    }

    # Sensitive directories in user HOME that must never be exposed
    SENSITIVE_HOME_NAMES: Set[str] = {
        ".ssh",
        ".gnupg",
        ".config",
        ".local",
        ".bashrc",
        ".zshrc",
        ".profile",
        ".cache",
    }

    def __init__(self, host_home: Path | None = None) -> None:
        self.host_home = (host_home or Path.home()).resolve()

    def validate_mount(self, mount: HostMount) -> None:
        """Validates an individual host-to-sandbox bind mount."""
        host_path = mount.host_path.resolve()

        # Disallow mounting root directly
        if host_path == Path("/"):
            raise PolicyValidationError("Cannot mount host root '/' into sandbox")

        # Disallow mounting host HOME root directly
        if host_path == self.host_home:
            raise PolicyValidationError(
                "Cannot mount entire host user HOME directory into sandbox. Select specific subfolders."
            )

        # Disallow sensitive subpaths in home
        try:
            rel_to_home = host_path.relative_to(self.host_home)
            first_part = rel_to_home.parts[0]
            if first_part in self.SENSITIVE_HOME_NAMES:
                raise PolicyValidationError(
                    f"Access to sensitive host HOME directory '{first_part}' is strictly prohibited"
                )
        except ValueError:
            # Not inside host home
            pass

        # Disallow system directories
        for restricted in self.RESTRICTED_PREFIXES:
            if restricted != Path("/") and host_path == restricted:
                raise PolicyValidationError(
                    f"Mounting system directory '{restricted}' directly is strictly prohibited"
                )

        # Validate sandbox mount destination lexically (do not resolve host symlinks)
        raw_sandbox_path = Path(mount.sandbox_path)
        if not raw_sandbox_path.is_absolute():
            raise PolicyValidationError(
                f"Sandbox mount path '{mount.sandbox_path}' must be an absolute path"
            )
        norm_sandbox = os.path.normpath(str(raw_sandbox_path))
        if norm_sandbox.startswith("//"):
            norm_sandbox = "/" + norm_sandbox.lstrip("/")
        sandbox_path = Path(norm_sandbox)

        if sandbox_path == Path("/") or any(
            sandbox_path == restricted or sandbox_path.is_relative_to(restricted)
            for restricted in self.RESTRICTED_SANDBOX_PREFIXES
        ):
            raise PolicyValidationError(
                f"Mounting over critical sandbox path '{mount.sandbox_path}' is strictly prohibited"
            )

        if not host_path.exists():
            raise PolicyValidationError(f"Host path does not exist: {host_path}")

    def validate_policy(self, policy: SecurityPolicy) -> None:
        """Validates all aspects of a SecurityPolicy."""
        for mount in policy.host_mounts:
            self.validate_mount(mount)

