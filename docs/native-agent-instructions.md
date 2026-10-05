# Native setup

Use this checklist on the running J614s installation. Preserve Alice Admin
(`alice`), hostname `t6040`, autologin, the empty password and passwordless sudo.
Mount and desktop changes do not require kernel replacement or enrollment.
Keep the working USB/kernel baseline and `idle=nop arm64.nowfxt`.

## Readable /boot

Confirm the mounted SD installation before editing:

```sh
uname -r
id
findmnt --mountpoint /boot -no SOURCE,FSTYPE,OPTIONS
sudo cat /boot/arch-m4-card.json
sudo cat /etc/fstab
pacman -Q | awk '$1 ~ /^(linux-m4rch|config-m4rch|linux-t6040|arch-m4-config|plasma-workspace|kwin|sddm)$/ {print}'
```

Expect `vfat` and layout `arch-m4-uefi-v2`. If unmounted, use the existing fstab
entry: `sudo mount /boot`. Stop if the card or installation is different.

Back up `/etc/fstab`. In its active `/boot` entry, replace only `uid`, `gid`,
`umask`, `fmask` and `dmask` options with:

```text
uid=0,gid=0,fmask=0133,dmask=0022
```

Preserve the device/PARTUUID, unrelated options and fsck fields. This gives
root-owned directories 0755 and files 0644; everyone can read, only root can
write. FAT ignores these permission options on remount, even when the command
succeeds. Validate the entry, then verify a **fresh mount after reboot**:

```sh
sudo systemctl daemon-reload
sudo findmnt --verify --verbose
# After reboot:
findmnt --mountpoint /boot -no SOURCE,FSTYPE,OPTIONS
stat -c '%a %U:%G %n' /boot /boot/EFI/BOOT/BOOTAA64.EFI
sudo -u alice test -r /boot/EFI/BOOT/BOOTAA64.EFI
sudo -u alice test -x /boot
sudo -u alice test ! -w /boot
sudo -u alice test ! -w /boot/EFI/BOOT/BOOTAA64.EFI
```

Check every exit status. If masks remain 0077, collect the fstab, `boot.mount`
unit/options and its journal. Installing `config-m4rch` does not migrate an
existing fstab entry; fresh images already use the readable policy.

## Software-rendered Plasma Wayland

Check the installed session and software compositor first:

```sh
pacman -Q plasma-workspace kwin plasma-x11-session kwin-x11 sddm
test -f /usr/share/wayland-sessions/plasma.desktop
systemctl --user cat plasma-kwin_wayland.service
sudo ls -l /etc/sddm.conf /etc/sddm.conf.d
```

The packaged KWin 6.7.5 supports QPainter. Verify support before applying this
setting to other versions. Back up modified files. Stage the Wayland service
and autologin overrides:

```sh
sudo mkdir -p /etc/systemd/user/plasma-kwin_wayland.service.d /etc/sddm.conf.d
sudo tee /etc/systemd/user/plasma-kwin_wayland.service.d/m4rch-software.conf >/dev/null <<'EOF'
[Service]
Environment=KWIN_COMPOSE=Q
EOF
sudo tee /etc/sddm.conf.d/zz-m4rch-wayland.conf >/dev/null <<'EOF'
[Autologin]
User=alice
Session=plasma.desktop
Relogin=false
EOF
sudo chmod 644 /etc/systemd/user/plasma-kwin_wayland.service.d/m4rch-software.conf /etc/sddm.conf.d/zz-m4rch-wayland.conf
systemctl --user daemon-reload
# As Alice:
kwriteconfig6 --file kwinrc --group Compositing --key Enabled --type bool true
```

Keep the existing software-rendering flags and X11 greeter. The greeter's
`DisplayServer=x11` does not select Alice's session. Inspect `/etc/sddm.conf`:
it loads after drop-ins and can override their autologin settings. Preserve
unrelated configuration and Alice's other KWin preferences.

Save work before logout/reboot; restarting SDDM ends the active graphical
agent. After login, verify `$XDG_SESSION_TYPE`, the running KWin service,
`qdbus6 org.kde.KWin /KWin org.kde.KWin.supportInformation` and both KWin/SDDM
journals. Settings staged on disk are not evidence of a working Wayland login.

If the desktop fails, use Ctrl–Alt–F2 (also Fn if needed). Restore the override's
session to `plasmax11.desktop`, including any conflicting main-config setting,
then restart SDDM from that console after saving work. Keep compositing enabled.

## CPU experiments

Select the sole kit on the cleaned card; if several exist, choose explicitly:

```sh
set -- /boot/cpu-tools-*
kit=$1
(cd "$kit" && sha256sum -c SHA256SUMS)
python3 "$kit/m4rch-cpu-benchmark" --inspect
sudo python3 "$kit/m4rch-power-report" --runtime
```

The repository’s `docs/cpu-performance.md` records the measured baseline.
Use `native-agent-followup.md` beside this guide for clock/cooling captures.
Linux exports `cpuinfo_cur_freq` root-readable (0400). Run the monitoring
parent with `sudo`, without a governor argument; it keeps the workload as Alice
and writes no policies. Store captures on ext4, with the same benchmark binary,
AC state, desktop and comparable starting temperatures.

Keep all twelve CPUs enabled for normal use. Investigate E/P placement and
sensor interpretation before governor trials. Do not derive scheduler
capacities from aggregate scores or write guessed clocks/fan values.

Return actual versions, mount permissions, session/backend, captures, failures
and rollback paths in a fresh handoff archive on `/boot`. Exclude credentials.
