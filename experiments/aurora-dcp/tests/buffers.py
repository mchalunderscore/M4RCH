#!/usr/bin/env python3
"""Exercise production retained allocation and descriptor callbacks with sanitizers."""
import argparse
from pathlib import Path
import subprocess
from desktop import block


def main(root, out):
    out.mkdir(parents=True, exist_ok=True)
    apple = root / 'drivers/gpu/drm/apple'
    dcp = (apple / 'dcp.c').read_text()
    template = (apple / 'iomfb_template.c').read_text()
    prefix = r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
typedef uint8_t u8; typedef uint32_t u32; typedef uint64_t u64;
typedef u64 dma_addr_t; typedef long ssize_t;
#define GFP_KERNEL 0
#define DCP_FIRMWARE_V_26_6_DESKTOP 266
#define SZ_16K 16384ul
#define DCP_MAX_MAPPINGS 8
#define ARRAY_SIZE(a) (sizeof(a)/sizeof((a)[0]))
#define ARRAY_SIZEOF(a) ARRAY_SIZE(a)
#define ALIGN(v,a) (((v)+(a)-1)&~((a)-1))
#define round_down(v,a) ((v)&~((a)-1))
#define check_add_overflow(a,b,c) __builtin_add_overflow(a,b,c)
#define DCP_FW_NAME(n) n
#define DCP_FW_VER 266
#define DCP_FW_H17(v) 0
#define DCP_FW_DESKTOP_26(v) 1
#define IOMMU_READ 1
#define IOMMU_WRITE 2
#define DMA_BIDIRECTIONAL 0
#define ERR_PTR(n) ((void *)(intptr_t)(n))
#define PTR_ERR(p) ((long)(intptr_t)(p))
#define IS_ERR(p) ((uintptr_t)(p)>=(uintptr_t)-4095)
#define dev_err(...) ((void)0)
#define dev_info(...) ((void)0)
#define dev_warn(...) ((void)0)
struct device_node {int unused;};
struct device {struct device_node *of_node;};
struct platform_device {struct device dev;};
struct sg_table {void *sgl;};
'''
    descriptor = block((apple / 'dcp-internal.h').read_text(), 'struct dcp_mem_descriptor {') + ';\n'
    shim = r'''
struct apple_dcp {
 struct device *dev; unsigned fw_compat; bool retain_dma;
 struct platform_device *piodma; void *iommu_dom;
 struct dcp_mem_descriptor memdesc[DCP_MAX_MAPPINGS]; unsigned long memdesc_map[1];
};
struct dcp_allocate_buffer_req {u64 size;};
struct dcp_allocate_buffer_resp {u64 mem_desc_id,dva_size,dva;};
struct dcp_map_buf_req {u64 buffer;};
struct dcp_map_buf_resp {u64 buffer,dva;int ret;};
struct dcp_unmap_buf_resp {u64 buffer,dva;};
static bool native=true,marker=true;
static unsigned generic_alloc,retained_alloc,generic_free,shared_alloc,shared_map,sg_alloc,sg_free,unmaps;
static int retained_error,shared_error,map_error;
static u8 payload[16384];
static bool j614s_display_board(void) {return native;}
static bool of_property_read_bool(struct device_node *n,const char *p) {return marker;}
static void *dma_alloc_coherent(struct device *d,size_t s,dma_addr_t *a,int g) {
 generic_alloc++;if(native)return NULL;*a=0x1000;return payload;
}
static void dma_free_coherent(struct device *d,size_t s,void *b,dma_addr_t a) {generic_free++;}
static void *apple_dart_dcp_alloc(struct device *d,size_t s,dma_addr_t *a) {
 retained_alloc++;if(retained_error)return ERR_PTR(retained_error);*a=0x10002000000ULL;return payload;
}
static int apple_dart_dcp_shared_alloc(struct device *d,struct device *p,size_t s,u64 *phys,u64 *dva) {
 shared_alloc++;assert(s==SZ_16K);if(shared_error)return shared_error;
 *phys=0x10100000000ULL;*dva=0x10004000000ULL;return 0;
}
static int apple_dart_dcp_shared_map(struct device *d,struct device *p,u64 phys,u64 dva,size_t size) {
 shared_map++;assert(phys==0x10100000000ULL&&dva==0x10004000000ULL&&size==SZ_16K);return map_error;
}
static unsigned find_first_zero_bit(unsigned long *b,unsigned n) {for(unsigned i=0;i<n;i++)if(!(*b&(1ul<<i)))return i;return n;}
static bool test_bit(unsigned n,unsigned long *b) {return (*b&(1ul<<n))!=0;}
static void set_bit(unsigned n,unsigned long *b) {*b|=1ul<<n;}
static void clear_bit(unsigned n,unsigned long *b) {*b&=~(1ul<<n);}
static int dma_get_sgtable(struct device *d,struct sg_table *t,void *b,u64 a,size_t s) {sg_alloc++;t->sgl=payload;return 0;}
static void sg_free_table(struct sg_table *t) {sg_free++;}
static ssize_t iommu_map_sgtable(void *d,u64 a,struct sg_table *t,int prot) {return SZ_16K;}
static size_t iommu_unmap(void *d,u64 a,size_t s) {unmaps++;return s;}
static void dma_unmap_resource(struct device *d,u64 a,size_t s,int dir,int flags) {unmaps++;}
'''
    markers = ['static bool dcp_j614s_desktop_live(', 'bool dcp_uses_retained_dma(',
               'void *dcp_alloc_dma(', 'void dcp_free_dma(']
    production = '\n'.join(block(dcp, m) for m in markers)
    markers = ['static bool dcpep_map_piodma(', 'static bool dcpep_unmap_piodma(',
               'static struct dcp_allocate_buffer_resp\ndcpep_cb_allocate_buffer(',
               'static u8 dcpep_cb_release_mem_desc(']
    production += '\n' + '\n'.join(block(template, m) for m in markers)
    checks = r'''
