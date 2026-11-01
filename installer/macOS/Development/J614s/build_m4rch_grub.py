#!/usr/bin/env python3
"""Prepare a private M4RCH GRUB configuration from the verified source image."""

import argparse
import hashlib
import json
from pathlib import Path
import re

from dissect.extfs import ExtFS

import preflight
import source_image_audit

SOURCE_GRUB_SHA256 = "9ce79210d19bd03a3da631f997cab297cd58c7c4f4fa64383f664bdd2abae667"
OLD = b"linux-aurora"
NEW = b"linux-m4rch"
BOOT_OPTIONS = (
    b"idle=wfi arm64.nowfxt pd_ignore_unused clk_ignore_unused log_buf_len=8M "
    b"mem_sleep_default=s2idle modprobe.blacklist=snd_soc_tas2764,snd_soc_tas2770 "
    b"user4k=on appledrm.t6041_dcpext=1"
)


def render(source, expected_sha256=SOURCE_GRUB_SHA256):
    if hashlib.sha256(source).hexdigest() != expected_sha256:
        raise ValueError("source GRUB configuration digest mismatch")
    if NEW in source or source.count(OLD) != 8:
        raise ValueError("source GRUB kernel references changed")
    if (
        len(re.findall(rb"(?m)^[ \t]*linux[ \t]+/vmlinuz-linux-aurora[ \t]", source))
        != 2
    ):
        raise ValueError("source GRUB has an unexpected kernel entry")
    if (
        len(
            re.findall(
                rb"(?m)^[ \t]*initrd[ \t]+/initramfs-linux-aurora\.img[ \t]*$", source
            )
        )
        != 2
    ):
        raise ValueError("source GRUB has an unexpected initramfs entry")
    renamed = source.replace(OLD, NEW)
    result, changed = re.subn(
        rb"(?m)^([ \t]*linux[ \t]+/vmlinuz-linux-m4rch[ \t]+[^\n]+)$",
        lambda match: match.group(1) + b" " + BOOT_OPTIONS,
        renamed,
    )
    if (
        changed != 2
        or result.replace(b" " + BOOT_OPTIONS, b"").replace(NEW, OLD) != source
    ):
        raise ValueError("unexpected GRUB transformation")
    return result


def build(boot_image, destination):
    if preflight.sha256(boot_image) != source_image_audit.EXPECTED["boot.img"]:
        raise ValueError("source boot image digest mismatch")
    with boot_image.open("rb") as file:
        fs = ExtFS(file)
        source = source_image_audit.read_text(fs, "/grub/grub.cfg").encode("utf-8")
    candidate = render(source)
    with destination.open("xb") as file:
        file.write(candidate)
    destination.chmod(0o600)
    return {
        "source_grub_sha256": SOURCE_GRUB_SHA256,
        "candidate_grub_sha256": hashlib.sha256(candidate).hexdigest(),
        "changes": "M4RCH kernel references and promoted J614s boot options",
        "boot_tested": False,
        "install_ready": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("boot_image", type=Path)
    parser.add_argument("new_output", type=Path)
    args = parser.parse_args()
    print(json.dumps(build(args.boot_image, args.new_output), indent=2))


if __name__ == "__main__":
    main()
