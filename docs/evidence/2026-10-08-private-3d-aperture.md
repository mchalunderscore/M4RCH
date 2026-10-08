# Ordinary3D aperture helper integration

Native caller895bbdc..895bc2c executes actual mcache helper895f738 and G16 HAL encoder89e8a9c. 1,024 whole command/descriptor comparisons,8,166 records and61 empty cases pass. Counts0..16; high addresses, u64 pointer wrap and random DSID/size fields covered. Trace disabled; authentication skipped. Audit uses existing TA setup for shared accelerator vtable, independently verifies real3D caller argument flow.

Descriptor970 holds16-byte source records; counta70. Output6a0..79f lies after actual first register backing and before metadata7a0. Updated descriptor a98/aa0/aa4 receives GPU pointer,index,count. Empty output is pointer0,indexffffffff,count0. Paired builder always generates these records for3D construction and derives scheduler aperture from updated descriptor; empty index normalized0 in the scheduler. Conflicting scheduler aperture rejected. Event/control remains optional and explicitly labeled.

Linux physical allocation, real GPU mappings, coherency, queue/event identity and live publication/completion remain unproven. No rendered pixels or hardware touched. submission_ready=false.
