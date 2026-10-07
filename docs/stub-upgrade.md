# Apple boot-stub upgrade

The maintained installation uses a separate 26.5.2/25F84 Apple boot stub.
Main macOS updates do not update it. The working installation now boots
entirely from NVMe: enrolled m1n1 stage 1 loads ESP `/boot.bin`, which contains
m1n1 stage 2, the board DT and U-Boot. Linux kernel and Mesa updates do not
require replacing the Apple stub.

For the G16S GPU port, prepare 26.6.2/25G83 to match Gravity's exercised
`mBoot-18000.161.10` profile. Preparation is deliberately separate from
`sudo make boot`, which currently updates/enrolls the Linux loader and has no
Apple-stub upgrade transaction.

```sh
make stub-upgrade STUB_OUTPUT=out/stub-upgrade-25G83-candidate
python3 scripts/prepare-stub-upgrade.py --verify \
  --output out/stub-upgrade-25G83-candidate
```

Use a fresh output directory for preparation; it never overwrites an existing
candidate. Downloads use HTTPS range requests to Apple's restore archive, with
pinned manifest/member hashes in `profiles/stub-25G83.lock.json`. The pinned
AEA tool authenticates/decrypts the matching Recovery image. Apple binaries
remain ignored local inputs. Wi-Fi, Bluetooth and trackpad payloads retain their
working 25F84 profile; the prepared Apple boot/GPU firmware is a separate input.

The output contains `payload/`, a target input lock, original BuildManifest,
firmware strings, GFX container layout and a verification receipt. The payload
contains no owner credentials, personalized tickets or boot policy. Its layout
passes local assembly/integrity checks; native personalization, paired Recovery
and boot remain unqualified. The default build/profile and installed volumes
are unchanged. `make boot` will not install this candidate.

Install the prepared candidate from a macOS terminal:

```sh
sudo make stub-install
```

The command validates the existing dedicated stub UUIDs, copies and verifies all
four installed role trees and protected host receipts, records durable rollback
intent, then replaces Apple System/Preboot/Recovery payload files. Data/owner
records and enrolled m1n1 stage 1 remain intact. ESP `/boot.bin`, GRUB and
the NVMe root are not written by this transaction. It rebuilds the hash-bound Recovery launcher and
asks Apple's bless tool to personalize/select this installation. No partition
resize or automatic reboot occurs; an SD card is not needed.

Backup copies remain writable: original BSD flags, including immutable owner
metadata flags, are stored in the verified transaction inventory and restored
on rollback. Live owner metadata is never unlocked to make a backup.

The backup path is printed and saved in `out/sdboot/stub-upgrade-state.json`.
Incomplete writes stop; do not run a different installer over them. Rerunning
`sudo make stub-install` can resume the same candidate during the payload-copy
phase: it validates the saved backup and rejects changes outside declared
replacement paths, including owner metadata or m1n1. The generated Data-volume
`private/var/db/Spotlight-V100` index is excluded from the live resume comparison;
the saved backup still receives full integrity verification. Later metadata/launcher
failures require the rollback command below if they cannot complete. If startup
selection alone fails, rerunning `sudo make stub-install` retries selection from
the verified staged state.

If desktop `bless` fails to create LocalPolicy, the transaction stays staged;
that error does not establish that Recovery enrollment succeeded. Try Apple's
personalization from Recovery before attempting custom-boot enrollment:

1. Shut down fully, hold power continuously, open Options, authenticate and
   open Utilities → Terminal. Connect Recovery to the Internet.
2. Mount the dedicated System volume by its verified UUID (printed by the
   installer), then run `bless --setBoot --mount "/Volumes/M4RCH"`, adjusting
   the mount path if `diskutil mount` prints a different one. If it fails,
   retain the exact error and stop; do not disable the pairing checks.
3. If it succeeds, shut down fully and hold power again. This separate entry
   into Recovery is necessary to test pairing with the newly selected M4RCH;
   selecting a volume inside an already running Recovery does not change it.
4. Run the bound enrollment script below. Its policy preflight must report
   paired One True Recovery before custom-boot authorization proceeds.

This Recovery personalization route is a diagnostic attempt, not yet verified
on the upgraded stub. The installed firmware and rollback backup are retained.

Keep the existing split loader for this first firmware boot; do not rebuild or
replace stage 1/stage 2 during the upgrade. After selection succeeds, shut down, hold power continuously and choose Options
to enter this selected installation's paired Recovery. Authenticate, open
Utilities → Terminal and run the **exact printed** `sh "…/enroll.sh" --update`
command. The new script forces custom-boot authorization even when the existing
m1n1 hash is unchanged. On returning to macOS:

