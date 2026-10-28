#!/usr/bin/env python3
"""Exercise the candidate's actual connector check with stubbed DRM plumbing."""
from pathlib import Path
import re, subprocess, sys, tempfile
root=Path(__file__).resolve().parents[2]
source=Path(sys.argv[1]) if len(sys.argv)>1 else root/'out/hdr-candidate/source'
src=source/'drivers/gpu/drm/apple/apple_drv.c'
s=src.read_text()
start=s.index('static int apple_connector_hdr_check(')
end=s.index('\nstatic const struct drm_connector_helper_funcs',start)
fn=s[start:end]
stub=r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <errno.h>
#define DRM_MODE_COLORIMETRY_BT2020_RGB 9
#define DRM_MODE_COLORIMETRY_DEFAULT 0
#define HDMI_STATIC_METADATA_TYPE1 0
#define HDMI_EOTF_SMPTE_ST2084 2
#define DRM_FORMAT_XRGB2101010 1
#define DRM_FORMAT_ARGB2101010 2
#define IS_ERR(x) ((uintptr_t)(x) > (uintptr_t)-4096)
#define PTR_ERR(x) (-1)
#define READ_ONCE(x) (x)
struct hdr_output_metadata { uint32_t metadata_type; struct { uint8_t eotf, metadata_type; } hdmi_metadata_type1; };
struct drm_property_blob { unsigned int length; void *data; };
struct drm_format_info { uint32_t format; };
struct drm_framebuffer { struct drm_format_info *format; };
struct drm_plane_state { struct drm_framebuffer *fb; };
struct drm_plane {int x;};
struct drm_crtc {struct drm_plane *primary;};
struct drm_crtc_state {bool active;};
struct drm_connector_state {struct drm_crtc *crtc; unsigned int colorspace; struct drm_property_blob *hdr_output_metadata;};
struct drm_connector {int x;}; struct platform_device {int x;};
struct apple_connector {struct drm_connector base; struct platform_device *dcp;};
struct drm_atomic_commit {struct drm_connector_state *old,*new;struct drm_plane_state *plane; struct drm_crtc_state crtc; int affected;};
#define to_apple_connector(p) ((struct apple_connector *)(p))
static bool enabled=true;
static bool apple_j614s_hdr_test(struct platform_device *p){return enabled && p;}
static struct drm_connector_state *drm_atomic_get_old_connector_state(struct drm_atomic_commit *s, struct drm_connector *c){(void)c;return s->old;}
static struct drm_connector_state *drm_atomic_get_new_connector_state(struct drm_atomic_commit *s, struct drm_connector *c){(void)c;return s->new;}
static struct drm_plane_state *drm_atomic_get_plane_state(struct drm_atomic_commit *s, struct drm_plane *p){(void)p;return s->plane;}
static struct drm_crtc_state *drm_atomic_get_crtc_state(struct drm_atomic_commit *s, struct drm_crtc *c){(void)c;return &s->crtc;}
static bool drm_connector_atomic_hdr_metadata_equal(struct drm_connector_state *a,struct drm_connector_state *b){return a->hdr_output_metadata==b->hdr_output_metadata;}
static int drm_atomic_add_affected_planes(struct drm_atomic_commit *s, struct drm_crtc *c){(void)c;s->affected++;return 0;}
'''
main=r'''
int main(void){
 struct platform_device dev; struct apple_connector conn={.dcp=&dev}; struct drm_plane plane; struct drm_crtc crtc={.primary=&plane};
 struct drm_format_info fmt={.format=DRM_FORMAT_ARGB2101010}; struct drm_framebuffer fb={.format=&fmt}; struct drm_plane_state ps={.fb=&fb};
 struct hdr_output_metadata m={.metadata_type=0,.hdmi_metadata_type1={.eotf=2,.metadata_type=0}};
 struct drm_property_blob blob={.length=sizeof(m),.data=&m};
 struct drm_connector_state old={.crtc=&crtc}, new={.crtc=&crtc,.colorspace=9,.hdr_output_metadata=&blob};
 struct drm_atomic_commit s={.old=&old,.new=&new,.plane=&ps,.crtc={.active=true}};
 assert(apple_connector_hdr_check(&conn.base,&s)==0 && s.affected==1);
 fmt.format=3; assert(apple_connector_hdr_check(&conn.base,&s)==-EINVAL); fmt.format=1;
 m.hdmi_metadata_type1.eotf=3; assert(apple_connector_hdr_check(&conn.base,&s)==-EINVAL); m.hdmi_metadata_type1.eotf=2;
 new.colorspace=0; assert(apple_connector_hdr_check(&conn.base,&s)==0); new.colorspace=10; assert(apple_connector_hdr_check(&conn.base,&s)==-EINVAL); new.colorspace=9;
 blob.length--; assert(apple_connector_hdr_check(&conn.base,&s)==-EINVAL); blob.length++;
 s.crtc.active=false; fmt.format=3; assert(apple_connector_hdr_check(&conn.base,&s)==0); fmt.format=1; s.crtc.active=true;
 new.crtc=NULL; assert(apple_connector_hdr_check(&conn.base,&s)==0); new.crtc=&crtc;
 new.hdr_output_metadata=NULL; new.colorspace=0; s.affected=0; assert(apple_connector_hdr_check(&conn.base,&s)==0 && !s.affected);
 old.hdr_output_metadata=&blob; old.colorspace=9; s.affected=0; assert(apple_connector_hdr_check(&conn.base,&s)==0 && s.affected==1);
 enabled=false; new.hdr_output_metadata=&blob; fmt.format=3; assert(apple_connector_hdr_check(&conn.base,&s)==0);
 puts("connector HDR admission and transition cases passed");
}
'''
with tempfile.TemporaryDirectory() as t:
 p=Path(t)/'test.c';p.write_text(stub+fn+main)
 subprocess.run(['cc','-Wall','-Wextra','-Werror',str(p),'-o',str(Path(t)/'test')],check=True)
 subprocess.run([str(Path(t)/'test')],check=True)
# Ensure the bytes compiled into the kernel match the checked generated EDID.
h=(src.parent/'j614s-hdr-edid.h').read_text()
compiled=bytes(int(x,16) for x in re.findall(r'0x([0-9a-f]{2})',h))
edid=(root/'experiments/hdr-j614s/j614s-test-edid.bin').read_bytes()
assert compiled==edid and len(edid)==256 and not sum(edid[:128])%256 and not sum(edid[128:])%256
print('compiled EDID matches generated data and both checksums')
# Verify the browser clip actually retains the requested full-range PQ values.
import json, struct
clip=root/'experiments/hdr-j614s/j614s-pq-ramp.webm'
info=json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=color_range,color_space,color_transfer,color_primaries','-of','json',str(clip)]))['streams'][0]
assert info == {'color_range':'pc','color_space':'bt2020nc','color_transfer':'smpte2084','color_primaries':'bt2020'}, info
raw=subprocess.check_output(['ffmpeg','-v','error','-i',str(clip),'-frames:v','1','-f','rawvideo','-pix_fmt','yuv420p10le','pipe:1'])
codes=[struct.unpack_from('<H',raw,2*(i*120+60))[0] for i in range(8)]
assert codes == [22,153,307,450,520,592,668,712], codes
print('browser clip PQ metadata and decoded luma values passed')
