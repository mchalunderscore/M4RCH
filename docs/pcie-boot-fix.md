# PCIe backport provenance

This filename is retained because the pinned patch header references it.
`patches/m1n1-t6040-pcie-upstream.patch` restores `src/pcie.c` exactly from
[Asahi m1n1 commit 0f221fc739afa52eecb9148f77c2d447f276456e](https://github.com/AsahiLinux/m1n1/commit/0f221fc739afa52eecb9148f77c2d447f276456e).
Other m1n1 files retain their pinned baseline or explicitly recorded patches.
The source revision, expected file hash and patch hash are recorded in
[the source lock](../sources.lock.json). See [architecture](architecture.md) for the current
bridge; the former session narrative is archived locally under `out/`.
