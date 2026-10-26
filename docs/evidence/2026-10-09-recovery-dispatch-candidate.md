# Native main-dispatch tracing for the remaining recovery wait

Built and reviewed; **not run**. Candidate: `out/recovery-dispatch/candidate`.
Module SHA256:
`332d9d04f3dc2ada1de5b312910a5d5e65eb92165a28f9a6f3768cb627b81191`.
Current boot1730bf24 is sealed after the preceding trial. Do not repeat that
candidate unchanged or run this candidate before a normal reboot.

The preceding native marker supports progress to64c0. Subsequent recovery
publishes scheduler mask7 and sampler mask8, waits for semaphore18e430,
publishes scheduler bit25, waits for18e438, then publishes power bit15 and
waits for18e408 before phase3. The normal sampler ACK has no native trace
point. Six RAM cases reach its signal; no configuration omission was found.
The three empty scheduler callbacks also return in nine qualified RAM cases.
Those checks exclude real scheduling, cache/trace locks and engine behavior.

This candidate changes only **status_a+0 from1 to3**, retaining bit0 and adding
native trace bit1. That bit emits role0 main-handler entry12f and exit130,
including the handler mask. A fresh bit25 (`0x2000000`) entry after the recovery
marker supports passing the first wait. Its matching exit supports return
after signaling the second ACK; it does not prove recovery consumed that
signal or distinguish the final power wait. Event112 additionally reports
lane/cursor state. Interpret timestamps, phase/token chronology and journal
health together; missing events do not locate a live PC.

All mappings, pointers, controls, native2/40ms defaults and the immutable
56-page triangle are preserved. A generated header appends the existing
trace-mask offset and initial value. The host counts completed cycles only
after phase/request/idle checks and fresh control consumption.

After four completed idle cycles, typed `trace-off` drains healthy RX, checks
idle phase/request state and coherent control cursors, clears only the owned
trace mask, then publishes and consumes one fresh native configuration command
(decimal22, hex0x16). Native disable and zero-copy semantics were independently
checked. Failure seals the session; submit is blocked until trace-off succeeds.
This reduces gated tracing during the long triangle capture. Queued and
unconditional records remain possible. Journal capacity is65536; the traffic
model is not a bound, and overflow retains backing and seals publication.

Validation passed: `W=1` build, complete final receipts, exact one-byte graph
difference, unchanged draw/maps/control records, reproducible preparation,
and88 actual-C replay cases under ASan/UBSan. The adjacent JSON binds all proofs.
This is a diagnostic expansion, not an established recovery fix.

After a different normal boot and clean PD/module baseline, run once:

```sh
sudo -n python experiments/t6040-gpu/run-root-envelope.py out/recovery-dispatch/candidate --graph --run
```

Only after two clean cycles and a usable resident session:

```sh
sudo -n python experiments/t6040-gpu/run-resident-gpu.py out/recovery-dispatch/candidate recover
```

Only after four clean cycles, with a healthy journal:

```sh
sudo -n python experiments/t6040-gpu/run-resident-gpu.py out/recovery-dispatch/candidate trace-off
```

Only after trace-off returns successfully with fresh control consumed:

```sh
sudo -n python experiments/t6040-gpu/run-resident-gpu.py out/recovery-dispatch/candidate submit
```

Inspect completion backing and target pixels at1/5/15/30seconds. Any failure
permits only sample/stop. All174 DMA pages remain retained; no force unload,
warm retry or work reuse. Recovery, teardown, GPU execution and rendering
remain unverified.
