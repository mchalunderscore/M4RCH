/* Hardware experiment: an in-dispatch GPU marker precedes the work. A live
 * host observation is diagnostic, not a Vulkan-guaranteed cross-device
 * synchronization primitive; a missing marker or mere overlap is inconclusive. */
#define _POSIX_C_SOURCE 200809L
#include <vulkan/vulkan.h>
#include <inttypes.h>
#include <fcntl.h>
#include <unistd.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

enum { GROUPS = 1024, LOCAL = 64, ITEMS = GROUPS * LOCAL };
static int marker_fd = -1;
static void mark(const char *phase, unsigned control, unsigned round)
{
    if (marker_fd >= 0) dprintf(marker_fd, "M4GPU phase=%s control=%u round=%u pid=%d", phase, control, round, getpid());
}

#define CHECK(x) do { VkResult r_ = (x); if (r_ != VK_SUCCESS) { fprintf(stderr, "%s: VkResult %d\n", #x, r_); exit(1); } } while (0)

struct context {
    VkDevice dev; VkQueue queue; VkBuffer buffer; VkDeviceMemory memory; uint32_t *map;
    VkDescriptorSetLayout layout; VkPipelineLayout pipeline_layout; VkPipeline pipeline;
    VkDescriptorPool descriptor_pool; VkDescriptorSet descriptor;
    VkCommandPool pool; VkCommandBuffer command; VkFence fence; VkQueryPool query;
};

static double now(void) { struct timespec t; clock_gettime(CLOCK_MONOTONIC, &t); return t.tv_sec + t.tv_nsec * 1e-9; }
static void delay_us(long us) { struct timespec t = { us / 1000000, (us % 1000000) * 1000 }; nanosleep(&t, NULL); }
static uint32_t expected(uint32_t i, uint32_t iterations, uint32_t seed) {
    uint32_t x = i ^ seed;
    for (uint32_t j = 0; j < iterations; j++) x = (x ^ (x >> 13)) * 1664525u + 1013904223u + j;
    return x;
}

