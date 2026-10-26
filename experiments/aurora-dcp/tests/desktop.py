#!/usr/bin/env python3
"""Exercise the production J614s register gate and D006 callback wrapper."""
import argparse
from pathlib import Path
import subprocess


def block(text, marker):
    start = text.index(marker); opening = text.index('{', start)
    end = opening + 1; depth = 1
    while depth:
        depth += (text[end] == '{') - (text[end] == '}'); end += 1
    return text[start:end]


def main(root, output):
    apple = root / 'drivers/gpu/drm/apple'
    dcp = (apple / 'dcp.c').read_text()
    start = dcp.rfind('static const struct {', 0, dcp.index('} t6041_dcp_regs'))
    registers = dcp[start:dcp.index('/* Refuse to touch', start)]
    gate = block(dcp, 'static int dcp_validate_t6041_dt(')
    internal = (apple / 'iomfb_internal.h').read_text()
    helper = block(internal, 'static inline bool iomfb_callback_size(')
    wrappers = internal[internal.index('#define TRAMPOLINE_VOID('):internal.index('/* Call a DCP function')]
    header = (apple / 'iomfb_v26_6_desktop.h').read_text()
    req = block(header, 'struct dcp_set_frame_sync_props_req_v26_6_desktop {') + ' __packed;'
    resp = block(header, 'struct dcp_set_frame_sync_props_resp_v26_6_desktop {') + ' __packed;'
    callback = block((apple / 'iomfb_template.c').read_text(),
        'static struct dcp_set_frame_sync_props_resp_v26_6_desktop\ndcpep_cb_set_frame_sync_props(')
    packet = block((apple / 'iomfb.h').read_text(), 'struct dcp_packet_header {') + ' __packed;'
    prefix = r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <errno.h>
typedef uint8_t u8; typedef uint32_t u32; typedef uint64_t u64;
#define __packed __attribute__((packed))
#define __maybe_unused __attribute__((unused))
#define __free(x)
#define ARRAY_SIZE(a) (sizeof(a)/sizeof((a)[0]))
#define IORESOURCE_MEM 0
#define dev_err(...) ((void)0)
#define dev_err_probe(dev, error, ...) (error)
#define trace_iomfb_callback(...) ((void)0)
#define DCP_FIRMWARE_V_26_6_DESKTOP 1
struct device_node { int unused; };
struct device { struct device_node *of_node; };
struct resource { u64 start, size; };
struct platform_device { struct device dev; unsigned num_resources; struct resource r[6]; };
struct apple_dcp { struct device *dev; int fw_compat; bool crashed; };
static bool j614s, piodma_ok=true, iommus_ok=true, mboxes_ok=true;
static int bad_name = -1;
static struct device_node node;
#define to_platform_device(d) ((struct platform_device *)(d))
static bool of_machine_is_compatible(const char *s) { return !strcmp(s,"apple,j614s") && j614s; }
static bool of_device_is_compatible(struct device_node *n, const char *s) { return !strcmp(s,"apple,t6041-dcp"); }
static struct device_node *of_get_child_by_name(struct device_node *n,const char *s) { return piodma_ok?&node:NULL; }
static struct resource *platform_get_resource(struct platform_device *p,int type,int index) { return index<p->num_resources?&p->r[index]:NULL; }
static u64 resource_size(struct resource *r) { return r->size; }
static int of_property_match_string(struct device_node *n,const char *p,const char *name) {
 const char *names[]={"coproc","disp-0","disp-1","disp-2","disp-3","disp-4"};
 for(int i=0;i<6;i++) if(!strcmp(names[i],name))return i==bad_name?-1:i;
 return -1;
}
static bool of_property_present(struct device_node *n,const char *p) { return !strcmp(p,"iommus")?iommus_ok:mboxes_ok; }
'''
    cases = r'''
TRAMPOLINE_INOUT(test_d006, dcpep_cb_set_frame_sync_props,
 struct dcp_set_frame_sync_props_req_v26_6_desktop,
 struct dcp_set_frame_sync_props_resp_v26_6_desktop);
