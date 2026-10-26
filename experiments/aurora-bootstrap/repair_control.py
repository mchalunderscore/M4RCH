#!/usr/bin/env python3
"""Build AUBS001 revision 2 from the preserved revision-1 artifacts."""
import argparse
import ctypes
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import struct

OUTPUT = Path(__file__).resolve().parents[2] / 'out/aurora-bootstrap'
R1_BOOT = 'de207da3c37f1e0e6a0ffe40104e1c6c9101335790d5653d4794bedc47187452'
R2_BOOT = '7005593ebd056d31cb440573ce8f84ee00447a84e81e1ee89f65b0e52ff37738'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(library, revision=2):
    previous = {2: R1_BOOT, 3: R2_BOOT}[revision]
    archive = OUTPUT / ('revisions/r' + str(revision - 1))
    if not archive.exists():
        if sha(OUTPUT / 'boot.bin') != previous:
            raise ValueError('Expected previous revision boot image')
        archive.mkdir(parents=True)
        for path in OUTPUT.iterdir():
            if path.is_file():
                shutil.copyfile(path, archive / path.name)
    if sha(archive / 'boot.bin') != previous:
        raise ValueError('Preserved previous revision differs')
    lib = ctypes.CDLL(library)
    lib.fdt_path_offset.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
    lib.fdt_getprop.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_char_p, ctypes.POINTER(ctypes.c_int)]
    lib.fdt_getprop.restype = ctypes.c_void_p
    lib.fdt_get_name.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.POINTER(ctypes.c_int)]
    lib.fdt_get_name.restype = ctypes.c_char_p
    lib.fdt_setprop.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_void_p, ctypes.c_int]
    lib.fdt_getprop_by_offset.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.POINTER(ctypes.c_char_p), ctypes.POINTER(ctypes.c_int)]
    lib.fdt_getprop_by_offset.restype = ctypes.c_void_p
    original = (archive / 'control.dtb').read_bytes()
    tree = ctypes.create_string_buffer(len(original) + 16384)
    assert lib.fdt_open_into(original, tree, len(tree)) == 0

    def snapshot(buffer):
        result = {}
        def visit(node, path):
            props = {}
            offset = lib.fdt_first_property_offset(buffer, node)
            while offset >= 0:
                name, length = ctypes.c_char_p(), ctypes.c_int()
                value = lib.fdt_getprop_by_offset(buffer, offset, ctypes.byref(name), ctypes.byref(length))
                props[name.value.decode()] = ctypes.string_at(value, length.value)
                offset = lib.fdt_next_property_offset(buffer, offset)
            result[path] = props
            child = lib.fdt_first_subnode(buffer, node)
            while child >= 0:
                name = lib.fdt_get_name(buffer, child, None).decode()
                visit(child, path.rstrip('/') + '/' + name)
                child = lib.fdt_next_subnode(buffer, child)
        visit(0, '/')
        return result
    expected_tree = snapshot(tree)

    def get(node, prop):
        length = ctypes.c_int()
        value = lib.fdt_getprop(tree, node, prop.encode(), ctypes.byref(length))
        return ctypes.string_at(value, length.value) if value else None

    paths = []
    cpu_parent = lib.fdt_path_offset(tree, b'/cpus')
    node = lib.fdt_first_subnode(tree, cpu_parent)
    while node >= 0:
        name = lib.fdt_get_name(tree, node, None).decode()
        if name.startswith('cpu@'):
            paths.append('/cpus/' + name)
        node = lib.fdt_next_subnode(tree, node)
    changed = []
    for path in paths:
        for prop, value in [('enable-method', b'spin-table\0'), ('cpu-release-addr', b'\0' * 8)]:
            node = lib.fdt_path_offset(tree, path.encode())
            old = get(node, prop)
            if old is None:
                assert lib.fdt_setprop(tree, node, prop.encode(), value, len(value)) == 0
                changed.append([path, prop])
            elif old != value:
                raise ValueError('Unexpected static CPU configuration: ' + path + '/' + prop)
    expected_cpu_changes = [['/cpus/cpu@10100', 'enable-method'], ['/cpus/cpu@10100', 'cpu-release-addr']] if revision == 2 else []
    if changed != expected_cpu_changes:
        raise ValueError('Expected exactly the native failure CPU fields to be missing')
    if revision == 3:
        for alias in ['wifi0', 'bluetooth0']:
            aliases = lib.fdt_path_offset(tree, b'/aliases')
            path = get(aliases, alias).rstrip(b'\0').decode()
            node = lib.fdt_path_offset(tree, path.encode())
            if get(node, 'brcm,board-type') != b'apple,hostomel\0':
                raise ValueError('Expected donor hostomel radio identity')
            value = b'apple,mriya\0'
            assert lib.fdt_setprop(tree, node, b'brcm,board-type', value, len(value)) == 0
            expected_tree[path]['brcm,board-type'] = value
            changed.append([path, 'brcm,board-type'])
    for path in paths:
        node = lib.fdt_path_offset(tree, path.encode())
        assert get(node, 'enable-method') == b'spin-table\0'
        assert get(node, 'cpu-release-addr') == b'\0' * 8
    assert lib.fdt_pack(tree) == 0
    size = struct.unpack_from('>I', tree.raw, 4)[0]
    updated = tree.raw[:size]
    expected_tree['/cpus/cpu@10100'].update({'enable-method': b'spin-table\0', 'cpu-release-addr': b'\0' * 8})
    assert snapshot(tree) == expected_tree, 'Unrelated device-tree data changed'
    assert lib.fdt_num_mem_rsv(original) == lib.fdt_num_mem_rsv(tree) == 0
    old_boot = (archive / 'boot.bin').read_bytes()
    prefix_size = 3473408
    assert old_boot[prefix_size:prefix_size + len(original)] == original
    tail = old_boot[prefix_size + len(original):]
    gzip.decompress(tail)
    (OUTPUT / 'control.dtb').write_bytes(updated)
    (OUTPUT / 'boot.bin').write_bytes(old_boot[:prefix_size] + updated + tail)
    profile = json.loads((archive / 'profile.json').read_text())
    fix = ('Supply spin-table placeholders for cpu@10100; m1n1 skips fixups for the running boot CPU' if revision == 2 else
           'Use J614s mriya Wi-Fi/Bluetooth firmware identity instead of J616s hostomel donor identity')
    profile.update(revision=revision, stage1_requires_recovery_enrollment=False,
                   stage1_changed_from_revision1=False,
                   fix=fix)
    profile['chainload_image_room_bytes'] = (OUTPUT / 'stage1.bin').stat().st_size - (OUTPUT / 'boot.bin').stat().st_size
    (OUTPUT / 'profile.json').write_text(json.dumps(profile, indent=2) + '\n')
    provenance = json.loads((archive / 'control-provenance.json').read_text())
    provenance.update(result_sha256=sha(OUTPUT / 'control.dtb'), revision=revision)
    provenance['cpu_placeholder_fix' if revision == 2 else 'radio_identity_fix'] = changed
    (OUTPUT / 'control-provenance.json').write_text(json.dumps(provenance, indent=2) + '\n')
    manifest = json.loads((archive / 'manifest.json').read_text())
    manifest['revision'] = revision
    for name in manifest['files']:
        path = OUTPUT / name
        manifest['files'][name] = {'bytes': path.stat().st_size, 'sha256': sha(path)}
    (OUTPUT / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    verification = {'test': 'AUBS001', 'revision': revision, 'phase': 'built', 'changed_properties': changed,
                    'all_control_cpu_placeholders_valid': True, 'control_cpu_nodes': len(paths),
                    'entire_tree_diff_checked': True,
                    'stage1_unchanged': sha(OUTPUT / 'stage1.bin') == sha(archive / 'stage1.bin'),
                    'stage2_m1n1_unchanged': True, 'uboot_unchanged': True,
                    'native_boot_tested': False, 'boot_sha256': sha(OUTPUT / 'boot.bin')}
    (OUTPUT / ('revision' + str(revision) + '-verification.json')).write_text(json.dumps(verification, indent=2) + '\n')
    print(json.dumps(verification))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--libfdt', required=True, help='Path to the libfdt shared library')
    parser.add_argument('--revision', type=int, choices=[2, 3], default=2)
    args = parser.parse_args()
    main(args.libfdt, args.revision)
