#!/usr/bin/env python3
"""Exercise the actual kernel timing parser under ASan/UBSan, without hardware."""
import argparse
from pathlib import Path
import struct
import subprocess


def encode(value):
    def obj(value):
        if isinstance(value, bool): return struct.pack('<I', 11 << 24 | value)
        if isinstance(value, int): return struct.pack('<IQ', 4 << 24 | 64, value)
        if isinstance(value, str): return struct.pack('<I', 9 << 24 | len(value)) + value.encode()
        if isinstance(value, list): children = value; tag = 2 << 24 | len(value)
        else:
            children = [item for pair in value.items() for item in pair]; tag = 1 << 24 | len(value)
        result = struct.pack('<I', tag)
        for child in children:
            result += bytes((-len(result)) & 3) + obj(child)
        return result
    return struct.pack('<I', 0xd3) + obj(value)


def mode(hz, identity):
    def axis(active, front, sync, back, rate):
        return dict(Active=active, Total=active+front+sync+back, FrontPorch=front,
                    SyncWidth=sync, BackPorch=back, PreciseSyncRate=rate,
                    SyncPolarity=1, PixelRepetition=0)
    return dict(ID=identity, IsVirtual=False, IsInterlaced=False, IsSplit=False,
        HorizontalAttributes=axis(3024,16,32,28,hz*2000*65536//1000),
        VerticalAttributes=axis(1964,10,8,18,hz*65536),
        ColorModes=[dict(ID=71,Depth=10,PixelEncoding=0,DynamicRange=0,EOTF=0),
                    dict(ID=93,Depth=8,PixelEncoding=0,DynamicRange=0,EOTF=0)])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('kernel', type=Path)
    parser.add_argument('work', type=Path)
    args = parser.parse_args(); work=args.work; work.mkdir(parents=True,exist_ok=True)
    stubs = work/'include/linux'; stubs.mkdir(parents=True,exist_ok=True)
    headers = {
      'types.h': '#include <stdint.h>\n#include <stdbool.h>\ntypedef uint8_t u8; typedef uint16_t u16; typedef uint32_t u32; typedef uint64_t u64;\n#define IS_ENABLED(x) 1\n',
      'of.h': '#include <string.h>\nstatic inline int of_machine_is_compatible(const char *s) { return !strcmp(s,"apple,j614s"); }\n',
      'errno.h': '#define EINVAL 22\n#define E2BIG 7\n#define ENOENT 2\n#define ENOMEM 12\n',
      'limits.h': '#define U32_MAX UINT32_MAX\n#define U64_MAX UINT64_MAX\n',
      'string.h': '#include <string.h>\n',
      'slab.h': '#include <stdlib.h>\n#define GFP_KERNEL 0\n#define kzalloc(s,f) calloc(1,s)\n#define kfree(p) free(p)\n',
      'unaligned.h': '#include <stdint.h>\n#include <string.h>\nstatic inline uint32_t get_unaligned_le32(const void *p) { uint32_t v; memcpy(&v,p,4); return v; }\nstatic inline uint64_t get_unaligned_le64(const void *p) { uint64_t v; memcpy(&v,p,8); return v; }\n',
    }
    for name,data in headers.items(): (stubs/name).write_text('#pragma once\n'+data)
    (work/'valid.bin').write_bytes(encode([mode(120,19),mode(60,42)]))
    bad=mode(60,42); bad['HorizontalAttributes']['PreciseSyncRate']//=1000
    (work/'wrong-units.bin').write_bytes(encode([bad]))
    bad=mode(60,42); bad['HorizontalAttributes']['Total']+=1
    (work/'wrong-porches.bin').write_bytes(encode([bad]))
    bad=mode(60,42); bad['IsVirtual']=True
    (work/'virtual.bin').write_bytes(encode([bad]))
    bad=mode(60,42); bad['VerticalAttributes']['Active']=1664
    (work/'foreign-panel.bin').write_bytes(encode([bad]))
    (work/'test.c').write_text(r'''
#include <stdio.h>
#include <assert.h>
#include "dcp-m4-timing.h"
int main(int argc, char **argv) {
    unsigned char buffer[65536]; struct dcp_m4_timing timing;
    for (int i=1; i<argc; i++) {
        FILE *f=fopen(argv[i],"rb"); assert(f);
        size_t n=fread(buffer,1,sizeof(buffer),f); assert(!ferror(f)); fclose(f);
        int ret=dcp_m4_parse_timing(buffer,n,&timing);
        if(i==1) {
            assert(!ret && timing.id==42 && timing.color_id==93);
            assert(timing.hdisplay==3024 && timing.vdisplay==1964 && timing.clock_khz==372000);
            for(size_t cut=0; cut<n; cut++) assert(dcp_m4_parse_timing(buffer,cut,&timing)<0);
        } else assert(ret<0);
    }
    puts("Timing parser: physical panel, variable IDs, Hz/kHz conversion, color selection and malformed/truncated catalogs PASS");
}
''')
    subprocess.run(['clang','-g','-O1','-fsanitize=address,undefined','-fno-omit-frame-pointer',
       '-I'+str(work/'include'),'-I'+str(args.kernel/'drivers/gpu/drm/apple'),str(work/'test.c'),'-o',str(work/'test')],check=True)
    subprocess.run([str(work/'test'),*[str(work/name) for name in ['valid.bin','wrong-units.bin','wrong-porches.bin','virtual.bin','foreign-panel.bin']]],check=True)

if __name__=='__main__': main()
