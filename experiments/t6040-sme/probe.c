/* SPDX-License-Identifier: MIT */
#include <stdio.h>
#include <errno.h>
#include <sys/auxv.h>
#include <sys/prctl.h>
#include <asm/hwcap.h>
#ifndef PR_SME_GET_VL
#define PR_SME_GET_VL 64
#endif
#ifndef HWCAP2_SME
#define HWCAP2_SME (1UL << 23)
#endif
#ifndef HWCAP2_SME2
#define HWCAP2_SME2 (1UL << 37)
#endif
int main(void) {
 unsigned long h=getauxval(AT_HWCAP), h2=getauxval(AT_HWCAP2);
 int vl=-1, error=0;
 if (h2&HWCAP2_SME) { errno=0; vl=prctl(PR_SME_GET_VL,0,0,0,0); error=errno; }
 printf("{\"hwcap\":%lu,\"hwcap2\":%lu,\"sme\":%s,\"sme2\":%s,\"sme_vl_result\":%d,\"sme_vl_bytes\":%d,\"errno\":%d}\n",h,h2,h2&HWCAP2_SME?"true":"false",h2&HWCAP2_SME2?"true":"false",vl,vl>=0?vl&0xffff:0,error);
 return 0;
}
