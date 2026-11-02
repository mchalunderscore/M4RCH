# J614s changes on Aurora packages

This document includes historical promotion and diagnostic records. For the current fork-based trial and updater state, see [status](status.md) and [the update workflow](aurora-update-workflow.md).

This records the migration and its current qualification limits.
The current J614s boot chain and recovery artifacts must remain available while
new candidates are built and tested. The source pins below were inspected on
1 November 2026; check the feed and recipe again for each update.

## Approach

Keep Aurora's packages unchanged when they already provide the required
behavior. Put configuration that has a supported override mechanism in a small
J614s integration package: for example, systemd drop-ins, modprobe settings and
initramfs configuration. Do not overwrite another package's files or patch an
installed binary in place. Inventory the actual files and ownership first;
some settings affect boot or shared SEP state and need explicit validation.

Where a source change is required, build from the corresponding Aurora ALARM
recipe and its pinned upstream source, with a small, ordered M4RCH patch and
configuration layer. Record the ALARM recipe commit, source commit, patch
hashes, configuration and resulting package hashes. Stop on a rejected patch,
an unexpected recipe change or an unverified change to the package interface.
Review upstream first and delete a local patch only after its replacement is
shown to provide the same J614s behavior.

Aurora's [package builder](https://github.com/aurora-silicon/alarm-aurora/blob/main/scripts/build-package)
uses `makepkg` on native AArch64. Its [kernel recipe](https://github.com/aurora-silicon/alarm-aurora/blob/main/packages/linux-aurora/PKGBUILD)
already applies `.patch` entries from `source` in order. A staging tool can
copy a pinned recipe and its support files, add our patches and verified
checksums, and invoke that recipe. It must preserve Aurora's existing build
and package functions and fail if its expected insertion points change.
U-Boot and Aura need package-specific adaptations: their current recipes do
not provide that kernel patch loop. A successful patch application does not
prove a working build or hardware behavior.

## Package decisions

| Area | Starting point and remaining work |
| --- | --- |
| Kernel | The [Aurora-based kernel and headers candidates](../packages/linux-aurora-j614s/README.md) are built with the rebased J614s changes. The device-tree handoff and hardware still need qualification. The earlier inspected recipe pin was `052924773992f3fd51ce2861f0e8202cd46619a6`; the newer staged recipe and its exact source pin are documented with the candidates. [Aurora PR 437](https://github.com/aurora-silicon/linux/pull/437) carries the common jack registration fix and was open when checked. |
| U-Boot | The patched Aurora package is installed; its stage 2 and the promoted persistent GRUB default have booted. |
| Aura / m1n1 | Aurora's Aura is derived from m1n1. The [built J614s overlay](../packages/aura-j614s/README.md) applies the retained loader behavior to a pinned Aura recipe and rebases the PMP and SD changes. Its stage two booted and the identical bundle was promoted as `aura-j614s-boot 20261101-3`; stage one remains unchanged. The known-good prior stage two is preserved on EFI, and the generic `update-m1n1` hook remains disabled. |
| Mesa | Prefer the Aurora host, FEX guest and Flatpak packages together when compatible; [ALARM PR 65](https://github.com/aurora-silicon/alarm-aurora/pull/65) pins all three to `c208afc` and explains their relationship to the kernel DRM name. Verify rendering and workloads on the actual kernel before treating that combination as qualified. |
| Touch ID | The owner prefers the Aurora stack. Keep Aurora `aurora-sep`, `libfprint-aurora` and `fprintd-aurora` as the default direction, but first compare their current package contents, service state and kernel behavior against the existing J614s keybag and xART policy. The fresh-install [integration notes](../installer/macOS/Development/J614s/README.md) say the stock SEP loader is masked and fingerprint has not been requalified. Do not infer that the package update alone safely enables it. |
| Audio and firmware | Keep Aurora packages where compatible; use separate supported configuration or machine-local firmware provisioning. J614s speakers remain disabled until the [speaker assessment](j614s-speaker-safety-investigation.md) gates are met. Do not publish device-specific firmware or calibration. |
| Other local packages | Audit fan, power, graphics/video and application packages individually against the fresh installation. Retain a local package only for a demonstrated missing behavior; preserve unique build inputs and provenance during migration. |

### U-Boot staging prototype

The initial shared-pin observation above is historical. [ALARM PR 83](https://github.com/aurora-silicon/alarm-aurora/pull/83)
reports that `01f255b` returned to main by mistake under an existing release
number. The PR proposes `d30213e` and `2026.07.aurora6-1`; its corresponding
[U-Boot PR 28](https://github.com/aurora-silicon/u-boot/pull/28) was merged and
reports tests on a J616s and other machines, not this J614s. PR 83 was open at
the time of this check. Reconcile the actual published feed and final merged
recipe before choosing a release baseline. Do not treat matching version
strings alone as proof of matching source.

[`stage-aurora-uboot.py`](../packages/tools/stage-aurora-uboot.py) stages an
experiment using the proposed PR 83 ALARM commit `2d2555e` and U-Boot
`d30213e`. It verifies the Aurora recipe, source archive and retained patch
series, then adds the patches to a copy of Aurora's recipe. It records hashes
and leaves the upstream build and package functions intact. For example:

```sh
python3 packages/tools/stage-aurora-uboot.py \
  --recipe /path/to/alarm-aurora/packages/uboot-aurora/PKGBUILD \
  --source-archive /path/to/u-boot-d30213e.tar.gz \
  --output /path/to/new-staging-directory
cd /path/to/new-staging-directory
makepkg --nobuild --nodeps
```

On this machine, makepkg verified the actual upstream source archives and
successfully applied all eight patches at both the historical and proposed
pins with fuzz disabled. At `d30213e`, the tool drops one logging-only hunk
because upstream PR 28 changed that FIFO message to debug-level output; the
rest of the retained-input patch is unchanged. Some hunks applied at offsets,
so source review is still required. The native build dependencies `bc`, `dtc`,
`python-pyelftools` and `swig` were absent from the system package database;
the candidate build below used temporary copies. Before promoting a candidate,
audit the patch series against the final published pin and complete hardware
checks. The older baseline is
available with `--baseline historical` and the corresponding pinned inputs.
The experimental `pkgrel` does not establish a safe update policy.

On 1 November 2026 the proposed recipe built on the J614s, using separately
downloaded, signature-checked Arch Linux ARM build tools in a temporary
directory. The package is retained in `cache/uboot-aurora-20261101/` together
with its staged recipe, patch copies and resolved `.config`. Package SHA-256:
`d499e5ae234a7016c00ffc724e63cfad7334b6aa15e28fa88c06e311eac49c2f`;
U-Boot SHA-256:
`410658b62acd693560175317456d36fee83eb8ae3e5a9f6e03d7bb2149f7cf8d`.
The package is unsigned and was installed on 1 November 2026.

[`assemble-aurora-uboot-stage2.py`](../packages/tools/assemble-aurora-uboot-stage2.py)
assembled a candidate using a root-copied current `/boot/efi/m1n1/boot.bin`.
Its hash matched the installer's booted record. The m1n1 prefix, J614s DTB,
and prior U-Boot also matched their recorded hashes. Independent extraction
confirmed that the candidate preserves the loader and DTB byte-for-byte and
contains the built package's U-Boot. Its SHA-256 is
`e36106dc730a691e7016a7b43588cd3f9f4046400affdf54e4506591b3fbde9f`.
The candidate and exact original are in `cache/uboot-aurora-20261101/stage2/`.

On 1 November 2026 the owner ran the trial and reported that Linux booted and
everything appeared to work. The subsequent boot ID was
`1e5f0eff-93f8-4d88-867d-89e6d7cc0124`, after baseline boot
`8b591e61-c43a-44db-9692-ef78260f47ca`. The kernel registered the J614s MTP
keyboard and trackpad, the internal panel reported connected, the root disk
was mounted and `wld0` reported carrier. These checks and the owner's report
establish a successful candidate boot, not comprehensive hardware or update
qualification. The trial used the package’s extracted U-Boot in the preserved
stage-2 layout; the identical package was installed afterward.

The trial boot logged a Noctalia greeter compositor crash and the PMP parent
domain failure; both also occurred in the preceding boot. The owner reports
that the greeter closes and reopens when the display switches from simpledrm
to the later DCP driver. That observation does not by itself resolve the
compositor crash. The Aurora SEP
service started in the trial boot, whereas no SEP messages appeared in the
previous boot's journal. It reported xART writes enabled with guard level 1,
then Touch ID failed to attach because `apple/msrk-j614s.bin` was unavailable.
This is not evidence of a U-Boot regression or of working Touch ID. Review the
effective service configuration and provisioning separately; do not reset or
recreate SEP state based on this trial.

### Promoted default and recovery

The boot-tested package `uboot-aurora 2026.07.aurora6-1.1` is installed;
`/usr/lib/asahi-boot/u-boot-nodtb.bin` matches the tested package and
`/boot/efi/m1n1/boot.bin` matches the booted stage 2. The generic updater
remains disabled because it does not reproduce this board's stage 2. Pacman
holds `uboot-aurora` with `IgnorePkg` until a reviewed update replaces the
patched package and stage 2 together.

GRUB was regenerated and checked with one entry pointing to
`/vmlinuz-linux-m4rch` and `/initramfs-linux-m4rch.img`, with persistent
`GRUB_DEFAULT=0`. The stage 2 was booted during the trial; the final GRUB
configuration has not yet been booted. The trial EFI backup and old pre-Wi-Fi
initramfs were removed from `/boot` only after verified copies were archived.
The known-good old stage 2 and previous boot configuration are in
`/var/lib/m4rch/uboot-recovery-20261101/`; use the [recovery guide](recovery.md)
from Linux recovery media. The archive shares the internal disk and is not a
backup against disk failure. Device firmware on EFI remains in place.

## Update and validation workflow

1. Inventory the current machine, package owners, effective service settings,
   boot partitions and recovery artifacts. The historical table in
   [status](status.md) describes the previous installation, not a current
   inventory. Capture the complete pacman transaction, including replacements.
2. Pin a matching Aurora ALARM recipe revision and its source inputs, compare
   upstream changes and review each local patch. Produce staged source and
   package artifacts without installing or altering the active boot chain.
3. Give patched packages an unambiguous version and provenance, and publish
   them in a local repository ahead of Aurora only after testing pacman's
   selection and upgrade behavior. Ensure an ordinary `pacman -Syu` cannot
   silently replace required J614s changes with an unpatched upstream build;
   also ensure that upstream updates become visible for review rather than
   being hidden indefinitely. Decide exact names, version ordering and hold
   policy from a real transaction before migration; same-name packages still
   need deliberate repository priority and version management.
4. Check the built package contents, dependencies, install scripts, hooks,
   initramfs and boot paths. Test kernel and stage-2 candidates with a
   recoverable trial path and preserve a known-working boot path. Verify the
   hardware features each change affects, including graphics, input, storage,
   audio and SEP where relevant. Keep Stage 1 enrollment separate from routine
   package updates.
5. Promote only after actual device validation, following the repository's
   boot-promotion and recovery instructions. Remove superseded local recipes
   or artifacts only after their replacement and unique provenance have been
   verified.

The U-Boot staging tool and boot-tested package are in place. A local package
repository and a general automatic update mechanism have not yet been implemented.

### Prepared kernel and package trial

The retired `install-aurora-candidate-trial.sh` helper installed the audited
Aura, kernel, headers, Mesa, Flatpak and UCM candidates. Its verified copy is
in `/var/lib/m4rch/aurora-kernel-promotion-20261101/retired-trial-helpers.tar`.
It also installs the [stock FEX compatibility bridge](../packages/mesa-aurora-fex-bridge/README.md)
and the signed `pahole` dependency. The helper is deliberately pinned to the
current installed package versions, boot files, local artifact hashes and
partition UUIDs; it stops if those inputs change. It archives rollback
packages, the current kernel, initramfs, EFI stage 2 and GRUB files under
`/var/lib/m4rch/aurora-candidate-trial-20261101/`, and checks that archive
before installing. It leaves `update-m1n1` disabled and checks that the existing
stage 2 has not changed.

The helper completed successfully on 1 November 2026. Its checks confirmed
the intended package versions, trial kernel, storage modules, Mriya firmware,
two-entry GRUB syntax, existing default and one-shot selection. The new kernel
booted as `7.3.0-1-9.1-ARCH` on 1 November (boot ID
`578da8ee-f2d4-4abd-b663-f45c37da7c48`). The screen remained blank and the
owner reported a watchdog reset. The persistent journal records input
initialization, root mounting and early userspace, then ends just after its
first flush; it does not identify the failing component. The old kernel booted
automatically afterward.

The new kernel uses the **currently booted stage 2 and its existing device
tree**, not the separately built draft DTB. The helper generates a separate
initramfs with the working J614s configuration and Wi-Fi firmware, checks for
its critical storage and firmware files, and adds a GRUB one-shot entry while
leaving the existing kernel as default. A trial failure normally returns to the
existing kernel on the following boot; recovery media and the verified archive
remain the fallback if GRUB or the loader cannot be reached. The new Aura
stage 2 is a separate later trial. The helper does not reboot or certify any
candidate as hardware-qualified.

Aurora’s open [J614s device-tree PR 795](https://github.com/aurora-silicon/linux/pull/795)
was unqualified when reviewed after the failed trial. The test used the
existing stage-2 DTB, not that PR’s DTB. The next diagnostic disables the
`aurora`, `appledrm` and `apple_pmp` modules for one boot to test whether
graphics/PMP initialization is involved; the temporary journal sync drop-in
captures more data if the system reaches persistent journaling. This is a
hypothesis test, not a claim that those drivers caused the reset.

The graphics-off diagnostic boot on 1 November (boot ID
`eaa032e8-a446-4f02-b433-6f009bb590da`) stayed up and reached a console.
With GPU, Apple DRM and PMP all disabled, the user reported the expected
graphics failures. PMP-dependent CPU frequency limits engaged, and no
individual driver has yet been identified as the cause of the original reset.
The owner then manually loaded `apple_pmp` with both graphics modules still
blacklisted. PMP bound to `500700000.pmp`, reported firmware and endpoint ready,
and the machine remained running with CPU limits cleared. This late manual
load does not establish that every cold-boot timing of PMP is safe.

On the same diagnostic boot, the owner manually loaded `appledrm` with
PMP running and the GPU module still blacklisted. The display driver took
over the internal panel, reported eDP connected, and the owner confirmed it
worked. These late loads do not rule out a cold-boot timing interaction.

After the owner manually loaded `aurora` on that diagnostic boot, its
probe rejected the J614s 16-core layout. The rebased admission patch was
present, but the installed `options asahi t6040_16core=1` targeted the
old module name. Reloading `aurora` with `t6040_16core=1` initialized the
GPU, exposed `renderD128` and allowed the installed Borealis/Zink stack to
clear and read back a pixel on the M4 Pro. A package-managed
the earlier `aurora-j614s-config` candidate (later retired after a successful Aurora-default boot)
provides the option under the new module name; automatic boot and extended
workloads are not yet qualified. The original watchdog reset happened even
when this option was missing, so its cause remains open.

The 1 November internal-display-gate diagnostic kernel was built by relinking
only the kernel image and mistakenly reusing the original `9.1` modules. It
reached initramfs emergency mode rather than mounting root. The on-screen
error capture showed `failed to validate module [...] BTF: -22` for `apple_sart`
and other modules; the storage and firmware failures followed. Kernel release,
configuration and `Module.symvers` matched, but the module BTF was based on the
previous kernel image. This failed diagnostic says nothing about whether the
display gate caused the earlier watchdog resets. The earlier image and working
kernel were preserved, and GRUB returned to the working kernel. A fresh `9.2`
recipe rebuilds the diagnostic image and its full module set together.

The matched `9.2` diagnostic booted on 1 November (boot ID
`53df21e3-0aec-4f14-abf2-9bc1ed73ebb7`) with
`apple_t6041_display.j614s_internal_only=1`. The boot log confirms that J614s
external-display staging was skipped, PMP initialized, and the patched
16-core Aurora GPU initialized without delayed module loading. The internal
eDP panel was connected, Wi-Fi was connected, and an offscreen Zink render on
the M4 Pro returned the expected pixel without a GL error. This supports an
interaction with the skipped staging path; it does not isolate a particular
operation within that path. External displays remain unqualified. This was a
one-shot trial; `linux-m4rch` was the GRUB default at the time.

An upstream investigation on 1 November found that Aurora's merged
[PR 628](https://github.com/aurora-silicon/linux/pull/628) fixes DISPEXT1
power-domain handling on J616s and explicitly requires four matching links in
the stage-2 device tree. The candidate kernel contains that PR's PMGR driver
change, but this Mac's live tree has no `power-domains` properties on
`/dcp@602e00000`, `/mailbox@602e08000`, `/iommu@602300000`, or
`/iommu@602340000`. The domain at
`/power-management@502800000/power-controller@498` is present. This is a
concrete mismatch and a plausible cause, not yet proof of the reset's cause.
The diagnostic 9.3 recipe adds the upstream links to the live tree before
staging, scoped to J614s and refusing conflicting properties; it retains the
9.2 internal-only opt-out for comparison. The official J614s DT proposal
[PR 795](https://github.com/aurora-silicon/linux/pull/795) remains unbooted
on this hardware and does not establish that this particular handoff works.
The matched 9.3 image and modules were built together and prepared for a
one-shot GRUB test on 1 November. Its emergency-diagnostic initramfs contains
the 9.3 storage modules and local firmware; the 9.3 GPU, display and PMP
modules are available from an isolated root-owned module directory. The test
enabled normal display staging. The earlier package, older kernel, and
stage-2 loader were preserved.

The 9.3 one-shot boot subsequently succeeded (boot ID
`74cb9a48-818a-43b4-a5f6-518dd0036f56`). Its boot log confirms all four
power-domain links, both staging steps, PMP readiness, both external DCP
services and the display subsystem; the internal panel and Wi-Fi connected.
An offscreen GPU render returned the expected pixel without a GL error. No
external monitor was connected during these checks, so actual HDMI and USB-C
output, hotplug and suspend remain unqualified. This single successful boot
supports the power-link explanation but does not conclusively prove it was the
sole cause of the earlier intermittent failures.

The owner authorized promotion after that boot. `linux-aurora` and its
headers at `7.3.0.aurora1-9.3` are now installed, with the exact booted image
at `/boot/vmlinuz-linux-aurora`, a newly generated matching initramfs at
`/boot/initramfs-linux-aurora.img`, and one persistent GRUB entry. The old
kernel's shared machine settings are owned by `aurora-j614s-config 20261101-4`;
the old package and trial boot files were retired after recovery was archived.
The kernel and headers are held in pacman until their patches are reconciled
with a subsequent Aurora update. The final default booted on 1 November, boot
ID `07cf152d-6be0-499a-a210-7363eba97a98`.
See [recovery](recovery.md) for the previous kernel and modules.

The networkd online wait was separately conditioned on an existing `en*` or
`eth*` interface, matching this machine's current networkd profiles. Wi-Fi is
managed by NetworkManager, whose own wait-online service remains enabled.
The condition is evaluated when the unit starts; a wired adapter appearing
later, or a future networkd profile with a different interface name, needs a
corresponding review. This network change does not resolve the kernel issue.
