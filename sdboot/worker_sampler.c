/* SPDX-License-Identifier: MIT
 * Five-second kernel-worker sampling. No hardware registers or policy writes.
 * Build on Linux: cc -O2 -Wall -Wextra worker_sampler.c -o worker-sampler
 */
#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <linux/perf_event.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <sys/syscall.h>
#include <time.h>
#include <unistd.h>

static double now(void) {
    struct timespec ts;
    if (clock_gettime(CLOCK_MONOTONIC, &ts)) { perror("clock_gettime"); exit(1); }
    return ts.tv_sec + ts.tv_nsec / 1e9;
}
static void ring_copy(void *target, const char *ring, size_t size, uint64_t position, size_t count) {
    size_t first = size - (position % size);
    if (first > count) first = count;
    memcpy(target, ring + position % size, first);
    memcpy((char *)target + first, ring, count - first);
}
int main(int argc, char **argv) {
    char path[80], comm[128], *end;
    if (argc != 3 || geteuid() != 0) {
        fprintf(stderr, "Usage: sudo worker-sampler KWORKER_PID NEW_OUTPUT.jsonl\n"); return 1;
    }
    errno = 0;
    long pid = strtol(argv[1], &end, 10);
    if (errno || *end || pid < 1 || pid > 2147483647) return 1;
    snprintf(path, sizeof(path), "/proc/%ld/comm", pid);
    FILE *name = fopen(path, "r");
    if (!name || !fgets(comm, sizeof(comm), name)) { perror("worker comm"); return 1; }
    fclose(name);
    if (strncmp(comm, "kworker/", 8)) { fprintf(stderr, "Select a kernel worker PID\n"); return 1; }
    struct perf_event_attr attr = {0};
    attr.size = sizeof(attr); attr.type = PERF_TYPE_SOFTWARE;
    attr.config = PERF_COUNT_SW_CPU_CLOCK; attr.sample_period = 10000000;
    attr.sample_type = PERF_SAMPLE_IP | PERF_SAMPLE_TID | PERF_SAMPLE_TIME | PERF_SAMPLE_CALLCHAIN;
    attr.disabled = 1; attr.exclude_user = 1; attr.exclude_hv = 1; attr.wakeup_events = 1;
    int fd = syscall(__NR_perf_event_open, &attr, (pid_t)pid, -1, -1, PERF_FLAG_FD_CLOEXEC);
    if (fd < 0) { perror("perf_event_open (no kernel changes attempted)"); return 1; }
    long page = sysconf(_SC_PAGESIZE);
    if (page <= 0) { close(fd); return 1; }
    size_t bytes = (size_t)page * 9;
    struct perf_event_mmap_page *map = mmap(NULL, bytes, PROT_READ|PROT_WRITE, MAP_SHARED, fd, 0);
    if (map == MAP_FAILED) { perror("mmap"); close(fd); return 1; }
    int output = open(argv[2], O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW, 0600);
    if (output < 0) { perror("new output"); munmap(map, bytes); close(fd); return 1; }
    FILE *stream = fdopen(output, "w");
    if (!stream) { close(output); munmap(map, bytes); close(fd); return 1; }
    const char *ring = (char *)map + page;
    size_t size = (size_t)page * 8;
    uint64_t tail = 0, samples = 0, lost = 0;
    int failed = 0;
    if (ioctl(fd, PERF_EVENT_IOC_RESET, 0) || ioctl(fd, PERF_EVENT_IOC_ENABLE, 0)) {
        perror("perf enable"); failed = 1;
    }
    double deadline = now() + 5.0;
    while (!failed && now() < deadline) {
        uint64_t head = __atomic_load_n(&map->data_head, __ATOMIC_ACQUIRE);
        if (head - tail > size) { fprintf(stderr, "Ring overrun\n"); failed = 1; break; }
        while (tail < head) {
            struct perf_event_header header;
            ring_copy(&header, ring, size, tail, sizeof(header));
            if (header.size < sizeof(header) || header.size > size || header.size > head-tail) {
                failed = 1; break;
            }
            unsigned char *record = malloc(header.size);
            if (!record) { failed = 1; break; }
            ring_copy(record, ring, size, tail, header.size);
            if (header.type == PERF_RECORD_SAMPLE && header.size >= 40) {
                uint64_t ip, timestamp, count; uint32_t tid[2];
                memcpy(&ip, record+8, 8); memcpy(tid, record+16, 8);
                memcpy(&timestamp, record+24, 8); memcpy(&count, record+32, 8);
                if (count > (header.size-40u)/8u) { free(record); failed = 1; break; }
                fprintf(stream, "{\"ip\":\"0x%llx\",\"pid\":%u,\"tid\":%u,\"time\":%llu,\"chain\":[",
                        (unsigned long long)ip, tid[0], tid[1], (unsigned long long)timestamp);
                for (uint64_t i=0; i<count; ++i) {
                    uint64_t address; memcpy(&address, record+40+i*8, 8);
                    fprintf(stream, "%s\"0x%llx\"", i ? "," : "", (unsigned long long)address);
                }
                fprintf(stream, "]}\n"); ++samples;
            } else if (header.type == PERF_RECORD_LOST && header.size >= 24) {
                uint64_t value; memcpy(&value, record+16, 8); lost += value;
            }
            free(record); tail += header.size;
            if (samples > 1000) { failed = 1; break; }
        }
        __atomic_store_n(&map->data_tail, tail, __ATOMIC_RELEASE);
        struct timespec pause = {.tv_nsec=50000000}; nanosleep(&pause, NULL);
    }
    ioctl(fd, PERF_EVENT_IOC_DISABLE, 0);
    fprintf(stream, "{\"summary\":true,\"samples\":%llu,\"lost\":%llu,\"failed\":%s}\n",
            (unsigned long long)samples, (unsigned long long)lost, failed ? "true" : "false");
    if (fclose(stream)) failed = 1;
    munmap(map, bytes); close(fd);
    return failed ? 1 : 0;
}
