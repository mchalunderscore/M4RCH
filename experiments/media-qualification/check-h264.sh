#!/usr/bin/env bash
set -euo pipefail
root=$(cd "$(dirname "$0")/../.." && pwd)
input="$root/cache/media-qualification/h264-main-720p.h264"
for tool in ffmpeg ffprobe gst-inspect-1.0 gst-launch-1.0 timeout python3; do
    command -v "$tool" >/dev/null || { echo "Missing tool: $tool" >&2; exit 2; }
done
for element in filesrc h264parse v4l2slh264dec videoconvert filesink; do
    gst-inspect-1.0 "$element" >/dev/null 2>&1 || { echo "Missing GStreamer element: $element" >&2; exit 2; }
done
[ -r "$input" ] || { echo "Missing test clip: $input" >&2; exit 2; }
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
ffmpeg -hide_banner -loglevel error -i "$input" -pix_fmt yuv420p -f rawvideo "$tmp/reference.i420"
timeout 30s gst-launch-1.0 -e filesrc location="$input" ! h264parse ! v4l2slh264dec ! videoconvert ! 'video/x-raw,format=I420' ! filesink location="$tmp/hardware.i420"
python3 - "$tmp/reference.i420" "$tmp/hardware.i420" <<'PY'
import sys
from pathlib import Path
ref, hw = (Path(p).read_bytes() for p in sys.argv[1:])
frame_size = 1280 * 720 * 3 // 2
print(f'Software bytes: {len(ref)}, hardware bytes: {len(hw)}, frame size: {frame_size}')
if len(ref) != 90 * frame_size or len(hw) != len(ref):
    raise SystemExit('FAIL: missing or extra frame data')
errors = sum(a != b for a, b in zip(ref, hw))
print(f'Differing bytes: {errors} / {len(ref)}')
if errors:
    raise SystemExit('INCONCLUSIVE: output differs; inspect frame layout and pixel differences')
print('PASS: 90 hardware-decoded I420 frames match software exactly')
PY
