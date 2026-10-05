m4rch experimental kernel modules and diagnostics

Copy this entire directory to the SD card as arch-m4-driver-tools. Keep every
file together, including modules.tar.gz and driver-tools-manifest.json.

First boot your existing working Arch installation and install the new modules:

    cd /run/initramfs/sd/arch-m4-driver-tools
    sudo sh ./install.sh

The installer uses Python 3 and depmod (Arch packages python and kmod). It checks
the hashes and release-directory layout, builds module dependency indexes, and
installs the new release beside existing releases. It does not modify your root
filesystem image file from macOS, load a driver, unload a driver, or enroll a new
boot bundle. It refuses to overwrite an existing module release or replace local
edits to /etc/modprobe.d/m4rch-drivers.conf.

The modules are specific to kernel_release in driver-tools-manifest.json. The
compressed kernel image hash is also recorded there. Installing from the older
running kernel is supported: these modules become usable after booting the new
matching bundle. Follow the project's experimental-driver instructions for the
separate macOS boot-bundle staging and Recovery enrollment step.

The blocklist prevents alias-based autoload of the experimental storage, power
and USB controllers. Explicit modprobe commands still work. Use the project's
documented test groups, one group per boot, with a saved baseline report. Built-in
drivers and firmware setup still run on boot; a blocklist does not make the
experimental device tree passive. Do not force module removal with rmmod -f.

After booting the experimental bundle, check the running release:

    uname -r

Before and after each trial, save a diagnostic report under a different name:

    sudo m4rch-driver-diagnostics --output /run/initramfs/sd/arch-m4-driver-baseline.txt
    sudo m4rch-driver-diagnostics --output /run/initramfs/sd/arch-m4-driver-after.txt

If the helper is not installed yet, it also runs directly from this directory:

    sudo sh ./m4rch-driver-diagnostics --output /run/initramfs/sd/m4rch-driver-diagnostics.txt

The collector reads existing logs and device metadata. It does not load modules,
mount filesystems, change power controls, or read disk contents. It publishes a
completed report atomically, preserving a previous report if collection fails.
Wait for the "Saved ... bytes" confirmation before shutdown. The report cannot
recover messages from a subsequent hard hang: photograph the final console in
that case. A clean shutdown is still required to persist unrelated filesystem
changes safely.
