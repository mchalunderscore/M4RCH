/* SPDX-License-Identifier: MIT */
#define _GNU_SOURCE
#include <errno.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#ifndef WORKER_VALIDATION_TEST
#include <sched.h>
#include <time.h>
#endif
struct observed {
 uint64_t gp[28];
 int64_t result;
 uint64_t padding;
 uint8_t vectors[32][16];
 uint64_t fpcr_before, fpcr_after, fpsr_before, fpsr_after;
};
_Static_assert(offsetof(struct observed, vectors)==240, "assembly offset");
_Static_assert(offsetof(struct observed, fpcr_before)==752, "assembly offset");
_Static_assert(sizeof(struct observed)==784, "assembly size");
static int valid(const struct observed *o) {
 for(unsigned int i=0;i<28;i++) {
  unsigned int reg=i<6?i+2:i+3;
  if(o->gp[i] != 256+reg)return 0;
 }
 for(unsigned int q=0;q<32;q++)for(unsigned int b=0;b<16;b++)
  if(o->vectors[q][b] != q+1)return 0;
 return o->fpcr_before==o->fpcr_after && o->fpsr_before==o->fpsr_after;
}
#ifdef WORKER_VALIDATION_TEST
int main(void) {
 struct observed o={0};
 for(unsigned int i=0;i<28;i++)o.gp[i]=256+(i<6?i+2:i+3);
 for(unsigned int q=0;q<32;q++)memset(o.vectors[q],q+1,16);
 if(!valid(&o))return 1;
 o.gp[27]^=1;if(valid(&o))return 2;o.gp[27]^=1;
 o.vectors[31][15]^=1;if(valid(&o))return 3;o.vectors[31][15]^=1;
 o.fpcr_after=1;if(valid(&o))return 4;o.fpcr_after=0;
 o.fpsr_after=1;if(valid(&o))return 5;
 return 0;
}
#else
extern void check_sleep_once(const struct timespec *, struct observed *);
int main(int argc,char **argv) {
 if(argc!=3)return 2;
 char *end;errno=0;long cpu=strtol(argv[1],&end,10);
 if(errno||*end||(cpu!=4&&cpu!=5))return 2;
 errno=0;long iterations=strtol(argv[2],&end,10);
 if(errno||*end||iterations<1||iterations>512)return 2;
 cpu_set_t mask;CPU_ZERO(&mask);CPU_SET(cpu,&mask);
 if(sched_setaffinity(0,sizeof(mask),&mask)){perror("affinity");return 3;}
 struct timespec delay={.tv_sec=0,.tv_nsec=20000000};
 for(long i=0;i<iterations;i++) {
  struct observed o={0};check_sleep_once(&delay,&o);
  if(!valid(&o)||(o.result!=0&&o.result!=-EINTR)||sched_getcpu()!=cpu) {
   fprintf(stderr,"state/affinity/syscall mismatch cpu=%ld iteration=%ld result=%lld\n",cpu,i,(long long)o.result);return 4;
  }
  if(i==0){puts("READY");fflush(stdout);}
 }
 printf("{\"cpu\":%ld,\"iterations\":%ld,\"gpr_simd_fpcr_fpsr_checks_passed\":true}\n",cpu,iterations);
 return 0;
}
#endif
