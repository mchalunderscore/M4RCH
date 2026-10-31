# Steam package source and licenses

This package combines Valve's Steam launcher with locally packaged helpers.
Valve's subscriber agreement and the upstream steam-launcher copyright file
are installed in the package's license directory. Those terms do not license
the separately identified open-source helpers.

`userpages.c` is based on Aurora Linux's
[`tools/aurora-userpages/userpages.c`](https://github.com/aurora-silicon/linux/blob/23827fe87f4ffbabf5b7907a5907f9316286ce55/tools/aurora-userpages/userpages.c)
at `23827fe87f4ffbabf5b7907a5907f9316286ce55`. Its include was adjusted to
use the packaged `userpages-prctl.h`; the rest matches that source. It is
GPL-2.0-only. The header is the same revision's
[`include/uapi/linux/prctl.h`](https://github.com/aurora-silicon/linux/blob/23827fe87f4ffbabf5b7907a5907f9316286ce55/include/uapi/linux/prctl.h),
under GPL-2.0 with the Linux syscall exception. Their exact packaged source is
installed under `usr/share/doc/steam-m4rch/userpages/`.

`steam-native4k-launch-loop.sh` derives from the Aurora Steam launcher, carries
Ryan Murray's copyright and the MIT SPDX notice in its header, and has local
adjustments. The MIT permission notice is in `MIT-aurora-steam-native.txt`.
The GPL text and syscall exception are `GPL-2.0-only.txt` and
`Linux-syscall-note.txt`, respectively. These notices are installed with the
package.
