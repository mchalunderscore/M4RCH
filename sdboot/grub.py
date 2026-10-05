"""Build the m4rch GRUB package with the upstream ARM64 memory fix.

The separate, signed build-dependency transaction never changes the desktop
package lock. Image builds and Linux updates use the same pacman package.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shutil
import subprocess

from common import download, manifest_files, run, sha256, verify_manifest, write_json
from image import install_packages, root_workspace, stop_chroot_processes, unmount_chroot



def recipe_inputs(project, lock):
    recipe = project / "packages/grub-m4rch"
    return {"recipe": manifest_files(recipe, [p.name for p in sorted(recipe.iterdir()) if p.is_file()]),
            "builder": sha256(project / "sdboot/grub.py"), "rootfs": lock["rootfs"],
            "source_date_epoch": lock["source_date_epoch"]}


def build(project, out, config, lock):
    directory = out / "grub"
    directory.mkdir(exist_ok=True)
    inputs = recipe_inputs(project, lock)
    manifest_path = directory / "manifest.json"
    if manifest_path.is_file():
        previous = verify_manifest(manifest_path)
        if previous.get("inputs") == inputs and previous.get("config") == config:
            print("Reusing verified grub-m4rch package.", flush=True)
            return previous
    pin = json.loads((project / "packages/grub-m4rch/source.json").read_text())
    source = lock["rootfs"]
    archive = download(source["url"], Path("/cache") / source["filename"], source["sha256"])
    sig = source["signature"]
    signature = download(sig["url"], Path("/cache") / (source["filename"] + ".sig"), sig["sha256"])
    keyring = Path("/work/grub-alarm.gpg")
    run(["gpg", "--batch", "--yes", "--dearmor", "--output", keyring, project / "keys/archlinuxarm-builder.asc"])
    result = run(["gpg", "--batch", "--no-default-keyring", "--keyring", keyring,
                  "--status-fd", "1", "--verify", signature, archive], stdout=subprocess.PIPE, text=True)
    signatures = [line.split() for line in result.stdout.splitlines() if line.startswith("[GNUPG:] VALIDSIG ")]
    if not any(source["signer"] in (fields[2], fields[-1]) for fields in signatures):
        raise ValueError("GRUB build root signature does not match the pinned key")
    cache = Path("/cache/grub-build-packages")
    with root_workspace() as workspace:
        root = workspace / "root"
        root.mkdir()
        run(["bsdtar", "--numeric-owner", "--acls", "--xattrs", "-xpf", archive, "-C", root])
        install_packages(root, {"packages": ["base-devel", *pin["makedepends"]]}, cache=cache,
                         lockfile=cache / "packages.lock.json", lock_output=directory / "build-packages.lock.json")
        stage = root / "tmp/grub-build"
        shutil.copytree(project / "packages/grub-m4rch", stage)
        for item in [pin, *pin.get("additional_sources", [])]:
            downloaded = download(item["url"], Path("/cache/grub") / item["filename"], item["sha256"])
            shutil.copyfile(downloaded, stage / item["filename"])
        run(["chroot", root, "chown", "-R", "alarm:alarm", "/tmp/grub-build"])
        run(["mount", "--bind", root, root])
        try:
            run(["mount", "-t", "proc", "proc", root / "proc"])
            environment = dict(os.environ, SOURCE_DATE_EPOCH=str(lock["source_date_epoch"]),
                               SYSTEMD_OFFLINE="1")
            run(["chroot", root, "runuser", "-u", "alarm", "--", "env",
                 "MAKEFLAGS=-j" + str(config["jobs"]), "PKGEXT=.pkg.tar.zst",
                 "bash", "-c", "cd /tmp/grub-build && makepkg --noconfirm --force"], env=environment)
            archives = list(stage.glob("grub-m4rch-*.pkg.tar.zst"))
            if len(archives) != 1:
                raise ValueError("Expected exactly one patched GRUB package")
            package = archives[0]
            # Repository signatures remain required; only our locally compiled
            # package is unsigned, via a one-transaction pacman configuration.
            settings = (root / "etc/pacman.conf").read_text()
            settings = re.sub(r"(?m)^LocalFileSigLevel\s*=.*$", "LocalFileSigLevel = Optional", settings)
            (root / "tmp/grub-pacman.conf").write_text(settings)
            run(["chroot", root, "pacman", "--config", "/tmp/grub-pacman.conf", "-U", "--noconfirm",
                 "/tmp/grub-build/" + package.name], env=environment)
            run(["chroot", root, "pacman", "-Qkk", "grub-m4rch"])
            version = subprocess.check_output(["chroot", root, "pacman", "-Q", "grub-m4rch"], text=True).strip().split()[1]
            if version != pin["package_version"]:
                raise ValueError("Built GRUB version does not match the pinned recipe")
            # ALARM's makepkg configuration includes the epoch in filenames.
            # FAT forbids ':', so omit it from this filename only. Pacman reads
            # the unchanged, epoch-bearing version from the package metadata.
            package_name = "grub-m4rch-" + version.split(":", 1)[-1] + "-aarch64.pkg.tar.zst"
            if recipe_inputs(project, lock) != inputs:
                raise ValueError("GRUB build inputs changed during compilation; rebuild")
            shutil.copyfile(package, directory / package_name)
        finally:
            stop_chroot_processes(root)
            unmount_chroot(root / "proc")
            unmount_chroot(root)
    manifest = {"schema": 1, "kind": "grub-m4rch-package", "config": config,
                "version": version, "package": package_name, "inputs": inputs,
                "files": manifest_files(directory, [package_name, "build-packages.lock.json"])}
    write_json(manifest_path, manifest)
    return verify_manifest(manifest_path)
