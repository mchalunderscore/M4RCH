#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

typedef uint32_t u32;
typedef unsigned long u64;
#define T6040 0x6040
#define NVME_ADMIN_CMD_CREATE_CQ 5
#define NVME_ADMIN_CMD_CREATE_SQ 1
#define NVME_CMD_FLUSH 0
#define NVME_CMD_READ 2
#define NVME_QUEUE_SIZE 64
#define NVME_QUEUE_CONTIGUOUS 1
#define PMGR_DIE_ID 0
#define USEC_PER_SEC 1000000
#define SZ_4K 4096
#define NVME_BOOT_STATUS 0x1300
#define NVME_BOOT_STATUS_OK 0xde71ce55
#define NVME_LINEAR_SQ_CTRL 0x24908
#define NVME_LINEAR_SQ_CTRL_EN 1
#define NVME_MAX_PEND_CMDS_CTRL 0x1210
#define NVMMU_NUM 0x28100
#define NVMMU_ASQ_BASE 0x28108
#define NVMMU_IOSQ_BASE 0x28110
#define NVME_ASQ 0x28
#define NVME_ACQ 0x30
#define NVME_AQA 0x24
#define NVME_IOQ_CQES 0x1208
#define NVME_IOQ_CMDS 0x1200
#define ADT_GETPROP(tree, node, name, out) ((void)(out), -1)
#define FIELD_GET(field, value) (0)
static enum { NVME_T8103, NVME_T8132 } nvme_type;
static bool nvme_initialized, nvme_handoff_done, nvme_handoff_failed;
static u32 chip_id = T6040, board_id = 4;
static u64 nvme_base, nvmmu_base;
static int nvme_die, nvme_rtkit, nvme_sart, nvme_asc, adt;
struct nvme_queue { bool adminq; u64 tcbs, cmds, cqes; };
static struct nvme_queue adminq, ioq;
struct nvme_command { int opcode; u64 prp1; u32 nsid, cdw10, cdw11, cdw12; };
static int failure, allocations, frees, boots, mmio_writes, commands;
static int adt_path_offset_trace(int tree, const char *name, int *path) { return 1; }
static const void *adt_getprop(int tree, int node, const char *name, u32 *length)
{ *length = 160; return &adt; }
static bool adt_get_property(int tree, int node, const char *name) { return true; }
static int adt_get_reg(int tree, int *path, const char *name, int index, u64 *base, void *size)
{ *base = index == 3 ? 0x40dcc0000 : 0x44dcc0000; return 0; }
static bool alloc_queue(struct nvme_queue *q) { allocations++; return failure != allocations; }
static void free_queue(struct nvme_queue *q) { frees++; }
static int asc_init(const char *path) { return failure == 3 ? 0 : 1; }
static int sart_init(const char *path) { return failure == 4 ? 0 : 1; }
static int rtkit_init(const char *name, int asc, void *ops, void *cookie, int sart, bool flags) { return failure == 5 ? 0 : 1; }
static bool rtkit_boot(int rtk) { boots++; return failure != 6; }
static void sart_free(int sart) { frees++; }
static void asc_free(int asc) { frees++; }
static int poll32(u64 address, u32 mask, u32 value, int timeout) { return failure == 7 ? -1 : 0; }
static void set32(u64 address, u64 value) { mmio_writes++; }
static void write32(u64 address, u64 value) { mmio_writes++; }
static void write64_lo_hi(u64 address, u64 value) { mmio_writes++; }
static bool nvme_ctrl_disable(void) { return failure != 8; }
static bool nvme_ctrl_enable(void) { return failure != 9; }
static bool nvme_exec_command(struct nvme_queue *q, struct nvme_command *cmd, void *result)
{ commands++; return !((failure == 10 && cmd->opcode == NVME_ADMIN_CMD_CREATE_CQ) || (failure == 11 && cmd->opcode == NVME_ADMIN_CMD_CREATE_SQ)); }

/* ACTUAL_INIT */
/* ACTUAL_FLUSH */
/* ACTUAL_READ */

static void reset_trial(void)
{
    allocations = frees = boots = mmio_writes = commands = 0;
    nvme_initialized = nvme_handoff_done = nvme_handoff_failed = false;
}

int main(void)
{
    for (failure = 1; failure <= 11; failure++) {
        reset_trial(); nvme_handoff_done = true;
        assert(!nvme_init() && !nvme_initialized && !nvme_handoff_done);
        if (failure >= 6) {
            assert(nvme_handoff_failed && !frees && boots == 1);
            int writes_before = mmio_writes, commands_before = commands;
            assert(!nvme_init() && boots == 1 && allocations == 2);
            assert(mmio_writes == writes_before && commands == commands_before);
        } else {
            assert(!nvme_handoff_failed && !boots);
            if (failure > 1) assert(frees > 0);
        }
    }
    failure = 0; reset_trial(); nvme_handoff_done = true;
    assert(nvme_init() && nvme_initialized && !nvme_handoff_done && !nvme_handoff_failed);
    /* An initialization after a prior successful shutdown invalidates proof. */
    nvme_initialized = false; nvme_handoff_done = true;
    assert(nvme_init() && !nvme_handoff_done);
    nvme_handoff_failed = true;
    int commands_before = commands;
    assert(!nvme_flush(1) && !nvme_read(1, 0, (void *)4096));
    assert(commands == commands_before);
    puts("NVMe initialization retains DMA buffers after failed adoption");
}
