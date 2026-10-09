# Native PWRGATE candidate ready for a fresh boot

The distinct candidate at `out/gfx-native-powergate/candidate` is finalized,
qualified offline and **never loaded**. This checkpoint supersedes the earlier
source-only qualification's pending-wrapper/receipt statements. The current
boot94cb owner has consumed its OFF attempt and retains174 pages; only its
existing typed diagnostics remain admitted. A normal fresh boot is required
before the new cold trial.

The new comparison adds the matched native management PWRGATE request before
CPU stop and paired provider OFF. It sends exactly one EP0
`0x0060000000000202`, accepts native type7/low8 in{1,2} after that sole request,
then checks native idle and performs fresh CTRL44 clears0x10 and0x20 with
readbacks. RX must be freshly empty at admission, after the ACK and before CPU
writes. A late or unknown ACK, pending frame, invalid status, failed readback or
reasserted START prevents OFF. Only checked CPU stop reaches paired PMP/PMC OFF
and the sole normal PM put. No SLEEP201, warm START/INIT220 or old reset trial
is repeated.

All174 pages, context, mappings, consumer and module remain retained on every
result. Native mapper-inactive and firmware-unmap effects remain outside this
probe. It tests management, CPU control and provider OFF; it establishes no
whole-GPU isolation, DMA/cache/fabric drain, retirement, restart or drawing.

The compiled command interface permits only `sample`, `gfx-snapshot` and one
combined `gfx-powergate`. Host and kernel consume intent before access and close
later control paths. Interrupted writes, lost state with durable history, and
capture/journal errors preserve the terminal boundary. Unknown startup admits
no commands and does not enter the old sleep/stop cleanup path. Initial cold
startup, graph/dormant draw bytes and two recovery requests remain comparable;
known healthy2-cycle or diagnostic0/1-cycle states can reach the new probe.

The final module built against the installed native-reset kernel with W=1,
exit0 and zero warnings/errors. Actual C/header/startup replay passed55 cases
under ASan/UBSan, including failures and retries after partial stop or consumed
PM put. Python qualification passed196 cases, including45 actual cold-main
flows and resident command/validation/main replays. Existing core, adapter and
provider qualifications compose separately. Independent source review passed;
mocked tests establish no live ACK, physical power collapse or reset.

Root finalized and revalidated all10 artifact,18 owner-source and13 preparation
input pins. The old native STATUS0 wrapper refuses this new family. The actual
new fresh-preflight CLI refuses current boot94cb before candidate validation or
GPU access; it creates no output. Read-only kernel/module notes and software
refcount confirm that the old consumed owner remains loaded with reference1,
while the new owner is not loaded. The kernel, USB providers and GRUB default5
remain unchanged. No new kernel installation or boot selection is needed.

| Final artifact | SHA256 |
| --- | --- |
| Owner | `7bced3badf35f4e99ade95428622e26e3259fbc37c16de13eb0d845e9b6745bc` |
| Candidate receipt | `3fe4a6da3a8db86709fc9d307708cf7332c21fbc1f4414b2f8ea5e3a29a61053` |
| Preparation | `bf34db138e283940da2820110811057dc7ac0adedbed85fcc82faeeb1634b217` |

After the user's normal fresh boot, root first performs the new read-only
preflight, then ONE cold attempt only if preflight succeeds:

```sh
sudo -n python experiments/t6040-gpu/gfx-native-powergate/preflight-fresh.py out/gfx-native-powergate/candidate out/gfx-native-powergate/fresh-preflight.json
sudo -n python experiments/t6040-gpu/gfx-native-powergate/run-root-powergate.py out/gfx-native-powergate/candidate --graph --run
```

Only qualified startup admits the new typed `gfx-powergate` command. Preserve
the final operation report and diagnose through admitted retained snapshots;
never retry a consumed intent, issue independent STOP/OFF, resume, submit work,
detach/unmap/free or unload. Do not reboot through tools. Root owns hardware;
subagents stay offline. Any later restart experiment needs separate evidence.

The [bound preparation evidence](2026-10-09-gfx-native-powergate-prepared.json)
joins the final candidate to [actual C/native qualification](2026-10-09-gfx-native-powergate-c-qualification.md),
[wrapper qualification](2026-10-09-gfx-native-powergate-wrapper-qualification.md)
and [independent review](2026-10-09-gfx-native-powergate-independent-review.md).
Earlier draft sources, qualifications and the unselected warning-bearing build
remain preserved. Private Apple binaries and full disassembly stay ignored;
APFS must be read-only if mounted. The GPU/Mesa/DCP desktop goal remains active.
