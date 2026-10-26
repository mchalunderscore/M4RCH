/* SPDX-License-Identifier: GPL-2.0-only */
#include <linux/soc/apple/pmgr-gfx-reset.h>
#define GFX_COLD_PAGES 174U
/* Same read-only provider normalization as the qualified cold coordinator. */
static int gfx_cold_snapshot(const char *phase,unsigned int index,
 struct apple_pmgr_gfx_reset_observation *observation)
{
 int ret;
 memset(observation,0,sizeof(*observation));
 ret=apple_pmgr_t6040_gfx_snapshot(observation);
 if(!ret && observation->operation_error) ret=observation->operation_error;
 if(!ret && observation->cleanup_error) ret=observation->cleanup_error;
 if(ret>0) ret=-EIO;
 if(!ret && !(observation->valid&APPLE_PMGR_GFX_VALID_BEFORE)) ret=-ENODATA;
 pr_info("m4rch gfx-cold-render-physical: phase=%s index=%u result=%d valid=%#x domain_on=%u word=%#x operation_error=%d cleanup_error=%d operand_samples_atomic=0\n",
  phase,index,ret,observation->valid,observation->domain_on,observation->before,
  observation->operation_error,observation->cleanup_error);
 return ret;
}
