#!/usr/bin/env python3
"""Prepare the explicitly enabled J614s GPU experiment against pinned Aurora."""
import argparse
import difflib
from pathlib import Path


def prepare(root, output):
    output.mkdir(parents=True, exist_ok=True)
    changes = {
        'drivers/gpu/drm/asahi/asahi_core.rs': (
            '        compute_preempt: i32 {',
            '''        t6040_16core: u32 {
            default: 0,
            description: "Experimental J614s 16-core T6040 full rendering (0: strict upstream layout)",
        },
        compute_preempt: i32 {'''),
        'drivers/gpu/drm/asahi/g17/mod.rs': (
            '''        let active_cores = id.core_masks.iter().map(|mask| mask.count_ones()).sum();
        if cfg''',
            '''        let active_cores = id.core_masks.iter().map(|mask| mask.count_ones()).sum();
        // Same physical two-by-ten topology as T6040, with two fused cores per
        // cluster. Keep the existing physical-slot buffers as an experimental
        // hypothesis; their use on this SKU still requires native rendering.
        let experimental_16core = crate::module_parameters::t6040_16core.value() == 1
            && cfg.chip_id == 0x6040
            && id.num_dies == 1
            && id.num_clusters == 2
            && id.num_cores == 10
            && active_cores == 16
            && id.core_masks.as_slice() == &[0x3db, 0x3db];
        if experimental_16core {
            dev_warn!(dev.as_ref(),
                "Experimental J614s 16-core T6040: two-by-ten physical-slot buffers; full rendering enabled\\n");
        }
        if cfg'''),
    }
    patch = []
    for name, (old, new) in changes.items():
        path = root / name
        text = path.read_text()
        original = text
        if new not in text:
            if text.count(old) != 1:
                raise ValueError('Pinned source context differs: ' + name)
            text = text.replace(old, new, 1)
        if name.endswith('g17/mod.rs'):
            old_guard = '.is_some_and(|cores| cores != (id.num_clusters, active_cores))\n        {'
            new_guard = '.is_some_and(|cores| cores != (id.num_clusters, active_cores))\n            && !experimental_16core\n        {'
            if new_guard not in text:
                if text.count(old_guard) != 1:
                    raise ValueError('Layout guard differs')
                text = text.replace(old_guard, new_guard, 1)
        if text != original:
            patch.extend(difflib.unified_diff(original.splitlines(True), text.splitlines(True),
                                             fromfile='a/' + name, tofile='b/' + name))
            path.write_text(text)
    if patch:
        (output / 'gpu16.patch').write_text(''.join(patch))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    prepare(args.root, args.output)
