"""Select the local Linux builder runtime and validate the supported Mac."""
from __future__ import annotations

import os
import platform
import shutil
import subprocess


def runtime():
    name = os.environ.get("RUNTIME")
    if name is None:
        candidates = ("container", "docker", "podman") if platform.system() == "Darwin" else ("podman", "docker")
        name = next((x for x in candidates if shutil.which(x)), None)
    if name not in ("container", "docker", "podman") or not shutil.which(name):
        raise ValueError("Install Apple container, Docker or Podman; optionally set RUNTIME=container|docker|podman")
    return name


def identify_mac(explicit):
    if platform.system() == "Darwin":
        actual = subprocess.check_output(["sysctl", "-n", "hw.model"], text=True).strip()
        if actual != "Mac16,8":
            raise ValueError(f"This Mac is {actual}; only Mac16,8 is supported")
        if explicit and explicit != actual:
            raise ValueError("Explicit target disagrees with this Mac")
        return actual
    if explicit != "Mac16,8":
        raise ValueError("On a non-Mac builder pass --model Mac16,8 explicitly")
    return explicit
