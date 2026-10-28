#!/bin/bash
set -euo pipefail
candidate=${1:?Pass the candidate package path}
previous=/var/cache/pacman/pkg/m4rch/mbpfan-m4rch-2.4.0-2-aarch64.pkg.tar.zst
backup=/var/lib/m4rch-fan-trial
test "$(id -u)" = 0
test -f "$candidate" && test -f "$previous"
test "$(uname -r)" = 7.3.0-m4rch
mkdir -p "$backup"
if test -e "$backup/mbpfan.conf.before-quiet"; then
  cmp -s /etc/mbpfan.conf "$backup/mbpfan.conf.before-quiet"
else
  cp -p /etc/mbpfan.conf "$backup/mbpfan.conf.before-quiet"
fi
rollback() {
  echo 'Installation failed; restoring the previous package and configuration.' >&2
  pacman -U --noconfirm "$previous" || true
  cp -p "$backup/mbpfan.conf.before-quiet" /etc/mbpfan.conf
  systemctl restart mbpfan.service || true
}
trap rollback ERR
pacman -U --noconfirm "$candidate"
install -m 644 /usr/share/doc/mbpfan-m4rch/quiet-trial.conf /etc/mbpfan.conf
systemctl restart mbpfan.service
systemctl is-active --quiet mbpfan.service
trap - ERR
echo "Installed quiet fan trial. Previous config: $backup/mbpfan.conf.before-quiet"
