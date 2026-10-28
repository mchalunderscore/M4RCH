#!/usr/bin/env python3
"""Exercise Mesa's actual command-buffer BO retention set and release paths."""
from pathlib import Path
import argparse
import subprocess
import tempfile

def function(source, name, prefix):
    start = source.index('\n' + name + '(') + 1
    opening = source.index('{', start)
    depth, end = 1, opening + 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return prefix + '\n' + source[start:end] + '\n'

parser = argparse.ArgumentParser()
parser.add_argument('mesa', type=Path)
root = parser.parse_args().mesa
source = (root/'src/asahi/vulkan/hk_cmd_lifetime.c').read_text()
code = r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#define ARRAY_SIZE(a) (sizeof(a)/sizeof((a)[0]))
#define VK_ERROR_OUT_OF_HOST_MEMORY -1
struct agx_bo {int refs;}; struct agx_device {int unused;};
struct dynarray {struct agx_bo *items[1024]; unsigned count;};
struct hk_cmd_buffer {struct {int error;} vk; struct agx_bo **retained_set; uint32_t retained_set_capacity,retained_set_count; struct agx_bo *recent_retained_bos[16]; struct dynarray large_bos;};
static bool fail_alloc;
static void *mock_calloc(size_t n,size_t s){return fail_alloc ? NULL : calloc(n,s);}
#define calloc mock_calloc
static void agx_bo_reference(struct agx_bo *b){assert(b->refs>0);b->refs++;}
static void agx_bo_unreference(struct agx_device *d,struct agx_bo *b){(void)d;assert(b->refs>0);b->refs--;}
static void vk_command_buffer_set_error(void *p,int e){*(int *)p=e;}
#define util_dynarray_append(a,v) ((a)->items[(a)->count++]=(v))
#define util_dynarray_foreach(a,T,p) for (T *p=(a)->items; p < (a)->items+(a)->count; ++p)
#define util_dynarray_clear(a) ((a)->count=0)
'''
for name, prefix in [('hk_retained_set_hash','static inline uint32_t'),('hk_retained_set_grow','static bool'),('hk_cmd_buffer_retain_bo','void'),('hk_cmd_buffer_release_bos','void')]:
    code += function(source, name, prefix)
code += r'''
int main(void){struct hk_cmd_buffer c={0};struct agx_device d={0};struct agx_bo bos[300];for(int i=0;i<300;i++){bos[i].refs=1;hk_cmd_buffer_retain_bo(&c,&bos[i]);assert(bos[i].refs==2);hk_cmd_buffer_retain_bo(&c,&bos[i]);assert(bos[i].refs==2);}assert(c.retained_set_count==300 && c.large_bos.count==300);hk_cmd_buffer_release_bos(&c,&d);for(int i=0;i<300;i++)assert(bos[i].refs==1);assert(c.retained_set_count==0 && c.large_bos.count==0);free(c.retained_set);struct hk_cmd_buffer bad={0};struct agx_bo b={.refs=1};fail_alloc=true;hk_cmd_buffer_retain_bo(&bad,&b);assert(bad.vk.error==-1 && b.refs==1 && bad.large_bos.count==0);return 0;}
'''
with tempfile.TemporaryDirectory() as directory:
    d = Path(directory)
    (d/'test.c').write_text(code)
    subprocess.run(['cc','-std=gnu11','-Wall','-Werror',str(d/'test.c'),'-o',str(d/'test')],check=True)
    subprocess.run([str(d/'test')],check=True)
print('PASS: actual BO retention set, growth, deduplication, release and allocation failure')
