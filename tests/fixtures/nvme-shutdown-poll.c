/* Host-only model for the actual internal m1n1 SHST wait. */
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
typedef uint64_t u64;
typedef uint32_t u32;
#define NVME_SHUTDOWN_TIMEOUT 5000000
#define NVME_CC 0x14
#define NVME_CSTS 0x1c
#define NVME_CC_SHN (3u << 14)
#define NVME_CC_SHN_NORMAL 1
#define NVME_CSTS_SHST (3u << 2)
#define NVME_CSTS_SHST_DONE 2
#define FIELD_PREP(mask, v) ((v) << 14)
#define FIELD_GET(mask, v) (((v) >> 2) & 3)
static u64 nvme_base = 0x44dcc0000ULL, now;
static int writes, delays, reads;
static bool complete, receive_failure;
static int acknowledgements;
struct rtkit_message { u64 msg; };
static void *nvme_rtkit;
static int rtkit_recv_one(void *rtkit, struct rtkit_message *message) {
    (void)rtkit; (void)message;
    acknowledgements++; /* Continuous log flood: only one ACK per invocation. */
    return receive_failure ? -1 : 0;
}
static u32 control;
static u64 timeout_calculate(u64 duration) { return now + duration; }
static bool timeout_expired(u64 deadline) { return now >= deadline; }
static void udelay(unsigned duration) { now += duration; delays++; }
static u32 read32(u64 address) {
    assert(address == nvme_base + NVME_CC || address == nvme_base + NVME_CSTS);
    if (address == nvme_base + NVME_CC) return control;
    reads++;
    return 1 | ((complete && writes && acknowledgements >= 2) ? 2u << 2 : 0);
}
static void mask32(u64 address, u32 clear, u32 set) {
    assert(address == nvme_base + NVME_CC);
    assert(clear == NVME_CC_SHN && set == 1u << 14);
    control = (control & ~clear) | set;
    writes++;
}
/* ACTUAL_SHUTDOWN */
int main(void) {
    control = 1; complete = true;
    assert(nvme_ctrl_shutdown());
    assert(writes == 1 && delays == 2 && now == 200);
    assert(control == (1 | 1u << 14));
    now = 0; writes = delays = reads = acknowledgements = 0; complete = false; control = 1;
    assert(!nvme_ctrl_shutdown());
    assert(now == NVME_SHUTDOWN_TIMEOUT && writes == 1);
    assert(control == (1 | 1u << 14));
    assert(acknowledgements == NVME_SHUTDOWN_TIMEOUT / 100);
    now = 0; writes = delays = reads = acknowledgements = 0;
    receive_failure = true;
    assert(!nvme_ctrl_shutdown());
    assert(now == 0 && acknowledgements == 1 && delays == 0);
    assert(control == (1 | 1u << 14));
    puts("Shutdown: ACK-dependent completion, message flood timeout, firmware failure and CC.EN verified");
}
