// SPDX-License-Identifier: GPL-2.0-only
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
void reference(void*,const void*,unsigned);void paired(void*,const void*,unsigned);
static double now(void){struct timespec t;clock_gettime(CLOCK_MONOTONIC,&t);return t.tv_sec+t.tv_nsec*1e-9;}
int main(void){unsigned char src[72],a[72],b[72];for(unsigned align=0;align<8;align++)for(unsigned n=0;n<=15;n++){memset(a,0xa5,72);memset(b,0xa5,72);for(unsigned i=0;i<72;i++)src[i]=i*37+align;reference(a+align,src+align,n);paired(b+align,src+align,n);if(memcmp(a,b,72))return 1;}for(uint32_t v=0;v<0x1000000;v++){uint32_t in[2]={v|0xaa000000,(v^0xffffff)|0x55000000},a[2],b[2];reference(a,in,2);paired(b,in,2);if(memcmp(a,b,8))return 2;}puts("PASS all24-bit RGB inputs, complementary upper lane, ignored alpha, offsets0..7, lengths0..15 and output sentinels");unsigned n=3024*1890;uint32_t *s=malloc(n*4),*d=malloc(n*4);if(!s||!d)return 3;for(unsigned i=0;i<n;i++)s[i]=i*2654435761U;for(unsigned order=0;order<2;order++)for(unsigned j=0;j<2;j++){unsigned method=order^j;double t=now();for(unsigned k=0;k<8;k++)(method?paired:reference)(d,s,n);double elapsed=now()-t;printf("%s %.3f Mpixels/s checksum %u\n",method?"paired":"reference",n*8/elapsed/1e6,d[n-1]);}free(s);free(d);}
