# Aurora bootstrap replacement (AUBS001)

Revision 3 corrects the J614s Wi-Fi and Bluetooth firmware identity. The Aurora
J616s donor uses `apple,hostomel`; this J614s uses `apple,mriya`, matching its
installed firmware. The existing live calibration handoff copies these board
types into Linux. Both properties were compared with the prior control tree and
the installed firmware inventory. The complete DT diff contains only these two
property replacements relative to revision 2. First stage, second-stage m1n1,
U-Boot, kernel, Mesa, speaker exclusion and CPU handoff checks remain unchanged.

Install revision 3 with the same `sudo python3 .../refresh.py` command below;
it checks the already-enrolled first-stage receipt and updates the rollback
script to recognize revision 3. No Recovery enrollment is needed. Revision 2
boot success and missing Wi-Fi are owner-reported; revision 3 still needs a
native Wi-Fi check. Build it with `repair_control.py --revision 3 --libfdt ...`.

Revision 1 reached U-Boot and adopted the live ANS session, then stopped at our
CPU handoff check: Aurora's `cpu@10100` omits the spin-table properties and m1n1
deliberately skips fixups for the already-running boot CPU. Revision 2 supplies
those two placeholders in the control DT. Secondary CPUs still require real
nonzero release addresses supplied by m1n1; the handoff validation is unchanged.

Revision 2 retains both m1n1 binaries and U-Boot byte for byte. With revision 1
already enrolled, install the correction from normal macOS Terminal:

```sh
sudo python3 experiments/aurora-bootstrap/refresh.py
```

This checks the existing first-stage enrollment receipt, updates `boot.bin` and
the rollback script's accepted image hash, and retains the native-working AURL001
rollback. It does not enroll a first stage or change the graphics stack. Boot
Arch normally afterward. The complete revision-1 host artifacts are preserved
under `out/aurora-bootstrap/revisions/r1`.

`repair_control.py --libfdt /path/to/libfdt` generates revision 2 directly from
those archived artifacts. It verifies the complete DT property map changes by
exactly the two missing CPU properties and retains the compressed U-Boot payload
verbatim. Fresh builds incorporate the same fix in `prepare.py`.

Replaces the two remaining Wallace-derived inputs in the active boot path:
the enrolled m1n1 first stage and the bootloader control DT. This is an Aurora
base with local J614s integration, not an unmodified upstream installation.

Sources remain pinned to the native-working AURL001 revisions:

* Aurora m1n1 aurora-wip `9f7cdfbd0623d96f21965434c3a7dda799ffcff4`.
* Aurora U-Boot aurora-wip `7680260272f3612a13f0c9a6c7bfbc5e9ba7ce8c`.
* Aurora Linux DT `420a1c8f5492daeaa59ffba565aac610f5218d27`, using the
  existing Aurora J616s-to-J614s template adaptation.

First-stage changes: native-tested J614s MCC cache geometry; disable the legacy
USB proxy timeout; reserve 1 MiB before BSS/stacks so the complete second-stage
image and configuration fit below the live firmware heap. Aurora's own embedded
stage-1 configuration targets `boot.bin` on the existing internal ESP, with its
checked live RTKit session handoff. No Wallace first-stage code or variable
appendage is used.

Second-stage m1n1 is byte-for-byte the native-working AURL001 artifact. The control
DT comes from Aurora's adapted J614s tree. Firmware memory reservations are
populated from the live machine rather than retained from a donor board.
Early U-Boot uses Aurora's watchdog binding and requires this control tree;
it never reads or applies the Wallace-targeted `/dtbs/board.dtbo`. The existing
local Linux handoff bridge still supplies live CPU release addresses, firmware
buffers, calibration, display and board data to the Aurora Linux template.

The kernel, GPU integration, Mesa, initramfs and GRUB default remain AURG016
revision 4. Built-in speaker protection remains in that Linux image. AUBS001
does not add any speaker drivers or enable its speaker nodes.

## Build

Inside the existing ARM build VM, prepare a clean `stage1` clone from the pinned
Aurora m1n1 commit. The `uboot` tree starts with the native-working AURL001 patch
and configuration. Run `prepare.py` once, then `build.sh`. Preparation refuses a
dirty first-stage tree; exported `stage1.patch` and `uboot.patch` contain the
complete final differences from their respective upstream commits. The manifest
records SHA-256 and byte counts. `stage.py --check` verifies the host artifacts.

## Install

From normal macOS Terminal, in this checkout:

```sh
sudo python3 experiments/aurora-bootstrap/stage.py
```

This authenticates mounting the existing ESP, validates the existing Arch stub
and source macOS identities, backs up both working stages and stages the paired
replacement. It checks the unchanged GRUB and GPU kit hashes. It does not enroll
the first stage, change startup selection, reboot or modify partitions. Existing
enrollment receipts are retained until Apple's Recovery enrollment succeeds.
It refuses a second installation over an existing AUBS001 archive/backup.

Then enter **this Arch installation's paired One True Recovery**. Select Arch
as the startup disk before shutting down; hold power to enter startup options
and open its Recovery. In Recovery Terminal, mount the Arch System volume if
necessary and run:

```sh
sh "/Volumes/M4RCH/Finish Installation.app/Contents/Resources/enroll.sh"
```

The script revalidates the machine, exact APFS roles, image hash, previous receipt
and paired Recovery before `kmutil configure-boot`. Apple requests the existing
owner credentials. Native first-stage boot remains unverified until this step
and the subsequent Linux boot succeed.

## Rollback

In the same paired Recovery, run:

```sh
sh "/Volumes/M4RCH/Finish Installation.app/Contents/Resources/aurora-bootstrap-rollback.sh"
```

It verifies and re-enrolls the preserved first stage, restores its source and
enrollment script, and restores the native-working AURL001 second-stage loader
and selector receipt. The kernel, desktop kit and GRUB remain unchanged. Copies
live in the stub's `aurora-bootstrap-AUBS001-backup` and ESP's `AUBS001` directory;
the rollback script validates their hashes before enrollment/restoration.