static void init(struct context *c, VkPhysicalDevice physical, uint32_t family,
                 VkQueueGlobalPriorityKHR priority, const uint32_t *code, size_t bytes)
{
    float qp = 1.0f;
    VkDeviceQueueGlobalPriorityCreateInfoKHR pri = { .sType = VK_STRUCTURE_TYPE_DEVICE_QUEUE_GLOBAL_PRIORITY_CREATE_INFO_KHR, .globalPriority = priority };
    VkDeviceQueueCreateInfo qci = { .sType = VK_STRUCTURE_TYPE_DEVICE_QUEUE_CREATE_INFO, .pNext = &pri, .queueFamilyIndex = family, .queueCount = 1, .pQueuePriorities = &qp };
    const char *ext[] = { VK_KHR_GLOBAL_PRIORITY_EXTENSION_NAME };
    VkPhysicalDeviceHostQueryResetFeatures reset = { .sType = VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_HOST_QUERY_RESET_FEATURES, .hostQueryReset = VK_TRUE };
    VkDeviceCreateInfo dci = { .sType = VK_STRUCTURE_TYPE_DEVICE_CREATE_INFO, .pNext = &reset, .queueCreateInfoCount = 1, .pQueueCreateInfos = &qci, .enabledExtensionCount = 1, .ppEnabledExtensionNames = ext };
    CHECK(vkCreateDevice(physical, &dci, NULL, &c->dev)); vkGetDeviceQueue(c->dev, family, 0, &c->queue);
    VkBufferCreateInfo bci = { .sType = VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO, .size = (ITEMS + 1) * sizeof(uint32_t), .usage = VK_BUFFER_USAGE_STORAGE_BUFFER_BIT, .sharingMode = VK_SHARING_MODE_EXCLUSIVE };
    CHECK(vkCreateBuffer(c->dev, &bci, NULL, &c->buffer));
    VkMemoryRequirements req; VkPhysicalDeviceMemoryProperties mem; vkGetBufferMemoryRequirements(c->dev, c->buffer, &req); vkGetPhysicalDeviceMemoryProperties(physical, &mem);
    uint32_t type = UINT32_MAX;
    for (uint32_t i = 0; i < mem.memoryTypeCount; i++) if ((req.memoryTypeBits & (1u << i)) && (mem.memoryTypes[i].propertyFlags & (VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT | VK_MEMORY_PROPERTY_HOST_COHERENT_BIT)) == (VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT | VK_MEMORY_PROPERTY_HOST_COHERENT_BIT)) { type = i; break; }
    if (type == UINT32_MAX) { fputs("No coherent host-visible memory\n", stderr); exit(1); }
    VkMemoryAllocateInfo mai = { .sType = VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO, .allocationSize = req.size, .memoryTypeIndex = type };
    CHECK(vkAllocateMemory(c->dev, &mai, NULL, &c->memory)); CHECK(vkBindBufferMemory(c->dev, c->buffer, c->memory, 0)); CHECK(vkMapMemory(c->dev, c->memory, 0, VK_WHOLE_SIZE, 0, (void **)&c->map));
    VkDescriptorSetLayoutBinding binding = { .binding = 0, .descriptorType = VK_DESCRIPTOR_TYPE_STORAGE_BUFFER, .descriptorCount = 1, .stageFlags = VK_SHADER_STAGE_COMPUTE_BIT };
    VkDescriptorSetLayoutCreateInfo dl = { .sType = VK_STRUCTURE_TYPE_DESCRIPTOR_SET_LAYOUT_CREATE_INFO, .bindingCount = 1, .pBindings = &binding };
    CHECK(vkCreateDescriptorSetLayout(c->dev, &dl, NULL, &c->layout));
    VkPushConstantRange push = { .stageFlags = VK_SHADER_STAGE_COMPUTE_BIT, .size = 2 * sizeof(uint32_t) };
    VkPipelineLayoutCreateInfo pl = { .sType = VK_STRUCTURE_TYPE_PIPELINE_LAYOUT_CREATE_INFO, .setLayoutCount = 1, .pSetLayouts = &c->layout, .pushConstantRangeCount = 1, .pPushConstantRanges = &push };
    CHECK(vkCreatePipelineLayout(c->dev, &pl, NULL, &c->pipeline_layout));
    VkShaderModule module; VkShaderModuleCreateInfo sm = { .sType = VK_STRUCTURE_TYPE_SHADER_MODULE_CREATE_INFO, .codeSize = bytes, .pCode = code };
    CHECK(vkCreateShaderModule(c->dev, &sm, NULL, &module));
    VkComputePipelineCreateInfo pc = { .sType = VK_STRUCTURE_TYPE_COMPUTE_PIPELINE_CREATE_INFO, .stage = { .sType = VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO, .stage = VK_SHADER_STAGE_COMPUTE_BIT, .module = module, .pName = "main" }, .layout = c->pipeline_layout };
    CHECK(vkCreateComputePipelines(c->dev, VK_NULL_HANDLE, 1, &pc, NULL, &c->pipeline)); vkDestroyShaderModule(c->dev, module, NULL);
    VkDescriptorPoolSize ps = { .type = VK_DESCRIPTOR_TYPE_STORAGE_BUFFER, .descriptorCount = 1 };
    VkDescriptorPoolCreateInfo dp = { .sType = VK_STRUCTURE_TYPE_DESCRIPTOR_POOL_CREATE_INFO, .maxSets = 1, .poolSizeCount = 1, .pPoolSizes = &ps };
    CHECK(vkCreateDescriptorPool(c->dev, &dp, NULL, &c->descriptor_pool));
    VkDescriptorSetAllocateInfo da = { .sType = VK_STRUCTURE_TYPE_DESCRIPTOR_SET_ALLOCATE_INFO, .descriptorPool = c->descriptor_pool, .descriptorSetCount = 1, .pSetLayouts = &c->layout };
    CHECK(vkAllocateDescriptorSets(c->dev, &da, &c->descriptor));
    VkDescriptorBufferInfo bi = { .buffer = c->buffer, .range = VK_WHOLE_SIZE };
    VkWriteDescriptorSet write = { .sType = VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET, .dstSet = c->descriptor, .dstBinding = 0, .descriptorCount = 1, .descriptorType = VK_DESCRIPTOR_TYPE_STORAGE_BUFFER, .pBufferInfo = &bi };
    vkUpdateDescriptorSets(c->dev, 1, &write, 0, NULL);
    VkCommandPoolCreateInfo cp = { .sType = VK_STRUCTURE_TYPE_COMMAND_POOL_CREATE_INFO, .flags = VK_COMMAND_POOL_CREATE_RESET_COMMAND_BUFFER_BIT, .queueFamilyIndex = family };
    CHECK(vkCreateCommandPool(c->dev, &cp, NULL, &c->pool));
    VkCommandBufferAllocateInfo ca = { .sType = VK_STRUCTURE_TYPE_COMMAND_BUFFER_ALLOCATE_INFO, .commandPool = c->pool, .level = VK_COMMAND_BUFFER_LEVEL_PRIMARY, .commandBufferCount = 1 };
    CHECK(vkAllocateCommandBuffers(c->dev, &ca, &c->command));
    VkFenceCreateInfo fc = { .sType = VK_STRUCTURE_TYPE_FENCE_CREATE_INFO }; CHECK(vkCreateFence(c->dev, &fc, NULL, &c->fence));
    VkQueryPoolCreateInfo qc = { .sType = VK_STRUCTURE_TYPE_QUERY_POOL_CREATE_INFO, .queryType = VK_QUERY_TYPE_TIMESTAMP, .queryCount = 2 }; CHECK(vkCreateQueryPool(c->dev, &qc, NULL, &c->query));
}

