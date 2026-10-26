#!/usr/bin/env python3
"""Admit the native T6041 boot-framebuffer aperture already in the live DT."""
import argparse
import difflib
from pathlib import Path


def prepare(root, output):
    path = root / 'drivers/gpu/drm/apple/apple_drv.c'
    before = path.read_text()
    old = '\treturn (of_device_is_compatible(dev->of_node, "apple,t8132-display-subsystem") ||'
    # Keep the condition readable and preserve the existing J713 branches.
    new = '\treturn (of_device_is_compatible(dev->of_node, "apple,t6041-display-subsystem") ||\n\t\tof_device_is_compatible(dev->of_node, "apple,t8132-display-subsystem") ||'
    assert before.count(old) == 1
    after = before.replace(old, new).replace(
        ' * The J713 loader describes the boot framebuffer only as a simple-framebuffer\n * node;',
        ' * The J713 and native J614s loaders describe the boot framebuffer only as\n * a simple-framebuffer node;')
    output.mkdir(parents=True, exist_ok=True)
    (output / 'apple_drv.before.c').write_text(before)
    (output / 'kernel-bootfb.patch').write_text(''.join(difflib.unified_diff(
        before.splitlines(True), after.splitlines(True),
        fromfile='a/drivers/gpu/drm/apple/apple_drv.c', tofile='b/drivers/gpu/drm/apple/apple_drv.c')))
    path.write_text(after)
    print('Prepared T6041 boot framebuffer lookup; existing reserved-memory and J713 paths preserved')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('root', type=Path); p.add_argument('output', type=Path)
    a = p.parse_args(); prepare(a.root, a.output)
