#!/usr/bin/env python3
"""Upgrade the dedicated Apple stub with a durable, verified local rollback."""
from __future__ import annotations
import argparse
import ctypes
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import plistlib
import shutil
import stat
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'lib'))
import card
import internal_boot
from card_disk import DiskUtil
from common import run, sha256
import enrollment
import recovery_launcher

STATE = 'stub-upgrade-state.json'
HOST_FILES = ('enrollment-state.json', 'launcher-state.json')
# Data-volume Spotlight index; generated while macOS mounts the stub.
SPOTLIGHT_INDEX = 'private/var/db/Spotlight-V100'


def runtime_index(name):
    return name == SPOTLIGHT_INDEX or name.startswith(SPOTLIGHT_INDEX + '/')


def xattrs(path):
    if hasattr(os, 'listxattr'):
        return {name: hashlib.sha256(os.getxattr(path,name,follow_symlinks=False)).hexdigest()
                for name in os.listxattr(path,follow_symlinks=False)}
    # Darwin's Python does not expose os.*xattr; use the native read-only APIs.
    library=ctypes.CDLL('/usr/lib/libSystem.B.dylib',use_errno=True)
    listing=library.listxattr;listing.restype=ctypes.c_ssize_t
    listing.argtypes=(ctypes.c_char_p,ctypes.c_void_p,ctypes.c_size_t,ctypes.c_int)
    getter=library.getxattr;getter.restype=ctypes.c_ssize_t
    getter.argtypes=(ctypes.c_char_p,ctypes.c_char_p,ctypes.c_void_p,ctypes.c_size_t,ctypes.c_uint32,ctypes.c_int)
    encoded=os.fsencode(path)
    def read(function,*arguments):
        for _ in range(3):
            length=function(*arguments,None,0,0,1) if function is getter else function(*arguments,None,0,1)
            if length<0:raise OSError(ctypes.get_errno(),'Cannot read stub xattrs',str(path))
            buffer=ctypes.create_string_buffer(length)
            actual=function(*arguments,buffer,length,0,1) if function is getter else function(*arguments,buffer,length,1)
            if actual>=0:return buffer.raw[:actual]
            if ctypes.get_errno()!=34:raise OSError(ctypes.get_errno(),'Cannot read stub xattrs',str(path))
        raise ValueError('Stub xattrs changed during inspection')
    names=read(listing,encoded).split(b'\0')
    return {os.fsdecode(name):hashlib.sha256(read(getter,encoded,name)).hexdigest() for name in names if name}


