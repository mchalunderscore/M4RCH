// Minimal libc-free AArch64 finit_module helper. Exit 1 on any syscall failure.
.text
.global _start
_start:
    ldr x1, [sp, #16]
    mov x0, #-100
    mov x2, #0
    mov x3, #0
    mov x8, #56
    svc #0
    cmp x0, #0
    b.lt fail
    adr x1, parameters
    mov x2, #0
    mov x8, #273
    svc #0
    cmp x0, #0
    b.lt fail
    mov x0, #0
    b exit
fail:
    neg x0, x0
exit:
    mov x8, #93
    svc #0
parameters:
    .asciz ""
