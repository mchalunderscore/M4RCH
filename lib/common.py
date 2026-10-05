"""Small, shared build primitives; no third-party Python dependencies."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import urllib.request


def run(args, **kwargs):
    print("+ " + " ".join(str(x) for x in args), flush=True)
    return subprocess.run([str(x) for x in args], check=True, **kwargs)


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def write_json(path, value):
    path = Path(path)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    tmp.replace(path)


def download(url, dest, digest):
    dest = Path(dest)
    if dest.exists():
        if sha256(dest) != digest:
            raise ValueError(f"Cached input has wrong SHA-256: {dest}; remove it and retry")
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_name(dest.name + ".part")
    if not url.startswith("https://"):
        raise ValueError("Downloads must use HTTPS")
    print(f"Downloading {url}", flush=True)
    run(["curl", "--fail", "--location", "--retry", "3", "--proto", "=https", "--proto-redir", "=https", "--output", part, url])
    if sha256(part) != digest:
        raise ValueError(f"SHA-256 mismatch for {url}; partial file preserved at {part}")
    part.replace(dest)
    return dest


def manifest_files(directory, names):
    return {name: {"sha256": sha256(Path(directory) / name),
                   "bytes": (Path(directory) / name).stat().st_size} for name in names}


def verify_manifest(path):
    path = Path(path)
    manifest = json.loads(path.read_text())
    for name, info in manifest["files"].items():
        file = path.parent / name
        if Path(name).is_absolute() or ".." in Path(name).parts:
            raise ValueError(f"Invalid manifest path: {name}")
        if not file.is_file() or file.stat().st_size != info["bytes"] or sha256(file) != info["sha256"]:
            raise ValueError(f"Artifact failed verification: {file}")
    return manifest
