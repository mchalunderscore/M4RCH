import copy
import hashlib
import shutil
import struct
import sys
import zipfile
from pathlib import Path

source, output = map(Path, sys.argv[1:])
if output.exists():
    raise SystemExit("output already exists")
with zipfile.ZipFile(source) as old, zipfile.ZipFile(output, "x", allowZip64=True) as new:
    for original in old.infolist():
        entry = copy.copy(original)
        fields = []
        data = entry.extra
        while data:
            if len(data) < 4:
                raise ValueError("truncated ZIP extra field")
            tag, length = struct.unpack_from("<HH", data)
            if len(data) < 4 + length:
                raise ValueError("truncated ZIP extra value")
            if tag != 1:
                fields.append(data[:4 + length])
            data = data[4 + length:]
        entry.extra = b"".join(fields)
        with old.open(original) as src, new.open(entry, "w", force_zip64=True) as dst:
            shutil.copyfileobj(src, dst, 1024 * 1024)
        print(entry.filename, flush=True)
h = hashlib.sha256()
with output.open("rb") as stream:
    while chunk := stream.read(8 * 1024 * 1024):
        h.update(chunk)
print("sha256", h.hexdigest(), flush=True)
