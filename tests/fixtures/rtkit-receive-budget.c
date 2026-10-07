/* Host model: compile actual RTKit dispatch with mocked mailbox handlers. */
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
typedef uint64_t u64;
typedef uint32_t u32;
typedef uint8_t u8;
struct asc_message { u64 msg0, msg1; };
struct rtkit_message { u64 msg; u8 ep; };
struct buffer { void *bfr; };
typedef struct {
    bool crashed;
    void *asc;
    u64 iop_power, ap_power, syslog_cnt, syslog_size;
    struct buffer syslog_bfr, crashlog_bfr, ioreport_bfr;
} rtkit_dev_t;
#define FIELD_GET(mask, value) (value)
#define rtkit_printf(...) ((void)0)
/* CONSTANTS */
static int remaining, receives, acknowledgements;
static bool invalid;
static bool asc_recv(void *asc, struct asc_message *msg) {
    (void)asc;
    if (!remaining) return false;
    remaining--; receives++;
    msg->msg1 = invalid ? 0x100 : RTKIT_EP_SYSLOG;
    msg->msg0 = MSG_SYSLOG_LOG;
    return true;
}
static bool asc_send(void *asc, struct asc_message *msg) {
    (void)asc; (void)msg; acknowledgements++; return true;
}
static bool rtkit_send(rtkit_dev_t *rtk, struct rtkit_message *msg) {
    (void)rtk; (void)msg; acknowledgements++; return true;
}
static bool rtkit_handle_buffer_request(rtkit_dev_t *rtk, struct rtkit_message *msg,
                                        struct buffer *buffer) {
    (void)rtk; (void)msg; (void)buffer; return true;
}
static void rtkit_crashed(rtkit_dev_t *rtk) { rtk->crashed = true; }
/* ACTUAL_RECEIVE */
int main(void) {
    rtkit_dev_t rtk = {0}; struct rtkit_message msg;
    /* Invalid endpoint flood must not bypass the single-message budget. */
    remaining = 100; invalid = true;
    assert(rtkit_recv_one(&rtk, &msg) == 0);
    assert(receives == 1 && remaining == 99);
    /* Normal logging is ACKed, then yields to the controller deadline. */
    invalid = false; receives = 0;
    assert(rtkit_recv_one(&rtk, &msg) == 0);
    assert(receives == 1 && acknowledgements == 1);
    /* Existing callers still drain available messages normally. */
    assert(rtkit_recv(&rtk, &msg) == 0);
    assert(remaining == 0 && acknowledgements == 99);
    rtk.crashed = true;
    assert(rtkit_recv_one(&rtk, &msg) == -1);
}
