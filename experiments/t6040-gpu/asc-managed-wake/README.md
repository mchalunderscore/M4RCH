# Experimental managed RTKit wake cycles

Derived from the bounded crashlog probe. Starts only from fresh observed status6a.
Holds ASC START and GFX power across up to three boot/acknowledged-shutdown cycles,
sending INIT220 after SLEEP without toggling START. Final stop/empty FIFO and both
power ACKs required for conditional unload; failures pin resources until reboot.
No native qualification yet. Use freshly qualified DATA bounds in boot-contract.h,
matching kernel/build/module hashes and a fresh boot. No application endpoints,
initialization objects or new DMA buffers. Never force unload.
