#!/usr/bin/env python3
"""Opt-in J614s firmware-catalog modes and experimental A413 switching."""
import argparse
import difflib
from pathlib import Path


def prepare(root, output):
    originals = {}
    def edit(name, old, new):
        p = root/'drivers/gpu/drm/apple'/name
        text = p.read_text(); originals.setdefault(name, text)
        assert text.count(old) == 1, (name, old[:80])
        p.write_text(text.replace(old, new))
    # Reuse every geometry/color validation from the original physical parser.
    edit('j614s-timing.h', 'static inline int j614s_parse_timing(const struct dcp_m4_timing_parser *p,\n\t\tstruct dcp_m4_timing *out)',
         'static inline int j614s_parse_catalog(const struct dcp_m4_timing_parser *p,\n\t\tstruct dcp_m4_timing *out, unsigned int capacity, unsigned int *count)')
    edit('j614s-timing.h', '\tu64 best = U64_MAX;', '\t*count = 0;')
    edit('j614s-timing.h', '\tu64 clock, score;', '\tu64 clock;')
    edit('j614s-timing.h', '''\t\t/* Prefer the physical 60-Hz SDR mode for the first takeover. */
\t\tscore = v[5] > 60U * 65536 ? v[5] - 60U * 65536 : 60U * 65536 - v[5];
\t\tif (score >= best)
\t\t\tcontinue;
\t\tbest = score;
\t\tfound = true;
\t\t*out = (struct dcp_m4_timing) {''', '''        /* IDs belong to this firmware session; never synthesize a mode. */
        for (unsigned int i = 0; i < *count; i++)
            if (out[i].id == id)
                return -EINVAL;
        if (*count == capacity)
            return -E2BIG;
        found = true;
        out[(*count)++] = (struct dcp_m4_timing) {''')
    p = root/'drivers/gpu/drm/apple/j614s-timing.h'
    p.write_text(p.read_text()+'''
#define J614S_MAX_MODES 32
/* Compatibility entry: retain the old nearest-60 selection without opt-in. */
static inline int j614s_parse_timing(const struct dcp_m4_timing_parser *p,
                                   struct dcp_m4_timing *out)
{
    struct dcp_m4_timing *modes;
    unsigned int count, chosen = 0;
    u64 best = U64_MAX;
    int ret;
    modes = kzalloc(sizeof(*modes) * J614S_MAX_MODES, GFP_KERNEL);
    if (!modes)
        return -ENOMEM;
    ret = j614s_parse_catalog(p, modes, J614S_MAX_MODES, &count);
    if (!ret) {
        for (unsigned int i = 0; i < count; i++) {
            u64 hz = modes[i].refresh_16_16;
            u64 score = hz > 60U * 65536 ? hz - 60U * 65536 : 60U * 65536 - hz;
            if (score < best) { best = score; chosen = i; }
        }
        *out = modes[chosen];
    }
    kfree(modes);
    return ret;
}

static inline int j614s_timing_catalog(const void *data, size_t size,
        struct dcp_m4_timing *out, unsigned int capacity, unsigned int *count)
{
    struct dcp_m4_timing_parser *p;
    int ret;
    if (!data || !out || !count || !capacity || size < 4 || size > (1U << 20) ||
        get_unaligned_le32(data) != 0xd3)
        return -EINVAL;
    *count = 0;
    p = kzalloc(sizeof(*p), GFP_KERNEL);
    if (!p)
        return -ENOMEM;
    p->data = data; p->size = size; p->pos = 4;
    ret = dcp_m4_timing_object(p, 0);
    if (!ret)
        ret = p->pos != size ? -EINVAL : j614s_parse_catalog(p, out, capacity, count);
    if (ret)
        *count = 0;
    kfree(p);
    return ret;
}
''')
    edit('iomfb_m4.c', '#include <linux/completion.h>', '#include <linux/completion.h>\n#include <linux/moduleparam.h>')
    edit('iomfb_m4.c', 'struct iomfb_m4 {', '''/* Experimental, restricted to the already UUID-qualified J614s backend. */
static bool j614s_modeset;
module_param(j614s_modeset, bool, 0400);
MODULE_PARM_DESC(j614s_modeset, "Expose physical J614s SDR modes and attempt A413 switching");

struct iomfb_m4 {''')
    edit('iomfb_m4.c', '\tstruct dcp_m4_timing timing;', '''\tstruct dcp_m4_timing timing;
    struct dcp_m4_timing modes[J614S_MAX_MODES];
    unsigned int mode_count, preferred;
    bool mode_programmed;
    u32 modeset_status;''')
    edit('iomfb_m4.c', '\tret = dcp_m4_runtime_health(r);\n\tif (ret)\n\t\tgoto failed;\n\tsmp_store_release(&r->done, true);', '''    if (j614s_display_board() && j614s_modeset) {
        /* Prefer the complete catalog when firmware publishes it. */
        int all = dcp_m4_raw_slot(r->properties, 0, "TimingElements", false);
        if (all >= 0)
            slot = all;
        ret = j614s_timing_catalog(r->properties->raw[slot].data,
                r->properties->raw[slot].size, r->modes, J614S_MAX_MODES, &r->mode_count);
        if (ret)
            goto failed;
        for (unsigned int i = 0; i < r->mode_count; i++) {
            if (r->modes[i].refresh_16_16 > r->modes[r->preferred].refresh_16_16)
                r->preferred = i;
            dev_info(dev, "J614s catalog mode %u color %u: %ux%u refresh16=%u clock=%u kHz\\n",
                r->modes[i].id, r->modes[i].color_id, r->modes[i].hdisplay,
                r->modes[i].vdisplay, r->modes[i].refresh_16_16, r->modes[i].clock_khz);
        }
    }
\tret = dcp_m4_runtime_health(r);
\tif (ret)
\t\tgoto failed;
\tsmp_store_release(&r->done, true);''')
    # New immutable catalog access: atomic validation never sends RPCs.
    edit('iomfb_m4.c', 'int iomfb_m4_error(struct apple_dcp *owner)', '''int iomfb_m4_get_mode_at(struct apple_dcp *owner, unsigned int index,
                         struct drm_display_mode *mode)
{
    struct iomfb_m4 *dcp = owner->v26_6;
    struct dcp_m4_runtime *r;
    const struct dcp_m4_timing *t;
    if (!dcp || !(r = dcp->runtime) || !smp_load_acquire(&r->done))
        return -ENODEV;
    if (READ_ONCE(dcp->error))
        return READ_ONCE(dcp->error);
    if (!r->mode_count)
        return index ? -ENOENT : iomfb_m4_get_mode(owner, mode);
    if (index >= r->mode_count)
        return -ENOENT;
    t = &r->modes[index];
    *mode = (struct drm_display_mode) {
        .clock = t->clock_khz,
        .hdisplay = t->hdisplay, .hsync_start = t->hsync_start,
        .hsync_end = t->hsync_end, .htotal = t->htotal,
        .vdisplay = t->vdisplay, .vsync_start = t->vsync_start,
        .vsync_end = t->vsync_end, .vtotal = t->vtotal,
        .type = DRM_MODE_TYPE_DRIVER | (index == r->preferred ? DRM_MODE_TYPE_PREFERRED : 0),
    };
    drm_mode_set_name(mode);
    return 0;
}

bool iomfb_m4_has_mode(struct apple_dcp *owner, const struct drm_display_mode *mode)
{
    struct drm_display_mode candidate;
    for (unsigned int i = 0; !iomfb_m4_get_mode_at(owner, i, &candidate); i++)
        if (drm_mode_equal(mode, &candidate))
            return true;
    return false;
}

int iomfb_m4_modeset(struct apple_dcp *owner, const struct drm_display_mode *mode)
{
    struct iomfb_m4 *dcp = owner->v26_6;
    struct dcp_m4_runtime *r;
    struct drm_display_mode candidate;
    unsigned int index;
    u8 request[8], response[4];
    int ret = -EINVAL;
    if (!dcp || !iomfb_m4_has_mode(owner, mode))
        return -EINVAL;
    mutex_lock(&dcp->lock);
    r = dcp->runtime;
    if (READ_ONCE(dcp->error)) { ret = READ_ONCE(dcp->error); goto out; }
    if (!r->mode_count) { ret = 0; goto out; }
    for (index = 0; index < r->mode_count; index++) {
        if (iomfb_m4_get_mode_at(owner, index, &candidate))
            goto out;
        if (drm_mode_equal(mode, &candidate))
            break;
    }
    if (index == r->mode_count)
        goto out;
    if (r->mode_programmed && r->timing.id == r->modes[index].id &&
        r->timing.color_id == r->modes[index].color_id) { ret = 0; goto out; }
    /* T604x UUID 6CC9349E: dispatch -> 0x1c4de4, 8-byte request,
     * 4-byte result, color then timing; vtable slot 0x250 -> 0x2363c8.
     * Transport/ABI corroborated offline; retained-panel acceptance untested.
     * No J713 power-state command or adaptive-sync request is sent.
     */
    put_unaligned_le32(r->modes[index].color_id, request);
    put_unaligned_le32(r->modes[index].id, request + 4);
    dev_info(dcp->dev, "J614s experimental A413 color=%u timing=%u refresh16=%u\\n",
             r->modes[index].color_id, r->modes[index].id, r->modes[index].refresh_16_16);
    r->deadline = jiffies + msecs_to_jiffies(8500);
    ret = dcp_m4_runtime_call(r, 413, false, request, sizeof(request), response, sizeof(response));
    r->deadline = 0;
    if (!ret) {
        r->modeset_status = get_unaligned_le32(response);
        dev_info(dcp->dev, "J614s A413 result=%08x\\n", r->modeset_status);
        if (r->modeset_status)
            ret = -EIO;
    }
    if (!ret)
        ret = dcp_m4_runtime_health(r);
    if (ret) {
        /* Never report a rejected mode as active or continue uncertain swaps. */
        dcp_m4_failed(dcp, ret);
        goto out;
    }
    r->timing = r->modes[index];
    r->mode_programmed = true;
out:
    mutex_unlock(&dcp->lock);
    return ret;
}

int iomfb_m4_error(struct apple_dcp *owner)''')
    edit('iomfb_m4.c', '\tseq_printf(s, "flips=%llu', '''    if (r) {
        seq_printf(s, "mode_count=%u preferred=%u programmed=%u timing=%u refresh16=%u A413=%08x\\n",
            r->mode_count, r->preferred, r->mode_programmed, r->timing.id,
            r->timing.refresh_16_16, r->modeset_status);
    }
\tseq_printf(s, "flips=%llu''')
    edit('iomfb_m4.h', 'int iomfb_m4_health(struct apple_dcp *dcp);', '''int iomfb_m4_get_mode_at(struct apple_dcp *dcp, unsigned int index, struct drm_display_mode *mode);
bool iomfb_m4_has_mode(struct apple_dcp *dcp, const struct drm_display_mode *mode);
int iomfb_m4_modeset(struct apple_dcp *dcp, const struct drm_display_mode *mode);
int iomfb_m4_health(struct apple_dcp *dcp);''')
    edit('iomfb_m4.h', 'static inline int iomfb_m4_health(struct apple_dcp *dcp)', '''static inline int iomfb_m4_get_mode_at(struct apple_dcp *dcp, unsigned int index,
                                     struct drm_display_mode *mode) { return -ENODEV; }
static inline bool iomfb_m4_has_mode(struct apple_dcp *dcp,
                                    const struct drm_display_mode *mode) { return false; }
static inline int iomfb_m4_modeset(struct apple_dcp *dcp,
                                  const struct drm_display_mode *mode) { return -ENODEV; }
static inline int iomfb_m4_health(struct apple_dcp *dcp)''')
    edit('iomfb.c', '''\t\tif (iomfb_m4_get_mode(dcp, &fixed))
\t\t\treturn 0;
\t\tmode = drm_mode_duplicate(dev, &fixed);
\t\tif (!mode)
\t\t\treturn 0;
\t\tdrm_mode_probed_add(connector, mode);''', '''        unsigned int count = 0;
        while (!iomfb_m4_get_mode_at(dcp, count, &fixed)) {
            mode = drm_mode_duplicate(dev, &fixed);
            if (!mode)
                break;
            drm_mode_probed_add(connector, mode);
            count++;
        }''')
    edit('iomfb.c', '\t\treturn 1;\n\t}\n\tmodes = dcp_modes_snapshot', '\t\treturn count;\n\t}\n\tmodes = dcp_modes_snapshot')
    edit('iomfb.c', '''\t\tstruct drm_display_mode fixed;

\t\treturn !iomfb_m4_get_mode(dcp, &fixed) && drm_mode_equal(mode, &fixed) ?
\t\t\tMODE_OK : MODE_BAD;''', '''        return iomfb_m4_has_mode(dcp, mode) ? MODE_OK : MODE_BAD;''')
    edit('iomfb.c', '''\t\tstruct drm_display_mode fixed;

\t\tcrtc_state = drm_atomic_get_new_crtc_state(commit, crtc);
\t\tif (!crtc_state || !crtc_state->active)
\t\t\treturn 0;
\t\tret = iomfb_m4_get_mode(dcp, &fixed);
\t\treturn ret ? ret : drm_mode_equal(&crtc_state->mode, &fixed) ? 0 : -EINVAL;''', '''        crtc_state = drm_atomic_get_new_crtc_state(commit, crtc);
        if (!crtc_state || !crtc_state->active)
            return 0;
        return iomfb_m4_modeset(dcp, &crtc_state->mode);''')
    edit('iomfb.c', '''\t\tstruct drm_display_mode fixed;

\t\treturn !iomfb_m4_get_mode(dcp, &fixed) && drm_mode_equal(mode, &fixed);''', '''        return iomfb_m4_has_mode(dcp, mode);''')
    edit('apple_drv.c', '''\tif (crtc_state->active)
\t\tdcp_crtc_atomic_modeset(crtc, commit);''', '''    if (crtc_state->active) {
        ret = dcp_crtc_atomic_modeset(crtc, commit);
        if (ret && iomfb_is_m4(dcp))
            goto failed;
    }''')
    output.mkdir(parents=True, exist_ok=True)
    patch = ''.join(''.join(difflib.unified_diff(old.splitlines(True),
        (root/'drivers/gpu/drm/apple'/name).read_text().splitlines(True),
        fromfile='a/drivers/gpu/drm/apple/'+name, tofile='b/drivers/gpu/drm/apple/'+name))
        for name, old in originals.items())
    (output/'kernel-multimode.patch').write_text(patch)
    print('Prepared opt-in J614s firmware-catalog mode enumeration and A413 switching')

if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('kernel',type=Path); p.add_argument('output',type=Path)
    a=p.parse_args(); prepare(a.kernel,a.output)
