# J614s Wi-Fi firmware recovery material

The initial J614s installation lacked BCM4388 C2 Mriya Wi-Fi firmware. The owner restored Wi-Fi using firmware from this Mac's macOS installation. `prepare_wifi_firmware.py` can prepare a private bundle from a macOS firmware directory; its bundled `install-wifi.sh` was written for the retired `linux-m4rch` installation and refuses the current kernel. It is not a current-system recovery procedure. Never publish firmware, calibration, or the bundle.

The old private installer and boot-image development tools targeted the retired M4RCH stack and required inputs no longer present in this checkout. They are in Git history at `9616ae8`; they do not build the current Aurora fork stack. The first installation used unencrypted Btrfs, and recovery from an interrupted conversion was not qualified.

See [installer comparison](../../../../docs/installer-upstream.md) for the current fork and validation limits, and [boot recovery](../../../../docs/recovery.md) for the current system's recovery path.
