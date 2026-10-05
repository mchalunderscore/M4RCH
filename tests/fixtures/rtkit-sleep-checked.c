#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>

enum rtkit_power_state { RTKIT_POWER_ON = 1, RTKIT_POWER_QUIESCED = 2, RTKIT_POWER_SLEEP = 3 };
typedef struct { bool crashed; int asc; enum rtkit_power_state ap_power, iop_power; } rtkit_dev_t;
struct asc_message { uint64_t msg0, msg1; };
struct rtkit_message { int ep; unsigned long msg; };
#define MGMT_TYPE 1
#define MGMT_MSG_AP_PWR_STATE 2
#define MGMT_MSG_IOP_PWR_STATE 3
#define MGMT_PWR_STATE 4
#define RTKIT_EP_MGMT 0
#define FIELD_PREP(mask, value) ((mask) * (value))
#define rtkit_printf(...) ((void)0)
static int failure, sends, receives, stops;
static bool running;
static bool asc_send(int asc, const struct asc_message *msg)
{ sends++; return !((failure == 2 && sends == 1) || (failure == 4 && sends == 2)); }
static int rtkit_recv(rtkit_dev_t *rtk, struct rtkit_message *msg)
{
    receives++;
    if ((failure == 3 && sends == 1) || (failure == 5 && sends == 2)) return -1;
    if (sends == 1) rtk->ap_power = RTKIT_POWER_QUIESCED;
    else rtk->iop_power = RTKIT_POWER_SLEEP;
    return 0;
}
static void asc_cpu_stop(int asc) { stops++; if (failure != 6) running = false; }
static bool asc_cpu_running(int asc) { return running; }

/* ACTUAL_SWITCH_POWER_STATE */
/* ACTUAL_CHECKED_SLEEP */

int main(void)
{
    for (failure = 0; failure <= 6; failure++) {
        rtkit_dev_t rtk = { failure == 1, 7, RTKIT_POWER_ON, RTKIT_POWER_ON };
        sends = receives = stops = 0; running = true;
        assert(rtkit_sleep_checked(&rtk) == (failure == 0));
        if (!failure) assert(sends == 2 && receives == 2 && stops == 1 && !running);
        else if (failure < 6) assert(!stops && running);
        else assert(stops == 1 && running);
    }
    puts("Checked RTKit sleep preserves failures");
}
