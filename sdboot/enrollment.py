"""Stage the internal loader and prepare its paired-Recovery enrollment.

The public prepare workflow selects the startup target and leaves its normal
boot metadata intact. Only Recovery enrolls the custom boot object. No partition
creation is confined to first-time setup; no SD-card access is performed here.
"""
from __future__ import annotations

import hashlib
from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import re
import sys
import tempfile

LIB = Path(__file__).resolve().parents[1] / "lib"
if str(LIB) not in sys.path:
    sys.path.insert(0, str(LIB))
import card
import internal_boot
from card_disk import DiskUtil
from common import run, sha256, verify_manifest

FORMAT = "arch-m4-sd-loader-enrollment-v1"
STATE = "enrollment-state.json"
KEYS = ("vgid", "store_uuid", "platform_uuid", "source_macos_vgid", "source_macos_store_uuid")
OLD_FILES = ("boot.bin", "enroll.sh", "enrolled.txt", "card.json")


def _launcher_module():
    if __package__:
        from . import recovery_launcher
    else:
        import recovery_launcher
    return recovery_launcher


def _info(path):
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"Expected a regular non-symlink file: {path}")
    return {"bytes": path.stat().st_size, "sha256": sha256(path)}


def _identity(value):
    result = {key: card.canonical_uuid(value[key]) for key in KEYS}
    if (value.get("storage_mode") != "internal-stub"
            or result["vgid"] == result["source_macos_vgid"]
            or result["store_uuid"] == result["source_macos_store_uuid"]):
        raise ValueError("Loader enrollment requires a separate internal Arch stub")
    if set(value["roles"]) != {"System", "Data", "Preboot", "Recovery"}:
        raise ValueError("Internal stub needs exactly four APFS roles")
    result.update(storage_mode="internal-stub", roles={
        role: {"uuid": card.canonical_uuid(entry["uuid"])}
        for role, entry in value["roles"].items()})
    return result


def _resolve(project, dutil):
    old = internal_boot.read_state(project)
    if old.get("phase") != "ready":
        raise ValueError("Existing internal stub setup is incomplete; no new partition will be created")
    internal_boot.resolve_partition(dutil, old)
    saved = old["identity"]
    identity = _identity(saved)
    if identity["platform_uuid"] != old["platform_uuid"]:
        raise ValueError("Internal stub platform identity disagrees with its state")
    main = old["partition"]["plan"]["main"]
    if (identity["source_macos_vgid"] != main["vgid"]
            or identity["source_macos_store_uuid"] != main["store_uuid"]):
        raise ValueError("Internal stub original macOS identity changed")
    # read_roles only uses these values as opaque dictionary fields. Supplying
    # placeholders never inventories, mounts or binds this loader to an SD.
    unused_sd = {"device": "", "root_device": "", **{key: "" for key in internal_boot.SD_KEYS}}
    roles = internal_boot.read_roles(dutil, internal_boot.container_for(dutil, old["partition"]),
                                    old["partition"]["store_uuid"], unused_sd)
    if any(roles[key] != identity[key] for key in ("vgid", "store_uuid")) or any(
            roles["roles"][role]["uuid"] != entry["uuid"] for role, entry in identity["roles"].items()):
        raise ValueError("Actual internal stub APFS UUIDs differ from the existing state")
    return old, identity, roles["roles"]


