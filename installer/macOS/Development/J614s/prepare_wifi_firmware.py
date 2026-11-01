#!/usr/bin/env python3
"""Prepare private J614s Wi-Fi firmware from this Mac's macOS installation."""

import argparse
import hashlib
from pathlib import Path
import shutil
import sys
import tempfile

INSTALLER = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(INSTALLER))
from asahi_firmware.wifi import WiFiFWCollection  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path, help="new private output directory")
    parser.add_argument(
        "--source", type=Path,
        default=Path("/usr/share/firmware/wifi/C-4388__s-C2"),
        help="BCM4388 C2 firmware directory from this Mac's macOS installation",
    )
    args = parser.parse_args()
    source = args.source.resolve(strict=True)
    if args.output.exists():
        parser.error("output already exists")
    with tempfile.TemporaryDirectory(prefix="m4rch-wifi-") as temp:
        # The upstream converter excludes this directory name because a 14.6.1
        # IPSW contained an incomplete version. This Mac's 27.0 files include
        # the Mriya binary and are used only for this explicit local repair.
        inputs = Path(temp) / "C-4388" / "s-C2"
        inputs.mkdir(parents=True)
        for item in source.iterdir():
            if not item.name.startswith(("mriya", "P-mriya")):
                continue
            if item.suffix not in {".trx", ".txt", ".clmb", ".txcb", ".sig"}:
                continue
            target = item.resolve(strict=True)
            if target.parent != source or not target.is_file():
                raise ValueError(f"unsafe firmware input: {item.name}")
            shutil.copyfile(target, inputs / item.name)
        files = dict(WiFiFWCollection(temp).files())
    prefix = "brcm/brcmfmac4388c2-pcie.apple,mriya"
    required = {prefix + ext for ext in (".bin", ".clm_blob", ".txcap_blob", ".sig")}
    if not required.issubset(files) or not any(
        name.startswith(prefix + "-") and name.endswith(".txt") for name in files
    ):
        raise ValueError("Mriya firmware is incomplete; no output was written")
    args.output.mkdir(mode=0o700, parents=False)
    (args.output / "brcm").mkdir(mode=0o700)
    sums = []
    for name, item in sorted(files.items()):
        if not name.startswith(prefix):
            raise ValueError(f"unexpected firmware name: {name}")
        path = args.output / name
        path.write_bytes(item.data)
        path.chmod(0o600)
        sums.append(f"{hashlib.sha256(item.data).hexdigest()}  {name}\n")
    (args.output / "SHA256SUMS").write_text("".join(sums))
    shutil.copyfile(Path(__file__).with_name("install-wifi.sh"), args.output / "install-wifi.sh")
    print(f"Prepared {len(files)} private firmware files in {args.output}")


if __name__ == "__main__":
    main()
