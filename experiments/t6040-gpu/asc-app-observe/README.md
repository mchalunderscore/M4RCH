# Bounded application startup observation

Extends application START-only test with250ms/32-message observation. No replies
to application traffic, root graph, work submissions or new DMA allocation.
Qualified crashlog/ON sequence precedes START32/33; exact shutdown ACKs,
stop readback and empty FIFO required for conditional unload. Pin on failure.
Cold status6a only, fresh DATA bounds/header and boot/build/module hash checks.
Built but not run natively. Sending START or observing silence proves no rendering.
