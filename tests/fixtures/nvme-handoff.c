#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

typedef uint32_t u32;
typedef uint64_t u64;
#define T6040 0x6040
#define NVME_ADMIN_CMD_DELETE_SQ 0
#define NVME_ADMIN_CMD_DELETE_CQ 4
static enum { NVME_T8103, NVME_T8132 } nvme_type;
static bool nvme_initialized, nvme_handoff_done, nvme_handoff_failed;
static bool init_ok = true, secure_bar = true;
static u32 chip_id = T6040, board_id = 4, reg_length = 160;
static u64 nvme_base, nvmmu_base;
static u64 mapped_nvme = 0x44dcc0000, mapped_nvmmu = 0x40dcc0000;
static int nvme_die, nvme_rtkit, nvme_sart, nvme_asc, adminq, ioq;
static int adt, mapped_calls, panic_count, init_calls, command_count, fail_at;
static int dt, dt_bufsize = 98304, dt_fail;
static bool marked;
static char events[128];
struct nvme_command { int opcode, cdw10; };

static void event(char value) { size_t n = strlen(events); events[n] = value; events[n + 1] = 0; }
static int adt_path_offset_trace(int tree, const char *name, int *path) { return 1; }
static const void *adt_getprop(int tree, int node, const char *name, u32 *length)
{ *length = reg_length; return &adt; }
static bool adt_get_property(int tree, int node, const char *name) { return secure_bar; }
static int adt_get_reg(int tree, int *path, const char *name, int index, u64 *base, void *size)
{ mapped_calls++; *base = index == 3 ? mapped_nvmmu : mapped_nvme; return 0; }
static bool nvme_init(void) { init_calls++; event('I'); nvme_handoff_done = false; nvme_initialized = init_ok; return init_ok; }
static bool nvme_exec_command(int *queue, struct nvme_command *command, void *result)
{ command_count++; event(command->opcode == NVME_ADMIN_CMD_DELETE_SQ ? 'S' : 'C'); return fail_at != command_count; }
static bool nvme_ctrl_shutdown(void) { event('H'); return fail_at != 3; }
static bool nvme_ctrl_disable(void) { event('D'); return fail_at != 4; }
/* Actual checked RTKit implementation is tested separately below. */
static bool rtkit_sleep_checked(int dev) { event('R'); return fail_at != 5 && fail_at != 6; }
static int pmgr_reset(int die, const char *name) { event('P'); return fail_at == 7 || !strcmp(name, "ANS") ? -1 : 0; }
static void rtkit_free(int dev) { event('r'); }
static void sart_free(int dev) { event('s'); }
static void asc_free(int dev) { event('a'); }
static void free_queue(int *queue) { event('q'); }
#define panic(...) do { panic_count++; event('!'); } while (0)
static int fdt_open_into(int from, int to, int size) { event('O'); assert(size == dt_bufsize); return dt_fail == 1; }
static int fdt_path_offset(int tree, const char *name) { assert(!strcmp(name, "/chosen")); return dt_fail == 2 ? -1 : 7; }
static int fdt_setprop_string(int tree, int node, const char *name, const char *value)
{ assert(node == 7 && !strcmp(name, "arch-m4,ans-handoff") && !strcmp(value, "v2")); event('M'); marked = true; return dt_fail == 3; }
static int fdt_pack(int tree) { event('K'); return dt_fail == 4; }

/* ACTUAL_TARGET_GUARDS */
/* ACTUAL_SHUTDOWN_CHECKED */
/* ACTUAL_PREPARE_HANDOFF */
/* ACTUAL_SHUTDOWN */
static int handoff_uefi(void)
{
    /* ACTUAL_UEFI_HOOK */
    return 0;
}

static void reset_trial(void)
{
    events[0] = 0; init_calls = command_count = panic_count = 0;
    init_ok = true; fail_at = dt_fail = 0;
    nvme_initialized = nvme_handoff_done = nvme_handoff_failed = marked = false;
}

int main(void)
{
    assert(validate_target());
    assert(nvme_type == NVME_T8132);
    chip_id = 0x8132; mapped_calls = 0;
    assert(!validate_target() && mapped_calls == 0);
    chip_id = T6040; board_id = 6;
    assert(!validate_target() && mapped_calls == 0);
    board_id = 4; reg_length = 16;
    assert(!validate_target());
    reg_length = 160; secure_bar = false;
    assert(!validate_target());
    secure_bar = true; mapped_nvmmu++;
    assert(!validate_target());
    mapped_nvmmu--; mapped_nvme++;
    assert(!validate_target());
    mapped_nvme--; assert(validate_target());

    reset_trial(); init_ok = false;
    assert(handoff_uefi() < 0 && !marked);
    assert(!strcmp(events, "I") && !command_count);
    reset_trial(); nvme_shutdown();
    assert(!strcmp(events, "ISCHDRPPrsaqq"));
    assert(init_calls == 1 && command_count == 2 && !nvme_initialized && nvme_handoff_done);
    nvme_shutdown();
    assert(init_calls == 1 && command_count == 2);
    reset_trial();
    assert(!handoff_uefi() && marked);
    assert(!strcmp(events, "ISCHDRPPrsaqqOMK"));
    nvme_shutdown(); assert(init_calls == 1);
    for (int failure = 1; failure <= 7; failure++) {
        reset_trial(); fail_at = failure;
        assert(handoff_uefi() < 0 && !marked && !nvme_handoff_done);
        assert(!strchr(events, 'q') && !strchr(events, 'O') && nvme_handoff_failed);
        int calls_before = init_calls;
        assert(handoff_uefi() < 0 && init_calls == calls_before);
        reset_trial(); fail_at = failure; nvme_shutdown();
        assert(panic_count == 1 && !nvme_handoff_done);
    }
    for (int failure = 1; failure <= 4; failure++) {
        reset_trial(); dt_fail = failure;
        assert(handoff_uefi() < 0);
    }
    puts("NVMe handoff control-flow checks passed");
    return 0;
}
