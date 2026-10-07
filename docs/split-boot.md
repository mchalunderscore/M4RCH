# Split internal boot

The working internal NVMe setup can use this chain:

Apple boot policy → enrolled m1n1 stage 1 → ESP `/boot.bin` (m1n1 stage 2,
board DT and U-Boot) → ESP GRUB → NVMe Linux.

Stage 1 binds the internal ESP by PARTUUID
`5fdb35c6-3a66-416d-8358-6555fd99fcc5` and reads `boot.bin` from its root.
It passes that identity to stage 2 as `asahi,efi-system-partition`.
The filename is deliberately at the ESP root, rather than Asahi's usual
`m1n1/boot.bin`. U-Boot is gzip-compressed so stage 2 can parse the metadata
appended by stage 1. Kernel and root filesystem locations are unchanged.

## First installation

From macOS, in the project directory:

```sh
make loader-split
sudo make boot-split
```

The second command resolves and checks the internal ESP, backs up any existing
`boot.bin`, writes and reads back the new stage 2, then prepares stage 1 using
the existing enrollment flow. No partition changes or SD access occur.
Complete the printed Recovery instructions; the manual command is:

```sh
sh "/Volumes/M4RCH/Finish Installation.app/Contents/Resources/enroll.sh" --update
```

The owner confirmed successful split boot without an SD card on 2026-10-07,
initially using the 26.5.2/25F84 Apple stub, then successfully booted Linux
with the upgraded 26.6.2/25G83 stub.

## Later stage-2 updates

```sh
make loader-split
sudo make stage2
```

Only ESP `/boot.bin` changes. Stage 1 and Apple boot policy are untouched;
Recovery enrollment is needed only when replacing stage 1 or its Apple stub.
The current pacman kernel updater does not rebuild this bundle automatically.

For the separately pinned Gravity source update, use the
[alignment profile](bootloader-alignment.md). It replaces only stage 2.

## Rollback

Each deployment prints its Mac-local backup under `out/split-boot-backups/`.
For a stage-2 failure, mount the internal ESP in macOS and restore the saved
`boot.bin` to its root. The previous stage-2 file exists only when one was
present at deployment; a first split installation has no older stage-2 file.

To return to the working monolithic chain, run `sudo make boot-internal` and
complete Recovery enrollment again. ESP `/boot.bin` can remain unused. The
enrollment tooling also retains the previous boot object in its rollback chain;
the deployment backup includes `monolithic-loader.bin` for inspection/recovery.
