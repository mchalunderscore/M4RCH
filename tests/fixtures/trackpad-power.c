/* Hardware-free harness for the exact patched driver functions. */
#include <assert.h>
#include <errno.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef uint8_t u8;
typedef uint32_t __le32;
#define __packed __attribute__((packed))
#define cpu_to_le32(value) ((uint32_t)(value))
#define dev_info(...) ((void)0)

struct gpio_desc { bool active_low; };
struct dchid_dev {
    void *dev;
    struct gpio_desc *mt_reset_gpio;
    bool power_req_v1;
};
struct dchid_iface {
    struct dchid_dev *dchid;
    const char *name;
    unsigned int index;
};

static char trace[512];
static unsigned int commands, gpio_calls;
static int command_results[8], gpio_error;
static struct gpio_desc gpio = { .active_low = true };

static void record(const char *format, ...)
{
    size_t length = strlen(trace);
    va_list args;
    int written;

    va_start(args, format);
    written = vsnprintf(trace + length, sizeof(trace) - length, format, args);
    va_end(args);
    assert(written >= 0 && (size_t)written < sizeof(trace) - length);
}

static int dchid_comm_cmd(struct dchid_dev *dchid, const void *data, size_t size)
{
    const unsigned char *packet = data;
    (void)dchid;
    assert(commands < sizeof(command_results) / sizeof(command_results[0]));
    assert(packet[0] == 0x40 && packet[2] == 7);
    if (size == 9) {
        assert(packet[1] == 2 && packet[4] <= 1);
        /* A failed host operation must never be reported as success. */
        assert(packet[5] == 0 && packet[6] == 0 && packet[7] == 0 && packet[8] == 0);
        record("%c%u ", packet[4] ? 'H' : 'W', packet[3]);
    } else {
        assert(size == 4 && packet[1] == 1);
        record("V1:%u ", packet[3]);
    }
    return command_results[commands++];
}

static int gpiod_set_value_cansleep(struct gpio_desc *desc, int value)
{
    assert(desc == &gpio);
    assert(value == 0 || value == 1);
    gpio_calls++;
    /* Model gpiolib's logical-to-physical conversion for the DT binding. */
    record("G%d/R%d ", value, value ^ desc->active_low);
    return gpio_error;
}

static void msleep(unsigned int milliseconds)
{
    record("D%u ", milliseconds);
}

static int dev_err_probe(void *dev, int error, const char *format, ...)
{
    (void)dev;
    (void)format;
    return error;
}

/* Generated from the pinned source plus the actual project patches. */
#include "driver-power.inc"

static void expect(const char *expected)
{
    if (strcmp(trace, expected)) {
        fprintf(stderr, "expected: %s\nobserved: %s\n", expected, trace);
        abort();
    }
}

int main(int argc, char **argv)
{
    struct dchid_dev dchid = { .mt_reset_gpio = &gpio };
    struct dchid_iface iface = { .dchid = &dchid, .name = "multi-touch", .index = 7 };
    assert(argc == 2);

    if (!strcmp(argv[1], "off")) {
        assert(dchid_reset_interface(&iface, PWR_STATE_OFF) == 0);
        expect("W0 G1/R0 D50 H0 ");
    } else if (!strcmp(argv[1], "on")) {
        assert(dchid_reset_interface(&iface, PWR_STATE_ON) == 0);
        expect("W2 G0/R1 H2 ");
    } else if (!strcmp(argv[1], "cycle")) {
        assert(dchid_reset_interface(&iface, PWR_STATE_OFF) == 0);
        assert(dchid_reset_interface(&iface, PWR_STATE_ON) == 0);
        expect("W0 G1/R0 D50 H0 W2 G0/R1 H2 ");
    } else if (!strcmp(argv[1], "gpio-failure")) {
        gpio_error = -EIO;
        assert(dchid_reset_interface(&iface, PWR_STATE_OFF) == -EIO);
        expect("W0 G1/R0 ");
        assert(!dchid.power_req_v1);
    } else if (!strcmp(argv[1], "will-timeout")) {
        command_results[0] = -ETIMEDOUT;
        assert(dchid_reset_interface(&iface, PWR_STATE_OFF) == -ETIMEDOUT);
        expect("W0 ");
        assert(!dchid.power_req_v1);
    } else if (!strcmp(argv[1], "legacy-fallback")) {
        command_results[0] = -EIO;
        assert(dchid_reset_interface(&iface, PWR_STATE_OFF) == 0);
        assert(dchid.power_req_v1);
        assert(dchid_reset_interface(&iface, PWR_STATE_ON) == 0);
        expect("W0 V1:0 V1:2 ");
    } else if (!strcmp(argv[1], "no-gpio")) {
        dchid.mt_reset_gpio = NULL;
        assert(dchid_reset_interface(&iface, PWR_STATE_OFF) == 0);
        assert(dchid_reset_interface(&iface, PWR_STATE_ON) == 0);
        expect("W0 H0 W2 H2 ");
    } else if (!strcmp(argv[1], "keyboard")) {
        iface.name = "keyboard";
        assert(dchid_reset_interface(&iface, PWR_STATE_OFF) == 0);
        assert(dchid_reset_interface(&iface, PWR_STATE_ON) == 0);
        expect("W0 H0 W2 H2 ");
    } else if (!strcmp(argv[1], "has-failure")) {
        command_results[1] = -EIO;
        assert(dchid_reset_interface(&iface, PWR_STATE_ON) == -EIO);
        expect("W2 G0/R1 H2 ");
        assert(!dchid.power_req_v1);
    } else if (!strcmp(argv[1], "unsupported-state")) {
        assert(dchid_reset_interface(&iface, PWR_STATE_SLEEP) == -EINVAL);
        expect("W1 ");
    } else {
        return 2;
    }
    return 0;
}
