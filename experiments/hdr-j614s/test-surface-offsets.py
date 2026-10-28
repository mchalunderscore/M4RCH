#!/usr/bin/env python3
"""Check the actual DCP surface layout against the 25G83 firmware audit."""
from pathlib import Path
import subprocess
import sys
import tempfile

root = Path(__file__).resolve().parents[2]
source = Path(sys.argv[1]) if len(sys.argv) > 1 else root / 'out/hdr-candidate/source'
header = (source / 'drivers/gpu/drm/apple/iomfb_plane.h').read_text()
header = header.replace('#include <drm/drm_fourcc.h>', '')
header = header.replace('#include <linux/types.h>', '')
prefix = '''#include <stdint.h>
#include <stddef.h>
typedef uint8_t u8;
typedef uint16_t u16;
typedef uint32_t u32;
typedef uint64_t u64;
#define __packed __attribute__((packed))
#define fourcc_code(a,b,c,d) ((a) | ((b) << 8) | ((c) << 16) | ((d) << 24))
'''
checks = '''
_Static_assert(sizeof(struct dcp_surface) == 0x1fd, "surface size");
_Static_assert(offsetof(struct dcp_surface, xfer_func) + 0x10 == 0x23, "firmware transfer offset");
_Static_assert(offsetof(struct dcp_surface, colorspace) + 0x10 == 0x24, "firmware colorspace offset");
_Static_assert(offsetof(struct dcp_surface, unk_num) + 0x10 == 0x205, "firmware numerator offset");
_Static_assert(offsetof(struct dcp_surface, unk_denom) + 0x10 == 0x209, "firmware denominator offset");
int main(void) { return 0; }
'''
with tempfile.TemporaryDirectory(prefix='m4rch-dcp-layout-') as tmp:
    source = Path(tmp) / 'layout.c'
    source.write_text(prefix + header + checks)
    subprocess.run(['cc', '-std=c11', '-Wall', '-Werror', '-fsyntax-only', str(source)], check=True)
print('DCP surface layout matches the audited firmware offsets')
