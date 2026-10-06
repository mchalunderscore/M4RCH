#!/bin/sh
# Build exact upstream tests. ROOT is the pinned Linux source/build tree.
set -eu
root=${1:?Linux source tree required}
out=${2:?Absolute output directory required}
case "$out" in /*) ;; *) echo 'Output must be absolute' >&2; exit 1 ;; esac
patch_file=$(CDPATH= cd -- "$(dirname "$0")/../../patches" && pwd)/selftest-sme-only-signal-frame.patch
mkdir -p "$out"
cd "$root"
make ARCH=arm64 INSTALL_HDR_PATH="$out/headers" headers_install
cd tools/testing/selftests/arm64/abi
gcc -fno-asynchronous-unwind-tables -fno-ident -s -Os -nostdlib -static \
    -include ../../../../include/nolibc/nolibc.h -I../.. -ffreestanding -Wall \
    tpidr2.c -o "$out/TPIDRABI" -lgcc
cd ../signal
mkdir -p "$out/compat/tools/testing/selftests/arm64/signal/testcases"
cp testcases/testcases.c "$out/compat/tools/testing/selftests/arm64/signal/testcases/testcases.c"
(cd "$out/compat" && patch -p1 <"$patch_file")
compat="$out/compat/tools/testing/selftests/arm64/signal/testcases/testcases.c"
for pair in tpidr2_restore:TPIDRRES tpidr2_siginfo:TPIDRFRM sme_vl:SMEVL \
    sme_trap_no_sm:SMENOSM sme_trap_non_streaming:SMENSTR sme_trap_za:SMEZA \
    fake_sigreturn_sme_change_vl:SMEBADVL; do
    src=${pair%:*}
    dest=${pair#*:}
    gcc -static -std=gnu99 -I. -I../.. -I../../../include -I../../../../include \
        -Itestcases -I"$out/headers/include" "testcases/$src.c" test_signals.c \
        test_signals_utils.c "$compat" signals.S sve_helpers.c \
        -o "$out/$dest"
done
