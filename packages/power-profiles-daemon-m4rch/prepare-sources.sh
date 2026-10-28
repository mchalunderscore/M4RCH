#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
repo=$(mktemp -d)
trap 'rm -rf "$repo"' EXIT
git clone --quiet --depth 1 --branch 0.30 https://gitlab.freedesktop.org/upower/power-profiles-daemon.git "$repo/source"
test "$(git -C "$repo/source" rev-parse HEAD)" = 5b4994c8a91290481bef87a5bae95391d0ec677f
git -C "$repo/source" archive --prefix=power-profiles-daemon-0.30/ --format=tar.gz -o "$PWD/power-profiles-daemon-0.30.tar.gz" HEAD
install -m 644 /var/cache/pacman/pkg/power-profiles-daemon-0.30-1-aarch64.pkg.tar.xz .
printf '%s\n' '6cce45f7b93af1563fe6842a1d2cb21dbc7434498f4a5f2cacb7b48d3c3175da  power-profiles-daemon-0.30.tar.gz' 'c1fe5080a573c73ed200217bbde3e11ba115568f810e260f004476929b3c7e64  power-profiles-daemon-0.30-1-aarch64.pkg.tar.xz' | sha256sum -c