```sh
sudo make stub-finish
```

This verifies the target-build enrollment receipt and restores the ordinary
loader-update script. Other loader staging is blocked while the stub upgrade
is pending.

For rollback, boot ordinary macOS and run:

```sh
sudo make stub-rollback
```

It revalidates the saved backup and target UUIDs, restores baseline files/host
receipts and prepares forced Recovery enrollment for 25F84. Follow its printed
Recovery instructions and run `sudo make stub-finish` afterward. Saved files do
**not** undo secure Apple LocalPolicy changes: rollback may need owner credentials
and re-personalization. Retain the backup until both native boot and rollback
are qualified; the new transaction has source tests, not native certification.

After installation, fresh Linux ADT/FDT/firmware captures must establish the
actual target firmware and memory reservations. Requalify ASC cold state,
protocol HELLO and endpoint enumeration; old receipts belong to earlier boots.
Matching the firmware version does not validate G16S initialization objects.

# Supplied G16S ABI reference

`M4-PRO-GPU-HARDWARE-ABI.md`, supplied by the owner from Gravity Discord,
has SHA256 `2818ced00eea77f662be9339ee6dae717bd1330e2a46bc927e53190edf6b98db`.
It describes J616s/25G83 with 20 enabled cores. Our J614s has 16 enabled cores,
with masks `0x3db/0x3db`; preserve those and both independent voltage ladders.
No author/source commit, capture method or redistribution licence was supplied.
The document is retained privately; its claims are candidate interface metadata.

It identifies concrete porting work: a different root interface identifier,
shifted main-object pointers, distinct channel/queue cursor semantics, larger
render/compute records, KSM dependencies and two-column voltage tables. In
particular, the stated queue prefetch acknowledgement is not command completion.
Unaligned fields require explicit wire access, not native struct casts. Qualify
these independently before submitting commands; retaining T8132 layouts while
changing only the chip ID would miss these differences.

## Failed LocalPolicy personalization

A Code 401 / bootpolicy Code 11 (“AP boot mode (11)”) was reproduced in both
ordinary macOS and Recovery on 2026-10-07. Moving the same `bless` command to
Recovery did not resolve it. Do not treat the candidate integrity check as
proof of personalization, or repeat Recovery trips without a new hypothesis.

From ordinary macOS, run `sudo make stub-diagnose`. It saves private evidence
under `out/stub-diagnostics/`: target policy, Apple logs, staged-file comparison,
verified rollback state and hashes comparing main/stub owner metadata. It may
mount existing APFS volumes, but does not update firmware or boot policy. The
output contains private machine metadata; keep it out of public commits.

Asahi's pinned repair path refreshes AdminUserRecoveryInfo from the current
macOS installation before startup personalization. Our upgrade preserved the
old owner file. Compare their hashes first; a difference alone does not prove
the cause of this policy error. No owner metadata or security reset is performed
by the diagnostic command.

### Reduced-policy recreation trial

The 2026-10-07 capture verified all staged payload files and the saved backup.
Main/stub owner metadata hashes match. LocalPolicy still records the old OS
version (`25.6.84.0.0,0`) and enrolled fuOS hash. Apple verified the candidate
firmware and created a paired-Recovery policy, then failed creating the OS
policy while retaining Permissive Security. `personalization = 0` alone is not
evidence that signatures are missing: the log reports firmware verification
succeeded.

The pinned Asahi installer `main.py:set_reduced_security` explicitly runs
`bputil -g -v <VGID>` from Recovery before `bless` in its non-paired Recovery
path. Our next trial follows that ordering, targeting only M4RCH.
`tools/boot/repair-stub-policy.sh` checks One True Recovery, exact System/VGID,
staged build and working stage-1 hash before offering this policy change. It
does not remove policies, reset global SIP or target primary macOS. This repair
is not yet hardware-verified. Reduced policy recreation invalidates custom-boot
authorization; follow with a fresh paired-Recovery entry and the bound existing
`enroll.sh --update`. Do not try Linux between those steps.

Stage the target-specific helper from macOS:

```sh
sudo make stub-policy-repair
```

Then in physically entered Recovery Utilities → Terminal:

```sh
sh "/Volumes/M4RCH/Finish Installation.app/Contents/Resources/repair-policy.sh"
```

If any check or Apple command fails, stop and retain its output. The helper
leaves its read-only policy captures in the printed Recovery `/tmp` directory.
On success it prints the second Recovery entry and enrollment instructions.
