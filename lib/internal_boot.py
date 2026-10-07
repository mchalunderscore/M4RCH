"""Provision or verify the dedicated internal Apple boot-stub identity."""
from __future__ import annotations

import json

import card
import internal_disk

STATE = "out/internal-boot-state.json"
SD_KEYS = ("root_partition_uuid", "root_volume_uuid", "root_image", "root_uuid")


def state_path(project):
    card.checked_path(project, STATE + ".tmp")
    return card.checked_path(project, STATE)


def read_state(project):
    state = json.loads(state_path(project).read_text())
    if state.get("format") != "arch-m4-internal-boot-v1":
        raise ValueError("Unrecognized internal boot state; retain it for inspection")
    if state.get("platform_uuid") != card.platform_uuid():
        raise ValueError("Internal boot state belongs to another Mac")
    return state


def resolve_partition(dutil, state, *, project):
    # Revalidates both the new partition and the complete retained macOS layout.
    extension = card.checked_path(project, "out/internal-layout-extension.json")
    if extension.exists():
        import internal_layout
        return internal_layout.resolve(dutil, state["partition"], extension)
    return internal_disk.validate_created(dutil, state["partition"])


def read_roles(dutil, container, store_uuid, sd):
    roles = {}
    for volume in container["Volumes"]:
        role = volume.get("Roles", [])
        if len(role) != 1 or role[0] in roles:
            raise ValueError("Unexpected internal-stub APFS roles; retain state for inspection")
        roles[role[0]] = {"uuid": card.canonical_uuid(volume["APFSVolumeUUID"]),
                          "device": volume["DeviceIdentifier"]}
    if set(roles) != {"System", "Data", "Preboot", "Recovery"}:
        raise ValueError("Internal stub role setup is incomplete; no additional partition will be created")
    groups = dutil.get("apfs", "listVolumeGroups", container["ContainerReference"], "-plist")["Containers"][0]["VolumeGroups"]
    if len(groups) != 1 or {v["Role"]: v["DeviceIdentifier"] for v in groups[0]["Volumes"]} != {
            role: roles[role]["device"] for role in ("System", "Data")}:
        raise ValueError("Internal stub System/Data group is ambiguous")
    all_volumes = [volume for item in dutil.apfs()["Containers"] for volume in item["Volumes"]]
    for entry in roles.values():
        if sum(v.get("APFSVolumeUUID", "").upper() == entry["uuid"] for v in all_volumes) != 1:
            raise ValueError("Duplicate internal boot UUID; detach copied images")
    return {"schema": 1, "storage_mode": "internal-stub", "vgid": card.canonical_uuid(groups[0]["APFSVolumeGroupUUID"]),
            "store_uuid": store_uuid, "roles": roles, "device": sd["device"], "root_device": sd["root_device"],
            **{key: sd[key] for key in SD_KEYS}}


def container_for(dutil, receipt):
    matches = [c for c in dutil.apfs()["Containers"] if c.get("APFSContainerUUID", "").upper() == receipt["container_uuid"].upper()]
    if len(matches) != 1:
        raise ValueError("Internal boot container is absent or ambiguous")
    return matches[0]


# First-time provisioning is independent of the SD card and Linux filesystem.
LABEL = "M4RCH"
BOOKKEEPING = {".fseventsd", ".Spotlight-V100", ".Trashes"}


def write_state(project, state):
    import os
    from common import write_json
    path = state_path(project)
    write_json(path, state)
    with path.open("rb") as stream:
        os.fsync(stream.fileno())
    os.sync()


def _volumes(container):
    """Stable identities, including exact names/roles, for interrupted writes."""
    return sorted(({"uuid": card.canonical_uuid(v["APFSVolumeUUID"]),
                    "roles": v["Roles"], "name": v["Name"]}
                   for v in container["Volumes"]), key=lambda v: v["uuid"])


def _step_done(before, after, step, initial_uuid):
    expected = [dict(v) for v in before]
    initial = next(v for v in expected if v["uuid"] == initial_uuid)
    if step == "data-role":
        initial["roles"] = ["Data"]
    elif step == "data-name":
        initial["name"] = LABEL + " - Data"
    else:
        role = step
        added = [v for v in after if v["uuid"] not in {x["uuid"] for x in before}]
        if len(added) != 1:
            return False
        if added[0]["roles"] != [role] or added[0]["name"] != LABEL + ("" if role == "System" else " " + role):
            return False
        expected.append(added[0])
    return sorted(expected, key=lambda v: v["uuid"]) == after


