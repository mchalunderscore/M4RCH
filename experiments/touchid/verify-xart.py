#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Check actual output of Aurora's read-only inspector before a trial load.

This supplements, but does not replace, the kernel's own APFS ownership and
xART guard. It fails closed when the inspector only prints a partial analysis.
"""
import ast
import re
import subprocess
import sys

INSPECTOR = '/usr/local/libexec/m4rch-apfs-xart-inspect'
DEVICE = '/dev/nvme0n1p1'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def main():
    result = subprocess.run([sys.executable, INSPECTOR, DEVICE], capture_output=True,
                            text=True, timeout=90, check=False)
    require(result.returncode == 0, 'Aurora inspector could not validate the container')
    lines = result.stdout.splitlines()
    def unique(prefix):
        matches = [line[len(prefix):] for line in lines if line.startswith(prefix)]
        require(len(matches) == 1, 'missing or ambiguous ' + prefix)
        return matches[0]
    require(sum('role=0x100' in line and line.startswith('volume oid=') for line in lines) == 1,
            'expected one xART volume')
    require(re.search(r'\bsnapshot_count=0 revert_xid=0 revert_sblock=0$',
                      unique('xart_volume_flags=')) is not None,
            'snapshot or revert state is not clear')
    ids = ast.literal_eval(unique('gigalocker_file_ids='))
    require(isinstance(ids, list) and len(ids) == 1, 'expected one gigalocker')
    inode = unique('gigalocker_inode_private_id=')
    match = re.fullmatch(r'(\d+) flags=0x([0-9a-f]+) links=(\d+) write_generation=(\d+)', inode)
    require(match is not None and int(match.group(3)) == 1, 'gigalocker inode is ambiguous')
    private_id = int(match.group(1))
    extents = ast.literal_eval(unique('gigalocker_extents_logical_bytes_physical_blocks_flags='))
    require(isinstance(extents, list) and len(extents) == 1 and len(extents[0]) == 5,
            'expected one gigalocker extent')
    logical, length, physical, flags, crypto = extents[0]
    require(logical == 0 and length == 0x600000 and physical > 0 and flags == 0 and crypto == 0,
            'unexpected or encrypted gigalocker extent')
    reference = ast.literal_eval(unique('gigalocker_extent_reference_block_length_kind_owner_refcount='))
    require(reference == (physical, 1536, 1, private_id, 1), 'gigalocker reference is not exclusive')
    records = ast.literal_eval(unique('gigalocker_records_slot_kind_length_revision_crc_valid='))
    require(isinstance(records, list) and len(records) > 0 and
            all(isinstance(item, tuple) and len(item) == 5 and item[4] is True for item in records),
            'missing or invalid gigalocker records')
    require(len({item[0] for item in records}) == len(records), 'duplicate slot')
    print('One unsnapshotted, exclusive, unencrypted 6 MiB gigalocker extent; all reported record CRCs valid.')
    print('The kernel must independently admit the extent and enforce the xART guard.')


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, SyntaxError, subprocess.TimeoutExpired) as exc:
        print('xART preflight failed:', exc, file=sys.stderr)
        sys.exit(1)
