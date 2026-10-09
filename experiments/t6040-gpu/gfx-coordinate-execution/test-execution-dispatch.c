/* SPDX-License-Identifier: GPL-2.0-only */
/* RAM dependencies for the actual transformed dispatcher, never native MMIO. */
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/types.h>
#include <errno.h>

typedef uint8_t u8;
typedef uint32_t u32;
typedef uint64_t u64;
struct kobject { int unused; };
struct kobj_attribute { int unused; };

#include "actual-recovery-contract.inc"
#include "actual-execution-state.inc"

static bool resident_session, recovery_resident, recovery_work_submitted;
static bool recovery_trace_disabled, recovery_session_failed, held;
static bool gfx_poweroff_gate_consumed, gfx_reset_scope_sealed;
static bool gfx_reset_scope_host_stopped, gfx_reset_scope_attempted;
static unsigned int recovery_completed_total, recovery_operation;
static int graph_io_lock;
static struct { unsigned int used, status, doorbells; } receive_journal;
static u8 rings[2][24];
static u32 producers[2], phase_word, request_word, request_flag, control_word;
static bool idle_ok, control_ok, cycles_ok, trace_ok, send_ok;
static bool locked, require_intent_on_hardware_event;
static unsigned int clean_mask, case_count;

enum event_kind { LOCK, UNLOCK, INTENT, READ, IDLE, CONTROL, RECOVER,
 TRACE_OFF, PTR, INVALIDATE, CACHE, PRODUCER, SEND, SAMPLE, SNAPSHOT,
 STOP, OFF, RESET, MESSAGE };
struct event { enum event_kind kind; unsigned int index; u64 value; };
static struct event events[256];
static unsigned int event_count;

static bool intent(void)
{
#ifdef GFX_COORDINATED_EXECUTION_TRIAL
 return gfx_execution_submit_intent;
#else
 return false;
#endif
}

static void event(enum event_kind kind, unsigned int index, u64 value)
{
 assert(event_count < sizeof(events) / sizeof(events[0]));
 events[event_count++] = (struct event){kind, index, value};
 if (kind != LOCK && kind != UNLOCK) assert(locked);
 if (require_intent_on_hardware_event &&
     (kind == READ || kind == IDLE || kind == CONTROL || kind == SEND ||
      kind == PTR || kind == INVALIDATE || kind == CACHE || kind == PRODUCER))
  assert(intent());
}

static void mutex_lock(int *lock)
{
 assert(lock == &graph_io_lock && !locked); locked = true; event(LOCK, 0, 0);
}
static void mutex_unlock(int *lock)
{
 assert(lock == &graph_io_lock && locked); event(UNLOCK, 0, 0); locked = false;
}
static bool sysfs_streq(const char *a, const char *b)
{
 size_t n = strlen(a); if (n && a[n - 1] == '\n') n--;
 return n == strlen(b) && !memcmp(a, b, n);
}
static void pr_info(const char *format, ...)
{
 if (strstr(format, "submit_intent=1")) { assert(intent()); event(INTENT, 0, 1); }
}
static int gfx_poweroff_attempt(void)
{
 event(OFF, 0, 0); gfx_poweroff_gate_consumed = true; return 0;
}
static int gfx_reset_scope_stop(void)
{
 event(STOP, 0, 0); gfx_reset_scope_sealed = true;
 gfx_reset_scope_host_stopped = true; return 0;
}
static int gfx_poweroff_sample(void) { event(SAMPLE, 0, 0); return 0; }
static int gfx_reset_scope_snapshot(void) { event(SNAPSHOT, 0, 0); return 0; }
static int gfx_reset_scope_reset(void) { event(RESET, 0, 0); return -EPERM; }
static void gfx_reset_scope_protocol(const char *phase) { (void)phase; }
static bool recovery_messages(void) { event(MESSAGE, 0, 0); return true; }
static void recovery_sample(unsigned int cycle, const char *phase)
{ (void)cycle; (void)phase; event(SAMPLE, 0, 1); }
static void recovery_power_sample(const char *phase) { (void)phase; }
static void ksm_status_sample(const char *phase) { (void)phase; }
static void joined_output_sample(const char *phase) { (void)phase; }
static bool recovery_idle(void) { event(IDLE, 0, 0); return idle_ok; }
static u32 recovery_read32(unsigned int offset)
{
 event(READ, offset, 0);
 if (offset == RECOVERY_STATUS + 0x4900) return phase_word;
 if (offset == RECOVERY_REQUEST) return request_word;
 if (offset == RECOVERY_REQUEST + 4) return request_flag;
 if (offset == RECOVERY_CONTROL || offset == RECOVERY_CONTROL + 8 ||
     offset == RECOVERY_CONTROL + 16) return control_word;
 assert(!"Unexpected dispatcher read"); return 0;
}
static bool recovery_control(unsigned int count, bool publish)
{
 event(CONTROL, publish, count);
 if (control_ok && publish) control_word = count;
 return control_ok;
}
static bool recovery_cycles(void)
{
 event(RECOVER, 0, 0); if (cycles_ok) recovery_completed_total += 2;
 return cycles_ok;
}
static bool recovery_trace_off(void)
{
 event(TRACE_OFF, 0, 0);
 if (!trace_ok || recovery_completed_total < 4 || recovery_work_submitted)
  return false;
 recovery_trace_disabled = true; return true;
}
static void *recovery_ptr(unsigned int offset)
{
 unsigned int i;
 for (i = 0; i < 2; i++) if (offset == recovery_work_rings[i]) {
  event(PTR, i, offset); return rings[i];
 }
 assert(!"Unexpected dispatcher pointer"); return NULL;
}
static void recovery_invalidate(void *p, size_t bytes)
{
 unsigned int i; assert(bytes == 24);
 for (i = 0; i < 2; i++) if (p == rings[i]) {
  event(INVALIDATE, i, bytes); return;
 }
 assert(!"Unexpected invalidate pointer");
}
static void ram_cache_clean(void *p)
{
 unsigned int i;
 for (i = 0; i < 2; i++) if (p == rings[i]) {
  assert(!memcmp(rings[i], recovery_work_records[i], 24));
  assert(producers[i] == 0);
  event(CACHE, i, 24); clean_mask |= 1U << i; return;
 }
 assert(!"Unexpected cache event pointer");
}
static void recovery_write32(unsigned int offset, u32 value)
{
 unsigned int i;
 for (i = 0; i < 2; i++) if (offset == recovery_work_cursors[i] + 16) {
  assert(value == 1 && (clean_mask & (1U << i)) && !producers[i]);
  assert(!memcmp(rings[i], recovery_work_records[i], 24));
  event(PRODUCER, i, value); producers[i] = value; return;
 }
 assert(!"Unexpected dispatcher write");
}
static bool recovery_send(u64 packet)
{
 assert(packet == 0x0083000000000000ULL);
 assert(producers[0] == 1 && producers[1] == 1 && clean_mask == 3);
 event(SEND, 0, packet); return send_ok;
}

