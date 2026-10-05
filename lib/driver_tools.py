"""Package kernel-matched modules and diagnostic tools for an existing SD root."""
from pathlib import Path
import re
import shutil
import tempfile

from common import manifest_files, write_json


FILES = {
    "install.sh": "install-driver-tools.sh",
    "install-driver-modules.py": "install-driver-modules.py",
    "m4rch-driver-diagnostics": "collect-driver-diagnostics.sh",
    "README.txt": "driver-tools-README.txt",
}


def stage(project, outdir, *, modules_archive, kernel_release, kernel_sha256, blocked_modules):
    """Stage a self-contained Linux installer without writing any mounted SD."""
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._+-]{0,127}", kernel_release):
        raise ValueError("Invalid kernel release")
    if not re.fullmatch(r"[0-9a-f]{64}", kernel_sha256):
        raise ValueError("Invalid kernel image SHA-256")
    blocked_modules = list(blocked_modules)
    if not blocked_modules or len(set(blocked_modules)) != len(blocked_modules) or any(
            not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", name) for name in blocked_modules):
        raise ValueError("A unique nonempty list of modules to block from autoload is required")
    project, outdir, modules_archive = map(Path, (project, outdir, modules_archive))
    if modules_archive.is_symlink() or not modules_archive.is_file():
        raise ValueError("Module archive must be a regular file")
    if outdir.is_symlink():
        raise ValueError("Driver-tools output must not be a symlink")
    outdir.mkdir(parents=True, exist_ok=True)
    names = [*FILES, "modules.tar.gz", "autoload-blocklist.conf", "driver-tools-manifest.json"]
    for name in names:
        destination = outdir / name
        if destination.is_symlink() or (destination.exists() and not destination.is_file()):
            raise ValueError(f"Driver-tools destination must be a regular file: {destination}")
    for name, source in [*((name, project / "templates" / template)
                           for name, template in FILES.items()),
                         ("modules.tar.gz", modules_archive)]:
        with tempfile.NamedTemporaryFile(dir=outdir, prefix=".driver-tool-", delete=False) as stream:
            temporary = Path(stream.name)
            try:
                with source.open("rb") as original:
                    shutil.copyfileobj(original, stream)
                stream.flush()
                temporary.chmod(0o644 if name in ("modules.tar.gz", "README.txt") else 0o755)
                temporary.replace(outdir / name)
            finally:
                temporary.unlink(missing_ok=True)
    blocklist = "# m4rch: explicit driver loading policy.\n"
    blocklist += "# blacklist blocks alias-based loading; explicit modprobe still works.\n"
    blocklist += "".join(f"blacklist {name}\n" for name in blocked_modules)
    with tempfile.NamedTemporaryFile(dir=outdir, prefix=".driver-blocklist-", delete=False) as stream:
        temporary = Path(stream.name)
        try:
            stream.write(blocklist.encode())
            stream.flush()
            temporary.chmod(0o644)
            temporary.replace(outdir / "autoload-blocklist.conf")
        finally:
            temporary.unlink(missing_ok=True)
    write_json(outdir / "driver-tools-manifest.json", {
        "schema": 1,
        "kernel_release": kernel_release,
        "kernel_image_sha256": kernel_sha256,
        "archive_prefix": f"usr/lib/modules/{kernel_release}",
        "blocked_modules": blocked_modules,
        "files": manifest_files(outdir, [*FILES, "modules.tar.gz", "autoload-blocklist.conf"]),
    })
    return outdir