def preparation():
    spec = importlib.util.spec_from_file_location('stub_preparation', ROOT / 'scripts/prepare-stub-upgrade.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def inventory(root, *, skip_runtime_index=False):
    """Hash files without following links; retain ownership, flags and xattrs."""
    result = {}
    for path in sorted(root.rglob('*')):
        relative = path.relative_to(root).as_posix()
        if skip_runtime_index and runtime_index(relative):
            if relative == SPOTLIGHT_INDEX and (path.is_symlink() or not path.is_dir()):
                raise ValueError('Unexpected Spotlight index root object')
            continue
        if relative.split('/')[0] in internal_boot.BOOKKEEPING:
            continue
        info = path.lstat()
        item = {'mode': stat.S_IMODE(info.st_mode), 'uid': info.st_uid, 'gid': info.st_gid,
                'flags': getattr(info, 'st_flags', 0)}
        if stat.S_ISLNK(info.st_mode):
            item.update(kind='link', target=os.readlink(path))
        elif stat.S_ISDIR(info.st_mode):
            item.update(kind='directory')
        elif stat.S_ISREG(info.st_mode):
            item.update(kind='file', bytes=info.st_size, sha256=sha256(path))
        else:
            raise ValueError('Unsupported stub object: ' + str(path))
        item['xattrs'] = xattrs(path)
        result[relative] = item
    return result


def destinations(dutil, identity, roles, *, writable=False):
    mounts = {}
    for role, entry in roles.items():
        mount = (card.mounted_writable(dutil, entry['device'], entry['uuid']) if writable
                 else card.mounted(dutil, entry['device']))
        mounts[role] = mount / identity['vgid'] if role in ('Preboot', 'Recovery') else mount
        if mounts[role].is_symlink() or not mounts[role].is_dir():
            raise ValueError('Invalid installed role root: ' + role)
    return mounts


def save(path, value):
    enrollment._atomic(path, (json.dumps(value, sort_keys=True, indent=2) + '\n').encode())


def replacement_paths(payload):
    """Apple payload files only; preserve owner databases and the Linux loader."""
    result = {}
    for role in ('System', 'Preboot', 'Recovery'):
        names = []
        for path in sorted((payload / role).rglob('*')):
            name = path.relative_to(payload / role).as_posix()
            if role == 'System' and (name == '.IAPhysicalMedia' or name.startswith(card.APP + '/')):
                continue
            if not path.is_dir() or path.is_symlink():
                names.append(name)
        result[role] = names
    return result


def copy_replacements(payload, mounts, names):
    for role, paths in names.items():
        for name in paths:
            source = payload / role / name
            target = card.checked_path(mounts[role], name, leaf_symlink=source.is_symlink())
            target.parent.mkdir(parents=True, exist_ok=True)
            if source.is_symlink():
                if target.exists() and not target.is_symlink():
                    raise ValueError('Unexpected target object: ' + str(target))
                if target.is_symlink() and os.readlink(target) == os.readlink(source):
                    continue
                # Validate the candidate link remains inside its source role tree.
                if not source.resolve().is_relative_to((payload / role).resolve()):
                    raise ValueError('Candidate link escapes role')
                temp = target.with_name(target.name + '.stub-upgrade-link')
                if temp.exists() or temp.is_symlink():
                    raise ValueError('Unexpected link staging path')
                temp.symlink_to(os.readlink(source))
                temp.replace(target)
            else:
                enrollment._atomic(target, source.read_bytes(), stat.S_IMODE(source.stat().st_mode))
                if sha256(target) != sha256(source):
                    raise ValueError('Installed Apple file failed readback')


def copy_backup_tree(source, target, expected):
    """Keep BSD flags in the receipt, not on the writable backup copy.

    copyfile without COPYFILE_STAT copies data, xattrs and ACLs before we
    restore ownership/mode. ditto can set schg before finishing metadata,
    making its own destination unwritable. Never clear flags on live files.
    """
    target.mkdir()
    library = ctypes.CDLL('/usr/lib/libSystem.B.dylib', use_errno=True)
    copyfile = library.copyfile
    copyfile.restype = ctypes.c_int
    copyfile.argtypes = (ctypes.c_char_p, ctypes.c_char_p, ctypes.c_void_p, ctypes.c_uint32)
    # SDK copyfile.h: ACL | XATTR | DATA, NOFOLLOW on both paths; omit STAT.
    flags = 1 | 4 | 8 | (1 << 18) | (1 << 19)
    for name, item in expected.items():
        src, dst = source / name, target / name
        if item['kind'] == 'directory':
            dst.mkdir()
        elif item['kind'] == 'link':
            dst.symlink_to(item['target'])
        if copyfile(os.fsencode(src), os.fsencode(dst), None,
                    flags & ~8 if item['kind'] == 'directory' else flags) != 0:
            raise OSError(ctypes.get_errno(), 'Cannot copy stub backup', str(src))
        os.chown(dst, item['uid'], item['gid'], follow_symlinks=False)
        os.chmod(dst, item['mode'], follow_symlinks=False)
    # Directory modes/ACLs can restrict child creation; installed role trees
    # are traversed as root. Hash verification remains mandatory below.
    actual = inventory(target)
    normalized = {name: {**item, 'flags': actual.get(name, {}).get('flags', 0)}
                  for name, item in expected.items()}
    if actual != normalized:
        raise ValueError('Backup data or metadata differs from installed role')
    immutable = stat.UF_IMMUTABLE | stat.SF_IMMUTABLE | stat.UF_APPEND | stat.SF_APPEND
    if any(item['flags'] & immutable for item in actual.values()):
        raise ValueError('Backup unexpectedly inherited immutable flags')
    return actual


def validate_backup(backup, record):
    for role, expected in record.get('backup_storage_inventory', record['backup_inventory']).items():
        if inventory(backup / 'roles' / role) != expected:
            raise ValueError('Rollback copy changed: ' + role)
    for name, expected in record['host_inventory'].items():
        path = backup / 'host' / name
        if sha256(path) != expected:
            raise ValueError('Host rollback receipt changed: ' + name)


def restore_tree(source, destination, expected):
    """Restore only differing entries; leave identical immutable owner files alone."""
    current = inventory(destination)
    for name, original in expected.items():
        if current.get(name) == original:
            continue
        src = source / name
        target = card.checked_path(destination, name, leaf_symlink=original['kind'] == 'link')
        target.parent.mkdir(parents=True, exist_ok=True)
        if original['kind'] == 'directory':
            target.mkdir(exist_ok=True)
            os.chmod(target, original['mode'])
            os.chown(target, original['uid'], original['gid'])
        else:
            run(['/usr/bin/ditto', '--rsrc', '--extattr', '--acl', src, target])
        if hasattr(os, 'chflags'):
            os.chflags(target, original['flags'], follow_symlinks=False)
    after = inventory(destination)
    if any(after.get(name) != value for name, value in expected.items()):
        raise ValueError('Restored baseline did not verify; retain backup and transaction')


def select_and_print(system, out, identity, managed, dutil, roles):
    def select():
        _, current, current_roles = enrollment._resolve(ROOT, dutil)
        if current != identity or current_roles != roles:
            raise ValueError('Stub identity changed before personalization')
        card.set_bootable(system)
        run(['/usr/sbin/bless', '--setBoot', '--mount', system])
    try:
        recovery_launcher.select_startup(system, out, identity, managed, select)
    except subprocess.CalledProcessError:
        print('\nApple startup selection failed; the firmware transaction remains staged.\n'
              'Do not repeat payload installation or bypass paired-Recovery checks.\n'
              'Shut down, hold power continuously and open Options > Utilities > Terminal.\n'
              'Connect Recovery to the Internet. Try Apple personalization there:\n'
              f'diskutil mount {identity["roles"]["System"]["uuid"]}\n'
              f'bless --setBoot --mount "{system}"\n'
              'Use the mount path printed by diskutil if it differs. If bless fails, stop and save its error.\n'
              'If it succeeds, shut down fully and hold power again to enter the now-selected\n'
              'M4RCH paired Recovery. Then run:\n'
              f'sh "{system / card.RESOURCES / "enroll.sh"}" --update\n'
              'The enrollment script will verify pairing before changing custom-boot policy.\n'
              'After successful enrollment, return to macOS and run sudo make stub-finish.\n'
              'Rollback remains available through sudo make stub-rollback.')
        raise
    print('\nApple firmware staged; Recovery enrollment is required before booting M4RCH.\n'
          'Shut down, hold power continuously, choose Options for this selected M4RCH installation,\n'
          'authenticate, open Utilities > Terminal and run:\n'
          f'sh "{system / card.RESOURCES / "enroll.sh"}" --update\n'
          'The script forces fresh custom-boot authorization even though m1n1 bytes are unchanged.\n'
          'After returning to macOS, run sudo make stub-finish.\n'
          'No automatic reboot was requested.')


def install(candidate, out):
    prep = preparation()
    prep.verify_candidate(candidate)
    dutil = DiskUtil()
    old, identity, roles = enrollment._resolve(ROOT, dutil)
    state_path = out / STATE
    if state_path.exists():
        record = json.loads(state_path.read_text())
        if (record['identity'] != identity or record['candidate'] != str(candidate)
                or record['candidate_manifest_sha256'] != sha256(candidate / 'payload/manifest.json')):
            raise ValueError('An upgrade with different inputs exists; retain its state')
        validate_backup(Path(record['backup']), record)
        if record['phase'] == 'awaiting-recovery':
            mounts = destinations(dutil, identity, roles, writable=True)
            system = mounts['System']
            managed = recovery_launcher.inspect(system, out, identity)['record']
            select_and_print(system, out, identity, managed, dutil, roles)
            return
        if record['phase'] in ('backed-up', 'copying'):
            mounts = destinations(dutil, identity, roles)
            validate_resume(mounts, record)
            baseline = json.loads((Path(record['backup'])/'host/internal-boot-state.json').read_text())
            # Validate legacy receipt compatibility before any resumed write.
            upgraded_state(baseline, record)
            card.confirm('RESUME STUB ' + identity['vgid'],
                'Resume the same verified Apple firmware transaction using its saved backup.\n'
                'Protected owner metadata and m1n1 were checked; no new backup or partition changes.')
            mounts = destinations(dutil, identity, roles, writable=True)
            validate_resume(mounts, record)
            record['phase']='copying';save(state_path, record)
            stage_upgrade(candidate, out, record, baseline, identity, roles, dutil, mounts)
            return
        raise ValueError('Upgrade transaction exists; use rollback or finish, never overwrite it')
    mounts = destinations(dutil, identity, roles)
    system = mounts['System']
    resources = card.checked_path(system, card.RESOURCES)
    enrollment._check_original_metadata(resources, old)
    if enrollment._receipt(resources, identity) != sha256(resources / 'boot.bin'):
        raise ValueError('Enroll or roll back the pending loader before upgrading Apple firmware')
    inspection = recovery_launcher.inspect(system, out, identity)
    if inspection['layout'] != 'normal':
        raise ValueError('Finish existing Recovery metadata cleanup before upgrading')
    fields = plistlib.loads((system / 'System/Library/CoreServices/SystemVersion.plist').read_bytes())
    if fields.get('ProductBuildVersion') != '25F84':
        raise ValueError('Expected the existing 25F84 stub baseline')
    names = replacement_paths(candidate / 'payload')
    baseline_bytes = sum(info['bytes'] for mount in mounts.values()
                         for info in inventory(mount).values() if info['kind'] == 'file')
    if shutil.disk_usage(ROOT / 'out').free < baseline_bytes + 256 * 1024 * 1024:
        raise ValueError('Insufficient space on macOS for the installed-stub backup')
    largest = max((candidate / 'payload' / role / name).stat().st_size
                  for role, entries in names.items() for name in entries
                  if not (candidate / 'payload' / role / name).is_symlink())
    free = internal_boot.container_for(dutil, old['partition']).get('CapacityFree')
    if not isinstance(free,int) or free < largest + 256 * 1024 * 1024:
        raise ValueError('Insufficient known free space in the dedicated stub for atomic file replacement')
    card.confirm('UPGRADE STUB ' + identity['vgid'],
        'Back up all four installed stub trees and host enrollment receipts, then replace\n'
        'only this dedicated Linux installation\'s Apple boot/recovery firmware with 25G83.\n'
        'The partition map, primary macOS, enrolled m1n1 and Linux ESP are unchanged.\n'
        'Apple personalization and paired Recovery authentication will follow.\n'
        'File rollback is available; a changed Apple LocalPolicy may require re-personalization.')
    backup = Path(tempfile.mkdtemp(prefix='stub-backup-25F84-', dir=ROOT / 'out'))
    backup.chmod(0o700)
    inventories = {}
    storage_inventories = {}
    for role, source in mounts.items():
        before = inventory(source)
        target = backup / 'roles' / role
        target.parent.mkdir(parents=True, exist_ok=True)
        storage_inventories[role] = copy_backup_tree(source, target, before)
        if inventory(source) != before:
            raise ValueError('Installed source or backup differs: ' + role)
        inventories[role] = before
    host = backup / 'host';host.mkdir(mode=0o700)
    host_inventory = {}
    sources = {'internal-boot-state.json': internal_boot.state_path(ROOT)}
    sources.update({name: out / name for name in HOST_FILES if (out / name).exists()})
    for name, source in sources.items():
        run(['/usr/bin/ditto', '--rsrc', '--extattr', '--acl', source, host / name])
        host_inventory[name] = sha256(source)
        if sha256(host / name) != host_inventory[name]:
            raise ValueError('Host receipt changed during backup')
    record = {'schema': 'm4rch.stub-upgrade.v1', 'phase': 'backed-up', 'identity': identity,
              'candidate': str(candidate), 'candidate_manifest_sha256': sha256(candidate / 'payload/manifest.json'),
              'backup': str(backup), 'backup_inventory': inventories,
              'backup_storage_inventory': storage_inventories, 'host_inventory': host_inventory,
              'replacements': names, 'boot_sha256': sha256(resources / 'boot.bin')}
    save(state_path, record) # Durable rollback precedes any active file write.
    validate_backup(backup, record)
    prep.verify_candidate(candidate)
    _, current, current_roles = enrollment._resolve(ROOT, dutil)
    if current != identity or current_roles != roles or any(inventory(mounts[r]) != i for r,i in inventories.items()):
        raise ValueError('Installed state changed before upgrade; no Apple file replaced')
    upgraded_state(old, record)
    mounts = destinations(dutil, identity, roles, writable=True)
    record['phase'] = 'copying';save(state_path, record)
    stage_upgrade(candidate, out, record, old, identity, roles, dutil, mounts)


def upgraded_state(old, record):
    """Legacy ready stubs predate bootstrap_inputs; retain their other fields."""
    updated = dict(old)
    updated['identity'] = {**old['identity'], 'apple_build':'25G83'}
    updated['bootstrap_inputs'] = {**old.get('bootstrap_inputs', {}),
        'stub_manifest_sha256': record['candidate_manifest_sha256']}
    updated['apple_stub_upgrade'] = {'build':'25G83', 'backup':record['backup']}
    return updated


def validate_resume(mounts, record):
    """Only the transaction's declared replacement paths may have changed."""
    allowed = {role: set(paths) for role, paths in record['replacements'].items()}
    allowed.setdefault('System', set()).update(p.as_posix() for p in card.launcher_files()
                                               if p != Path('.IAPhysicalMedia'))
    allowed['System'].update(('IAPhysicalMedia-disabled.plist',
                              (Path(card.RESOURCES)/'card.json').as_posix()))
    for role, mount in mounts.items():
        paths = allowed.get(role, set())
        paths = paths | {p.as_posix() for name in paths for p in Path(name).parents if p != Path('.')}
        expected = record['backup_inventory'][role]
        current = inventory(mount, skip_runtime_index=(role == 'Data'))
        for name in set(expected) | set(current):
            if role == 'Data' and runtime_index(name):
                continue
            if name not in paths and expected.get(name) != current.get(name):
                raise ValueError('Protected installed object changed before resume: ' + role + '/' + name)
    resources = mounts['System']/card.RESOURCES
    if sha256(resources/'boot.bin') != record['boot_sha256']:
        raise ValueError('Protected loader changed before resume')


def stage_upgrade(candidate, out, record, old, identity, roles, dutil, mounts):
    state_path = out/STATE
    backup = Path(record['backup'])
    names = record['replacements']
    copy_replacements(candidate / 'payload', mounts, names)
    system = mounts['System'];resources = system / card.RESOURCES
    if sha256(resources / 'boot.bin') != record['boot_sha256']:
        raise ValueError('The protected Linux loader changed')
    generated = card.launcher_files()
    for relative, data in generated.items():
        if relative == Path('.IAPhysicalMedia'):
            continue
        enrollment._atomic(card.checked_path(system, relative), data, 0o755 if relative.suffix == '.sh' else 0o644)
    installer = plistlib.dumps({'AppName':card.APP, 'ProductBuildVersion':'25G83', 'ProductVersion':'26.6.2'})
    enrollment._atomic(system / 'IAPhysicalMedia-disabled.plist', installer, 0o644)
    # Archive old hash-bound host generations; new ones bind the target metadata.
    for name in HOST_FILES:
        (out / name).unlink(missing_ok=True)
    updated = upgraded_state(old, record)
    internal_boot.write_state(ROOT, updated)
    enrollment._atomic(resources / 'card.json', (json.dumps(updated['identity'],sort_keys=True,indent=2)+'\n').encode())
    record['phase']='metadata-ready';save(state_path, record)
    plan = recovery_launcher.plan(system, out, identity)
    managed = recovery_launcher.ensure(system, out, identity, plan)
    text = enrollment.render(ROOT, identity, resources / 'boot.bin', launcher=managed,
                             force_enrollment=True, stub_build='25G83')
    enrollment._atomic(resources / 'enroll.sh', text.encode(), 0o755)
    (resources / 'stub-enrolled.txt').unlink(missing_ok=True)
    record['phase']='awaiting-recovery';save(state_path, record)
    print('Verified rollback:', backup)
    select_and_print(system, out, identity, managed, dutil, roles)


def rollback(out):
    path = out / STATE
    record = json.loads(path.read_text())
    dutil = DiskUtil()
    _, identity, roles = enrollment._resolve(ROOT, dutil)
    if identity != record['identity']:
        raise ValueError('Upgrade rollback identity changed')
    backup = Path(record['backup']);validate_backup(backup,record)
    card.confirm('ROLLBACK STUB ' + identity['vgid'],
        'Restore the saved installed 25F84 stub files and host receipts.\n'
        'Apple boot-policy changes are not undone by copying files; personalization/enrollment may be required.')
    mounts = destinations(dutil, identity, roles, writable=True)
    record['phase']='rolling-back';save(path,record)
    for role, names in record['replacements'].items():
        for name in names:
            if name not in record['backup_inventory'][role]:
                target=card.checked_path(mounts[role],name,leaf_symlink=True)
                if target.is_file() or target.is_symlink():target.unlink()
    for role, destination in mounts.items():
        restore_tree(backup/'roles'/role,destination,record['backup_inventory'][role])
    for name in HOST_FILES:
        (out/name).unlink(missing_ok=True)
    for name in record['host_inventory']:
        destination=internal_boot.state_path(ROOT) if name=='internal-boot-state.json' else out/name
        run(['/usr/bin/ditto','--rsrc','--extattr','--acl',backup/'host'/name,destination])
    system=mounts['System'];resources=system/card.RESOURCES
    (resources/'stub-enrolled.txt').unlink(missing_ok=True)
    # Force a policy refresh after restore; do not trust the old same-byte receipt.
    inspection=recovery_launcher.inspect(system,out,identity)
    if not inspection['managed']:
        managed=recovery_launcher.ensure(system,out,identity,recovery_launcher.plan(system,out,identity))
    else:managed=inspection['record']
    text=enrollment.render(ROOT,identity,resources/'boot.bin',launcher=managed,
                           force_enrollment=True,stub_build='25F84')
    enrollment._atomic(resources/'enroll.sh',text.encode(),0o755)
    record['phase']='rollback-awaiting-recovery';save(path,record)
    select_and_print(system,out,identity,managed,dutil,roles)


def finish(out):
    path=out/STATE;record=json.loads(path.read_text())
    if record['phase'] not in ('awaiting-recovery','rollback-awaiting-recovery'):
        raise ValueError('No staged stub enrollment to finish')
    dutil=DiskUtil();_,identity,roles=enrollment._resolve(ROOT,dutil)
    if identity!=record['identity']:raise ValueError('Stub identity changed')
    mounts=destinations(dutil,identity,roles);resources=mounts['System']/card.RESOURCES
    build='25G83' if record['phase']=='awaiting-recovery' else '25F84'
    marker=card.checked_path(resources,'stub-enrolled.txt')
    if marker.read_text().splitlines()!=[identity['vgid'],record['boot_sha256'],build]:
        raise ValueError('Recovery has not produced the bound stub enrollment receipt')
    if sha256(resources/'boot.bin')!=record['boot_sha256']:
        raise ValueError('Enrolled loader changed')
    version=plistlib.loads((mounts['System']/'System/Library/CoreServices/SystemVersion.plist').read_bytes())
    if version.get('ProductBuildVersion') != build or enrollment._receipt(resources,identity) != record['boot_sha256']:
        raise ValueError('Installed version or loader receipt differs from the completed upgrade')
    inspection=recovery_launcher.inspect(mounts['System'],out,identity)
    if not inspection['ready']:
        raise ValueError('Finish Recovery metadata cleanup before completing the upgrade')
    normal_script=enrollment.render(ROOT,identity,resources/'boot.bin',launcher=inspection['record'])
    enrollment._atomic(resources/'enroll.sh',normal_script.encode(),0o755)
    record['phase']='complete' if build=='25G83' else 'rolled-back';save(path,record)
    print('Recovery enrollment receipt verified for',build,'. Backup retained:',record['backup'])


def stage_policy_repair(out):
    """Stage a bounded Recovery helper; do not change policy from macOS."""
    record=json.loads((out/STATE).read_text())
    if record['phase']!='awaiting-recovery':
        raise ValueError('Policy repair requires the staged firmware awaiting Recovery')
    dutil=DiskUtil();_,identity,roles=enrollment._resolve(ROOT,dutil)
    if identity!=record['identity']:raise ValueError('Policy repair identity differs')
    validate_backup(Path(record['backup']),record)
    source=ROOT/'tools/boot/repair-stub-policy.sh'
    text=source.read_text()
    if (('VGID='+identity['vgid']) not in text or
        ('SYSTEM_UUID='+roles['System']['uuid']) not in text or
        ('BOOT_SHA='+record['boot_sha256']) not in text):
        raise ValueError('Recovery helper does not match this transaction')
    system=card.mounted_writable(dutil,roles['System']['device'],roles['System']['uuid'])
    resources=card.checked_path(system,card.RESOURCES)
    if sha256(resources/'boot.bin')!=record['boot_sha256']:
        raise ValueError('Working stage 1 changed')
    target=card.checked_path(resources,'repair-policy.sh')
    enrollment._atomic(target,text.encode(),0o755)
    print('Recovery helper staged; no boot policy was changed. In Recovery Terminal run:')
    print(f'sh "{target}"')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=('install','rollback','finish','policy-repair'))
    p.add_argument('--candidate',type=Path,default=ROOT/'out/stub-upgrade-25G83-candidate')
    a=p.parse_args();card.require_macos()
    if os.geteuid()!=0:raise PermissionError('Installed stub changes and protected backups require sudo')
    out=ROOT/'out/sdboot'
    with enrollment._lock(out):
        if a.action=='install':install(a.candidate.resolve(),out)
        elif a.action=='rollback':rollback(out)
        elif a.action=='policy-repair':stage_policy_repair(out)
        else:finish(out)

if __name__=='__main__':main()
