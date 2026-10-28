#!/usr/bin/env python3
"""Compile and exercise the paired parameter handlers without a VM or GPU.

Arguments are the patched Mesa and virglrenderer source directories.
"""
from pathlib import Path
import argparse
import subprocess
import tempfile


def function(path, name):
    source = path.read_text()
    start = source.index('\n' + name + '(') + 1
    opening = source.index('{', start)
    depth = 1
    end = opening + 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return 'static int\n' + source[start:end] + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mesa', type=Path)
    parser.add_argument('virgl', type=Path)
    args = parser.parse_args()
    mesa, virgl = args.mesa.resolve(), args.virgl.resolve()
    code = r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <errno.h>
#include "drm_hw.h"
#include "asahi_proto.h"
static union { uint64_t align; uint8_t bytes[4096]; } storage;
static unsigned calls;
struct drm_context { int fd; };
struct asahi_context { int unused; };
static struct asahi_context *to_asahi_context(struct drm_context *ctx) {
    static struct asahi_context a; (void)ctx; return &a;
}
static void *asahi_context_rsp(struct asahi_context *ctx,
    struct vdrm_ccmd_req *hdr, unsigned size) {
    (void)ctx; (void)hdr; assert(size <= sizeof(storage)); return &storage;
}
static int drmIoctl(int fd, unsigned long cmd, void *arg) {
    (void)fd; assert(cmd == DRM_IOCTL_ASAHI_GET_PARAMS); calls++;
    struct drm_asahi_get_params *p = arg;
    struct asahi_ccmd_get_params_rsp *rsp = (void *)&storage;
    assert(p->pointer == (uintptr_t)rsp->payload);
    if (p->param_group == DRM_ASAHI_PARAM_GROUP_VM_STATUS) {
        struct drm_asahi_vm_status *s = (void *)(uintptr_t)p->pointer;
        assert(s->vm_id == 42); s->error = -EIO;
    } else if (p->param_group == DRM_ASAHI_PARAM_GROUP_QUEUE_LIMITS) {
        struct drm_asahi_queue_limits *l = (void *)(uintptr_t)p->pointer;
        assert(!l->max_queues); l->max_queues = 8; l->max_in_flight_per_queue = 16;
    }
    return 0;
}
'''
    code += function(virgl/'src/drm/asahi/asahi_renderer.c', 'asahi_ccmd_get_params')
    code += r'''
struct vdrm_device { struct { unsigned wire_format_version; } caps; };
struct agx_device { struct vdrm_device *vdrm; };
static void *vdrm_alloc_rsp(struct vdrm_device *dev,
    struct vdrm_ccmd_req *req, uint32_t size) {
    (void)dev; (void)req; assert(size <= sizeof(storage));
    memset(&storage, 0xa5, sizeof(storage)); return &storage;
}
static int vdrm_send_req(struct vdrm_device *dev, struct vdrm_ccmd_req *req, bool sync) {
    (void)dev; assert(sync);
    struct drm_context ctx = {0};
    assert(((struct asahi_ccmd_get_params_req *)req)->params.pointer == 0);
    return asahi_ccmd_get_params(&ctx, req);
}
'''
    code += function(mesa/'src/asahi/lib/agx_device_virtio.c', 'agx_virtio_query_params')
    code += r'''
int main(void) {
    struct vdrm_device v = {.caps.wire_format_version = 3};
    struct agx_device dev = {.vdrm = &v};
    struct drm_asahi_vm_status status = {.vm_id = 42};
    struct drm_asahi_get_params q = {.param_group = DRM_ASAHI_PARAM_GROUP_VM_STATUS,
        .pointer = (uintptr_t)&status, .size = sizeof(status)};
    assert(agx_virtio_query_params(&dev, &q) == 0);
    assert(status.vm_id == 42 && status.error == -EIO && calls == 1);
    struct drm_asahi_queue_limits limits = {0};
    q = (struct drm_asahi_get_params){.param_group = DRM_ASAHI_PARAM_GROUP_QUEUE_LIMITS,
        .pointer = (uintptr_t)&limits, .size = sizeof(limits)};
    assert(agx_virtio_query_params(&dev, &q) == 0);
    assert(limits.max_queues == 8 && limits.max_in_flight_per_queue == 16);
    v.caps.wire_format_version = 2;
    assert(agx_virtio_query_params(&dev, &q) == -EOPNOTSUPP && calls == 2);
    v.caps.wire_format_version = 3;
    q.param_group = DRM_ASAHI_PARAM_GROUP_VM_STATUS_MIRROR;
    assert(agx_virtio_query_params(&dev, &q) == -EOPNOTSUPP);
    q.param_group = DRM_ASAHI_PARAM_GROUP_VM_STATUS;
    q.size = UINT32_MAX;
    assert(agx_virtio_query_params(&dev, &q) == -EINVAL);
    struct drm_context ctx = {0};
    struct asahi_ccmd_get_params_req req = {.hdr.len = sizeof(req),
        .params = {.param_group = DRM_ASAHI_PARAM_GROUP_VM_STATUS,
                   .size = sizeof(status), .pointer = UINT64_MAX}};
    assert(asahi_ccmd_get_params(&ctx, &req.hdr) == -EINVAL); /* missing input */
    req.params.param_group = 0;
    req.params.size = UINT32_MAX;
    assert(asahi_ccmd_get_params(&ctx, &req.hdr) == -EINVAL);
    req.params.param_group = DRM_ASAHI_PARAM_GROUP_VM_STATUS_MIRROR;
    req.params.size = sizeof(status);
    assert(asahi_ccmd_get_params(&ctx, &req.hdr) == -EINVAL);
    assert(calls == 2);
    puts("PASS: queue limits, VM error round trip, old host rejection, bounds and pointer isolation");
}
'''
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory)
        (path/'test.c').write_text(code)
        subprocess.run(['cc', '-std=gnu11', '-Wall', '-Werror',
                        '-I'+str(mesa/'src/virtio/virtio-gpu'),
                        '-I'+str(virgl/'src/drm/asahi'), '-I'+str(virgl/'src/drm'),
                        str(path/'test.c'), '-o', str(path/'test')], check=True)
        subprocess.run([str(path/'test')], check=True)


if __name__ == '__main__':
    main()
