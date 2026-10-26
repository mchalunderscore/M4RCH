# Retained transport re-entry boundary

Offline source integration only. No hardware action, source-kit change, candidate
change, wake trial, or teardown was performed. The paired coordinate candidate
remains frozen and never loaded. The companion JSON pins the inputs below.

The positive retirement result in
`docs/evidence/2026-10-08-graph-retirement-native-result.json:173` covers a
71-page operand-free control fixture: acknowledged shutdown, detached owned
root, no remaining table references, ordinary unload, released MMIO claims and
one successful runtime suspend. It does not cover the 174-page joined context.
The joined INIT receipt explicitly retains its live context, backing, module and
GFX ownership after ACKs and ASC control0/status6e. No same-context second boot,
DMA retirement or render execution is established by either result.

Gravity provides a useful autonomous cold boot sequence, but its generic RTKit
restart functions are unsuitable for this retained experiment.
`out/gpu-gravity-contract/linux/drivers/soc/apple/rtkit.c:773` stops mailbox work
and frees five shared buffers and the syslog message buffer before resetting
host completions. `apple_rtkit_wake` at line1087 sends INIT0x220, then calls
`apple_rtkit_boot`. Boot at line961 waits for endpoint-map/IOP ACK completions;
it does not start the CPU, restore DATA or establish fresh firmware state.
`asahi/g16.rs:338` performs START then autonomous boot, while its destructor at
line225 retains GPU mappings when shutdown fails. These functions supply no
qualified method to restart this already published joined context.

The matched RTBuddy review already establishes a conditional memory-preserving
route: prior native IOP status1/2 selects start options0, which enables provider
power, activates/maps firmware and runs the CPU. The saved preloaded firmware
path neither copies mutated DATA nor establishes a reset vector; repeated iBoot
mapping can intentionally be a no-op. Native PWRGATE202 also requires a distinct
IOP handshake and checked CPU stop. Our packet-free STOP does not establish
that native bookkeeping/handshake. Paired PMP/PMC completion and strict physical
OFF observation therefore cannot by themselves establish readiness to reboot
firmware or reuse application state.

The frozen owner exposes the concrete future integration point under
`graph_io_lock` in `out/gfx-native-coordinate/candidate/asc-graph-init/recovery-cycle.h:247`.
Any separate re-entry profile would first require successful first coordination
ON/OFF, the sole PM put, usage0/suspended ownership, and the strict provider-OFF
observation (`gfx-reset-scope.h:237`). It would retain the same consumer, all174
page identities, installed root and joined context. A second PM get and a
separate coordinator session would preserve the first epoch's evidence; resetting
the current paired-once session or clearing terminal flags would not do so.

The smallest useful later probe would admit at most one START after a fresh
ACTIVE observation and second paired ON, only if ASC again satisfies the
original cold boundary: START clear, status0x6a, empty RX FIFO
(`asc-graph-init.c:347`). This is a conservative experiment admission condition,
not a native guarantee that OFF/ON produces0x6a or proof of fresh DATA. The probe
would seek fresh autonomous HELLO12/map using a new host-only protocol journal,
then retain everything. No INIT0x220, application endpoint/root publication,
queue/counter reset, context reattach, free or unload follows that transport
observation. A status6e/6c/48 outcome refuses before START and does not repeat
the failed warm trials.

`graph-map.h:96` allocates and copies new backing, so `root_prepare` cannot be
reused against the retained `owned[]` array. `joined-context-init.h:17` requires
an empty reserved context table and publishes its root; it cannot attach the
already populated context a second time. `graph-map.h:81` correctly refuses
release when the joined context remains retained. Any eventual application
rejoin must separately establish the firmware's retained-context contract.

No re-entry source is prepared now. The first fresh coordinated idle result
must select whether such a transport probe has an admissible new hypothesis.
