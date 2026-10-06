/* SPDX-License-Identifier: MIT */
.text
.global check_sleep_once
.type check_sleep_once, %function
check_sleep_once:
sub sp, sp, #256
stp x19, x20, [sp, #0]
stp x21, x22, [sp, #16]
stp x23, x24, [sp, #32]
stp x25, x26, [sp, #48]
stp x27, x28, [sp, #64]
stp x29, x30, [sp, #80]
stp q8, q9, [sp, #96]
stp q10, q11, [sp, #128]
stp q12, q13, [sp, #160]
stp q14, q15, [sp, #192]
str x1, [sp, #224]
str x0, [sp, #232]
mrs x2, fpcr
str x2, [sp, #240]
mrs x2, fpsr
str x2, [sp, #248]
mov x2, #258
mov x3, #259
mov x4, #260
mov x5, #261
mov x6, #262
mov x7, #263
mov x9, #265
mov x10, #266
mov x11, #267
mov x12, #268
mov x13, #269
mov x14, #270
mov x15, #271
mov x16, #272
mov x17, #273
mov x18, #274
mov x19, #275
mov x20, #276
mov x21, #277
mov x22, #278
mov x23, #279
mov x24, #280
mov x25, #281
mov x26, #282
mov x27, #283
mov x28, #284
mov x29, #285
mov x30, #286
movi v0.16b, #1
movi v1.16b, #2
movi v2.16b, #3
movi v3.16b, #4
movi v4.16b, #5
movi v5.16b, #6
movi v6.16b, #7
movi v7.16b, #8
movi v8.16b, #9
movi v9.16b, #10
movi v10.16b, #11
movi v11.16b, #12
movi v12.16b, #13
movi v13.16b, #14
movi v14.16b, #15
movi v15.16b, #16
movi v16.16b, #17
movi v17.16b, #18
movi v18.16b, #19
movi v19.16b, #20
movi v20.16b, #21
movi v21.16b, #22
movi v22.16b, #23
movi v23.16b, #24
movi v24.16b, #25
movi v25.16b, #26
movi v26.16b, #27
movi v27.16b, #28
movi v28.16b, #29
movi v29.16b, #30
movi v30.16b, #31
movi v31.16b, #32
ldr x0, [sp, #232]
mov x1, #0
mov x8, #101
svc #0
ldr x1, [sp, #224]
str x2, [x1, #0]
str x3, [x1, #8]
str x4, [x1, #16]
str x5, [x1, #24]
str x6, [x1, #32]
str x7, [x1, #40]
str x9, [x1, #48]
str x10, [x1, #56]
str x11, [x1, #64]
str x12, [x1, #72]
str x13, [x1, #80]
str x14, [x1, #88]
str x15, [x1, #96]
str x16, [x1, #104]
str x17, [x1, #112]
str x18, [x1, #120]
str x19, [x1, #128]
str x20, [x1, #136]
str x21, [x1, #144]
str x22, [x1, #152]
str x23, [x1, #160]
str x24, [x1, #168]
str x25, [x1, #176]
str x26, [x1, #184]
str x27, [x1, #192]
str x28, [x1, #200]
str x29, [x1, #208]
str x30, [x1, #216]
str x0, [x1, #224]
str q0, [x1, #240]
str q1, [x1, #256]
str q2, [x1, #272]
str q3, [x1, #288]
str q4, [x1, #304]
str q5, [x1, #320]
str q6, [x1, #336]
str q7, [x1, #352]
str q8, [x1, #368]
str q9, [x1, #384]
str q10, [x1, #400]
str q11, [x1, #416]
str q12, [x1, #432]
str q13, [x1, #448]
str q14, [x1, #464]
str q15, [x1, #480]
str q16, [x1, #496]
str q17, [x1, #512]
str q18, [x1, #528]
str q19, [x1, #544]
str q20, [x1, #560]
str q21, [x1, #576]
str q22, [x1, #592]
str q23, [x1, #608]
str q24, [x1, #624]
str q25, [x1, #640]
str q26, [x1, #656]
str q27, [x1, #672]
str q28, [x1, #688]
str q29, [x1, #704]
str q30, [x1, #720]
str q31, [x1, #736]
ldr x2, [sp, #240]
str x2, [x1, #752]
mrs x2, fpcr
str x2, [x1, #760]
ldr x2, [sp, #248]
str x2, [x1, #768]
mrs x2, fpsr
str x2, [x1, #776]
ldp q8, q9, [sp, #96]
ldp q10, q11, [sp, #128]
ldp q12, q13, [sp, #160]
ldp q14, q15, [sp, #192]
ldp x19, x20, [sp, #0]
ldp x21, x22, [sp, #16]
ldp x23, x24, [sp, #32]
ldp x25, x26, [sp, #48]
ldp x27, x28, [sp, #64]
ldp x29, x30, [sp, #80]
add sp, sp, #256
ret
.size check_sleep_once, .-check_sleep_once
.section .note.GNU-stack,"",%progbits
