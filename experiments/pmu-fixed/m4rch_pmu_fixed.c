// SPDX-License-Identifier: GPL-2.0-only OR MIT
/* Temporary J614s fixed-counter experiment. No PMU registration or IRQs. */
#include <linux/cpu.h>
#include <linux/debugfs.h>
#include <linux/ktime.h>
#include <linux/module.h>
#include <linux/mutex.h>
#include <linux/of.h>
#include <linux/seq_file.h>
#include <linux/workqueue.h>
#include <asm/apple_m1_pmu.h>
#include <asm/barrier.h>
#include <asm/cputype.h>
#include <asm/arch_timer.h>
#include "policy.h"

static unsigned int cpu;
module_param(cpu, uint, 0400);
MODULE_PARM_DESC(cpu, "One online M4 CPU; fixed at load time");
static struct dentry *directory;
static DEFINE_MUTEX(sample_lock);
static const unsigned int lengths[] = {256, 4096, 65536};
struct result {
    u32 midr;
    u64 pmcr0, pmcr1, final0, final1;
    u64 loops[3], cycles[3], instructions[3], ticks[3];
    unsigned int completed;
    long status;
};

static bool m4_cpu(void)
{
    u32 id = read_cpuid_id();
    return MIDR_IMPLEMENTOR(id) == 0x61 &&
           (MIDR_PARTNUM(id) == 0x054 || MIDR_PARTNUM(id) == 0x055);
}

static long check_cpu(void *unused)
{
    return m4_cpu() ? 0 : -ENODEV;
}

static long sample_cpu(void *argument)
{
    struct result *r = argument;
    unsigned long flags;
    unsigned int i;
    u64 c0, c1, t0, t1, c_end, i_end, accumulator, n;
    long status = 0;

    if (!m4_cpu())
        return -ENODEV;
    /* Local interrupt/preemption exclusion limits each loop to this CPU. */
    local_irq_save(flags);
    r->midr = read_cpuid_id();
    r->pmcr0 = read_sysreg_s(SYS_IMP_APL_PMCR0_EL1);
    r->pmcr1 = read_sysreg_s(SYS_IMP_APL_PMCR1_EL1);
    if (fixed_owned(r->pmcr0)) {
        status = -EBUSY;
        goto untouched;
    }
    c0 = read_sysreg_s(SYS_IMP_APL_PMC0_EL1);
    c1 = read_sysreg_s(SYS_IMP_APL_PMC1_EL1);
    /* Avoid approaching the documented bit63 overflow indication. */
    if (c0 >= BIT_ULL(63) - BIT_ULL(28) || c1 >= BIT_ULL(63) - BIT_ULL(28)) {
        status = -ERANGE;
        goto untouched;
    }
    write_sysreg_s(fixed_filter(r->pmcr1), SYS_IMP_APL_PMCR1_EL1);
    write_sysreg_s(r->pmcr0 | FIXED_ENABLE, SYS_IMP_APL_PMCR0_EL1);
    isb();
    if (read_sysreg_s(SYS_IMP_APL_PMCR0_EL1) != (r->pmcr0 | FIXED_ENABLE) ||
        read_sysreg_s(SYS_IMP_APL_PMCR1_EL1) != fixed_filter(r->pmcr1)) {
        status = -EIO;
        goto restore;
    }
    for (i = 0; i < ARRAY_SIZE(lengths); i++) {
        n = lengths[i];
        accumulator = 0;
        isb();
        t0 = arch_timer_read_counter();
        c0 = read_sysreg_s(SYS_IMP_APL_PMC0_EL1);
        c1 = read_sysreg_s(SYS_IMP_APL_PMC1_EL1);
        /* Three dependent scalar instructions per iteration. */
        asm volatile("1: add %0, %0, #1\n"
                     "subs %1, %1, #1\n"
                     "b.ne 1b\n"
                     : "+r" (accumulator), "+r" (n) : : "cc", "memory");
        isb();
        i_end = read_sysreg_s(SYS_IMP_APL_PMC1_EL1);
        c_end = read_sysreg_s(SYS_IMP_APL_PMC0_EL1);
        t1 = arch_timer_read_counter();
        r->loops[i] = lengths[i];
        r->cycles[i] = c_end - c0;
        r->instructions[i] = i_end - c1;
        r->ticks[i] = t1 - t0;
        r->completed++;
        if (c_end & BIT_ULL(63) || i_end & BIT_ULL(63) ||
            accumulator != lengths[i] || t1 < t0 || c_end < c0 || i_end < c1 ||
            r->cycles[i] == 0 || r->instructions[i] == 0) {
            status = -EIO;
            break;
        }
        /* Stop further loops if even this tiny measurement exceeds 2ms. */
        if (r->ticks[i] > (u32)read_sysreg(cntfrq_el0) / 500) {
            status = -ETIMEDOUT;
            break;
        }
    }
restore:
    write_sysreg_s(r->pmcr0, SYS_IMP_APL_PMCR0_EL1);
    write_sysreg_s(r->pmcr1, SYS_IMP_APL_PMCR1_EL1);
    isb();
untouched:
    r->final0 = read_sysreg_s(SYS_IMP_APL_PMCR0_EL1);
    r->final1 = read_sysreg_s(SYS_IMP_APL_PMCR1_EL1);
    if (r->final0 != r->pmcr0 || r->final1 != r->pmcr1)
        status = -EUCLEAN;
    local_irq_restore(flags);
    return status;
}

static int sample_show(struct seq_file *seq, void *unused)
{
    struct result r = {};
    unsigned int i;
    mutex_lock(&sample_lock);
    cpus_read_lock();
    r.status = cpu_online(cpu) ? work_on_cpu(cpu, sample_cpu, &r) : -ENODEV;
    cpus_read_unlock();
    seq_printf(seq, "cpu=%u midr=%08x status=%ld timer_hz=%u pmcr0=%016llx pmcr1=%016llx final0=%016llx final1=%016llx\n",
               cpu, r.midr, r.status, (u32)read_sysreg(cntfrq_el0), r.pmcr0, r.pmcr1,
               r.final0, r.final1);
    for (i = 0; i < r.completed; i++)
        seq_printf(seq, "loops=%llu cycles=%llu instructions=%llu ticks=%llu\n",
                   r.loops[i], r.cycles[i], r.instructions[i], r.ticks[i]);
    mutex_unlock(&sample_lock);
    return 0; /* Userspace validates status; failed evidence is retained. */
}
DEFINE_SHOW_ATTRIBUTE(sample);

static int __init trial_init(void)
{
    long status;
    if (!of_machine_is_compatible("apple,j614s") || cpu >= nr_cpu_ids)
        return -ENODEV;
    cpus_read_lock();
    status = cpu_online(cpu) ? work_on_cpu(cpu, check_cpu, NULL) : -ENODEV;
    cpus_read_unlock();
    if (status)
        return status;
    directory = debugfs_create_dir("m4rch-pmu-fixed", NULL);
    if (IS_ERR(directory))
        return PTR_ERR(directory);
    if (IS_ERR(debugfs_create_file("sample", 0400, directory, NULL, &sample_fops))) {
        debugfs_remove_recursive(directory);
        return -ENOMEM;
    }
    return 0;
}
static void __exit trial_exit(void)
{
    debugfs_remove_recursive(directory);
}
module_init(trial_init);
module_exit(trial_exit);
MODULE_LICENSE("Dual MIT/GPL");
MODULE_DESCRIPTION("J614s optional fixed-counter count experiment; no interrupts");