#include "actual-execution-dispatch.inc"

static unsigned int count_event(enum event_kind kind)
{
 unsigned int i, count = 0;
 for (i = 0; i < event_count; i++) count += events[i].kind == kind;
 return count;
}
static void reset(void)
{
 assert(!locked); memset(rings, 0, sizeof(rings)); memset(producers, 0, sizeof(producers));
 event_count = clean_mask = 0; phase_word = request_word = request_flag = 0;
 resident_session = recovery_resident = held = true;
 recovery_work_submitted = recovery_session_failed = false;
 gfx_poweroff_gate_consumed = gfx_reset_scope_sealed = gfx_reset_scope_host_stopped = false;
 gfx_reset_scope_attempted = false;
 recovery_trace_disabled = idle_ok = control_ok = cycles_ok = trace_ok = send_ok = true;
 recovery_completed_total = 4; recovery_operation = 0; control_word = 34;
 require_intent_on_hardware_event = false;
#ifdef GFX_COORDINATED_EXECUTION_TRIAL
 gfx_execution_submit_intent = false;
#endif
}
static int command(const char *name)
{
 ssize_t result = recovery_command_store(NULL, NULL, name, strlen(name));
 assert(!locked); return (int)result;
}
static void quarantined(const char *name, int expected)
{
 event_count = 0; assert(command(name) == expected);
 assert(intent() && event_count == 2 && events[0].kind == LOCK && events[1].kind == UNLOCK);
 case_count++;
}
static void quarantine_all(void)
{
 const char *blocked[] = {"gfx-poweroff", "stop", "control", "recover", "trace-off", "gfx-reset", "unknown"};
 unsigned int i;
 for (i = 0; i < sizeof(blocked) / sizeof(blocked[0]); i++) quarantined(blocked[i], -EPERM);
 quarantined("submit", -EALREADY);
}
static void diagnostics(void)
{
 event_count = 0; assert(command("sample") == (int)strlen("sample"));
 assert(count_event(SAMPLE) == 1 && count_event(MESSAGE) == 0 && count_event(READ) == 0);
 case_count++;
 event_count = 0; assert(command("gfx-snapshot") == (int)strlen("gfx-snapshot"));
 assert(count_event(SNAPSHOT) == 1 && count_event(MESSAGE) == 0 && count_event(READ) == 0);
 case_count++;
}

