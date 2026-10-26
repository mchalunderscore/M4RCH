# Experimental handshake-only RTKit shutdown probe

Extends the bounded ASC enumeration probe with AP QUIESCED (type b/state10),
then IOP SLEEP (type6/state1), requiring exact management ACKs. No system or
application endpoints start and no buffer address is supplied. Default gate
refuses startup. Failed retirement pins resources until reboot; never force
unload. Conditional normal unload is restricted to both ACKs, core-stop
readback and an empty RX FIFO; this does not authorize full driver teardown.

First 25G83 trial received no AP ACK after the minimal HELLO/map exchange,
therefore retained resources. No successful retirement has been established.
Next qualify system endpoint1/crashlog lifecycle and IOP ON before retrying;
the donor RTKit implementation starts system endpoints to complete boot.

Build only against the exact booted GPU-contract tree; bind every native run
to its boot ID, kernel build ID and module hash. Inspect failure logs before
any retry; a started pinned instance requires a normal reboot.
