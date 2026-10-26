# Combined draw and postdraw native cycle ready

The v16 candidate keeps trace3 through the existing control33, then submits the same one TA/3D draw and captures15s. Unlike v15's shared-only restore, opcode22 refreshes the actual firmware trace cache. The four native PID/subpriority corrections remain.

After immutable full image/completion/queue/journal/object/DATA/page-table capture, the selected host may issue one retained postdraw native202 cycle. It requires bounded admission drain, its own ACK, native idle and checked CPU stop before paired OFF/PMput; physical OFF and reference accounting are independently checked. Only a qualified OFF admits a separate paired ON/PMget and carried-AP20 management rejoin. Postdraw admission has an explicit250ms/256-frame budget for tracing backlog, with staleEP0/crash/type/capacity and final fresh mailbox guards preserved.

All174 pages, mappings and context remain pinned. There is no root/application/work replay, cursor reset, DATA restore, second cycle, unsupported kill2c, arbitrary bit clear, unload or free. Unknown OFF prevents device access until separately qualified ON. Management rejoin does not prove application reuse, DMA retirement or rebootless rendering.

Continuous tracing may fill the inherited 65,536-record journal before the 15-second observation ends. Overflow seals the draw, retains its captured prefix and prevents the postdraw cycle. The prefix may still locate where dispatch stops.

The module build is clean. 36 actual C sanitizer cases and 24 essential host cases passed; frozen unchanged checks are composed without a broad rerun. The candidate has never loaded. Its actual preflight refuses current consumed boot d834. Kernel/GRUB are unchanged.

Candidate: `/home/alice/Desktop/m4rch/out/gfx-postdraw-native-cycle/candidate`. Owner SHA256 `37ade18e241273dfcaea73fd5ccb9643f1f043c4683347c45f794552e5f76c3c`. Source receipt `08383fcfe70b92f5562288f2ec60b01f7712d5e4f9cf40a7a728dce7e05ed1c5`. The JSON companion pins the selected build, actual checks, previous trial and native integration findings. One manual reboot into the existing native-reset kernel is required before the selected trial.