def render(project, identity, boot, *, launcher=None, initial=False, owner_sha256=None):
    """Render an internal-only Recovery script with shell-safe validated data."""
    checked = _identity(identity)
    info = _info(Path(boot))
    previous = identity.get("previous_boot_sha256", info["sha256"])
    if not re.fullmatch(r"[a-f0-9]{64}", previous):
        raise ValueError("Invalid previous boot SHA-256")
    values = {"VGID": checked["vgid"], "STORE_UUID": checked["store_uuid"],
              "PLATFORM_UUID": checked["platform_uuid"],
              "SOURCE_MACOS_VGID": checked["source_macos_vgid"],
              "SOURCE_MACOS_STORE_UUID": checked["source_macos_store_uuid"],
              "BOOT_SHA256": info["sha256"], "PREVIOUS_BOOT_SHA256": previous,
              "BOOT_BYTES": str(info["bytes"]), **{
                  role.upper() + "_UUID": entry["uuid"] for role, entry in checked["roles"].items()}}
    # Retain the legacy flag name: it enables bound metadata validation in the
    # Recovery script, not an automatic firmware redirect or host-side arming.
    values["AUTO_LAUNCH"] = "1" if launcher is not None else "0"
    values["INITIAL_ENROLLMENT"] = "1" if initial else "0"
    if owner_sha256 is None:
        if initial:
            raise ValueError("First enrollment requires the verified copied owner digest")
        owner_sha256 = "0" * 64
    if not isinstance(owner_sha256, str) or not re.fullmatch(r"[a-f0-9]{64}", owner_sha256):
        raise ValueError("Invalid first-enrollment owner digest")
    values["OWNER_SHA256"] = owner_sha256
    for name in ("system_version", "installer", "app_info", "app_launcher"):
        digest = launcher[name + "_sha256"] if launcher is not None else "0" * 64
        if not isinstance(digest, str) or not re.fullmatch(r"[a-f0-9]{64}", digest):
            raise ValueError("Invalid Recovery launcher metadata digest")
        values[name.upper() + "_SHA256"] = digest
    text = (Path(project) / "sdboot/recovery-enroll.sh").read_text()
    for key, value in values.items():
        text = text.replace("##" + key + "##", value)
    if re.search(r"##[A-Z_]+##", text):
        raise ValueError("Unresolved Recovery template marker")
    return text


def _record(out, identity, old_hash):
    path = card.checked_path(out, STATE)
    if not path.exists():
        return None
    value = json.loads(path.read_text())
    if (value.get("format") != FORMAT or value.get("identity") != identity
            or value.get("old_state_sha256") != old_hash
            or value.get("phase") not in ("prepared", "staged")):
        raise ValueError("Loader enrollment state identity changed; retain it for inspection")
    return value


def _receipt(resources, identity):
    path = card.checked_path(resources, "enrolled.txt")
    try:
        _info(path)
        lines = path.read_text().splitlines()
    except PermissionError:
        raise ValueError("Reading this root-owned enrollment receipt needs sudo; status remains read-only") from None
    if (len(lines) != 2 or lines[0] != identity["vgid"]
            or not re.fullmatch(r"[a-f0-9]{64}", lines[1])):
        raise ValueError("Missing or invalid existing enrollment receipt")
    return lines[1]


def _check_original_metadata(resources, old):
    data = json.loads(card.checked_path(resources, "card.json").read_text())
    def stable(value):
        return {**{key: item for key, item in value.items()
                   if key not in ("device", "root_device", "roles")},
                "roles": {role: entry["uuid"] for role, entry in value["roles"].items()}}
    if stable(data) != stable(old["identity"]):
        raise ValueError("Existing internal stub metadata and preserved host state disagree")


def _atomic(path, data, mode=0o600):
    path = Path(path)
    card.checked_path(path.parent, path.name)
    descriptor, filename = tempfile.mkstemp(prefix=".sd-loader-", dir=path.parent)
    temporary = Path(filename)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            os.fchmod(stream.fileno(), mode)
            stream.flush()
            os.fsync(stream.fileno())
        if temporary.read_bytes() != data:
            raise ValueError("Staged loader file failed readback")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
    os.sync()


def _save(out, value):
    _atomic(card.checked_path(out, STATE), (json.dumps(value, sort_keys=True, indent=2) + "\n").encode())


def _previous_receipt(record):
    # Older records used the same generation for installed bytes and receipt.
    # Superseding a pending update separates those two identities.
    value = record.get("previous_receipt_sha256", record["previous"]["sha256"])
    if not isinstance(value, str) or not re.fullmatch(r"[a-f0-9]{64}", value):
        raise ValueError("Invalid previous enrollment receipt in loader state")
    return value