static void submit(struct context *c, uint32_t iterations, uint32_t seed)
{
    __atomic_store_n(&c->map[ITEMS], 0u, __ATOMIC_SEQ_CST);
    CHECK(vkResetFences(c->dev, 1, &c->fence)); CHECK(vkResetCommandBuffer(c->command, 0));
    /* Reset before submission so an earlier result cannot masquerade as start. */
    vkResetQueryPool(c->dev, c->query, 0, 2);
    VkCommandBufferBeginInfo begin = { .sType = VK_STRUCTURE_TYPE_COMMAND_BUFFER_BEGIN_INFO, .flags = VK_COMMAND_BUFFER_USAGE_ONE_TIME_SUBMIT_BIT };
    CHECK(vkBeginCommandBuffer(c->command, &begin));
    vkCmdWriteTimestamp(c->command, VK_PIPELINE_STAGE_COMPUTE_SHADER_BIT, c->query, 0);
    vkCmdBindPipeline(c->command, VK_PIPELINE_BIND_POINT_COMPUTE, c->pipeline);
    vkCmdBindDescriptorSets(c->command, VK_PIPELINE_BIND_POINT_COMPUTE, c->pipeline_layout, 0, 1, &c->descriptor, 0, NULL);
    uint32_t push[] = { iterations, seed }; vkCmdPushConstants(c->command, c->pipeline_layout, VK_SHADER_STAGE_COMPUTE_BIT, 0, sizeof(push), push);
    vkCmdDispatch(c->command, GROUPS, 1, 1);
    VkMemoryBarrier barrier = { .sType = VK_STRUCTURE_TYPE_MEMORY_BARRIER, .srcAccessMask = VK_ACCESS_SHADER_WRITE_BIT, .dstAccessMask = VK_ACCESS_HOST_READ_BIT };
    vkCmdPipelineBarrier(c->command, VK_PIPELINE_STAGE_COMPUTE_SHADER_BIT, VK_PIPELINE_STAGE_HOST_BIT, 0, 1, &barrier, 0, NULL, 0, NULL);
    vkCmdWriteTimestamp(c->command, VK_PIPELINE_STAGE_BOTTOM_OF_PIPE_BIT, c->query, 1); CHECK(vkEndCommandBuffer(c->command));
    VkSubmitInfo si = { .sType = VK_STRUCTURE_TYPE_SUBMIT_INFO, .commandBufferCount = 1, .pCommandBuffers = &c->command };
    CHECK(vkQueueSubmit(c->queue, 1, &si, c->fence));
}

