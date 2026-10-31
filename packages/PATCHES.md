# Patch organization

Each package owns its source patches. The `patches/m4rch/` directories in
`mbpfan-m4rch` and `power-profiles-daemon-m4rch` contain the m4rch fan and
power-profile policy patches. Other patches in those packages implement or
carry support from their respective upstream projects.
The package-root symlinks let makepkg find the policy patches by their usual
source names; the canonical patch contents live in `patches/m4rch/`.

Linux, m1n1 and U-Boot packages use prebuilt inputs, not a fresh source build.
The package-managed default has booted. The source records identify the base, ordered deltas,
configuration and limits of the evidence:

- [Linux source record](linux-m4rch/promoted-source/source-stack.md): apply
  the integration series and then the retained-input handoff series to the
  pinned Aurora source archive. The previous kernel was built from a different
  reconstruction and is preserved in the recovery record.
- [m1n1 source record](m1n1-m4rch/promoted-source/source-stack.md): apply the
  `upstream-integration` series in order to its pinned Aurora archive.
- [U-Boot source record](u-boot-m4rch/promoted-source/source-stack.md): apply
  the `behaviour` series in order to its pinned Aurora archive.

Each series has its own ordering; they are not a single alphabetical patch
sequence. SHA-256 files verify the recorded combined patch bytes.

The m1n1 series is a net behavioral diff against Aurora m1n1 `6918c029`; the
U-Boot `behaviour` series is applied to Aurora U-Boot `01f255b6`.
These replace intermediate changes and later reversals with the final behavior.
The patches are ordered and can depend on one another; intermediate U-Boot
states are not build targets.
The original m1n1 packaged record remains compressed in its
`promoted-source/provenance/` directory, with its original SHA-256 value.
The U-Boot package carries the current behavior series. Neither source
comparison nor the patch records establish a reproducible binary build.

Attribution and license information for retained code belongs with its
package and source record. Unique pre-promotion source and machine-local material is preserved in the recovery archive.
