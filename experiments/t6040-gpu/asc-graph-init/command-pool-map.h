/* SPDX-License-Identifier: GPL-2.0-only */
/* Joined owned command allocation, still no submission or context publication. */
#define POOL_FIRST_PAGE (ARENA_OBJECT_PAGES + 2)
#define NOTIFY_FIRST_PAGE (POOL_FIRST_PAGE + POOL_PAGES)
#define DEVICE_TABLE_FIRST (NOTIFY_FIRST_PAGE + 2)
#define NOTIFY_STATE_VA (FW_BASE + POOL_BYTES)
#define NOTIFY_RING_VA (NOTIFY_STATE_VA + PAGE_SIZE)
static u8 pool_notifications[POOL_PAGES][24];
static bool command_pool_prepare(u64 *firmware_l2)
{
 unsigned int i,j,part;
 u64 *root=page_address(owned[DEVICE_TABLE_FIRST]);
 u64 *l1=page_address(owned[DEVICE_TABLE_FIRST+1]);
 u64 *l2=page_address(owned[DEVICE_TABLE_FIRST+2]);
 const u64 device_flags=0x00e0000000000c0bULL; /* Candidate shared protections. */
 if ((FW_BASE>>25)!=(ROOT_VA>>25) || ((FW_BASE+POOL_BYTES-1)>>25)!=(ROOT_VA>>25) ||
     (DEVICE_BASE&(PAGE_SIZE-1)) || ((DEVICE_BASE+POOL_BYTES-1)>>25)!=(DEVICE_BASE>>25) ||
     JOB_COUNT*COMMAND_BYTES>POOL_BYTES || POOL_PAGES*PAGE_SIZE!=POOL_BYTES) return false;
 root[(DEVICE_BASE>>36)&63]=page_to_phys(owned[DEVICE_TABLE_FIRST+1])|3;
 l1[(DEVICE_BASE>>25)&2047]=page_to_phys(owned[DEVICE_TABLE_FIRST+2])|3;
 for (i=0;i<POOL_PAGES;i++) {
  u64 va=FW_BASE+(u64)i*PAGE_SIZE,pa=page_to_phys(owned[POOL_FIRST_PAGE+i]);
  u8 *record=pool_notifications[i];
  if (firmware_l2[(va>>14)&2047] || (pa>>12)>U32_MAX) return false;
  firmware_l2[(va>>14)&2047]=pa|FW_GRAPH_RW;
  l2[((DEVICE_BASE+(u64)i*PAGE_SIZE)>>14)&2047]=pa|device_flags;
  put_unaligned_le64(va,record);put_unaligned_le32(pa>>12,record+8);
  put_unaligned_le16(1,record+16);put_unaligned_le16(5,record+18);
 }
 for (i=0;i<JOB_COUNT;i++) for (j=0;j<COMMAND_BYTES;j+=part) {
  unsigned int pos=i*COMMAND_BYTES+j;
  void *cpu=(u8 *)page_address(owned[POOL_FIRST_PAGE+(pos>>PAGE_SHIFT)])+(pos&(PAGE_SIZE-1));
  part=min_t(unsigned int,COMMAND_BYTES-j,PAGE_SIZE-(pos&(PAGE_SIZE-1)));
  memcpy(cpu,job_bytes[i]+j,part);
 }
 for (i=0;i<JOB_COUNT;i++) for (j=0;j<COMMAND_BYTES;j+=part) {
  unsigned int pos=i*COMMAND_BYTES+j,index=pos>>PAGE_SHIFT;
  u64 pa=page_to_phys(owned[POOL_FIRST_PAGE+index]);
  void *cpu=(u8 *)page_address(owned[POOL_FIRST_PAGE+index])+(pos&(PAGE_SIZE-1));
  part=min_t(unsigned int,COMMAND_BYTES-j,PAGE_SIZE-(pos&(PAGE_SIZE-1)));
  if (firmware_l2[((FW_BASE+pos)>>14)&2047]!=(pa|FW_GRAPH_RW) ||
      l2[((DEVICE_BASE+pos)>>14)&2047]!=(pa|device_flags) || memcmp(cpu,job_bytes[i]+j,part)) return false;
 }
 for (j=JOB_COUNT*COMMAND_BYTES;j<POOL_BYTES;j++)
  if (*((u8 *)page_address(owned[POOL_FIRST_PAGE+(j>>PAGE_SHIFT)])+(j&(PAGE_SIZE-1)))) return false;
 for (i=0;i<2;i++) {
  u64 va=NOTIFY_STATE_VA+(u64)i*PAGE_SIZE,pa=page_to_phys(owned[NOTIFY_FIRST_PAGE+i]);
  if ((va>>25)!=(ROOT_VA>>25) || firmware_l2[(va>>14)&2047]) return false;
  firmware_l2[(va>>14)&2047]=pa|FW_GRAPH_RW;
 }
 memcpy(page_address(owned[NOTIFY_FIRST_PAGE+1]),pool_notifications,sizeof(pool_notifications));
 put_unaligned_le32(POOL_PAGES,(u8 *)page_address(owned[NOTIFY_FIRST_PAGE])+0x10);
 if (memcmp(page_address(owned[NOTIFY_FIRST_PAGE+1]),pool_notifications,sizeof(pool_notifications)) ||
     get_unaligned_le32(page_address(owned[NOTIFY_FIRST_PAGE])) ||
     get_unaligned_le32((u8 *)page_address(owned[NOTIFY_FIRST_PAGE])+0x10)!=POOL_PAGES) return false;
 pr_info("m4rch joined-pool: ring state_va=%#llx entries_va=%#llx head=0 tail=%u owned_pages=2 publication=0\n",(u64)NOTIFY_STATE_VA,(u64)NOTIFY_RING_VA,POOL_PAGES);
 for (i=0;i<POOL_PAGES;i++)
  pr_info("m4rch joined-pool: mapping %u va=%#llx pa=%#llx descriptor=%*phN\n",i,(u64)FW_BASE+(u64)i*PAGE_SIZE,page_to_phys(owned[POOL_FIRST_PAGE+i]),24,pool_notifications[i]);
 pr_info("m4rch joined-pool: PASS jobs=%u pages=%u device_root=%#llx firmware_root_index=%llu notifications=%u publication=0\n",
         JOB_COUNT,POOL_PAGES,page_to_phys(owned[DEVICE_TABLE_FIRST]),((u64)FW_BASE>>36)&63,POOL_PAGES);
 return true;
}
