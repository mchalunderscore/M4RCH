#!/usr/bin/env python3
"""Run actual imported DMA setup and pure recovery logic using host-only shims."""
import argparse
from pathlib import Path
import re
import subprocess


def function(source, signature):
    start=source.index(signature); brace=source.index('{',start); depth=1; end=brace+1
    while depth:
        if source[end]=='{': depth+=1
        if source[end]=='}': depth-=1
        end+=1
    return source[start:end]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('kernel',type=Path); parser.add_argument('work',type=Path)
    args=parser.parse_args(); root=args.kernel; work=args.work; work.mkdir(parents=True,exist_ok=True)
    dma=function((root/'arch/arm64/mm/dma-mapping.c').read_text(),'void arch_setup_dma_ops(')
    prefix=r'''
#include <stdbool.h>
#include <stdint.h>
#include <string.h>
#include <assert.h>
#include <stdio.h>
struct device { bool noncoherent, result; int warnings; };
static uint64_t clidr;
#define read_sysreg(x) clidr
#define CLIDR_LOC(x) (((x)>>24)&7)
#define ARCH_DMA_MINALIGN 128
#define TAINT_CPU_OUT_OF_SPEC 0
#define WARN_TAINT(condition,...) assert(!(condition))
#define dev_warn(d,...) ((d)->warnings++)
static int cache_line_size_of_cpu(void) { return 64; }
static bool device_property_present(struct device *dev,const char *s) { assert(!strcmp(s,"dma-noncoherent")); return dev->noncoherent; }
static void dev_assign_dma_coherent(struct device *dev,bool coherent) { dev->result=coherent; }
static void xen_setup_dma_ops(struct device *dev) { (void)dev; }
'''
    suffix=r'''
int main(void) {
    struct device explicit_nc={.noncoherent=true}; clidr=0;
    arch_setup_dma_ops(&explicit_nc,false); assert(!explicit_nc.result && !explicit_nc.warnings);
    struct device ordinary={0}; arch_setup_dma_ops(&ordinary,false); assert(ordinary.result && ordinary.warnings==1);
    struct device legacy={.noncoherent=true}; clidr=1ULL<<24;
    arch_setup_dma_ops(&legacy,false); assert(!legacy.result && !legacy.warnings);
    struct device coherent={0}; clidr=0;
    arch_setup_dma_ops(&coherent,true); assert(coherent.result && !coherent.warnings);
    puts("PR429: actual arch_setup_dma_ops preserves explicit NC and existing coherent/legacy policies PASS");
}
'''
    (work/'dma.c').write_text(prefix+dma+suffix)
    subprocess.run(['clang','-O1','-g','-fsanitize=address,undefined',str(work/'dma.c'),'-o',str(work/'dma')],check=True)
    subprocess.run([str(work/'dma')],check=True)
    # The same regression must fail on the actual pre-PR source.
    original=Path('/project/out/aurora-dcp/dma-mapping-before-pr429.c')
    if original.exists():
        (work/'dma-before.c').write_text(prefix+function(original.read_text(),'void arch_setup_dma_ops(')+suffix)
        subprocess.run(['clang',str(work/'dma-before.c'),'-o',str(work/'dma-before')],check=True)
        before=subprocess.run([str(work/'dma-before')],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        assert before.returncode!=0
        print('Pre-PR429 negative control reproduces the policy regression')
    base=root/'drivers/gpu/drm/asahi/g17'
    timeout=(base/'timeout.rs').read_text()
    # This module is already host-testable upstream via cfg_attr(not(test),...).
    (work/'timeout.rs').write_text(timeout)
    preparation=(base/'preparation.rs').read_text()
    admission=preparation[preparation.index("pub(super) struct Admission<'a>"):preparation.index('#[pin_data]')]
    regression=function(preparation,'fn a_recovery_extends_the_deadline_once_from_the_start()')
    source='''#![allow(dead_code)]
const EBUSY:i32=-16; const EIO:i32=-5;
type Result<T=()> = core::result::Result<T,i32>;
mod g17 {
    use core::sync::atomic::{AtomicU64,Ordering};
    static CLOCK:AtomicU64=AtomicU64::new(0);
    fn now_ns()->u64 { CLOCK.load(Ordering::SeqCst) }
    mod timeout;
    mod preparation {
        use core::cell::Cell;
        use crate::{Result,EBUSY,EIO};
'''+admission+'''
        mod compute_deadline_tests { use super::*;
            #[test]
'''+regression+'''
            #[test] fn recovery_is_bounded_and_cancellation_still_wins() {
                use core::sync::atomic::Ordering;
                super::super::CLOCK.store(100,Ordering::SeqCst);
                let ok=||Ok(());
                let a=Admission::new(100,&ok); a.extend_for_recovery();
                assert_eq!(a.slice_ms(),Ok(10));
                let limit=a.deadline.get();
                super::super::CLOCK.store(limit,Ordering::SeqCst);
                a.extend_for_recovery(); assert_eq!(a.deadline.get(),limit);
                assert_eq!(a.check(),Err(EBUSY));
                let fail=||Err(EIO);
                let b=Admission::new(u64::MAX,&fail); b.extend_for_recovery();
                assert_eq!(b.check(),Err(EIO));
            }
        }
    }
}
'''
    # Inline the complete upstream timeout module without changing its test bodies.
    source=source.replace('    mod timeout;', '    mod timeout {\n'+re.sub(r'^//!.*$', '',timeout,flags=re.M)+'\n    }')
    (work/'recovery.rs').write_text(source)
    subprocess.run(['rustc','--edition=2021','--test',str(work/'recovery.rs'),'-o',str(work/'recovery')],check=True)
    subprocess.run([str(work/'recovery'),'--test-threads=1'],check=True)

if __name__=='__main__': main()