def _check_protection(container):
    # Internal APFS hardware encryption is valid; password protection and
    # cryptographic migration are not valid first-install destinations.
    for volume in container["Volumes"]:
        if (volume.get("Locked") is not False or volume.get("FileVault") is not False
                or type(volume.get("Encryption")) is not bool
                or volume.get("CryptoMigrationOn") is not False):
            raise ValueError("Boot volume protection state changed")


def _create_roles(project, dutil, state):
    """Persist each role-write intent; recognize only its exact before/after."""
    from copy import deepcopy
    receipt = state["partition"]
    initial_uuid = receipt["initial_volume_uuid"]
    steps = ("data-role", "data-name", "System", "Preboot", "Recovery")
    while state["role_step"] < len(steps):
        resolve_partition(dutil, state, project=project)
        container = container_for(dutil, receipt)
        current = _volumes(container)
        step = steps[state["role_step"]]
        pending = state.get("pending")
        if pending is not None:
            if pending != {"step": step, "before": state["volumes"]}:
                raise ValueError("Internal volume-write intent changed; retain state for inspection")
            if _step_done(state["volumes"], current, step, initial_uuid):
                state.update(volumes=current, role_step=state["role_step"] + 1)
                state.pop("pending")
                write_state(project, state)
                continue
        if current != state["volumes"]:
            raise ValueError("Internal boot volumes differ from the recorded role write")
        initial = next((v for v in container["Volumes"]
                        if card.canonical_uuid(v["APFSVolumeUUID"]) == initial_uuid), None)
        if initial is None:
            raise ValueError("Created Data volume UUID is missing")
        # Unknown protection states and password-encrypted destinations are
        # unsafe; hardware-transparent APFS Encryption=True is normal here.
        _check_protection(container)
        if read_state(project) != state:
            raise ValueError("Internal setup state changed before a role write")
        state["pending"] = {"step": step, "before": deepcopy(current)}
        write_state(project, state)
        if step == "data-role":
            dutil.run("apfs", "changeVolumeRole", initial["DeviceIdentifier"], "D")
        elif step == "data-name":
            dutil.run("rename", initial["DeviceIdentifier"], LABEL + " - Data")
        else:
            args = ["apfs", "addVolume", container["ContainerReference"], "APFS",
                    LABEL + ("" if step == "System" else " " + step), "-role",
                    {"System": "S", "Preboot": "B", "Recovery": "R"}[step]]
            if step == "System":
                args += ["-groupWith", initial["DeviceIdentifier"]]
            dutil.run(*args)
        # Re-enter at the recorded intent: errors after command execution must
        # never cause a second addVolume or another internal partition.
    state["phase"] = "payload"
    write_state(project, state)


def _copy_payload(source, destination):
    """Resume verified copies without replacing unknown files or links."""
    import os
    from pathlib import Path
    import shutil
    import tempfile
    from common import sha256
    source, destination = Path(source), Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    for path in sorted(source.rglob("*")):
        name = path.relative_to(source)
        target = card.checked_path(destination, name, leaf_symlink=path.is_symlink())
        if path.is_symlink():
            if target.is_symlink():
                if os.readlink(target) != os.readlink(path):
                    raise ValueError(f"Changed stub link: {name}")
            elif target.exists():
                raise ValueError(f"Unexpected stub destination: {name}")
            else:
                target.symlink_to(os.readlink(path))
        elif path.is_dir():
            if target.exists() and not target.is_dir():
                raise ValueError(f"Unexpected stub directory: {name}")
            target.mkdir(exist_ok=True)
        else:
            if target.exists():
                if not target.is_file() or target.is_symlink() or sha256(target) != sha256(path):
                    raise ValueError(f"Changed stub destination: {name}")
            else:
                descriptor, temporary = tempfile.mkstemp(prefix=".stub-copy-", dir=target.parent)
                try:
                    with os.fdopen(descriptor, "wb") as stream, path.open("rb") as original:
                        shutil.copyfileobj(original, stream, 1024 * 1024)
                        os.fchmod(stream.fileno(), path.stat().st_mode & 0o777)
                        stream.flush()
                        os.fsync(stream.fileno())
                    os.replace(temporary, target)
                finally:
                    if os.path.exists(temporary):
                        os.unlink(temporary)


def _check_payload_destination(source, destination, *, extras=(), root=False):
    """Reject unrelated files on the newly created volume during copy resume."""
    from pathlib import Path
    source, destination = Path(source), Path(destination)
    if destination.is_symlink():
        raise ValueError("Symlink at first-install payload root")
    if not destination.exists():
        return
    expected = {p.relative_to(source).as_posix() for p in source.rglob("*")}
    allowed = set(extras)
    for name in tuple(allowed):
        allowed.update(p.as_posix() for p in Path(name).parents if str(p) != ".")
    for path in destination.rglob("*"):
        name = path.relative_to(destination).as_posix()
        if root and name.split("/", 1)[0] in BOOKKEEPING:
            first = destination / name.split("/", 1)[0]
            if first.is_symlink() or not first.is_dir():
                raise ValueError("Unexpected bookkeeping entry on first-install volume")
            continue
        if name in expected or name in allowed:
            continue
        raise ValueError(f"Unrelated file on the fresh boot volume: {name}")