int main(void) {
 struct device dev={0};struct platform_device pi={0};
 struct apple_dcp d={.dev=&dev,.fw_compat=266,.retain_dma=true,.piodma=&pi,.iommu_dom=&pi};
 dma_addr_t dva=0;
 assert(dcp_alloc_dma(&d,16384,&dva)==payload&&dva==0x10002000000ULL);
 assert(retained_alloc==1&&!generic_alloc);
 dcp_free_dma(&d,16384,payload,dva);assert(!generic_free);
 d.retain_dma=false;assert(!dcp_alloc_dma(&d,16384,&dva)&&retained_alloc==1&&!generic_alloc);
 d.retain_dma=true;retained_error=-ENOSPC;assert(!dcp_alloc_dma(&d,16384,&dva)&&!generic_alloc);
 retained_error=-ENODEV;assert(!dcp_alloc_dma(&d,16384,&dva)&&!generic_alloc);retained_error=0;
 native=false;assert(dcp_alloc_dma(&d,16384,&dva)==payload&&generic_alloc==1);
 dcp_free_dma(&d,16384,payload,dva);assert(generic_free==1);native=true;
 marker=false;assert(!dcp_uses_retained_dma(&d));marker=true;
 d.fw_compat=12;assert(!dcp_uses_retained_dma(&d));d.fw_compat=266;
 struct dcp_allocate_buffer_req req={.size=1367};
 struct dcp_allocate_buffer_resp a=dcpep_cb_allocate_buffer(&d,&req);
 assert(a.dva==0x10004000000ULL&&a.dva_size==4096&&a.mem_desc_id==0);
 assert(d.memdesc[0].retained_shared&&!d.memdesc[0].buf&&!d.memdesc[0].map.sgl);
 assert(shared_alloc==1&&!sg_alloc&&generic_alloc==1);
 struct dcp_map_buf_req m={.buffer=0};struct dcp_map_buf_resp resp={0};
 map_error=-EIO;assert(!dcpep_map_piodma(&d,&m,&resp)&&!d.memdesc[0].piodma_mapped);
 map_error=0;assert(dcpep_map_piodma(&d,&m,&resp));assert(shared_map==2&&resp.dva==a.dva&&resp.buffer==0);
 assert(dcpep_map_piodma(&d,&m,&resp)&&shared_map==2);
 struct dcp_unmap_buf_resp u={.buffer=0,.dva=a.dva+16384};
 assert(!dcpep_unmap_piodma(&d,&u));u.dva=a.dva;assert(dcpep_unmap_piodma(&d,&u));
 assert(!unmaps&&d.memdesc[0].piodma_mapped);
 u32 id=0;dcpep_cb_release_mem_desc(&d,&id);
 assert(!test_bit(0,d.memdesc_map)&&!d.memdesc[0].retained_shared&&!unmaps&&!sg_free&&generic_free==1);
 assert(!dcpep_map_piodma(&d,&m,&resp)&&!dcpep_unmap_piodma(&d,&u));
 shared_error=-ENOSPC;a=dcpep_cb_allocate_buffer(&d,&req);assert(!a.dva&&!test_bit(0,d.memdesc_map));shared_error=0;
 unsigned n=shared_alloc;d.piodma=NULL;a=dcpep_cb_allocate_buffer(&d,&req);assert(!a.dva&&shared_alloc==n);d.piodma=&pi;
 req.size=0;a=dcpep_cb_allocate_buffer(&d,&req);assert(!a.dva&&shared_alloc==n);
 req.size=UINT64_MAX;a=dcpep_cb_allocate_buffer(&d,&req);assert(!a.dva&&shared_alloc==n);
 req.size=16384;*d.memdesc_map=255;a=dcpep_cb_allocate_buffer(&d,&req);assert(!a.dva&&shared_alloc==n);
 *d.memdesc_map=0;native=false;a=dcpep_cb_allocate_buffer(&d,&req);
 assert(a.dva==0x1000&&sg_alloc==1&&!d.memdesc[0].retained_shared);
 assert(dcpep_map_piodma(&d,&m,&resp));dcpep_cb_release_mem_desc(&d,&id);
 assert(sg_free==1&&generic_free==2&&!test_bit(0,d.memdesc_map));
 puts("Retained-buffer production tests PASS");
}
'''
    src = out / 'buffers.c'; src.write_text(prefix + descriptor + shim + production + checks)
    subprocess.run(['clang-19','-std=gnu11','-g','-fsanitize=address,undefined','-fno-omit-frame-pointer',
                    '-Werror=implicit-function-declaration',str(src),'-o',str(out/'buffers')],check=True)
    subprocess.run([str(out/'buffers')],check=True)
    # r8's actual allocation path cannot serve a host buffer on this reserved SID23.
    original = (apple / 'dcp.c').read_text()
    old = Path('/project/out/aurora-dcp/shared-r8/dcp.c').read_text()
    assert 'dma_alloc_coherent(dcp->dev, bfr->size,' in old
    assert 'bfr->buffer = dcp_alloc_dma(dcp, bfr->size, &bfr->iova);' in original
    assert 'if (READ_ONCE(ep->compact))' in (apple/'afk.c').read_text()
    print('Retained-buffer allocator coverage PASS: RTKit, AFK ring, EPIC fallback, IOMFB, paired descriptors')
    # Compile the actual r8 host-allocation branch against the same reserved
    # SID23 fixture: it must reproduce ENOMEM rather than pass this regression.
    start = old.index('\t\tbfr->buffer = dma_alloc_coherent(dcp->dev, bfr->size,')
    end = old.index('\n\t}', start)
    negative = prefix + descriptor + shim + '''
struct apple_rtkit_shmem {size_t size;dma_addr_t iova;void *buffer;};
static int original_host_alloc(struct apple_dcp *dcp, struct apple_rtkit_shmem *bfr) {
''' + old[start:end] + '''
return 0;
}
int main(void) {
 struct device dev={0};struct apple_dcp dcp={.dev=&dev};
 struct apple_rtkit_shmem bfr={.size=0x4000};
 assert(original_host_alloc(&dcp,&bfr)==-ENOMEM&&!bfr.buffer);
 puts("Original r8 host-allocation negative control PASS: reproduces ENOMEM");
}
'''
    src = out/'original.c';src.write_text(negative)
    subprocess.run(['clang-19','-std=gnu11','-g','-fsanitize=address,undefined',str(src),'-o',str(out/'original')],check=True)
    subprocess.run([str(out/'original')],check=True)


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('root',type=Path);p.add_argument('out',type=Path)
    a=p.parse_args();main(a.root,a.out)
