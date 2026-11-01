#!/usr/bin/env python3
"""Stage the promoted M4RCH package recipe with a completed new kernel build."""

import argparse
import importlib.util
import json
from pathlib import Path
import shlex
import shutil
import tarfile
import tempfile

import preflight
import rootfs_audit

HERE = Path(__file__).resolve().parent
RELEASE = "7.3.0-m4rch-aurora1"
RECIPE_SOURCES = (
    "Image",
    "modules.tar.gz",
    "linux-m4rch.preset",
    "mkinitcpio-m4rch.conf",
    "m4rch-j614s.conf",
    "update-m1n1",
    "50-m4rch.cfg",
    "apple-j614s.dtb",
    "kernel.config",
    "upstream-integration.patch",
    "mtp-handoff.patch",
    "touchid.patch",
    "jack.patch",
    "source-stack.md",
    "t6040-j614s.dts",
    "GPL-2.0",
)
REQUIRED_MODULES = rootfs_audit.ROOTS + (
    "kernel/drivers/soc/apple/apple-sart.ko",
    "kernel/drivers/md/dm-crypt.ko",
    "kernel/drivers/md/dm-integrity.ko",
    "kernel/crypto/xts.ko",
    "kernel/sound/core/seq/snd-seq.ko",
)


def validate_config(text):
    expected = {
        'CONFIG_LOCALVERSION="-m4rch-aurora1"',
        "CONFIG_RUST=y",
        "CONFIG_SND_SEQUENCER=m",
        "CONFIG_SND_SEQ_DEVICE=m",
        "CONFIG_BTRFS_FS=m",
        "CONFIG_NVME_APPLE=m",
        "CONFIG_DM_CRYPT=m",
        "CONFIG_DM_INTEGRITY=m",
        "CONFIG_CRYPTO_XTS=m",
    }
    if not expected.issubset(set(text.splitlines())):
        raise ValueError("rebuilt kernel config does not meet candidate requirements")


def verify_modules(archive_path):
    prefix = f"lib/modules/{RELEASE}/"
    with tarfile.open(archive_path, "r:gz") as archive:
        members = archive.getmembers()
        names = [item.name.removeprefix("./") for item in members]
        if len(names) != len(set(names)):
            raise ValueError("duplicate module archive path")
        by_name = dict(zip(names, members))
        dep = by_name.get(prefix + "modules.dep")
        if dep is None or not dep.isfile():
            raise ValueError("rebuilt kernel has no modules.dep")
        closure = rootfs_audit.module_closure(
            archive.extractfile(dep).read().decode("utf-8"), REQUIRED_MODULES
        )
        for name in closure:
            entry = by_name.get(prefix + name)
            if entry is None or not entry.isfile():
                raise ValueError(f"rebuilt module missing: {name}")
            data = archive.extractfile(entry).read()
            if b"vermagic=" + RELEASE.encode() not in data:
                raise ValueError(f"module release mismatch: {name}")
    return closure


def prepare(build, archive_root, output):
    image = build / "arch/arm64/boot/Image"
    modules = build / "modules.tar.gz"
    config = build / ".config"
    validate_config(config.read_text())
    if b"Linux version " + RELEASE.encode() not in image.read_bytes():
        raise ValueError("rebuilt kernel Image release mismatch")
    closure = verify_modules(modules)
    if output.exists():
        raise FileExistsError(output)
    with tempfile.TemporaryDirectory(
        prefix=".m4rch-package-", dir=output.parent
    ) as temporary:
        staged = Path(temporary) / "candidate"
        staged.mkdir(mode=0o700)
        for name, path in (
            ("Image", image),
            ("modules.tar.gz", modules),
            ("kernel.config", config),
        ):
            shutil.copyfile(path, staged / name)
        spec = importlib.util.spec_from_file_location(
            "m4rch_native", archive_root / "packages/tools/native.py"
        )
        native = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(native)
        for name in native.LINUX_PATCHES:
            native.assemble_patch("linux-m4rch", name, staged / name)
        package = archive_root / "packages/linux-m4rch"
        for name in ("source-stack.md", "t6040-j614s.dts"):
            shutil.copyfile(package / "promoted-source" / name, staged / name)
        for name in ("linux-m4rch.preset", "GPL-2.0"):
            shutil.copyfile(package / name, staged / name)
        for name in ("mkinitcpio-m4rch.conf", "m4rch-j614s.conf", "update-m1n1", "50-m4rch.cfg"):
            shutil.copyfile(package / "promoted-inputs" / name, staged / name)
        dtb = archive_root / preflight.INPUTS["dtb"][0]
        if preflight.sha256(dtb) != preflight.INPUTS["dtb"][1]:
            raise ValueError("retained J614s DTB digest mismatch")
        shutil.copyfile(dtb, staged / "apple-j614s.dtb")
        hashes = {name: preflight.sha256(staged / name) for name in RECIPE_SOURCES}
        recipe = (package / "PKGBUILD").read_text()
        declarations = [
            line for line in recipe.splitlines() if line.startswith("source=(")
        ]
        if len(declarations) != 1 or not declarations[0].endswith(")"):
            raise ValueError("package recipe source declaration changed")
        if tuple(shlex.split(declarations[0][len("source=(") : -1])) != RECIPE_SOURCES:
            raise ValueError("package recipe source order changed")
        recipe += (
            "\nsha256sums=("
            + " ".join(repr(hashes[name]) for name in RECIPE_SOURCES)
            + ")\n"
        )
        (staged / "PKGBUILD").write_text(recipe)
        receipt = {
            "kernel_release": RELEASE,
            "source_hashes": hashes,
            "required_module_closure": closure,
            "native_boot_tested": False,
            "install_ready": False,
        }
        (staged / "candidate-receipt.json").write_text(
            json.dumps(receipt, indent=2) + "\n"
        )
        staged.rename(output)
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("build", type=Path)
    parser.add_argument("m4rch_root", type=Path)
    parser.add_argument("new_output", type=Path)
    args = parser.parse_args()
    print(json.dumps(prepare(args.build, args.m4rch_root, args.new_output), indent=2))


if __name__ == "__main__":
    main()
