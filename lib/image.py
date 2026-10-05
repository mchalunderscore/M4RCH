"""Shared filesystem and signed-package transaction primitives for the SD build."""
from __future__ import annotations

import contextlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import stat
import subprocess
import tempfile
import tarfile
import time

from common import download, run, sha256, write_json

PROJECT = Path(__file__).resolve().parent.parent


def write(root, name, text, mode=0o644):
    path = root / name.lstrip("/")
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        path.unlink()
    elif path.is_file():
        path.chmod(path.stat().st_mode | stat.S_IWUSR)
    path.write_text(text)
    path.chmod(mode)


def link(root, name, target):
    path = root / name.lstrip("/")
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() or path.is_symlink():
        path.unlink()
    path.symlink_to(target)


def newc(tree, epoch):
    """Canonical Linux newc archive. Never follows a symlink out of the tree."""
    data = bytearray()

    def member(name, mode, payload, inode):
        encoded = name.encode() + b"\0"
        fields = (inode, mode, 0, 0, 1, epoch, len(payload), 0, 0, 0, 0, len(encoded), 0)
        data.extend(b"070701" + b"".join(f"{x:08x}".encode() for x in fields))
        data.extend(encoded)
        data.extend(b"\0" * (-len(data) % 4))
        data.extend(payload)
        data.extend(b"\0" * (-len(data) % 4))

    for inode, path in enumerate(sorted(tree.rglob("*")), 1):
        info = path.lstat()
        if stat.S_ISLNK(info.st_mode):
            payload = os.readlink(path).encode()
        elif stat.S_ISREG(info.st_mode):
            payload = path.read_bytes()
        elif stat.S_ISDIR(info.st_mode):
            payload = b""
        else:
            raise ValueError(f"Unexpected special file in initramfs: {path}")
        member("./" + str(path.relative_to(tree)), info.st_mode, payload, inode)
    member("TRAILER!!!", 0, b"", 0)
    data.extend(b"\0" * (-len(data) % 512))
    return bytes(data)


def stop_chroot_processes(root):
    """Reap only daemons rooted in this disposable package-install chroot."""
    def remaining():
        result = []
        for process in Path("/proc").iterdir():
            if not process.name.isdigit() or int(process.name) <= 1:
                continue
            try:
                if os.readlink(process / "root") == str(root):
                    result.append(int(process.name))
            except (FileNotFoundError, PermissionError, ProcessLookupError):
                pass
        return result

    # Package upgrades can replace gpg-agent and its sockets, leaving an older
    # agent unreachable by gpgconf. Scope cleanup by the process root, never
    # by an executable name that could match unrelated container processes.
    for sig in (signal.SIGTERM, signal.SIGKILL):
        for pid in remaining():
            print(f"Stopping package-build chroot process {pid}", flush=True)
            try:
                os.kill(pid, sig)
            except ProcessLookupError:
                pass
        deadline = time.monotonic() + 5
        while remaining() and time.monotonic() < deadline:
            time.sleep(0.1)
        if not remaining():
            return
    raise ValueError("Package-build chroot still has running processes")


def install_packages(root, config, *, cache=None, lockfile=None, lock_output=None):
    (root / "proc").mkdir(exist_ok=True)
    # Pacman reads mountinfo for CheckSpace. Give the chroot a real mountpoint
    # rather than disabling its disk-space check.
    run(["mount", "--bind", root, root])
    try:
        run(["mount", "-t", "proc", "proc", root / "proc"])
        try:
            _install_packages(root, config, cache=cache, lockfile=lockfile, lock_output=lock_output)
        finally:
            # gpg-agent is started by pacman-key and holds the chroot open.
            try:
                run(["chroot", root, "gpgconf", "--homedir", "/etc/pacman.d/gnupg", "--kill", "all"])
                stop_chroot_processes(root)
            finally:
                unmount_chroot(root / "proc")
    finally:
        unmount_chroot(root)
    # Remove the builder's private signing key only AFTER its agents exit.
    shutil.rmtree(root / "etc/pacman.d/gnupg")