def _check_backups(resources, record, _seen=None):
    backup = card.checked_path(resources, record["backup"])
    seen = set() if _seen is None else set(_seen)
    if backup in seen or len(seen) >= 64:
        raise ValueError("Invalid loader rollback chain")
    seen.add(backup)
    if not backup.is_dir():
        raise ValueError("Loader rollback directory is missing")
    if not set((*OLD_FILES, "internal-boot-state.json")).issubset(record["backups"]):
        raise ValueError("Loader rollback set is incomplete")
    for name, info in record["backups"].items():
        if _info(card.checked_path(backup, name)) != info:
            raise ValueError("Loader rollback files no longer match their saved hashes")
    if record["backups"]["boot.bin"] != record["previous"]:
        raise ValueError("Loader rollback payload differs from its recorded generation")
    baseline = _previous_receipt(record)
    if _receipt(backup, record["identity"]) != baseline:
        raise ValueError("Loader rollback receipt differs from its recorded enrollment")
    if record["previous"]["sha256"] != baseline:
        # This snapshot contains an abandoned staged loader. Follow its saved
        # state to verify the retained backup of the actually enrolled loader.
        if "enrollment-state.json" not in record["backups"]:
            raise ValueError("Missing enrolled-loader rollback chain")
        parent = json.loads((backup / "enrollment-state.json").read_text())
        if (parent.get("format") != FORMAT or parent.get("identity") != record["identity"]
                or parent.get("old_state_sha256") != record["old_state_sha256"]
                or parent.get("phase") not in ("prepared", "staged")
                or record["previous"] not in (parent["previous"], parent["target"])
                or baseline != _previous_receipt(parent)
                or record["backups"]["enroll.sh"] not in (parent["backups"]["enroll.sh"], parent["script"])):
            raise ValueError("Loader rollback chain no longer matches the pending update")
        _check_backups(resources, parent, seen)
    return backup


def status(project, out, *, emit=True):
    """Read-only: an unmounted System volume is reported, never mounted."""
    project, out = Path(project), Path(out)
    card.require_macos()
    dutil = DiskUtil()
    old, identity, roles = _resolve(project, dutil)
    record = _record(out, identity, sha256(internal_boot.state_path(project)))
    result = {"identity": identity, "phase": "not-staged" if record is None else record["phase"],
              "system_device": roles["System"]["device"], "mounted": False}
    if not dutil.info(roles["System"]["device"]).get("MountPoint"):
        result["note"] = "System volume is unmounted; receipt and loader contents were not inspected."
    else:
        system = card.mounted(dutil, roles["System"]["device"], allow_mount=False)
        resources = card.checked_path(system, card.RESOURCES)
        _check_original_metadata(resources, old)
        receipt_path = card.checked_path(resources, "enrolled.txt")
        initial = old.get("initial_enrollment") is True and not receipt_path.exists()
        receipt = None if initial else _receipt(resources, identity)
        installed = _info(card.checked_path(resources, "boot.bin"))
        result.update(mounted=True, receipt_sha256=receipt, boot=installed)
        if record is not None:
            _check_backups(resources, record)
            script = _info(card.checked_path(resources, "enroll.sh"))
            if script not in (record["backups"]["enroll.sh"], record["script"]):
                raise ValueError("Recovery script is outside the saved update")
            if installed not in (record["previous"], record["target"]) or receipt not in (
                    _previous_receipt(record), record["target"]["sha256"]):
                raise ValueError("Installed boot payload or receipt is outside the saved update")
            if (receipt == record["target"]["sha256"] and receipt != _previous_receipt(record)
                    and installed != record["target"]):
                raise ValueError("Enrolled loader is missing from the recorded active update")
            result["phase"] = ("enrolled" if installed == record["target"] and receipt == installed["sha256"]
                               else "awaiting-recovery" if installed == record["target"] else "prepared")
            result["backup"] = str(resources / record["backup"])
        elif initial:
            if installed != {"sha256": old["identity"]["boot_sha256"], "bytes": old["identity"]["boot_bytes"]}:
                raise ValueError("Initial un-enrolled loader differs from its creation receipt")
            result["phase"] = "awaiting-first-enrollment"
        elif installed["sha256"] != receipt:
            result["phase"] = "unfinished-legacy-update"
        else:
            result["phase"] = "enrolled"
        launcher = _launcher_module()
        if card.checked_path(out, launcher.STATE).exists():
            current = launcher.inspect(system, out, identity)
            result["recovery_launcher"] = current["layout"]
            result["launcher_backup"] = str(resources / current["record"]["backup"])
            if result["phase"] == "enrolled" and current["layout"] != "normal":
                result["phase"] = "enrolled-cleanup-pending"
    if emit:
        print(json.dumps(result, indent=2))
    return result


