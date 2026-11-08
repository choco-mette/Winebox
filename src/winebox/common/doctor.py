"""System dependency and health verification (Pre-flight checks)."""

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import List


@dataclass
class CheckResult:
    name: str
    passed: bool
    details: str
    remediation: str = ""


class SystemDoctor:
    """Verifies that the Linux host environment is ready for WineBox."""

    @staticmethod
    def check_bwrap() -> CheckResult:
        bwrap_path = shutil.which("bwrap")
        if not bwrap_path:
            return CheckResult(
                name="Bubblewrap binary",
                passed=False,
                details="Bubblewrap (bwrap) not found in PATH",
                remediation="Install bubblewrap using your package manager (e.g., 'sudo apt install bubblewrap')",
            )
        return CheckResult(name="Bubblewrap binary", passed=True, details=bwrap_path)

    @staticmethod
    def check_user_namespaces() -> CheckResult:
        """Tests whether unprivileged user namespaces work with bwrap."""
        bwrap_path = shutil.which("bwrap")
        if not bwrap_path:
            return CheckResult(
                name="User Namespaces",
                passed=False,
                details="Cannot verify namespaces: bwrap missing",
                remediation="Install bubblewrap first",
            )

        try:
            res = subprocess.run(
                [bwrap_path, "--unshare-user", "--ro-bind", "/", "/", "true"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if res.returncode == 0:
                return CheckResult(
                    name="User Namespaces",
                    passed=True,
                    details="Unprivileged user namespaces active and working with bwrap",
                )
            return CheckResult(
                name="User Namespaces",
                passed=False,
                details=f"bwrap test failed (code {res.returncode}): {res.stderr.strip()}",
                remediation="Enable unprivileged userns (sysctl kernel.unprivileged_userns_clone=1 or check AppArmor)",
            )
        except Exception as e:
            return CheckResult(
                name="User Namespaces",
                passed=False,
                details=f"Failed to run bwrap test: {e}",
                remediation="Ensure user namespaces are supported by your kernel",
            )

    @staticmethod
    def check_wine() -> CheckResult:
        wine_path = shutil.which("wine")
        if not wine_path:
            return CheckResult(
                name="Wine binary",
                passed=False,
                details="Wine binary not found in PATH",
                remediation="Install Wine using your package manager (e.g., 'sudo apt install wine')",
            )
        try:
            res = subprocess.run([wine_path, "--version"], capture_output=True, text=True, timeout=5)
            version = res.stdout.strip() if res.returncode == 0 else "version unknown"
            return CheckResult(name="Wine binary", passed=True, details=f"{wine_path} ({version})")
        except Exception as e:
            return CheckResult(
                name="Wine binary",
                passed=True,
                details=f"{wine_path} (could not query version: {e})",
            )

    @staticmethod
    def check_display() -> CheckResult:
        display = os.environ.get("DISPLAY")
        wayland = os.environ.get("WAYLAND_DISPLAY")
        if not display and not wayland:
            return CheckResult(
                name="Display Server",
                passed=False,
                details="Neither DISPLAY nor WAYLAND_DISPLAY found in environment",
                remediation="Ensure an X11 or Wayland session is active when running GUI applications",
            )
        details = []
        if display:
            details.append(f"X11: {display}")
        if wayland:
            details.append(f"Wayland: {wayland}")
        return CheckResult(name="Display Server", passed=True, details=", ".join(details))

    @staticmethod
    def check_audio() -> CheckResult:
        uid = os.getuid()
        pulse_socket = Path(f"/run/user/{uid}/pulse/native")
        pipewire_socket = Path(f"/run/user/{uid}/pipewire-0")

        if pulse_socket.exists():
            return CheckResult(name="Audio Server", passed=True, details=f"PulseAudio socket at {pulse_socket}")
        if pipewire_socket.exists():
            return CheckResult(name="Audio Server", passed=True, details=f"PipeWire socket at {pipewire_socket}")

        return CheckResult(
            name="Audio Server",
            passed=False,
            details="Neither PulseAudio nor PipeWire user socket detected in /run/user/<uid>/",
            remediation="Ensure PulseAudio or PipeWire is running in your user session",
        )

    @staticmethod
    def check_gpu() -> CheckResult:
        dri_path = Path("/dev/dri")
        if dri_path.exists() and any(dri_path.iterdir()):
            return CheckResult(name="GPU Acceleration", passed=True, details=f"DRI devices present in {dri_path}")
        return CheckResult(
            name="GPU Acceleration",
            passed=False,
            details="/dev/dri not found or empty",
            remediation="Check if GPU drivers (Mesa / proprietary) are installed for hardware acceleration",
        )

    def run_all(self) -> List[CheckResult]:
        return [
            self.check_bwrap(),
            self.check_user_namespaces(),
            self.check_wine(),
            self.check_display(),
            self.check_audio(),
            self.check_gpu(),
        ]