def unmount_chroot(path):
    # GnuPG's shutdown acknowledgement precedes its final process exit. Its
    # nondumpable agents may also hide /proc/PID/root from container root.
    # Wait for the mount to become free; never use a lazy/forced unmount while
    # the root tree is about to be packaged or removed.
    deadline = time.monotonic() + 15
    while True:
        result = subprocess.run(["umount", str(path)], capture_output=True, text=True)
        if result.returncode == 0:
            print(f"Unmounted package-build mount {path}", flush=True)
            return
        if time.monotonic() >= deadline:
            raise ValueError(f"Cannot release package-build mount {path}: {result.stderr.strip()}")
        time.sleep(0.2)


@contextlib.contextmanager
def root_workspace():
    """Retain failed mounted trees instead of recursively deleting through them."""
    temporary = Path(tempfile.mkdtemp(prefix="image-", dir="/work"))
    try:
        yield temporary
    finally:
        try:
            mountpoints = [line.split()[4] for line in Path("/proc/self/mountinfo").read_text().splitlines()]
            # mkdtemp's /work/image-* path contains no mountinfo-escaped bytes.
            mounted = any(path == str(temporary) or path.startswith(str(temporary) + "/")
                          for path in mountpoints)
        except OSError:
            mounted = True
        if mounted:
            print(f"Retaining {temporary}: mounts could not be confirmed released; "
                  "container exit will release them.", flush=True)
        else:
            shutil.rmtree(temporary)