static void finish(struct context *c, uint32_t iterations, uint32_t seed, int full)
{
    CHECK(vkWaitForFences(c->dev, 1, &c->fence, VK_TRUE, UINT64_C(5000000000)));
    uint32_t stride = full ? 1 : 4093;
    for (uint32_t i = 0; i < ITEMS; i += stride) {
        uint32_t want = expected(i, iterations, seed);
        if (c->map[i] != want) { fprintf(stderr, "compute mismatch index=%u got=%#x expected=%#x\n", i, c->map[i], want); exit(1); }
    }
}

static int started(struct context *c)
{
    /* See header: only a positive observation before fence completion counts. */
    return __atomic_load_n(&c->map[ITEMS], __ATOMIC_SEQ_CST) == 0x4d344750u;
}

static void destroy(struct context *c)
{
    CHECK(vkDeviceWaitIdle(c->dev));
    vkDestroyQueryPool(c->dev, c->query, NULL); vkDestroyFence(c->dev, c->fence, NULL);
    vkDestroyCommandPool(c->dev, c->pool, NULL); vkDestroyDescriptorPool(c->dev, c->descriptor_pool, NULL);
    vkDestroyPipeline(c->dev, c->pipeline, NULL); vkDestroyPipelineLayout(c->dev, c->pipeline_layout, NULL);
    vkDestroyDescriptorSetLayout(c->dev, c->layout, NULL); vkUnmapMemory(c->dev, c->memory);
    vkDestroyBuffer(c->dev, c->buffer, NULL); vkFreeMemory(c->dev, c->memory, NULL); vkDestroyDevice(c->dev, NULL);
}

