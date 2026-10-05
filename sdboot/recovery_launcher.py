"""Verified Recovery metadata and startup selection, independent of a loader.

The caller holds enrollment's lock and verifies the mounted APFS identity.
Planning/inspection are read-only; ensure saves intent and rollback only.
select_startup restores normal metadata and calls interactive boot selection.
Old armed layouts remain readable for cleanup; this module never creates one.
No command, disk mounting, credentials, reboot or boot-policy tool lives here.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import plistlib
import re
import stat
import sys
import tempfile

LIB = Path(__file__).resolve().parents[1] / "lib"
if str(LIB) not in sys.path:
    sys.path.insert(0, str(LIB))
import card

FORMAT = "arch-m4-recovery-launcher-v1"
STATE = "launcher-state.json"
PATHS = {
    "version": "System/Library/CoreServices/SystemVersion.plist",
    "hidden_version": "System/Library/CoreServices/SystemVersion-disabled.plist",
    "installer": ".IAPhysicalMedia",
    "disabled_installer": "IAPhysicalMedia-disabled.plist",
    "app_info": "Finish Installation.app/Contents/Info.plist",
    "app_launcher": "Finish Installation.app/Contents/MacOS/launch.sh",
}
BINDINGS = {"system_version_sha256": "version", "installer_sha256": "installer",
            "app_info_sha256": "app_info", "app_launcher_sha256": "app_launcher"}


def _path(base, relative):
    base = Path(base)
    if base.is_symlink() or not base.is_dir():
        raise ValueError(f"Invalid launcher metadata directory: {base}")
    return card.checked_path(base, relative)


def _digest(data):
    return hashlib.sha256(data).hexdigest()


def _info(path):
    if path.is_symlink():
        raise ValueError(f"Symlink in launcher metadata: {path}")
    if not path.exists():
        return None
    if not path.is_file():
        raise ValueError(f"Expected a regular launcher metadata file: {path}")
    data = path.read_bytes()
    return {"bytes": len(data), "sha256": _digest(data),
            "mode": stat.S_IMODE(path.stat().st_mode)}


def _spec(data, mode):
    return {"bytes": len(data), "sha256": _digest(data), "mode": mode,
            "hex": data.hex()}


def _file_info(spec):
    return {key: spec[key] for key in ("bytes", "sha256", "mode")}


def _identity(value):
    keys = ("vgid", "store_uuid", "platform_uuid", "source_macos_vgid", "source_macos_store_uuid")
    result = {key: card.canonical_uuid(value[key]) for key in keys}
    if (value.get("storage_mode") != "internal-stub"
            or result["vgid"] == result["source_macos_vgid"]
            or result["store_uuid"] == result["source_macos_store_uuid"]
            or set(value["roles"]) != {"System", "Data", "Preboot", "Recovery"}):
        raise ValueError("Recovery launcher requires the dedicated internal stub")
    result["storage_mode"] = "internal-stub"
    result["roles"] = {role: {"uuid": card.canonical_uuid(entry["uuid"])}
                       for role, entry in value["roles"].items()}
    return result


def _json(value):
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def _sync_dir(path):
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _atomic(path, data, mode=0o600):
    if path.is_symlink():
        raise ValueError(f"Symlink at launcher destination: {path}")
    descriptor, temporary = tempfile.mkstemp(prefix=".launcher-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            os.fchmod(stream.fileno(), mode)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        _sync_dir(path.parent)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _rename(source, destination):
    os.replace(source, destination)
    _sync_dir(destination.parent)


def _snapshot(system):
    return {key: _info(_path(system, relative)) for key, relative in PATHS.items()}


def _layout(files):
    if bool(files["version"]) == bool(files["hidden_version"]):
        raise ValueError("Expected exactly one normal or hidden SystemVersion")
    if files["installer"] and files["disabled_installer"]:
        raise ValueError("Both active and disabled installer markers exist")
    if files["hidden_version"] and files["installer"]:
        return "armed"
    if files["version"] and not files["installer"]:
        return "normal"
    return "intermediate"


def _managed_for(record, key):
    if key == "hidden_version":
        key = "version"
    if key == "disabled_installer":
        key = "installer"
    return record["managed"][key]


def _validate_record(system, out, identity, record):
    if (record.get("format") != FORMAT or record.get("identity") != _identity(identity)
            or not re.fullmatch(r"recovery-launcher-backup-[A-Za-z0-9_-]+", record.get("backup", ""))
            or set(record.get("originals", {})) != set(PATHS)
            or set(record.get("managed", {})) != set(BINDINGS.values())):
        raise ValueError("Invalid or foreign Recovery launcher intent")
    for binding, key in BINDINGS.items():
        spec = record["managed"][key]
        try:
            data = bytes.fromhex(spec["hex"])
        except (ValueError, KeyError, TypeError):
            raise ValueError("Invalid Recovery launcher payload") from None
        if (spec != _spec(data, 0o755 if key == "app_launcher" else 0o644)
                or record.get(binding) != spec["sha256"]):
            raise ValueError("Recovery launcher payload hash changed")
    resources = _path(system, card.RESOURCES)
    backup = _path(resources, record["backup"])
    if not backup.is_dir():
        raise ValueError("Missing Recovery launcher rollback directory")
    saved_plan = {key: value for key, value in record.items() if key != "backup"}
    intent = _path(backup, "intent.json")
    if _info(intent) is None or intent.read_bytes() != _json(saved_plan):
        raise ValueError("Recovery launcher rollback intent changed")
    expected_names = {"intent.json"}
    for key, original in record["originals"].items():
        if original is not None:
            expected_names.add(key)
        if _info(_path(backup, key)) != original:
            raise ValueError(f"Recovery launcher rollback changed: {key}")
    if {path.name for path in backup.iterdir()} != expected_names:
        raise ValueError("Unexpected file in Recovery launcher rollback")
    files = _snapshot(system)
    for key, actual in files.items():
        allowed = (None, record["originals"][key], _file_info(_managed_for(record, key)))
        if actual not in allowed:
            raise ValueError(f"Unknown modification to Recovery launcher metadata: {key}")
    layout = _layout(files)
    # App files cannot disappear once they existed. Only the two rename pairs
    # can move to an absent destination as part of an interrupted transaction.
    for key in ("app_info", "app_launcher"):
        if files[key] is None and record["originals"][key] is not None:
            raise ValueError(f"Missing Recovery launcher app metadata: {key}")
    if files["installer"] is None and files["disabled_installer"] is None:
        if record["originals"]["disabled_installer"] is not None:
            raise ValueError("Missing Recovery installer marker")
    return files, layout


def inspect(system, out, identity):
    """Verify saved rollback and all active metadata without writing anything."""
    state = _path(out, STATE)
    if _info(state) is None:
        return {"managed": False, "layout": _layout(_snapshot(system)), "record": None}
    record = json.loads(state.read_text())
    files, layout = _validate_record(system, out, identity, record)
    # This describes files only, never the firmware's selected startup target.
    ready = (layout == "normal" and all(
        files[key] == _file_info(_managed_for(record, key))
        for key in ("version", "disabled_installer", "app_info", "app_launcher")))
    return {"managed": True, "layout": layout, "record": record, "ready": ready}


def plan(system, out, identity):
    """Return a serializable, hash-bound plan; never create or change a file."""
    current = inspect(system, out, identity)
    if current["managed"]:
        return {key: value for key, value in current["record"].items() if key != "backup"}
    originals = _snapshot(system)
    if current["layout"] != "normal" or originals["hidden_version"] or originals["installer"]:
        raise ValueError("An unmanaged Recovery launcher must start with normal boot metadata")
    version = _path(system, PATHS["version"]).read_bytes()
    fields = plistlib.loads(version)
    for key in ("ProductVersion", "ProductBuildVersion"):
        if not isinstance(fields.get(key), str) or not fields[key].strip():
            raise ValueError(f"SystemVersion is missing {key}")
    generated = card.launcher_files()
    managed = {
        "version": _spec(version, 0o644),
        "installer": _spec(plistlib.dumps({"AppName": card.APP,
                                           "ProductVersion": fields["ProductVersion"],
                                           "ProductBuildVersion": fields["ProductBuildVersion"]}), 0o644),
        "app_info": _spec(generated[Path(PATHS["app_info"])], 0o644),
        "app_launcher": _spec(generated[Path(PATHS["app_launcher"])], 0o755),
    }
    # Renames preserve modes. Avoid silently changing system-version metadata.
    if originals["version"]["mode"] != 0o644:
        raise ValueError("Unexpected SystemVersion permissions")
    return {"format": FORMAT, "identity": _identity(identity), "originals": originals,
            "managed": managed, **{binding: managed[key]["sha256"] for binding, key in BINDINGS.items()}}


def ensure(system, out, identity, proposed):
    """Persist verified original files and intent, without arming the launcher."""
    if plan(system, out, identity) != proposed:
        raise ValueError("Recovery launcher plan changed before staging")
    existing = inspect(system, out, identity)
    if existing["managed"]:
        return existing["record"]
    resources = _path(system, card.RESOURCES)
    backup = Path(tempfile.mkdtemp(prefix="recovery-launcher-backup-", dir=resources))
    for key, original in proposed["originals"].items():
        if original is not None:
            source = _path(system, PATHS[key])
            _atomic(backup / key, source.read_bytes(), original["mode"])
    _atomic(backup / "intent.json", _json(proposed))
    record = {**proposed, "backup": backup.name}
    _validate_record(system, out, identity, record)
    if _snapshot(system) != proposed["originals"]:
        raise ValueError("Recovery launcher metadata changed while saving rollback")
    _atomic(_path(out, STATE), _json(record))
    return record


def _current(system, out, identity, record):
    current = inspect(system, out, identity)
    if not current["managed"] or current["record"] != record:
        raise ValueError("Recovery launcher intent changed")
    return current


def complete(system, out, identity, record):
    """Restore normal boot metadata after interrupted Recovery cleanup; no bless."""
    _current(system, out, identity, record)
    if _path(system, PATHS["installer"]).exists():
        _rename(_path(system, PATHS["installer"]), _path(system, PATHS["disabled_installer"]))
    if _path(system, PATHS["hidden_version"]).exists():
        _rename(_path(system, PATHS["hidden_version"]), _path(system, PATHS["version"]))
    _current(system, out, identity, record)
    return record


def select_startup(system, out, identity, record, select_boot):
    """Restore normal Arch metadata, then select it as the startup target.

    A failed selection leaves the normal layout. Interrupted renames are
    detected from their hashes and can be retried. Selection is repeated for
    pending updates: the user may have changed Startup Disk meanwhile.
    Recovery is entered physically through Options, not an installer redirect.
    The caller must skip selection when the loader receipt is already current.
    """
    _current(system, out, identity, record)
    complete(system, out, identity, record)
    for key in ("app_info", "app_launcher", "disabled_installer"):
        path = _path(system, PATHS[key])
        # The application's directories already belong to the original stub.
        path.parent.mkdir(parents=True, exist_ok=True)
        spec = _managed_for(record, key)
        if _info(path) != _file_info(spec):
            _atomic(path, bytes.fromhex(spec["hex"]), spec["mode"])
    _current(system, out, identity, record)
    select_boot()
    # Recheck after authentication. Never hide the version or activate a marker:
    # those files did not redirect this Mac's enrolled custom loader to Recovery.
    if not _current(system, out, identity, record)["ready"]:
        raise ValueError("Normal startup metadata failed final verification")
    return record