def _install_packages(root, config, *, cache=None, lockfile=None, lock_output=None):
    """Resolve once, then reuse a hash-pinned package transaction offline."""
    cache = Path(cache) if cache is not None else Path("/cache/desktop-packages")
    cache.mkdir(exist_ok=True)
    lockfile = Path(lockfile) if lockfile is not None else PROJECT / "packages.lock.json"
    if not lockfile.exists():
        lockfile = cache / "packages.lock.json"
    pkgdir = root / "var/cache/pacman/pkg"
    pkgdir.mkdir(parents=True, exist_ok=True)
    for file in pkgdir.iterdir():
        if file.is_file():
            file.unlink()
    # These are device nodes inside the isolated Linux build filesystem, never
    # Mac /dev nodes. Pacman/GnuPG need random/null even without mounting /dev.
    for name, major, minor in (("null", 1, 3), ("zero", 1, 5), ("random", 1, 8), ("urandom", 1, 9)):
        path = root / "dev" / name
        if not path.exists() and not path.is_symlink():
            os.mknod(path, stat.S_IFCHR | 0o666, os.makedev(major, minor))
        info = path.lstat()
        if not stat.S_ISCHR(info.st_mode) or info.st_rdev != os.makedev(major, minor):
            raise ValueError(f"Unexpected build-root device node: {path}")
        # mknod respects the builder's umask. Package creation later runs as an
        # ordinary user, which must be able to open the same /dev/null for write.
        path.chmod(0o666)
        os.chown(path, 0, 0)
    link(root, "dev/fd", "/proc/self/fd")
    for name, descriptor in (("stdin", 0), ("stdout", 1), ("stderr", 2)):
        link(root, "dev/" + name, "/proc/self/fd/" + str(descriptor))
    write(root, "etc/resolv.conf", Path("/etc/resolv.conf").read_text())
    write(root, "etc/pacman.d/mirrorlist", "Server = https://ca.us.mirror.archlinuxarm.org/$arch/$repo\n")
    pacman_conf = root / "etc/pacman.conf"
    settings = pacman_conf.read_text()
    if not re.search(r"(?m)^LocalFileSigLevel\s*=", settings):
        raise ValueError("Cannot locate pacman LocalFileSigLevel setting")
    pacman_conf.write_text(re.sub(r"(?m)^LocalFileSigLevel\s*=.*$", "LocalFileSigLevel = Required", settings))
    env = dict(os.environ, SYSTEMD_OFFLINE="1")
    run(["chroot", root, "pacman-key", "--init"], env=env)
    run(["chroot", root, "pacman-key", "--populate", "archlinuxarm"], env=env)
    if lockfile.exists():
        package_lock = json.loads(lockfile.read_text())
        if package_lock["requested"] != config["packages"]:
            raise ValueError("Package selection changed. Regenerate packages.lock.json before building.")
        for entry in package_lock["files"]:
            file = download(entry["url"], cache / entry["filename"], entry["sha256"])
            shutil.copyfile(file, pkgdir / file.name)
    else:
        # Resolve the new transaction first, then seed exactly its filenames
        # from the shared cache. Seeding every cached version would leave stale
        # duplicates in pacman's -U input; ignoring the cache redownloads KDE.
        run(["chroot", root, "pacman", "-Sy", "--disable-sandbox", "--noconfirm"], env=env)
        planned = run(["chroot", root, "pacman", "-Sup", "--noconfirm", "--print-format", "%f", *config["packages"]], env=env, stdout=subprocess.PIPE, text=True)
        filenames = planned.stdout.splitlines()
        if not filenames or any(not re.fullmatch(r"[A-Za-z0-9@+_.:-]+\.pkg\.tar\.(?:xz|zst|gz)", name) for name in filenames):
            raise ValueError("Could not determine exact package filenames for the signed transaction")
        for name in filenames:
            for suffix in ("", ".sig"):
                candidate = cache / (name + suffix)
                if candidate.is_file():
                    shutil.copyfile(candidate, pkgdir / candidate.name)
        run(["chroot", root, "pacman", "-Su", "--disable-sandbox", "--noconfirm", "--downloadonly", *config["packages"]], env=env)
        repositories = {}
        for db in (root / "var/lib/pacman/sync").glob("*.db"):
            with tarfile.open(db) as archive:
                for member in archive:
                    if member.name.endswith("/desc"):
                        text = archive.extractfile(member).read().decode()
                        filename = re.search(r"%FILENAME%\n([^\n]+)", text)
                        if filename:
                            repositories[filename[1]] = db.stem
        files = []
        for package in sorted(pkgdir.glob("*.pkg.tar.*")):
            if package.suffix == ".sig":
                continue
            repo = repositories[package.name]
            url = "https://ca.us.mirror.archlinuxarm.org/aarch64/" + repo + "/" + package.name
            signature = package.with_name(package.name + ".sig")
            if not signature.exists():
                run(["curl", "-fL", "--retry", "3", "-o", signature, url + ".sig"])
            for file, source in ((package, url), (signature, url + ".sig")):
                shutil.copyfile(file, cache / file.name)
                files.append({"filename": file.name, "url": source, "sha256": sha256(file)})
        package_lock = {"schema": 1, "requested": config["packages"], "files": files}
        write_json(cache / "packages.lock.json", package_lock)
    packages = sorted("/var/cache/pacman/pkg/" + p.name for p in pkgdir.glob("*.pkg.tar.*") if p.suffix != ".sig")
    for package in packages:
        if not (pkgdir / (Path(package).name + ".sig")).is_file():
            raise ValueError(f"Missing required package signature: {package}")
    if packages:
        # Hooks for a stock kernel are irrelevant to the separately enrolled M4
        # bundle. Do not waste space building a generic initramfs in the chroot.
        for hook in ("90-mkinitcpio-install.hook", "60-mkinitcpio-remove.hook"):
            link(root, "etc/pacman.d/hooks/" + hook, "/dev/null")
        run(["chroot", root, "pacman", "-U", "--disable-sandbox", "--noconfirm", *packages], env=env)
    for file in pkgdir.iterdir():
        if file.is_file():
            file.unlink()
    write_json(lock_output or "/out/packages.lock.json", package_lock)