def _write_once(path, data, mode=0o600):
    """Only write an absent or identical first-install file, atomically."""
    from pathlib import Path
    import os
    import tempfile
    path = Path(path)
    card.checked_path(path.parent, path.name)
    if path.exists():
        if not path.is_file() or path.is_symlink() or path.read_bytes() != data:
            raise ValueError(f"Changed first-install file: {path}")
        if path.stat().st_mode & 0o777 != mode:
            path.chmod(mode)
    else:
        descriptor, temporary = tempfile.mkstemp(prefix=".stub-copy-", dir=path.parent)
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(data)
                os.fchmod(stream.fileno(), mode)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
            os.sync()
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)


def ensure(project, source, expected, *, dutil=None):
    """Create/resume one internal Apple stub; never touch removable media.

    Current ready installations return before requiring a cached Apple payload.
    The caller serializes this workflow with loader enrollment's process lock.
    """
    import hashlib
    import os
    from pathlib import Path
    import shlex
    from card_disk import DiskUtil
    from common import sha256
    import stub_payload
    card.require_macos()
    if os.geteuid() != 0:
        raise PermissionError("First-time internal boot setup requires sudo")
    project, source = Path(project), Path(source)
    path = state_path(project)
    state = read_state(project) if path.exists() else None
    if state is not None and state.get("phase") == "ready":
        return state
    # All authenticated software and owner inputs precede the partition prompt.
    stub_payload.prepare(project / "cache", project / "out/stub")
    stub = stub_payload.verify(project / "out/stub")
    manifest_hash = sha256(project / "out/stub/manifest.json")
    dutil = dutil or DiskUtil()
    owner_data = card.source_owner_metadata(dutil)
    inputs = {"loader": expected, "stub_manifest_sha256": manifest_hash,
              "owner_sha256": hashlib.sha256(owner_data).hexdigest()}
    if state is None:
        plan = internal_disk.inspect(dutil)
        main = plan["main"]
        card.confirm("CREATE INTERNAL " + main["store_uuid"],
                     f"Shrink macOS APFS from {main['current_bytes']} to {main['target_bytes']} bytes.\n"
                     "Create a separate 4 GiB APFS container named M4RCH on the internal SSD.\n"
                     "This changes the internal partition map. Keep a current backup and connect power.\n"
                     "No SD card is read, written or reflashed.\nCommand: " +
                     shlex.join(["/usr/sbin/diskutil", *plan["resize_argv"]]))
        if (sha256(source) != expected["sha256"] or source.stat().st_size != expected["bytes"]
                or sha256(project / "out/stub/manifest.json") != manifest_hash
                or card.source_owner_metadata(dutil) != owner_data):
            raise ValueError("First-install inputs changed during confirmation")
        stub_payload.verify(project / "out/stub")
        state = {"format": "arch-m4-internal-boot-v1", "platform_uuid": card.platform_uuid(),
                 "phase": "partition-started", "bootstrap_inputs": inputs,
                 "reviewed_plan": {"partition": plan}, "initial_enrollment": True}
        write_state(project, state)
        state["partition"] = internal_disk.create(dutil, plan)
        state["phase"] = "partition-created"
        write_state(project, state)
    if state.get("bootstrap_inputs") != inputs:
        raise ValueError("Interrupted first-install software/owner inputs changed; retain state for inspection")
    if state["phase"] == "partition-started":
        # A successful resize followed by an interrupted host receipt is adopted
        # only if the exact planned physical range and still-blank volume match.
        # If no change happened, require a fresh typed confirmation, never retry
        # a partial resize or allocate over an existing stub.
        plan = state["reviewed_plan"]["partition"]
        try:
            receipt = internal_disk.recover_created(dutil, plan)
        except ValueError:
            fresh = internal_disk.inspect(dutil)
            if internal_disk._stable_plan(fresh) != internal_disk._stable_plan(plan):
                raise ValueError("Interrupted resize is not the unchanged layout or exact completed plan; retain state") from None
            card.confirm("CREATE INTERNAL " + plan["main"]["store_uuid"],
                         "The recorded resize did not change the disk. Confirm the same 4 GiB operation again.\n"
                         "Command: " + shlex.join(["/usr/sbin/diskutil", *plan["resize_argv"]]))
            receipt = internal_disk.create(dutil, plan)
        state.update(partition=receipt, phase="partition-created")
        write_state(project, state)
    if state["phase"] == "partition-created":
        receipt = internal_disk.recover_created(dutil, state["partition"]["plan"])
        if any(receipt[k] != state["partition"][k] for k in ("container_uuid", "store_uuid", "initial_volume_uuid", "bytes")):
            raise ValueError("Created container differs from its durable receipt")
        state.update(phase="roles", role_step=0, volumes=_volumes(container_for(dutil, receipt)))
        write_state(project, state)
    if state["phase"] == "roles":
        _create_roles(project, dutil, state)
    if state["phase"] != "payload":
        raise ValueError("Unknown interrupted first-install phase; retain state for inspection")
    resolve_partition(dutil, state, project=project)
    container = container_for(dutil, state["partition"])
    if _volumes(container) != state["volumes"]:
        raise ValueError("Boot volumes changed before payload installation")
    _check_protection(container)
    unused_sd = {"device": "", "root_device": "", **{k: "" for k in SD_KEYS}}
    identity = read_roles(dutil, container, state["partition"]["store_uuid"], unused_sd)
    main = state["partition"]["plan"]["main"]
    identity.update(platform_uuid=state["platform_uuid"], source_macos_vgid=main["vgid"],
                    source_macos_store_uuid=main["store_uuid"], status="awaiting-first-enrollment",
                    apple_build=stub["apple_build"], boot_sha256=expected["sha256"], boot_bytes=expected["bytes"])
    mounts = {role: card.mounted_writable(dutil, entry["device"], entry["uuid"])
              for role, entry in identity["roles"].items()}
    for role, mount in mounts.items():
        destination = mount / identity["vgid"] if role in ("Preboot", "Recovery") else mount
        extras = ((str(card.RESOURCES / name) for name in ("boot.bin", "enroll.sh", "ASAHI-LICENSE", "card.json"))
                  if role == "System" else ("var/db/AdminUserRecoveryInfo.plist",) if role == "Preboot" else ())
        extras = tuple(extras) + (("restore",) if role == "System" else ())
        _check_payload_destination(project / "out/stub" / role, destination,
                                   extras=extras, root=role in ("System", "Data"))
        if role in ("Preboot", "Recovery"):
            for entry in mount.iterdir():
                if entry.name != identity["vgid"] and entry.name not in BOOKKEEPING:
                    raise ValueError("Unrelated volume-group directory on first-install boot volume")
    # Check every target tree before changing ownership or copying any role.
    for role, mount in mounts.items():
        destination = mount / identity["vgid"] if role in ("Preboot", "Recovery") else mount
        dutil.run("enableOwnership", identity["roles"][role]["device"])
        _copy_payload(project / "out/stub" / role, destination)
    resources = card.checked_path(mounts["System"], card.RESOURCES)
    resources.mkdir(parents=True, exist_ok=True)
    _write_once(resources / "boot.bin", source.read_bytes(), 0o644)
    if sha256(resources / "boot.bin") != expected["sha256"]:
        raise ValueError("First-install loader failed readback")
    _write_once(resources / "enroll.sh", b'#!/bin/sh\nprintf "%s\\n" "Return to macOS and rerun sudo make boot to finish enrollment preparation."\n', 0o755)
    _write_once(resources / "ASAHI-LICENSE", (project / "third_party/ASAHI-LICENSE").read_bytes(), 0o644)
    # The pinned payload's original Asahi app files stay intact until the new
    # hash-bound launcher plan has saved them. No owner database is logged.
    owner = card.checked_path(mounts["Preboot"], Path(identity["vgid"]) / "var/db/AdminUserRecoveryInfo.plist")
    owner.parent.mkdir(parents=True, exist_ok=True)
    _write_once(owner, owner_data)
    from common import run
    run(["/usr/bin/chflags", "schg", owner])
    restore = mounts["System"] / "restore"
    expected_link = str(mounts["Preboot"] / identity["vgid"] / "restore")
    if restore.is_symlink():
        if os.readlink(restore) != expected_link:
            raise ValueError("Unexpected first-install restore link")
    elif restore.exists():
        raise ValueError("Unexpected first-install restore destination")
    else:
        restore.symlink_to(expected_link)
    # Initial startup selection needs the signed Apple metadata and installer
    # marker. Its first-enrollment workflow disables the marker after bless.
    _write_once(resources / "card.json", (json.dumps(identity, sort_keys=True, indent=2) + "\n").encode())
    if read_state(project) != state:
        raise ValueError("Internal first-install state changed during payload copy")
    state.update(phase="ready", identity=identity)
    write_state(project, state)
    return state
