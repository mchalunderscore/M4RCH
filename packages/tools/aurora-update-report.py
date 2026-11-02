#!/usr/bin/env python3
"""Compare installed Aurora components with the locally synced package database."""
import subprocess
import sys

# One row per source/recipe family; related split packages are updated together.
FAMILIES = (
    ('Aura', ('aura',), 'fork recipe'),
    ('U-Boot', ('uboot-aurora',), 'fork recipe'),
    ('Kernel', ('linux-aurora', 'linux-aurora-headers'), 'fork recipe'),
    ('Mesa', ('mesa-aurora', 'vulkan-aurora', 'opencl-rusticl-aurora', 'vulkan-lavapipe-aurora'), 'fork recipes'),
    ('ALSA UCM', ('alsa-ucm-conf-aurora',), 'fork recipe'),
    ('Touch ID', ('aurora-sep', 'libfprint-aurora', 'fprintd-aurora'), 'stock; review SEP changes'),
    ('Speaker protection', ('speakerguardd',), 'stock; review hardware support'),
    ('Audio', ('aurora-audio',), 'fork recipe'),
    ('System', ('aurora-system-fixes', 'upower-aurora'), 'stock; review changes'),
)

def run(*args):
    return subprocess.run(args, text=True, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, check=False)

def version(package, database):
    result = run('pacman', '-Q' if database == 'installed' else '-Si', package)
    if result.returncode:
        return None
    if database == 'installed':
        fields = result.stdout.strip().split(maxsplit=1)
        return fields[1] if len(fields) == 2 else None
    for line in result.stdout.splitlines():
        key, separator, value = line.partition(':')
        if separator and key.strip() == 'Version':
            return value.strip()
    return None

def main():
    held = run('pacman-conf', 'IgnorePkg')
    if held.returncode:
        sys.exit('Cannot read pacman IgnorePkg configuration: ' + held.stderr.strip())
    ignored = set(held.stdout.split())
    print('Comparing against locally synced pacman databases; refresh them separately when needed.\n')
    for family, packages, workflow in FAMILIES:
        print(f'{family} ({workflow}):')
        for package in packages:
            installed = version(package, 'installed')
            upstream = version(package, 'repo')
            if not installed:
                continue
            if not upstream:
                state = 'not found in sync databases'
            else:
                compared = run('vercmp', upstream, installed)
                if compared.returncode:
                    sys.exit(f'vercmp failed for {package}: {compared.stderr.strip()}')
                relation = int(compared.stdout.strip())
                state = 'UPDATE AVAILABLE' if relation > 0 else ('local build ahead' if relation < 0 else 'matches')
            suffix = ' [held]' if package in ignored else ''
            print(f'  {package}: installed {installed}; repo {upstream or "unavailable"}; {state}{suffix}')
        print()
    print('Review the Aurora ALARM fork, upstream changes and source pins before building updates.')
    print('Boot components require coordinated review and hardware qualification.')

if __name__ == '__main__':
    main()
