/* SPDX-License-Identifier: GPL-2.0-only */
/* Include after owned[], clean_page/pool_graph_cpu and UAT constants.
 * Two final owned[] pages are allocated with the original single allocation
 * loop, retained with every other page, and freed only by original root_release.
 * No existing Work/stamp/notification VA is changed by this aperture mapping.
 */
#include "full-power-timestamp-contract.h"
#define FULL_POWER_TIMESTAMP_TABLE_PAGE (ARRAY_SIZE(owned) - 2U)
#define FULL_POWER_TIMESTAMP_DATA_PAGE (ARRAY_SIZE(owned) - 1U)
static u64 *gfx_full_power_timestamp_borrowed;
static bool gfx_full_power_timestamp_published;
static u64 gfx_full_power_timestamp_table_descriptor(void)
{
 return page_to_phys(owned[FULL_POWER_TIMESTAMP_TABLE_PAGE]) | 3ULL;
}
static bool gfx_full_power_timestamp_prepare(u64 *l1, u64 *l2)
{
 u64 *table, table_pa, data_pa;
 u8 *hardware;
 unsigned int i;
 if (PAGE_SIZE != 0x4000 || ARRAY_SIZE(owned) < 4 || !l1 || !l2 ||
     ((ROOT_VA >> 36) & 63) != ((FULL_POWER_TIMESTAMP_VA >> 36) & 63) ||
     ((FULL_POWER_TIMESTAMP_VA >> 25) & 2047) != FULL_POWER_TIMESTAMP_L1_INDEX ||
     ((FULL_POWER_TIMESTAMP_VA >> 14) & 2047) != FULL_POWER_TIMESTAMP_L2_INDEX ||
     l1[FULL_POWER_TIMESTAMP_L1_INDEX] || gfx_full_power_timestamp_published ||
     !owned[FULL_POWER_TIMESTAMP_TABLE_PAGE] || !owned[FULL_POWER_TIMESTAMP_DATA_PAGE])
  return false;
 table = page_address(owned[FULL_POWER_TIMESTAMP_TABLE_PAGE]);
 table_pa = page_to_phys(owned[FULL_POWER_TIMESTAMP_TABLE_PAGE]);
 data_pa = page_to_phys(owned[FULL_POWER_TIMESTAMP_DATA_PAGE]);
 if ((table_pa & ~PA_MASK) || (data_pa & ~PA_MASK) || table_pa == data_pa)
  return false;
 hardware = pool_graph_cpu(l2, FULL_POWER_TIMESTAMP_HW_VA, 0x30);
 if (!hardware || get_unaligned_le64(hardware + 0x28)) return false;
 for (i = 0; i < PAGE_SIZE / sizeof(u64); i++)
  if (table[i] || ((u64 *)page_address(owned[FULL_POWER_TIMESTAMP_DATA_PAGE]))[i]) return false;
 /* Native selected conversion is identity. First page only, explicit fresh
  * zero RAM policy; no unallocated pages of the 64MiB aperture are advertised. */
 table[FULL_POWER_TIMESTAMP_L2_INDEX] = data_pa | FW_GRAPH_RW;
 l1[FULL_POWER_TIMESTAMP_L1_INDEX] = table_pa | 3ULL;
 put_unaligned_le64(FULL_POWER_TIMESTAMP_VA, hardware + 0x28);
 pr_info("m4rch gfx-full-power-timestamp: prepared=1 virtual=%#llx physical=%#llx l1_index=%u l2_index=%u table_physical=%#llx bytes=%lu hardware28=%#llx cache=fw-shared-rw owned=1 published=0 existing_work_addresses_changed=0\n",
  FULL_POWER_TIMESTAMP_VA, data_pa, FULL_POWER_TIMESTAMP_L1_INDEX,
  FULL_POWER_TIMESTAMP_L2_INDEX, table_pa, PAGE_SIZE,
  get_unaligned_le64(hardware + 0x28));
 return table[FULL_POWER_TIMESTAMP_L2_INDEX] == (data_pa | FW_GRAPH_RW) &&
        l1[FULL_POWER_TIMESTAMP_L1_INDEX] == (table_pa | 3ULL);
}
/* Run before writing the first borrowed child. The existing parent path and
 * all existing TEXT/DATA descriptors remain the caller's validated owners. */
static bool gfx_full_power_timestamp_borrowed_available(u64 *parent)
{
 return parent && !gfx_full_power_timestamp_published &&
        !READ_ONCE(parent[FULL_POWER_TIMESTAMP_L1_INDEX]);
}
/* Run after installed=true and before the single clean_page(target_page).
 * If readback fails, root_release must remove both borrowed child slots. */
static bool gfx_full_power_timestamp_publish_borrowed(u64 *parent)
{
 if (!gfx_full_power_timestamp_borrowed_available(parent)) return false;
 gfx_full_power_timestamp_borrowed = parent;
 gfx_full_power_timestamp_published = true;
 WRITE_ONCE(parent[FULL_POWER_TIMESTAMP_L1_INDEX], gfx_full_power_timestamp_table_descriptor());
 return READ_ONCE(parent[FULL_POWER_TIMESTAMP_L1_INDEX]) == gfx_full_power_timestamp_table_descriptor();
}
static bool gfx_full_power_timestamp_can_detach(void)
{
 return !gfx_full_power_timestamp_published ||
  (gfx_full_power_timestamp_borrowed &&
   READ_ONCE(gfx_full_power_timestamp_borrowed[FULL_POWER_TIMESTAMP_L1_INDEX]) == gfx_full_power_timestamp_table_descriptor());
}
/* Call before clearing the graph's target_slot, then clean the shared parent
 * once and invalidate both VAs. Any unexpected entry refuses detachment. */
static bool gfx_full_power_timestamp_remove_borrowed(void)
{
 if (!gfx_full_power_timestamp_can_detach()) return false;
 if (gfx_full_power_timestamp_published) {
  WRITE_ONCE(gfx_full_power_timestamp_borrowed[FULL_POWER_TIMESTAMP_L1_INDEX], 0);
  if (READ_ONCE(gfx_full_power_timestamp_borrowed[FULL_POWER_TIMESTAMP_L1_INDEX])) return false;
 }
 gfx_full_power_timestamp_published = false;
 gfx_full_power_timestamp_borrowed = NULL;
 return true;
}
static void gfx_full_power_timestamp_invalidate(void)
{
 u64 operand = (FULL_POWER_TIMESTAMP_VA >> 12) & 0x00000ffffffffffcULL;
 asm volatile(".arch armv8.4-a\n\ttlbi vaae1os, %0" :: "r"(operand) : "memory");
}