static void register_tests(void) {
 struct platform_device p={.dev.of_node=&node,.num_resources=6,
 .r={{0x402e00000ULL,0x4000},{0x400000000ULL,0x4000000},
     {0x402240000ULL,0x10000},{0x4023a8000ULL,0x4000},
     {0x402800000ULL,0x800000},{0x504800000ULL,0xbc000}}};
 j614s=true; assert(!dcp_validate_t6041_dt(&p.dev));
 for(int i=0;i<6;i++) {
  p.r[i].start^=0x4000; assert(dcp_validate_t6041_dt(&p.dev)==-ENODEV);p.r[i].start^=0x4000;
  p.r[i].size++;assert(dcp_validate_t6041_dt(&p.dev)==-ENODEV);p.r[i].size--;
  bad_name=i;assert(dcp_validate_t6041_dt(&p.dev)==-ENODEV);bad_name=-1;
 }
 p.num_resources=5;assert(dcp_validate_t6041_dt(&p.dev)==-ENODEV);
 j614s=false;assert(!dcp_validate_t6041_dt(&p.dev));
 p.num_resources=6;assert(dcp_validate_t6041_dt(&p.dev)==-ENODEV);
 p.num_resources=5;
 piodma_ok=false;assert(dcp_validate_t6041_dt(&p.dev)==-ENODEV);piodma_ok=true;
 iommus_ok=false;assert(dcp_validate_t6041_dt(&p.dev)==-ENODEV);iommus_ok=true;
 mboxes_ok=false;assert(dcp_validate_t6041_dt(&p.dev)==-ENODEV);mboxes_ok=true;
}
static void callback_tests(void) {
 struct { struct dcp_packet_header h; u8 bytes[256]; } packet;
 struct apple_dcp d={.fw_compat=DCP_FIRMWARE_V_26_6_DESKTOP};
 memset(&packet,0xa5,sizeof(packet));packet.h.in_len=0x54;packet.h.out_len=0x50;
 void *in=packet.bytes,*out=packet.bytes+packet.h.in_len;
 assert(test_d006(&d,6,out,in));assert(!d.crashed);
 assert(!memcmp(out,in,73));for(int i=73;i<76;i++)assert(((u8*)out)[i]==0);
 assert(((u8*)out)[76]==0xa5 && ((u8*)out)[0x50]==0xa5);
 for(int short_input=0;short_input<2;short_input++) {
  memset(&packet,0xa5,sizeof(packet));packet.h.in_len=short_input?0x53:0x54;
  packet.h.out_len=short_input?0x50:0x4f;d.crashed=false;
  out=packet.bytes+packet.h.in_len;
  assert(!test_d006(&d,6,out,in));assert(d.crashed);
  for(int i=0;i<256;i++)assert(packet.bytes[i]==0xa5);
 }
 packet.h.in_len=0x58;packet.h.out_len=0x54;d.crashed=false;
 assert(test_d006(&d,6,packet.bytes+packet.h.in_len,in));assert(!d.crashed);
 d.fw_compat=0;packet.h.in_len=packet.h.out_len=0;
 assert(iomfb_callback_size(&d,in,0x54,0x50));
}
int main(void) { register_tests();callback_tests();puts("Desktop production tests PASS: J614s/J616s windows, malformed resources, D006 echo/padding and truncated callback refusal"); }
'''
    output.mkdir(parents=True, exist_ok=True)
    unit = output / 'desktop.c'; unit.write_text('\n'.join([prefix, packet, helper, wrappers, registers, gate, req, resp, callback, cases]))
    exe = output / 'desktop-test'
    subprocess.run(['clang', '-g', '-O1', '-fsanitize=address,undefined', '-fno-omit-frame-pointer',
                    str(unit), '-o', str(exe)], check=True)
    subprocess.run([str(exe)], check=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('root', type=Path); p.add_argument('output', type=Path)
    a = p.parse_args(); main(a.root, a.output)
