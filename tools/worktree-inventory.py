#!/usr/bin/env python3
"""Read-only grouping of the current Git worktree for project cleanup."""
import argparse
import collections
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def group(path, state):
    if state == 'D' and (path.startswith(('experiments/', 'sdboot/', 'scripts/', 'tests/', 'packages/legacy/')) or path in ('Makefile.legacy', 'README.legacy.md')):
        return 'retired tracked workflows and tests'
    if path.startswith(('experiments/external-display/', 'experiments/vrr-', 'experiments/hdr-', 'patches/experimental-j614s-hdr', 'patches/j614s-hdr', 'patches/uboot-j614s')):
        return 'display and boot experiments'
    if path.startswith(('experiments/power-profiles/', 'packages/power-profiles-daemon-m4rch/')):
        return 'power profiles'
    if path.startswith(('experiments/speaker-safety/', 'packages/alsa-ucm-conf-m4rch/', 'packages/asahi-scripts-m4rch/')):
        return 'audio and platform configuration'
    if path.startswith(('packages/steam-m4rch/', 'packages/muvm-m4rch/', 'packages/fex-', 'packages/proton-arm64-sme/', 'packages/virglrenderer-m4rch/', 'packages/mesa-', 'packages/tools/', 'patches/linux-asahi-', 'tools/steam-', 'tools/gpu-', 'tests/test-asahi-')):
        return 'graphics, Steam, emulation and package tooling'
    if path.startswith(('packages/mbpfan-m4rch/', 'patches/experimental-aurora-pr512-fan', 'patches/experimental-j614s-fan', 'tools/suspend-')):
        return 'fan and sleep work'
    if path.startswith(('docs/', 'README', 'HANDOVER', 'THIRD_PARTY')):
        return 'documentation and provenance'
    if path.startswith(('investigate/', 'patches/diagnostics/')):
        return 'local diagnostics and private review'
    return 'other changes'


def inventory():
    output = subprocess.check_output(['git', '-C', str(ROOT), 'status', '--porcelain=v1', '-z', '--untracked-files=all', '--no-renames'])
    result = collections.defaultdict(list)
    for raw in output.split(b'\0'):
        if not raw:
            continue
        line = raw.decode('utf-8', 'surrogateescape')
        status, path = line[:2], line[3:]
        category = group(path, status.strip())
        result[category].append({'status': status, 'path': path})
    return {name: sorted(items, key=lambda x: x['path']) for name, items in sorted(result.items())}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--json', action='store_true', help='Print the grouped paths as JSON')
    args = parser.parse_args()
    groups = inventory()
    if args.json:
        print(json.dumps(groups, indent=2, ensure_ascii=True))
        return
    for name, entries in groups.items():
        counts = collections.Counter(item['status'].strip() for item in entries)
        detail = ', '.join(f'{status}: {count}' for status, count in sorted(counts.items()))
        print(f'{name}: {len(entries)} ({detail})')
    print(f'Total: {sum(map(len, groups.values()))}; ignored files and Git history are not included.')


if __name__ == '__main__':
    main()
