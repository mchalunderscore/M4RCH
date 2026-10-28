# Guest data-limit accounting

`guest-data-limit.patch` is a local patch against the pinned FEX source
`14c92681f4d62cf84d901460e0358de09c8847a7`. The package recipe applies it in
`prepare()`; the normal preparation tool records its checksum with the source
archive. The current package revision is `2610-5`.

FEX previously forwarded RLIMIT_DATA directly to the host kernel. The kernel
therefore charged FEX runtime/JIT mappings to an x86 application's data limit.
Garry's Mod's Chromium renderer set a 16 GiB limit and then failed a 4 KiB mmap.

The patch retains guest soft/hard values separately and uses FEX's guest VMA
tracker to charge private writable mappings. Shared mappings and grow-down
stack mappings retain Linux's exclusions. Other resource limits keep their
existing handlers; this patch specifically addresses RLIMIT_DATA.

Enforcement covers mmap and fixed replacements, mprotect, mremap, munmap and
brk. Mapping checks and updates share the existing VMA mutex. Partial mprotect
failures retain accounting for any successfully changed prefix. A zero soft
limit follows Linux's compatibility rule and falls back to the hard limit.
Both x86-64 and legacy i386 resource-limit interfaces use the same state.

A per-process memfd holds limit state, with file locking for remote prlimit.
Fork snapshots the state while locked and creates an independent child record.
Exec carries an internal descriptor independently of the guest environment.
Guest descriptor reshuffling relocates that descriptor before dup2/dup3 can
overwrite it; close and close_range preserve it. Remote lookups recognize PID
namespaces and wait for child initialization rather than using a parent's record.
Invalid internal state fails closed instead of being ignored in release builds.

## Validation

`packages/tools/test-fex-data-limits.c` is the integration regression source.
Build it for native ARM64, x86-64 and i386 against the corresponding libc, then
run the ARM binary directly in muvm and the x86 binaries through FEX in muvm's
4 KiB-page guest, as the normal desktop user. The tests cover:

- under/over-limit mappings, private versus shared mappings and Linux zero limits;
- fixed replacement, unmap credit, protection changes and remapping;
- a writable prefix surviving a failed mprotect across an unmapped hole;
- brk refusal, hard-limit/error behavior and invalid pointers;
- concurrent allocation checks, remote prlimit (including PID/user/network namespaces) and fork snapshots;
- descriptor reshuffling and fork/exec with a replaced environment.

Native ARM64 and both emulated architectures passed. The owner also confirmed
Garry's Mod's original Chromium main menu loads, with sandboxing enabled and no
CEF replacement. That menu confirmation used revision 3; later revisions add
partial-mprotect and fork-snapshot hardening covered by the standalone tests.
Evidence and built archives are under `out/steam-investigation/`.

## Current compatibility boundaries

This remains a local compatibility patch, rather than complete virtualization
of Linux resource administration. In particular:

- Exec of a native ARM64 helper after changing the virtual data limit returns
  EOPNOTSUPP. Applying a lower native hard limit before exec cannot be rolled
  back by an unprivileged emulator if exec fails. Rejecting the handoff retains
  enforcement instead of silently discarding the limit.
- Hard-limit increases are conservatively denied; privileged increases are not
  implemented. Normal unprivileged soft-limit changes within the hard limit work.
- Remote virtual limit access requires access to the target's proc descriptors.
  Inaccessible or initializing emulated targets can return an access error or
  EAGAIN; they do not fall back to modifying the emulator's host data limit.
- Existing FEX limitations around unusual clone flags are unchanged.

These boundaries matter when evaluating other software. The test results and
working menu establish the specific accounting and integration fixes, not
universal game compatibility or full kernel resource-limit equivalence.
