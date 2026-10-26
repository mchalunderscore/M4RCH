/* SPDX-License-Identifier: GPL-2.0-only */
struct gfx_pause_operands {
 bool ksm_valid,output_valid,fault_valid;
 u64 request,ack,enabled0,enabled1,config[4],status[4],fault_info,fault_addr;
 unsigned int changed[6];
};
static struct gfx_pause_operands gfx_pause_sample;
