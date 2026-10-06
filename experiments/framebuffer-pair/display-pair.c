// SPDX-License-Identifier: GPL-2.0-only
#include <stdint.h>
#include <string.h>
uint32_t pixel(uint32_t p){p=((p&255)<<2)|((p&0xff00)<<4)|((p&0xff0000)<<6);return p|((p>>8)&0x00300c03);}
void reference(void *d,const void *s,unsigned n){for(unsigned i=0;i<n;i++){uint32_t x;memcpy(&x,(const char*)s+4*i,4);x=pixel(x);memcpy((char*)d+4*i,&x,4);}}
void paired(void *d,const void *s,unsigned n){char *dst=d;const char *src=s;while(n>=2){uint64_t x;memcpy(&x,src,8);x=((x&0x000000ff000000ffULL)<<2)|((x&0x0000ff000000ff00ULL)<<4)|((x&0x00ff000000ff0000ULL)<<6);x|=(x>>8)&0x00300c0300300c03ULL;memcpy(dst,&x,8);src+=8;dst+=8;n-=2;}if(n){uint32_t x;memcpy(&x,src,4);x=pixel(x);memcpy(dst,&x,4);}}
