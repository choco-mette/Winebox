"""Mount builder for generating deterministic Bubblewrap command line arguments."""

import os
from pathlib import Path
from typing import Dict, List, Optional
from winebox.domain.models import HostMount, MountMode, SecurityPolicy


class MountBuilder:
    """Builds Bubblewrap (bwrap) argument lists based on security policy and filesystem paths."""

    def __init__(
        self,
        prefix_path: Path,
        isolated_home_path: Path,
        policy: SecurityPolicy,
        custom_runner_dir: Optional[Path] = None,
        sandbox_workdir: Optional[str] = None,
    ) -> None:
        self.prefix_path = prefix_path.resolve()
        self.isolated_home_path = isolated_home_path.resolve()
        self.policy = policy
        self.custom_runner_dir = custom_runner_dir.resolve() if custom_runner_dir else None
        self.sandbox_workdir = sandbox_workdir

    def build_bwrap_args(self) -> List[str]:
        """Generates the full list of Bubblewrap CLI arguments."""
        args: List[str] = [
            "bwrap",
            # Base namespaces isolation (ADR-012)
            "--unshare-user",
            "--unshare-ipc",
            "--unshare-pid",
            "--unshare-uts",
            "--unshare-cgroup",
            "--die-with-parent",
            "--new-session",
            # Base pseudo filesystems
            "--proc", "/proc",
            "--dev", "/dev",
            "--ro-bind-try", "/sys", "/sys",
            "--tmpfs", "/tmp",
            "--tmpfs", "/run",
            # Minimal host system runtime (read-only)
            "--ro-bind", "/usr", "/usr",
            "--ro-bind-try", "/lib", "/lib",
            "--ro-bind-try", "/lib64", "/lib64",
            "--ro-bind-try", "/bin", "/bin",
            "--ro-bind-try", "/opt", "/opt",
            "--ro-bind", "/etc/ld.so.cache", "/etc/ld.so.cache",
            "--ro-bind-try", "/etc/ld.so.conf", "/etc/ld.so.conf",
            "--ro-bind-try", "/etc/ld.so.conf.d", "/etc/ld.so.conf.d",
            "--ro-bind-try", "/etc/resolv.conf", "/etc/resolv.conf",
            "--ro-bind-try", "/etc/hosts", "/etc/hosts",
            "--ro-bind-try", "/etc/nsswitch.conf", "/etc/nsswitch.conf",
            "--ro-bind-try", "/etc/fonts", "/etc/fonts",
            "--ro-bind-try", "/etc/ssl", "/etc/ssl",
            "--ro-bind-try", "/etc/pki", "/etc/pki",
            "--ro-bind-try", "/etc/ca-certificates", "/etc/ca-certificates",
            "--ro-bind-try", "/etc/vulkan", "/etc/vulkan",
            "--ro-bind-try", "/etc/glvnd", "/etc/glvnd",
            "--ro-bind-try", "/etc/drirc", "/etc/drirc",
            "--ro-bind-try", "/etc/alternatives", "/etc/alternatives",
            "--setenv", "PATH", os.environ.get("PATH", "/usr/bin:/bin"),
        ]

        # Ensure isolated home mount point exists
        dot_wine = self.isolated_home_path / ".wine"
        dot_wine.mkdir(parents=True, exist_ok=True)

        # Network policy (ADR-014)
        if self.policy.network:
            args.append("--share-net")
        else:
            args.append("--unshare-net")

        # Isolated HOME & WINEPREFIX (ADR-006)
        user_name = os.environ.get("USER", "winebox")
        sandbox_home = f"/home/{user_name}"
        args.extend([
            "--bind", str(self.isolated_home_path), sandbox_home,
            "--setenv", "HOME", sandbox_home,
            "--setenv", "USER", user_name,
        ])

        sandbox_prefix = f"{sandbox_home}/.wine"
        args.extend([
            "--bind", str(self.prefix_path), sandbox_prefix,
            "--setenv", "WINEPREFIX", sandbox_prefix,
        ])

        uid = os.getuid()
        runtime_dir = f"/run/user/{uid}"
        if self.policy.display or self.policy.audio:
            args.extend([
                "--dir", runtime_dir,
                "--setenv", "XDG_RUNTIME_DIR", runtime_dir,
            ])

        # Hardware: Display (ADR-013)
        if self.policy.display:
            display_var = os.environ.get("DISPLAY")
            if display_var:
                args.extend([
                    "--ro-bind-try", "/tmp/.X11-unix", "/tmp/.X11-unix",
                    "--setenv", "DISPLAY", display_var,
                ])
                xauth = os.environ.get("XAUTHORITY") or str(Path.home() / ".Xauthority")
                if xauth and Path(xauth).exists():
                    args.extend([
                        "--ro-bind-try", xauth, f"{sandbox_home}/.Xauthority",
                        "--setenv", "XAUTHORITY", f"{sandbox_home}/.Xauthority",
                    ])
            wayland_var = os.environ.get("WAYLAND_DISPLAY")
            if wayland_var:
                wayland_sock = Path(f"{runtime_dir}/{wayland_var}")
                if wayland_sock.exists():
                    args.extend([
                        "--ro-bind-try", str(wayland_sock), f"{runtime_dir}/{wayland_var}",
                        "--setenv", "WAYLAND_DISPLAY", wayland_var,
                    ])

        # Hardware: Audio (ADR-013)
        if self.policy.audio:
            pulse_dir = Path(f"{runtime_dir}/pulse")
            if pulse_dir.exists():
                args.extend([
                    "--ro-bind-try", str(pulse_dir), f"{runtime_dir}/pulse",
                    "--setenv", "PULSE_SERVER", f"unix:{runtime_dir}/pulse/native",
                ])
            pipewire_socket = Path(f"{runtime_dir}/pipewire-0")
            if pipewire_socket.exists():
                args.extend([
                    "--ro-bind-try", str(pipewire_socket), f"{runtime_dir}/pipewire-0",
                ])

        # Hardware: GPU (ADR-013)
        if self.policy.gpu:
            if Path("/dev/dri").exists():
                args.extend(["--dev-bind-try", "/dev/dri", "/dev/dri"])
            # NVIDIA devices
            for nv_dev in ["/dev/nvidiactl", "/dev/nvidia0", "/dev/nvidia-modeset", "/dev/nvidia-uvm"]:
                if Path(nv_dev).exists():
                    args.extend(["--dev-bind-try", nv_dev, nv_dev])

        # Hardware: Gamepad / Controller input
        if self.policy.gamepad:
            if Path("/dev/input").exists():
                args.extend(["--dev-bind-try", "/dev/input", "/dev/input"])

        # Custom Runner directory (ADR-011)
        if self.custom_runner_dir and self.custom_runner_dir.exists():
            sandbox_runner = "/app/runner"
            args.extend([
                "--ro-bind", str(self.custom_runner_dir), sandbox_runner,
                "--setenv", "PATH", f"{sandbox_runner}/bin:/usr/bin:/bin",
                "--setenv", "LD_LIBRARY_PATH", f"{sandbox_runner}/lib:{sandbox_runner}/lib64",
            ])

        # Explicit custom host mounts
        for mount in self.policy.host_mounts:
            flag = "--bind" if mount.mode == MountMode.RW else "--ro-bind"
            args.extend([flag, str(mount.host_path), str(mount.sandbox_path)])

        # Custom environment variables
        for k, v in self.policy.env_vars.items():
            args.extend(["--setenv", k, v])

        # Working directory inside sandbox
        target_workdir = self.sandbox_workdir or sandbox_home
        args.extend(["--chdir", target_workdir])

        return args

