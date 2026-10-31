#!/bin/sh
# Derive the read-only Touch ID trial tree from the verified current board DTB.
set -eu
if [ "$#" -ne 2 ]; then
    echo "usage: $0 CURRENT-J614S-DTB OUTPUT-DTB" >&2
    exit 2
fi
input=$1 output=$2
expected=5ef0aec63e8bb4b0deb9343f17de11dcc35a2c00815d1209cf283a69e87c42c6
actual=$(sha256sum "$input" | cut -d' ' -f1)
[ "$actual" = "$expected" ] || { echo 'unexpected base DTB; refusing' >&2; exit 1; }
[ "$input" != "$output" ] || { echo 'output must differ from input' >&2; exit 1; }
cp "$input" "$output"
fdtput -t s "$output" /aliases sep /sep@406600000
fdtput -t s "$output" /spi@429108000 status okay
fdtput -t s "$output" /spi@429108000/fingerprint@0 status okay
fdtput -t s "$output" /spi@429108000/fingerprint@0 firmware-name apple/mesacal-j614s.bin apple/msrk-j614s.bin
