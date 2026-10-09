# Independent checked GFX reset API review

The final offline patch was reviewed against the matched PMGR driver and the saved
registered GFX provider metadata. It applies to the original driver without fuzz;
the resulting source and public header exactly match the staged implementation.
No hardware or live sysfs access, module operation or kernel-tree mutation was performed by this reviewer.

The independent replay of the actual extracted C core passed **98 fault cases**
under ASan and UBSan. Tests inject errors before and after committed writes,
permanent read/write failures, stuck control bits, power/target loss, existing
reset consumers, and cleanup failures. LSan is disabled in the ptrace sandbox.
The adjacent JSON binds the patch, original/staged source, header, tests, provider
metadata and replay report by SHA-256.

Five findings were resolved during review:

- The driver-owned pulse now holds `rcdev.lock`, refuses a nonempty reset-reference
  list, and excludes new reset references throughout the pulse.
- It rejects preexisting PS_RESET bit12 and BUSY bit11 in addition to device RESET
  bit31 and DEV_DISABLE bit10, and requires ON with ACTUAL/TARGET15.
- Cleanup begins after the first attempted update because an error may follow a
  committed bus write; primary and cleanup errors remain separate.
- Cleanup first attempts to inhibit AUTO_ENABLE again, then confirms inhibition
  and both release bits before restoring the original policy. Failed access can
  leave inhibition unconfirmed; the public header states that uncertainty.

- Register reads publish their value and validity only on success. A failed
  provider read cannot corrupt an earlier valid poll sample.

The reviewed lock order is provider device mutex, reset-controller mutex, existing
IRQ-safe domain spinlock, and MMIO regmap lock. Device references and the provider
mutex protect driver-data lifetime, and driver data is published only after
successful registration. The domain spinlock covers the whole 10 microsecond
pulse and bounded polls; the implementation does not call the legacy reset
callbacks while holding their lock.

The test model excludes execution of the kernel DT/device wrapper and actual
concurrency. Inspection of reset core establishes the mutex/list relationship;
it is not a live concurrency test. PMGR command readback establishes neither ASC,
GPU engine, UAT, cache, PHY nor outstanding-DMA reset coverage. No Apple native PAC
or PHY path is invoked. All GPU backing must remain retained, including after a
successful pulse. This remains an offline candidate for a new kernel build; it
must not be installed as a duplicate PMGR driver over the current built-in provider.
