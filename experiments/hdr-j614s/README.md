# J614s HDR diagnostics

The promoted internal HDR path has been tuned visually by the owner. It has
not been measured for luminance or color accuracy. See the
[HDR status](../../docs/hdr-investigation.md) for limits and provenance.

The connector admission and surface-layout tests operate on the actual patched
kernel source and require its path explicitly:

```sh
python3 experiments/hdr-j614s/test-candidate.py /path/to/patched-linux
python3 experiments/hdr-j614s/test-surface-offsets.py /path/to/patched-linux
```

Both passed against the promoted source before its extracted build tree was
retired. The local `out/retired-kernel-source-deltas/README.md` describes how
to reconstruct that source from the retained upstream base and its verified
delta. The tests do not exercise real atomic commits, physical luminance or
color accuracy. The old trial and rollback instructions are historical and
available via `git show e7baa0e:experiments/hdr-j614s/README.md`.
