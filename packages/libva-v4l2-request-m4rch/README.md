# Apple AVD VA-API bridge

Installed as `libva-v4l2-request-m4rch 1.3.r11-2`. This packages unmodified
[omacom/libva-v4l2_request](https://github.com/omacom/libva-v4l2_request) at
`4f60c51f7841dd74bb61c94a4ad31e630bbdab01`. The recipe compiles H.264 and
VP9 only: AV1, HEVC, VP8 and MPEG-2 are disabled. The test-only GStreamer
plugins were extracted to `cache/media-qualification/` and not installed.

The system-wide session default is package-managed in
`/usr/lib/environment.d/60-m4rch-video.conf` and is also set in the running
systemd user and D-Bus activation environments.
Existing desktop processes retain their previous environment until a new login.
`m4rch-vaapi` can select the bridge for an individual process, including from an
existing terminal. For example, an FFmpeg application must also request VA-API hardware
decode; selecting the driver alone does not force an application to use it:

```sh
m4rch-vaapi vainfo --display drm --device /dev/dri/renderD128
m4rch-vaapi ffmpeg -hwaccel vaapi -hwaccel_device /dev/dri/renderD128 \
  -hwaccel_output_format vaapi -i INPUT -vf 'hwdownload,format=nv12' -f null -
```

To roll back, remove the package with `sudo pacman -R
libva-v4l2-request-m4rch`, run `systemctl --user unset-environment
LIBVA_DRIVER_NAME`, and log out and back in. Firefox, browsers,
video players, sandbox access, GPU video display, 10-bit formats and broad
codec conformance have not been qualified. A successful hardware frame download
does not prove browser acceleration or display correctness. Upstream documents
an M1-specific test matrix and unqualified cases; it does not claim M4 support.

On J614s with `linux-m4rch 7.3.0-28`, the installed package produced 90/90
matching frames for a 720p H.264 Main clip, 240/240 for a 1080p H.264
Main clip, and 60/60 for a 360p VP9 profile 0 clip against software FFmpeg, using VA-API hardware surfaces and hwdownload.
A 180-second 720p H.264 Main stream also decoded 5,400/5,400 matching
frames at faster than real time; the kernel log showed no AVD errors in the
inspected boot. This limited smoke
test does not establish reliability for arbitrary streams. An isolated direct
GStreamer H.264 test also matched all 90 frames. The pinned source's 182 Meson
tests passed; those tests do not replace target hardware qualification.
