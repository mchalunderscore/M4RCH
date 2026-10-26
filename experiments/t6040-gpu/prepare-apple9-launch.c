/* SPDX-License-Identifier: MIT */
/* Offline serializer using the pinned Gravity launcher; no device access. */
#include "agx_apple9_launch.h"
#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
static unsigned long long number(const char *s) {
 char *end; errno=0; unsigned long long v=strtoull(s,&end,0);
 if(errno || *s=='-' || !*s || *end) { fprintf(stderr,"invalid number: %s\n",s); exit(2); }
 return v;
}
int main(int argc,char **argv) {
 if(argc!=13) { fprintf(stderr,"usage: stage output shader_base launch_address resource_table entry_offset publications scratch tile_bytes samples resource_count preamble_address\n"); return 2; }
 unsigned long long v[11];v[0]=number(argv[1]);for(int i=1;i<11;i++)v[i]=number(argv[i+2]);
 if(v[0]>2 || v[4]>0xffffffff || v[5]>1022 || v[6]>32768 || v[7]>255 || v[8]>255 || v[9]>18) return 2;
 struct agx_apple9_launch_parameters p={.shader_base=v[1],.launch_address=v[2],.resource_table=v[3],.entry_offset=v[4],.publication_count=v[5],.frame_extent_a=v[6],.frame_extent_b=v[6],.tile_bytes=v[7],.samples=v[8],.resource_count=v[9],.preamble_address=v[10]};
 unsigned char bytes[AGX_APPLE9_COMPUTE_LAUNCH_SIZE];size_t size=v[0]==2?sizeof(bytes):AGX_APPLE9_GRAPHICS_LAUNCH_SIZE;
 if(!agx_apple9_launch_build(bytes,size,v[0],&p)) { fprintf(stderr,"launcher rejected parameters\n");return 1; }
 FILE *f=fopen(argv[2],"wb");if(!f){perror(argv[2]);return 1;}bool ok=fwrite(bytes,1,size,f)==size;if(fclose(f))ok=false;return ok?0:1;
}
