# Experimental application endpoint start-only trial

Cold status6a only. Qualify crashlog1 and reserved firmware DATA offer, IOP/AP ON,
then send management START for advertised32/33. No root graph, work submission
or new DMA buffer. Sending START does not prove app readiness. Exact power ACKs,
stop readback and empty FIFO required for conditional retirement; otherwise pins
until reboot. Revalidate fresh boot/build/module and firmware DATA contract.
Not yet run natively. Warm wake remains unresolved; never force module removal.