#ifdef GFX_COORDINATED_EXECUTION_TRIAL
static void refusal(int expected, bool no_hardware, bool seals)
{
 require_intent_on_hardware_event = true;
 assert(command("submit\n") == expected && intent() && !recovery_work_submitted);
 assert(count_event(INTENT) == 1 && !count_event(CACHE) && !count_event(PRODUCER) && !count_event(SEND));
 if (no_hardware) assert(!count_event(READ) && !count_event(IDLE) && !count_event(CONTROL));
 if (seals) assert(recovery_session_failed);
 case_count++; quarantine_all();
}
static void publication(void)
{
 unsigned int i, position = 0;
 const enum event_kind kinds[] = {PTR, INVALIDATE, CACHE, PRODUCER, PTR, INVALIDATE, CACHE, PRODUCER, SEND};
 const unsigned int indexes[] = {0, 0, 0, 0, 1, 1, 1, 1, 0};
 require_intent_on_hardware_event = true;
 assert(command("submit") == (int)strlen("submit"));
 assert(intent() && recovery_work_submitted && !recovery_session_failed);
 assert(count_event(INTENT) == 1 && count_event(CACHE) == 2 && count_event(PRODUCER) == 2 && count_event(SEND) == 1);
 for (i = 0; i < event_count; i++) if (events[i].kind >= PTR && events[i].kind <= SEND) {
  assert(position < sizeof(kinds) / sizeof(kinds[0]));
  assert(events[i].kind == kinds[position] && events[i].index == indexes[position]); position++;
 }
 assert(position == sizeof(kinds) / sizeof(kinds[0]));
 assert(!memcmp(rings, recovery_work_records, sizeof(rings)));
 case_count++; quarantine_all(); diagnostics();
}
#endif

int main(void)
{
 const char *restored[] = {"control", "recover", "trace-off", "submit", "gfx-reset"};
 unsigned int i;
 reset(); assert(command("stop") == (int)strlen("stop") && count_event(STOP) == 1); case_count++;
 reset(); assert(command("gfx-poweroff") == (int)strlen("gfx-poweroff") && count_event(OFF) == 1); case_count++;
 reset(); diagnostics();
#ifdef GFX_COORDINATED_EXECUTION_TRIAL
 (void)restored; (void)i;
 reset(); recovery_resident = false; refusal(-ENODEV, true, false);
 reset(); recovery_session_failed = true; refusal(-EIO, true, true);
 reset(); gfx_poweroff_gate_consumed = true; refusal(-EIO, true, false);
 reset(); gfx_reset_scope_sealed = true; refusal(-EIO, true, false);
 reset(); gfx_reset_scope_host_stopped = true; refusal(-EIO, true, false);
 reset(); held = false; refusal(-EIO, true, false);
 reset(); recovery_trace_disabled = false; refusal(-EBUSY, true, false);
 reset(); recovery_completed_total = 3; refusal(-EBUSY, true, false);
 reset(); recovery_work_submitted = true; require_intent_on_hardware_event = true;
 assert(command("submit") == -EALREADY && intent() && !count_event(READ)); case_count++; quarantine_all();
 reset(); idle_ok = false; refusal(-EBUSY, false, false);
 reset(); phase_word = 1; refusal(-EBUSY, false, false);
 reset(); request_word = 1; refusal(-EBUSY, false, false);
 reset(); request_flag = 1; refusal(-EBUSY, false, false);
 reset(); control_ok = false; refusal(-EIO, false, true);
 reset(); publication();
 reset(); send_ok = false; require_intent_on_hardware_event = true;
 assert(command("submit") == -EIO && intent() && recovery_work_submitted && recovery_session_failed);
 assert(count_event(SEND) == 1 && producers[0] == 1 && producers[1] == 1); case_count++; quarantine_all(); diagnostics();
 reset(); recovery_completed_total = 2; recovery_trace_disabled = false;
 assert(command("control") == (int)strlen("control") && control_word == 35); case_count++;
 assert(command("recover") == (int)strlen("recover") && recovery_completed_total == 4); case_count++;
 assert(command("trace-off") == (int)strlen("trace-off") && recovery_trace_disabled); case_count++;
 event_count = 0; publication();
 reset(); assert(command("gfx-reset") == -EINVAL && !count_event(RESET) && !intent()); case_count++;
 reset(); cycles_ok = false; assert(command("recover") == -EIO && recovery_session_failed && !intent()); case_count++;
 reset(); trace_ok = false; assert(command("trace-off") == -EIO && recovery_session_failed && !intent()); case_count++;
#else
 for (i = 0; i < sizeof(restored) / sizeof(restored[0]); i++) {
  reset(); assert(command(restored[i]) == -EPERM && event_count == 2); case_count++;
 }
#endif
 printf("{\"passed\":true,\"hardware_access\":false,\"case_count\":%u,\"execution_macro\":%s}\n", case_count,
#ifdef GFX_COORDINATED_EXECUTION_TRIAL
 "true"
#else
 "false"
#endif
 );
 return 0;
}