@contextmanager
def _lock(out):
    """Keep staging and startup selection in one serialized transaction."""
    out = Path(out)
    card.require_macos()
    if os.geteuid() != 0:
        raise ValueError("Staging the fixed SD loader requires sudo")
    lock = card.checked_path(out, ".enrollment.lock")
    descriptor = os.open(lock, os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError("Another loader staging process is active") from None
        yield
    finally:
        os.close(descriptor)


def stage(project, out, *, replace_pending=False, nvme=False):
    """Low-level manual staging, retained for explicit recovery tooling."""
    with _lock(out):
        return _stage(Path(project), Path(out), replace_pending=replace_pending, nvme=nvme)


def _source(out, nvme):
    source_dir = card.checked_path(out, "nvme-loader") if nvme else out
    card.checked_path(source_dir, "loader-manifest.json")
    manifest = verify_manifest(source_dir / "loader-manifest.json")
    if manifest.get("schema") != 1 or manifest.get("kind") != "j614s-sd-loader":
        raise ValueError("Expected a fixed j614s-sd-loader manifest")
    if manifest.get("boot_protocol") != "uefi-arm64":
        raise ValueError("Build the current UEFI bridge with make loader before staging it")
    if nvme and not manifest.get("inputs", {}).get("nvme_handoff"):
        raise ValueError("Build the ANS-aware loader with make loader before staging it")
    source = card.checked_path(source_dir, "loader.bin")
    expected = _info(source)
    if expected != manifest["files"].get("loader.bin"):
        raise ValueError("Loader changed after manifest verification")
    return source, expected


def _stage(project, out, *, replace_pending=False, nvme=False, launcher=None, confirm=None):
    project, out = Path(project), Path(out)
    card.require_macos()
    if os.geteuid() != 0:
        raise ValueError("Staging the fixed SD loader requires sudo")
    source, expected = _source(out, nvme)
    dutil = DiskUtil()
    old, identity, roles = _resolve(project, dutil)
    state_file = internal_boot.state_path(project)
    old_hash = sha256(state_file)
    record = _record(out, identity, old_hash)
    system = card.mounted(dutil, roles["System"]["device"])
    resources = card.checked_path(system, card.RESOURCES)
    _check_original_metadata(resources, old)
    receipt = _receipt(resources, identity)
    installed = _info(card.checked_path(resources, "boot.bin"))
    old_script = _info(card.checked_path(resources, "enroll.sh"))
    if record is None and (installed["sha256"] != receipt
            or installed != {"sha256": old["identity"]["boot_sha256"], "bytes": old["identity"]["boot_bytes"]}):
        raise ValueError("An unfinished or unknown legacy boot update exists; enroll or restore it first")
    resume = record is not None and record["target"] == expected
    supersede = False
    if record is not None:
        _check_backups(resources, record)
        if (installed not in (record["previous"], record["target"])
                or receipt not in (_previous_receipt(record), record["target"]["sha256"])
                or old_script not in (record["backups"]["enroll.sh"], record["script"])):
            raise ValueError("Interrupted loader update no longer matches its recorded inputs")
        if (receipt == record["target"]["sha256"] and receipt != _previous_receipt(record)
                and installed != record["target"]):
            raise ValueError("Enrolled loader is missing from the recorded active update")
        supersede = not resume and (installed != record["target"] or receipt != installed["sha256"])
        if supersede and not replace_pending:
            raise ValueError("Finish enrolling the pending loader before staging a different loader, or explicitly replace it with sudo make boot REPLACE_PENDING=1")
    if (launcher is not None and installed == expected and receipt == expected["sha256"]
            and (record is None or record["target"] == expected)):
        # A newer launcher template is not a reason to restage an enrolled
        # boot object. The caller may only need to finish saved metadata cleanup.
        return record or {"identity": identity, "target": expected, "phase": "enrolled"}
    previous_receipt = _previous_receipt(record) if resume else receipt
    text = render(project, {**identity, "previous_boot_sha256": previous_receipt}, source,
                  launcher=launcher).encode()
    script_info = {"bytes": len(text), "sha256": hashlib.sha256(text).hexdigest()}
    if resume and record["script"] != script_info and launcher is not None:
        # Upgrade a verified older manual script to hash-bound metadata checks,
        # including a pending update of the same boot object. Snapshot it as a
        # new generation so its script and enrolled-loader ancestry survive.
        resume = False
        text = render(project, {**identity, "previous_boot_sha256": receipt}, source,
                      launcher=launcher).encode()
        script_info = {"bytes": len(text), "sha256": hashlib.sha256(text).hexdigest()}
    if resume:
        if record["script"] != script_info or old_script not in (record["backups"]["enroll.sh"], script_info):
            raise ValueError("Recovery script changed during an unfinished update")
        if installed == expected and old_script == script_info:
            if record["phase"] != "staged":
                record["phase"] = "staged"
                _save(out, record)
            result = "already enrolled" if receipt == expected["sha256"] else "already staged; Recovery enrollment is pending"
            print(f"Fixed SD loader {result}.")
            return record
    operation = "REPLACE PENDING LOADER " if supersede else "STAGE LOADER "
    detail = (f"Supersede pending loader {record['target']['sha256']} with {expected['sha256']}.\n"
              f"Preserve the enrollment receipt for {receipt} and its verified rollback chain.\n"
              if supersede else "")
    confirmation = card.confirm if confirm is None else confirm
    consequence = ("No SD card, partition map, macOS volume or boot policy is changed by staging."
                   if launcher is None else
                   "The SD and partition map are unchanged. This workflow also selects Arch as the startup target\n"
                   "for paired Recovery. Apple will request owner authorization; enrollment runs from Recovery Terminal.")
    confirmation(operation + identity["vgid"],
                 detail + f"Replace only the boot payload in the existing internal Linux boot stub ({identity['vgid']}).\n"
                 "The current payload and enrollment files will be retained for rollback.\n"
                 + consequence)
    writable = card.mounted_writable(dutil, roles["System"]["device"], roles["System"]["uuid"])
    old_again, identity_again, roles_again = _resolve(project, dutil)
    if (writable != system or identity_again != identity or roles_again != roles
            or sha256(state_file) != old_hash or _info(source) != expected
            or _record(out, identity, old_hash) != record
            or _receipt(resources, identity) != receipt
            or _info(resources / "boot.bin") != installed or _info(resources / "enroll.sh") != old_script):
        raise ValueError("Loader staging inputs changed after confirmation")
    _check_original_metadata(resources, old_again)
    if record is not None:
        _check_backups(resources, record)
    if not resume:
        base = "sd-loader-backup-" + installed["sha256"]
        backup = card.checked_path(resources, base)
        number = 1
        while backup.exists():
            number += 1
            backup = card.checked_path(resources, base + "-" + str(number))
        backup.mkdir(mode=0o700)
        copies = {name: card.checked_path(resources, name) for name in OLD_FILES}
        copies["internal-boot-state.json"] = state_file
        if record is not None:
            copies["enrollment-state.json"] = card.checked_path(out, STATE)
        expected_backups = {name: _info(original) for name, original in copies.items()}
        for name, original in copies.items():
            _atomic(backup / name, original.read_bytes(), original.stat().st_mode & 0o777)
        if any(_info(backup / name) != info for name, info in expected_backups.items()):
            raise ValueError("Rollback sources changed during backup; active payload was not replaced")
        record = {"format": FORMAT, "phase": "prepared", "identity": identity,
                  "old_state_sha256": old_hash, "target": expected, "previous": installed,
                  "previous_receipt_sha256": receipt,
                  "script": script_info, "backup": backup.name,
                  "backups": expected_backups}
        _check_backups(resources, record)
        _save(out, record)
    _check_backups(resources, record)
    # Durable intent and rollback precede either active-file replacement.
    # On interruption a retry accepts only the recorded old/new combinations.
    source_bytes = source.read_bytes()
    if len(source_bytes) != expected["bytes"] or hashlib.sha256(source_bytes).hexdigest() != expected["sha256"]:
        raise ValueError("Loader source changed before active-file replacement")
    _atomic(resources / "boot.bin", source_bytes, 0o644)
    _atomic(resources / "enroll.sh", text, 0o755)
    if _info(resources / "boot.bin") != expected or _info(resources / "enroll.sh") != script_info:
        raise ValueError("Staged loader failed final verification; rollback retained")
    record["phase"] = "staged"
    _save(out, record)
    if launcher is None:
        print(f"Fixed SD loader staged. In this Arch installation's paired Recovery run:\n"
              f'sh "{resources / "enroll.sh"}" --update\n'
              f"Rollback files: {resources / record['backup']}\n"
              "Later kernel/initramfs/GRUB updates change only the SD files and need no enrollment.")
    return record


def _answer(prompt):
    """No response, including EOF, never authorizes a mutation or reboot."""
    try:
        return input(prompt).strip().lower() in ("y", "yes")
    except EOFError:
        return False


def prepare(project, out, *, replace_pending=False, nvme=True):
    """Prepare the one-command, owner-authorized Recovery enrollment flow."""
    recovery_launcher = _launcher_module()
    project, out = Path(project), Path(out)
    with _lock(out):
        source, expected = _source(out, nvme)  # Reject absent/unattested artifacts before disk access.
        dutil = DiskUtil()
        internal_boot.ensure(project, source, expected, dutil=dutil)
        old, identity, roles = _resolve(project, dutil)
        system = card.mounted(dutil, roles["System"]["device"])
        resources = card.checked_path(system, card.RESOURCES)
        receipt_path = card.checked_path(resources, "enrolled.txt")
        if old.get("initial_enrollment") is True and not receipt_path.exists():
            return _prepare_initial(project, out, dutil, old, identity, roles, source, expected)
        plan = recovery_launcher.plan(system, out, identity)
        approved = False

        def confirm(_phrase, description):
            nonlocal approved
            if approved:
                return
            print(description)
            if not _answer("Prepare this loader update? [y/N] "):
                raise ValueError("Cancelled; no loader or Recovery metadata was changed")
            approved = True

        record = _stage(project, out, replace_pending=replace_pending, nvme=nvme,
                        launcher=plan, confirm=confirm)
        # Re-resolve after staging and refuse a concurrent identity change even
        # though cooperating commands are already serialized by our lock.
        _, checked_identity, checked_roles = _resolve(project, dutil)
        if checked_identity != identity or checked_roles != roles:
            raise ValueError("Internal installation identity changed during staging")
        enrolled = _receipt(resources, identity) == record["target"]["sha256"]
        inspection = recovery_launcher.inspect(system, out, identity)
        if enrolled:
            if inspection["managed"] and inspection["layout"] != "normal":
                confirm("", "Enrollment already succeeded. Finish restoring this Arch installation's normal boot metadata.")
                writable = card.mounted_writable(dutil, roles["System"]["device"], roles["System"]["uuid"])
                _, current_identity, current_roles = _resolve(project, dutil)
                if writable != system or current_identity != identity or current_roles != roles:
                    raise ValueError("Internal System identity changed before enrollment cleanup")
                recovery_launcher.complete(system, out, identity, inspection["record"])
            print("This loader is already enrolled. No Recovery enrollment is needed.")
            return record
        confirm("", "Prepare the verified M4RCH update for paired Recovery enrollment.\n"
                "Apple will request owner authorization to select it as the startup disk.")
        writable = card.mounted_writable(dutil, roles["System"]["device"], roles["System"]["uuid"])
        if writable != system:
            raise ValueError("Internal System mount point changed before startup selection")
        managed = recovery_launcher.ensure(system, out, identity, plan)

        def recheck_target():
            _, current_identity, current_roles = _resolve(project, dutil)
            if (current_identity != identity or current_roles != roles
                    or _record(out, identity, sha256(internal_boot.state_path(project))) != record
                    or _info(resources / "boot.bin") != record["target"]
                    or _info(resources / "enroll.sh") != record["script"]
                    or _receipt(resources, identity) != _previous_receipt(record)):
                raise ValueError("Loader enrollment target changed during startup selection")

        def select_boot():
            recheck_target()
            card.set_bootable(system)
            run(["/usr/sbin/bless", "--setBoot", "--mount", system])
            recheck_target()

        try:
            recovery_launcher.select_startup(system, out, identity, managed, select_boot)
        except Exception:
            print("Enrollment preparation did not complete. The loader backup is retained.\n"
                  "Correct the reported error, then rerun the same make boot command.")
            raise
        print("\nRecovery enrollment is ready. After shutting down:\n"
              "1. Hold the power button continuously until startup options appear.\n"
              "2. Choose Options, then Continue to enter the paired Recovery.\n"
              "3. If Recovery asks, authenticate with your ordinary macOS owner account.\n"
              "4. Open Utilities > Terminal and run the command below.\n"
              "5. Confirm the update and answer Apple's enrollment prompts.\n"
              f"Loader rollback files: {resources / record['backup']}\n"
              f"Recovery metadata rollback files: {resources / managed['backup']}\n"
              f'sh "{resources / "enroll.sh"}" --update\n'
              "Later kernel/initramfs/GRUB updates stay on the SD and need no enrollment.")
        if _answer("Shut down now? [y/N] "):
            run(["/sbin/shutdown", "-h", "now"])
        else:
            print("Left the Mac running. Shut down normally when you are ready.")
        return record


def _prepare_initial(project, out, dutil, old, identity, roles, source, expected):
    """Select a freshly created Apple stub, without inventing an enrollment receipt."""
    import plistlib
    state_file = internal_boot.state_path(project)
    state_hash = sha256(state_file)
    if expected != {"sha256": old["identity"]["boot_sha256"], "bytes": old["identity"]["boot_bytes"]}:
        raise ValueError("First enrollment is pending for the recorded loader; finish it before staging another loader")
    system = card.mounted(dutil, roles["System"]["device"])
    resources = card.checked_path(system, card.RESOURCES)
    _check_original_metadata(resources, old)
    core = card.checked_path(system, "System/Library/CoreServices")
    version = card.checked_path(core, "SystemVersion.plist")
    if _info(resources / "boot.bin") != expected:
        raise ValueError("Un-enrolled loader differs from its first-install receipt")
    # The software payload is still pinned by bootstrap_inputs. These metadata
    # bytes are saved before changing the original Asahi app or picker marker.
    fields = plistlib.loads(version.read_bytes())
    if (fields.get("ProductBuildVersion"), fields.get("ProductVersion")) != ("25F84", "26.5.2"):
        raise ValueError("Initial Apple System metadata is not the supported build")
    installer = plistlib.dumps({"AppName": card.APP, "ProductBuildVersion": "25F84", "ProductVersion": "26.5.2"})
    generated = card.launcher_files()
    info_path = card.checked_path(system, Path(card.APP) / "Contents/Info.plist")
    app_path = card.checked_path(system, Path(card.APP) / "Contents/MacOS/launch.sh")
    payloads = {"app_info": generated[Path(card.APP) / "Contents/Info.plist"],
                "app_launcher": generated[Path(card.APP) / "Contents/MacOS/launch.sh"],
                "installer": installer, "system_version": version.read_bytes()}
    bindings = {key + "_sha256": hashlib.sha256(data).hexdigest() for key, data in payloads.items()}
    script = render(project, identity, source, launcher=bindings, initial=True,
                    owner_sha256=old["bootstrap_inputs"]["owner_sha256"]).encode()
    record_path = card.checked_path(out, "initial-enrollment-state.json")
    descriptor = {"format": "arch-m4-first-enrollment-v1", "identity": identity,
                  "old_state_sha256": state_hash, "target": expected,
                  "script": {"bytes": len(script), "sha256": hashlib.sha256(script).hexdigest()},
                  "bindings": bindings}
    active = card.checked_path(system, ".IAPhysicalMedia")
    disabled = card.checked_path(system, "IAPhysicalMedia-disabled.plist")

    def recheck():
        _, checked, checked_roles = _resolve(project, dutil)
        if (checked != identity or checked_roles != roles or sha256(state_file) != state_hash
                or _info(source) != expected or _info(resources / "boot.bin") != expected
                or version.read_bytes() != payloads["system_version"]):
            raise ValueError("First-enrollment target changed during preparation")
        _check_original_metadata(resources, old)
        # The owner metadata belongs to the currently authenticated host, not
        # to arbitrary copied identifiers or a synthetic enrollment receipt.
        preboot = card.mounted(dutil, roles["Preboot"]["device"])
        owner = card.checked_path(preboot, Path(identity["vgid"]) / "var/db/AdminUserRecoveryInfo.plist")
        if (_info(owner)["sha256"] != old["bootstrap_inputs"]["owner_sha256"]
                or card.source_owner_metadata(dutil) != owner.read_bytes()):
            raise ValueError("First-enrollment owner metadata changed")
        if card.checked_path(resources, "enrolled.txt").exists():
            raise ValueError("An enrollment receipt appeared during first-enrollment preparation")

    recheck()
    if record_path.exists():
        record = json.loads(record_path.read_text())
        if ({key: record.get(key) for key in descriptor} != descriptor
                or record.get("phase") not in ("prepared", "selected", "ready")
                or record.get("backup") != "first-enrollment-backup"):
            raise ValueError("First-enrollment intent changed; retain state and backups")
        for name, saved in record["originals"].items():
            if _info(card.checked_path(resources, record["backup"] + "/" + name)) != saved:
                raise ValueError("First-enrollment metadata backup changed")
    else:
        print("Prepare first enrollment of the new internal M4RCH.\n"
              "Apple will request owner authorization to personalize it and select it as the startup disk.\n"
              "The custom loader is enrolled separately from paired Recovery; the SD card is unchanged.")
        if not _answer("Prepare first enrollment? [y/N] "):
            raise ValueError("Cancelled; created boot container is retained. Rerun sudo make boot to resume")
        card.mounted_writable(dutil, roles["System"]["device"], roles["System"]["uuid"])
        recheck()
        backup = card.checked_path(resources, "first-enrollment-backup")
        backup.mkdir(mode=0o700, exist_ok=True)
        originals = {"enroll.sh": resources / "enroll.sh", "app-info.plist": info_path,
                     "installer.plist": active}
        saved = {name: _info(path) for name, path in originals.items()}
        for name, path in originals.items():
            internal_boot._write_once(backup / name, path.read_bytes(), path.stat().st_mode & 0o777)
        if any(_info(backup / name) != entry for name, entry in saved.items()):
            raise ValueError("First-enrollment backup failed verification")
        record = {**descriptor, "phase": "prepared", "backup": backup.name, "originals": saved}
        _atomic(record_path, (json.dumps(record, sort_keys=True, indent=2) + "\n").encode())
    recheck()
    # Durable first-install intent and original metadata precede mutations.
    card.mounted_writable(dutil, roles["System"]["device"], roles["System"]["uuid"])
    for target, key, mode in ((info_path, "app_info", 0o644), (app_path, "app_launcher", 0o755)):
        target.parent.mkdir(parents=True, exist_ok=True)
        expected_file = {"bytes": len(payloads[key]), "sha256": bindings[key + "_sha256"]}
        if target.exists() and _info(target) != expected_file:
            if target != info_path or _info(target) != record["originals"]["app-info.plist"]:
                raise ValueError("Unknown first-enrollment app modification")
        _atomic(target, payloads[key], mode)
    old_script = _info(resources / "enroll.sh")
    if old_script not in (record["originals"]["enroll.sh"], descriptor["script"]):
        raise ValueError("Unknown first-enrollment script modification")
    _atomic(resources / "enroll.sh", script, 0o755)
    if bool(active.exists()) == bool(disabled.exists()):
        raise ValueError("First-enrollment picker marker is missing or duplicated")
    marker = active if active.exists() else disabled
    marker_info = _info(marker)
    expected_marker = {"bytes": len(installer), "sha256": bindings["installer_sha256"]}
    if marker_info != expected_marker:
        if record["phase"] != "prepared" or marker != active or marker_info != record["originals"]["installer.plist"]:
            raise ValueError("First-enrollment picker marker changed")
        _atomic(active, installer, 0o644)
    if record["phase"] == "prepared":
        recheck()
        card.set_bootable(system)
        run(["/usr/sbin/bless", "--setBoot", "--mount", system])
        recheck()
        record["phase"] = "selected"
        _atomic(record_path, (json.dumps(record, sort_keys=True, indent=2) + "\n").encode())
    if active.exists():
        active.replace(disabled)
        os.sync()
    record["phase"] = "ready"
    _atomic(record_path, (json.dumps(record, sort_keys=True, indent=2) + "\n").encode())
    print("\nFirst enrollment is ready. Shut down, hold power continuously until startup options appear,\n"
          "choose Options > Continue, then authenticate with your ordinary macOS owner account.\n"
          "Open Utilities > Terminal and run:\n"
          f'sh "{resources / "enroll.sh"}" --enroll\n'
          "Confirm the new installation policy and answer Apple's credential prompts.\n"
          "After enrollment, shut down and select M4RCH. Later SD kernel updates need no enrollment.")
    if _answer("Shut down now? [y/N] "):
        run(["/sbin/shutdown", "-h", "now"])
    return record
