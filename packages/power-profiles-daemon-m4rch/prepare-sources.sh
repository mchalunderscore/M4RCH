#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
commit=1a151ccd8bb42c050960f65ca3dee31effde6b36
curl -fsSL "https://gitlab.freedesktop.org/upower/power-profiles-daemon/-/archive/${commit}/power-profiles-daemon-${commit}.tar.gz" -o power-profiles-daemon-source.tar.gz
install -m 644 /var/cache/pacman/pkg/power-profiles-daemon-0.30-1-aarch64.pkg.tar.xz .
printf '%s\n' 'a0c3514a84f43df2b6b331d11ec2497fe83e2e9db666a7ff1336cfefae63020d  power-profiles-daemon-source.tar.gz' 'c1fe5080a573c73ed200217bbde3e11ba115568f810e260f004476929b3c7e64  power-profiles-daemon-0.30-1-aarch64.pkg.tar.xz' | sha256sum -c