int main(int argc, char **argv)
{
    if (argc != 2) { fprintf(stderr, "usage: %s shader.spv\n", argv[0]); return 2; }
    const char *marker_descriptor = getenv("M4_GPU_TRACE_FD");
    if (marker_descriptor) { marker_fd = atoi(marker_descriptor); if (marker_fd < 3) return 1; }
    FILE *f = fopen(argv[1], "rb"); if (!f || fseek(f, 0, SEEK_END)) return 1; long n = ftell(f);
    if (n <= 0 || (n % 4) || fseek(f, 0, SEEK_SET)) return 1;
    uint32_t *code = malloc((size_t)n); if (!code || fread(code, 1, (size_t)n, f) != (size_t)n) return 1; fclose(f);
    VkApplicationInfo ai = { .sType = VK_STRUCTURE_TYPE_APPLICATION_INFO, .pApplicationName = "m4rch GPU scheduling experiment", .apiVersion = VK_API_VERSION_1_2 };
    VkInstanceCreateInfo ici = { .sType = VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO, .pApplicationInfo = &ai }; VkInstance instance; CHECK(vkCreateInstance(&ici, NULL, &instance));
    uint32_t count = 0; CHECK(vkEnumeratePhysicalDevices(instance, &count, NULL)); if (!count) return 1;
    VkPhysicalDevice *devices = calloc(count, sizeof(*devices)); if (!devices) return 1; CHECK(vkEnumeratePhysicalDevices(instance, &count, devices));
    VkPhysicalDevice physical = VK_NULL_HANDLE;
    for (uint32_t i = 0; i < count; i++) { VkPhysicalDeviceProperties p; vkGetPhysicalDeviceProperties(devices[i], &p); if (strstr(p.deviceName, "Apple M4 Pro")) { physical = devices[i]; printf("GPU: %s\n", p.deviceName); break; } }
    free(devices); if (!physical) { fputs("M4 Pro GPU not found\n", stderr); return 1; }
    uint32_t nqueue = 0; vkGetPhysicalDeviceQueueFamilyProperties(physical, &nqueue, NULL); VkQueueFamilyProperties *q = calloc(nqueue, sizeof(*q)); if (!q) return 1;
    vkGetPhysicalDeviceQueueFamilyProperties(physical, &nqueue, q); uint32_t family = UINT32_MAX;
    for (uint32_t i = 0; i < nqueue; i++) if ((q[i].queueFlags & VK_QUEUE_COMPUTE_BIT) && q[i].timestampValidBits) { family = i; break; }
    free(q); if (family == UINT32_MAX) { fputs("No compute queue with timestamps\n", stderr); return 1; }
    struct context low = {0}, medium_bg = {0}, medium = {0};
    init(&low, physical, family, VK_QUEUE_GLOBAL_PRIORITY_LOW_KHR, code, (size_t)n);
    init(&medium_bg, physical, family, VK_QUEUE_GLOBAL_PRIORITY_MEDIUM_KHR, code, (size_t)n);
    init(&medium, physical, family, VK_QUEUE_GLOBAL_PRIORITY_MEDIUM_KHR, code, (size_t)n); free(code);
    uint32_t loops = 256; double elapsed = 0;
    submit(&low, 64, 1); finish(&low, 64, 1, 0);
    for (;;) {
        double t = now(); submit(&low, loops, 2); finish(&low, loops, 2, 0); elapsed = now() - t;
        printf("calibration iterations=%u elapsed=%.3f s\n", loops, elapsed); fflush(stdout);
        if (elapsed >= 0.08 || loops >= 1048576) break;
        loops *= elapsed < 0.02 ? 4 : 2; if (loops > 1048576) loops = 1048576;
    }
    if (elapsed < 0.01) { puts("INCONCLUSIVE: workload too short to observe scheduling"); return 2; }
    const char *delay_text = getenv("M4_GPU_CONTENDER_DELAY_US");
    long contender_delay = delay_text ? strtol(delay_text, NULL, 10) : 0;
    if (contender_delay < 0 || contender_delay > 100000) { fputs("Invalid contender delay\n", stderr); return 1; }
    printf("contender delay after in-dispatch marker: %ld us\n", contender_delay);
    for (unsigned control = 0; control < 2; control++) {
        struct context *background = control ? &medium_bg : &low;
        unsigned overlap = 0, valid = 0;
        for (unsigned round = 0; round < 5; round++) {
            mark("begin", control, round);
            submit(background, loops, 3 + round);
            double limit = now() + 1.0;
            while (!started(background) && vkGetFenceStatus(background->dev, background->fence) == VK_NOT_READY && now() < limit) delay_us(100);
            if (vkGetFenceStatus(background->dev, background->fence) != VK_NOT_READY || !started(background)) {
                finish(background, loops, 3 + round, 0); puts("round: INCONCLUSIVE background finished before contender"); continue;
            }
            mark("gpu_started", control, round);
            if (contender_delay) delay_us(contender_delay);
            if (vkGetFenceStatus(background->dev, background->fence) != VK_NOT_READY) {
                finish(background, loops, 3 + round, 0); puts("round: INCONCLUSIVE background finished during delay"); continue;
            }
            valid++; mark("contender_submit", control, round);
            submit(&medium, 64, 100 + round); finish(&medium, 64, 100 + round, 1);
            mark("contender_done", control, round);
            int running = vkGetFenceStatus(background->dev, background->fence) == VK_NOT_READY;
            overlap += running; finish(background, loops, 3 + round, 0);
            mark("background_done", control, round);
            printf("%s round=%u contender_finished_while_background_unfinished=%d\n", control ? "same-priority" : "low-vs-medium", round, running); fflush(stdout);
        }
        printf("%s valid=%u overlap=%u/5\n", control ? "same-priority" : "low-vs-medium", valid, overlap);
    }
    puts("INCONCLUSIVE for preemption: marker and fence overlap show progress, not a context save/restore. Compare synchronized GPU traces and buffer summaries.");
    destroy(&low); destroy(&medium_bg); destroy(&medium); vkDestroyInstance(instance, NULL);
    return 0;
}
