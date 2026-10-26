# Native G16 scheduler NOP body and timestamp conversion

Private-derived offline evidence for the matched AGX353.14 binary. SHA256 is
recorded in the accompanying JSON. This is implementation arithmetic tested
against native instructions in emulated RAM, not live firmware acceptance.

## Results

512 randomized cached-prior body patches, 512 uncached body patches following
the actual native branch and helper BL/RET, and 1,024 independent timestamp
conversions matched. Full 0x200-byte record and 0x100-byte queue comparisons
check that unspecified bytes remain unchanged. No external services run.

The record header uses the previously qualified kind2 timestamp/queue/priority
encoding. The body sets bit0 at +0x20 and inserts a previous scheduler timestamp
into the low47 bits of +0x28, ORing queue ID low7 bits at bit40. This differs from
the main header's queue ID at bit42. Preserve the native overlap; arbitrary-width
inputs characterize masks, not valid protocol timestamp values.

Four u64 notification words are copied to +0x128/+0x130/+0x138/+0x140. The low byte
at +0x148 is cleared, as are the low50 bits of four descriptor words at
+0x150/+0x158/+0x160/+0x168. Word +0x178 becomes zero. Two caller payload words
are copied into +0x10/+0x18. In this NOP caller these are a command type and
channel-state GPU address, not an ordinary work-command pointer pair.

A DMB ISH precedes queue counter advancement. Return value x0 is the original
queue +0x48 timestamp. The audit stops before the atomic pending-count increment,
which still needs qualification alongside real publication and synchronization.

## Uncached prior dependency

If queue +0x98 bit0 is clear, the actual native branch calls
convertEventMachineTSToHWTS with event index and timestamp arguments, subtracts
one from the returned timestamp, then joins the same body patch. No helper is
stubbed in the uncached test.

The helper reads the event-machine pointer through queue +0x68 / accelerator
+0x140. A nonnegative signed 32-bit timestamp selects event-machine +0x1458;
a negative timestamp selects +0x1460. Each event index advances 24 bytes and the
selected epoch is loaded with acquire semantics. Epoch and timestamp bits are
combined, decremented, divided by queue capacity and rebased against queue +0x90.
The final high counter arithmetic truncates to 32 bits; the slot occupies low8.
Tests include signed boundary and sentinel inputs. They do not establish which
values the event machine should contain during a real job.

## Remaining work

External backing initialization before the patched body remains unqualified.
Atomic pending count, cached-prior update, capacity-full handling and firmware
consumption still need validation. Allocation/map cache policy and actual
rendering job structures remain separate requirements. The retained failed
warm INIT hardware probe still requires reboot before another hardware trial.

Run:

```sh
python experiments/t6040-gpu/audit-private-nop-body.py \
  /boot/GPUC003/private-apple/com.apple.AGXG16X \
  /tmp/private-nop-body.json
```

No private binary or disassembly is included in this evidence.
