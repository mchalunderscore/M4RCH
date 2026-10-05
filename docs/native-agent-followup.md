# Native verification

Verify the next boot before further CPU tuning. Keep the working kernel,
loader, governors, fan settings and `idle=nop arm64.nowfxt`.

## Mount and desktop

From Alice's graphical terminal:

```sh
capture="$HOME/m4rch-check-$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -m 700 "$capture"
{
    uname -r
    pacman -Q | awk '$1 ~ /^(linux-m4rch|config-m4rch|linux-t6040|arch-m4-config|plasma-workspace|kwin|sddm)$/ {print}'
    findmnt --mountpoint /boot -no SOURCE,FSTYPE,OPTIONS
    stat -c '%a %U:%G %n' /boot /boot/EFI/BOOT/BOOTAA64.EFI
    printf 'Session=%s Desktop=%s\n' "$XDG_SESSION_TYPE" "$XDG_CURRENT_DESKTOP"
    qdbus6 org.kde.KWin /KWin org.kde.KWin.supportInformation
} > "$capture/boot-desktop.txt" 2>&1
systemctl --user show plasma-kwin_wayland.service -p Environment > "$capture/kwin-environment.txt"
journalctl --user -b -u plasma-kwin_wayland.service --no-pager > "$capture/kwin-journal.txt"
sudo journalctl -b -u sddm --no-pager > "$capture/sddm-journal.txt"
```

Expect `/boot` vfat with root-owned directories 0755/files 0644 and masks
`fmask=0133,dmask=0022`. As Alice, verify readability/traversal and no writes:

```sh
test -r /boot/EFI/BOOT/BOOTAA64.EFI
test -x /boot
test ! -w /boot
test ! -w /boot/EFI/BOOT/BOOTAA64.EFI
```

Check each exit status. FAT ignores these masks on remount; if a fresh boot
still shows 0077, capture `/etc/fstab`, `systemctl cat boot.mount`, its `What`,
`Where`, `Options` properties and journal before changing settings.

Expect `wayland` and the actual QPainter backend. Exercise keyboard/trackpad,
scaling, Firefox, Codex, Bluetooth playback and the right-port YubiKey. Have
the user test authentication without logging credentials. Right-port USB2 is
the demonstrated path; left ports/USB3 remain disabled. The console fallback
and configuration steps are in the accompanying setup guide (`instructions.md`
on the card; `docs/native-agent-instructions.md` in the repository).

## Clocks and cooling

The previous unprivileged capture could not read mode-0400 hardware clocks.
Use a privileged monitoring parent with Alice's workload and no policy changes:

```sh
# If several kits exist, choose the intended directory explicitly.
set -- /boot/cpu-tools-*
kit=$1
(cd "$kit" && sha256sum -c SHA256SUMS)
sudo sh -c '
for policy in /sys/devices/system/cpu/cpufreq/policy*; do
    printf "\n%s\n" "$policy"
    ls -l "$policy/cpuinfo_cur_freq"
    cat "$policy/scaling_governor" "$policy/scaling_cur_freq" "$policy/cpuinfo_cur_freq"
done
' > "$capture/clock-access.txt" 2>&1
sudo python3 "$kit/m4rch-power-report" --runtime > "$capture/power-root.json"
sudo sh "$kit/run.sh" --cpus all --output "$capture/cooling-idle" -- sleep 60
```

Record AC/ambient conditions, fan behaviour and readable sensor/min/max/target
fields. The prior run reported a 114.25°C CPU sensor peak and modestly rising
fan targets; this needs interpretation, not guessed fan or frequency writes.
Inactive GPU readings do not establish temperatures. With `idle=nop`, this is
not a deep-idle measurement. The repository’s `docs/cpu-performance.md` records
the measured baseline.

Inspect and save `./geekbench7 --help` before selecting new comparisons. Use
supported local-result flags, the same binary/governor/desktop and comparable
cooling. If supported, isolate one verified P CPU versus one E CPU and repeat
in reverse order. Use root monitoring while keeping the benchmark as Alice.
Keep new Wayland measurements separate from the X11 baseline. Sampled CPU
residency is approximate; aggregate scores cannot calibrate core capacities.

## Return evidence

Write a short report in the capture directory: observed mount/session/backend,
clock access, cooling, failures and any changes with rollback. Use a new name:

```sh
stamp=$(date -u +%Y%m%dT%H%M%SZ)
sudo tar -czf "/boot/m4rch-native-check-$stamp.tar.gz" \
    -C "$(dirname "$capture")" "$(basename "$capture")"
sync
```

Preserve previous evidence and exclude credentials or tokens.
