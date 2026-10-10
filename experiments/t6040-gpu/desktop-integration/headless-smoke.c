/* SPDX-License-Identifier: MIT */
#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <poll.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/stat.h>
#include <unistd.h>
#include <EGL/egl.h>
#include <EGL/eglext.h>
#include <GLES3/gl3.h>
#include <gbm.h>
#include <xf86drm.h>
#include "asahi_drm.h"
#include "smoke-criteria.h"

static void fail(const char *what)
{
   fprintf(stderr, "FAIL: %s\n", what);
   exit(1);
}

static bool extension(const char *extensions, const char *wanted)
{
   if (!extensions)
      return false;
   size_t n = strlen(wanted);
   for (const char *p = extensions; (p = strstr(p, wanted)); p += n)
      if ((p == extensions || p[-1] == ' ') && (p[n] == 0 || p[n] == ' '))
         return true;
   return false;
}

static GLuint shader(GLenum type, const char *text)
{
   GLuint s = glCreateShader(type);
   glShaderSource(s, 1, &text, NULL);
   glCompileShader(s);
   GLint ok;
   glGetShaderiv(s, GL_COMPILE_STATUS, &ok);
   if (!ok) {
      char log[4096];
      glGetShaderInfoLog(s, sizeof(log), NULL, log);
      fprintf(stderr, "%s\n", log);
      fail("shader compilation");
   }
   return s;
}

static void save_frame(int directory, unsigned frame, const uint8_t *pixels)
{
   const char *name = frame == 0 ? "frame0.rgba" : "frame1.rgba";
   int fd = openat(directory, name, O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW, 0600);
   if (fd < 0)
      fail("exclusive frame output creation");
   size_t offset = 0;
   while (offset < SMOKE_BYTES) {
      ssize_t n = write(fd, pixels + offset, SMOKE_BYTES - offset);
      if (n <= 0)
         fail("frame output write");
      offset += (size_t)n;
   }
   if (fsync(fd) || close(fd))
      fail("frame output durability");
}

static void json_string(FILE *file, const char *text)
{
   fputc('"', file);
   for (const unsigned char *p = (const unsigned char *)text; *p; ++p) {
      if (*p == '"' || *p == '\\')
         fputc('\\', file);
      if (*p < 32)
         fprintf(file, "\\u%04x", *p);
      else
         fputc(*p, file);
   }
   fputc('"', file);
}

int main(int argc, char **argv)
{
   if (argc != 3) {
      fprintf(stderr, "Usage: %s EXPLICIT_RENDER_NODE EXISTING_EMPTY_OUTPUT_DIR\n", argv[0]);
      return 2;
   }
   /* An external deadline is still required: a wedged kernel operation might
    * not be interruptible. No success is inferred from a timeout or cleanup. */
   alarm(30);
   const char *software = getenv("LIBGL_ALWAYS_SOFTWARE");
   if (software && strcmp(software, "0"))
      fail("LIBGL_ALWAYS_SOFTWARE is set");
   const char *gallium = getenv("GALLIUM_DRIVER");
   const char *loader = getenv("MESA_LOADER_DRIVER_OVERRIDE");
   if ((gallium && strcmp(gallium, "asahi")) || (loader && strcmp(loader, "asahi")))
      fail("a non-Asahi driver override is set");
   int directory = open(argv[2], O_RDONLY | O_DIRECTORY | O_NOFOLLOW);
   if (directory < 0)
      fail("output directory");
   struct stat existing;
   for (unsigned i = 0; i < 3; ++i) {
      const char *name = i == 0 ? "smoke.json" : i == 1 ? "frame0.rgba" : "frame1.rgba";
      if (!fstatat(directory, name, &existing, AT_SYMLINK_NOFOLLOW) || errno != ENOENT)
         fail("output names must not exist");
   }
   int fd = open(argv[1], O_RDWR | O_CLOEXEC | O_NOFOLLOW);
   struct stat st;
   if (fd < 0 || fstat(fd, &st) || !S_ISCHR(st.st_mode) ||
       drmGetNodeTypeFromFd(fd) != DRM_NODE_RENDER)
      fail("explicit node is not a DRM render node");
   drmVersionPtr version = drmGetVersion(fd);
   if (!version || !version->name || strcmp(version->name, "asahi"))
      fail("DRM driver is not Asahi");
   drmFreeVersion(version);
   struct drm_asahi_params_global params = {0};
   struct drm_asahi_get_params query = {
      .param_group = 0, .pointer = (uint64_t)(uintptr_t)&params, .size = sizeof(params),
   };
   if (drmIoctl(fd, DRM_IOCTL_ASAHI_GET_PARAMS, &query) || query.size < sizeof(params))
      fail("complete Asahi GET_PARAMS");
   uint64_t masks[DRM_ASAHI_MAX_CLUSTERS];
   for (unsigned i = 0; i < DRM_ASAHI_MAX_CLUSTERS; ++i)
      masks[i] = params.core_masks[i];
   struct agx_g16_device_info info;
   if (!agx_g16_decode_device(params.chip_id, params.gpu_variant, params.num_dies,
                              params.num_clusters_total, params.num_cores_per_cluster,
                              masks, DRM_ASAHI_MAX_CLUSTERS, &info) ||
       !smoke_j614_identity(params.gpu_generation, params.gpu_revision, &info))
      fail("device does not match captured J614s T6040/G16S identity");
   struct gbm_device *gbm = gbm_create_device(fd);
   if (!gbm || gbm_device_get_fd(gbm) != fd)
      fail("GBM device binding");
   EGLDisplay display = eglGetPlatformDisplay(EGL_PLATFORM_GBM_KHR, gbm, NULL);
   EGLint major, minor;
   if (display == EGL_NO_DISPLAY || !eglInitialize(display, &major, &minor))
      fail("GBM EGL initialization");
   const char *egl_extensions = eglQueryString(display, EGL_EXTENSIONS);
   if (!extension(egl_extensions, "EGL_KHR_surfaceless_context") ||
       !eglBindAPI(EGL_OPENGL_ES_API))
      fail("surfaceless GLES support");
   EGLint attributes[] = {EGL_RENDERABLE_TYPE, EGL_OPENGL_ES3_BIT,
                         EGL_RED_SIZE, 8, EGL_GREEN_SIZE, 8, EGL_BLUE_SIZE, 8,
                         EGL_ALPHA_SIZE, 8, EGL_NONE};
   EGLConfig config;
   EGLint count;
   if (!eglChooseConfig(display, attributes, &config, 1, &count) || count != 1)
      fail("GLES3 EGL configuration");
   EGLint context_attributes[] = {EGL_CONTEXT_CLIENT_VERSION, 3, EGL_NONE};
   EGLContext context = eglCreateContext(display, config, EGL_NO_CONTEXT, context_attributes);
   if (context == EGL_NO_CONTEXT ||
       !eglMakeCurrent(display, EGL_NO_SURFACE, EGL_NO_SURFACE, context))
      fail("surfaceless GLES3 context");
   const char *renderer = (const char *)glGetString(GL_RENDERER);
   if (!smoke_hardware_renderer(renderer))
      fail("renderer does not identify hardware Apple M4 Pro/G16S");
   const char *vendor = (const char *)glGetString(GL_VENDOR);
   const char *gl_version = (const char *)glGetString(GL_VERSION);
   if (!vendor || !gl_version)
      fail("renderer strings");
   GLuint vertex = shader(GL_VERTEX_SHADER,
      "#version 300 es\n"
      "const vec2 p[3]=vec2[3](vec2(-.75,-.75),vec2(.75,-.75),vec2(0.,.75));\n"
      "void main(){gl_Position=vec4(p[gl_VertexID],0.,1.);}\n");
   GLuint fragment = shader(GL_FRAGMENT_SHADER,
      "#version 300 es\nprecision highp float;\n"
      "uniform vec4 color;out vec4 pixel;void main(){pixel=color;}\n");
   GLuint program = glCreateProgram();
   glAttachShader(program, vertex); glAttachShader(program, fragment); glLinkProgram(program);
   GLint linked;
   glGetProgramiv(program, GL_LINK_STATUS, &linked);
   if (!linked)
      fail("shader program link");
   glUseProgram(program);
   GLint color = glGetUniformLocation(program, "color");
   if (color < 0)
      fail("color uniform");
   GLuint texture, framebuffer, vertex_array;
   glGenTextures(1, &texture); glBindTexture(GL_TEXTURE_2D, texture);
   glTexStorage2D(GL_TEXTURE_2D, 1, GL_RGBA8, SMOKE_WIDTH, SMOKE_HEIGHT);
   glGenFramebuffers(1, &framebuffer); glBindFramebuffer(GL_FRAMEBUFFER, framebuffer);
   glFramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_TEXTURE_2D, texture, 0);
   if (glCheckFramebufferStatus(GL_FRAMEBUFFER) != GL_FRAMEBUFFER_COMPLETE)
      fail("RGBA8 offscreen framebuffer");
   glGenVertexArrays(1, &vertex_array); glBindVertexArray(vertex_array);
   glViewport(0, 0, SMOKE_WIDTH, SMOKE_HEIGHT);
   glDisable(GL_DITHER); glDisable(GL_BLEND); glDisable(GL_DEPTH_TEST);
   uint8_t pixels[2][SMOKE_BYTES];
   unsigned colored[2];
   bool native_export = extension(egl_extensions, "EGL_ANDROID_native_fence_sync");
   PFNEGLCREATESYNCKHRPROC create_sync = (PFNEGLCREATESYNCKHRPROC)eglGetProcAddress("eglCreateSyncKHR");
   PFNEGLDESTROYSYNCKHRPROC destroy_sync = (PFNEGLDESTROYSYNCKHRPROC)eglGetProcAddress("eglDestroySyncKHR");
   PFNEGLDUPNATIVEFENCEFDANDROIDPROC dup_fence = (PFNEGLDUPNATIVEFENCEFDANDROIDPROC)eglGetProcAddress("eglDupNativeFenceFDANDROID");
   if (native_export && (!create_sync || !destroy_sync || !dup_fence))
      fail("native fence entrypoints");
   for (unsigned frame = 0; frame < 2; ++frame) {
      glClearColor(0, 0, 1, 1); glClear(GL_COLOR_BUFFER_BIT);
      glUniform4f(color, frame == 0 ? 1 : 0, frame == 1 ? 1 : 0, 0, 1);
      glDrawArrays(GL_TRIANGLES, 0, 3);
      GLsync fence = glFenceSync(GL_SYNC_GPU_COMMANDS_COMPLETE, 0);
      if (!fence || glGetError() != GL_NO_ERROR)
         fail("draw/fence submission");
      EGLSyncKHR native = EGL_NO_SYNC_KHR;
      if (native_export) {
         const EGLint attrs[] = {EGL_SYNC_NATIVE_FENCE_FD_ANDROID,
                                EGL_NO_NATIVE_FENCE_FD_ANDROID, EGL_NONE};
         native = create_sync(display, EGL_SYNC_NATIVE_FENCE_ANDROID, attrs);
         if (native == EGL_NO_SYNC_KHR)
            fail("native fence creation");
      }
      glFlush();
      GLenum waited = glClientWaitSync(fence, 0, UINT64_C(5000000000));
      if (waited != GL_ALREADY_SIGNALED && waited != GL_CONDITION_SATISFIED)
         fail("GPU completion fence did not signal within five seconds");
      glDeleteSync(fence);
      if (native_export) {
         int fence_fd = dup_fence(display, native);
         struct pollfd p = {.fd = fence_fd, .events = POLLIN};
         if (fence_fd < 0 || poll(&p, 1, 5000) != 1 || !(p.revents & POLLIN) ||
             (p.revents & (POLLERR | POLLNVAL)))
            fail("exported native fence did not signal");
         close(fence_fd); destroy_sync(display, native);
      }
      memset(pixels[frame], 0xa5, SMOKE_BYTES);
      glReadPixels(0, 0, SMOKE_WIDTH, SMOKE_HEIGHT, GL_RGBA, GL_UNSIGNED_BYTE, pixels[frame]);
      if (glGetError() != GL_NO_ERROR || !smoke_pixels(pixels[frame], frame, &colored[frame]))
         fail("complete fresh triangle/background pixel readback");
      save_frame(directory, frame, pixels[frame]);
   }
   if (memcmp(pixels[0], pixels[1], SMOKE_BYTES) == 0 || colored[0] != colored[1])
      fail("second draw is stale or geometry coverage changed");
   int report_fd = openat(directory, "smoke.json", O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW, 0600);
   FILE *report = report_fd < 0 ? NULL : fdopen(report_fd, "w");
   if (!report)
      fail("exclusive report creation");
   fputs("{\n  \"schema\": \"m4rch.t6040-headless-smoke.v1\",\n  \"render_node\": ", report);
   json_string(report, argv[1]);
   fputs(",\n  \"renderer\": ", report); json_string(report, renderer);
   fputs(",\n  \"vendor\": ", report); json_string(report, vendor);
   fputs(",\n  \"gl_version\": ", report); json_string(report, gl_version);
   fprintf(report, ",\n  \"egl_version\": [%d, %d],\n  \"chip_id\": %u,\n  \"revision\": %u,\n"
                   "  \"generation\": 16,\n  \"variant\": \"S\",\n  \"clusters\": 2,\n"
                   "  \"logical_slots_per_cluster\": 10,\n  \"core_masks\": [987, 987],\n"
                   "  \"hardware_renderer\": true,\n  \"frames\": 2,\n  \"width\": 64,\n  \"height\": 64,\n"
                   "  \"colored_pixels\": [%u, %u],\n  \"completion_fence_waits\": 2,\n"
                   "  \"native_fence_export\": %s,\n  \"pixel_readback_passed\": true,\n"
                   "  \"desktop_presentation_qualified\": false\n}\n",
           major, minor, params.chip_id, params.gpu_revision, colored[0], colored[1],
           native_export ? "true" : "false");
   if (fflush(report) || fsync(report_fd) || fclose(report) || fsync(directory))
      fail("report durability");
   /* A completed GL fence establishes this userspace submission boundary;
    * it does not prove firmware teardown, suspend or display presentation. */
   glDeleteFramebuffers(1, &framebuffer); glDeleteTextures(1, &texture);
   glDeleteVertexArrays(1, &vertex_array); glDeleteProgram(program);
   glDeleteShader(vertex); glDeleteShader(fragment);
   eglMakeCurrent(display, EGL_NO_SURFACE, EGL_NO_SURFACE, EGL_NO_CONTEXT);
   eglDestroyContext(display, context); eglTerminate(display);
   gbm_device_destroy(gbm); close(fd); close(directory);
   puts("PASS: hardware identity, two completed draws and fresh pixel readbacks");
   return 0;
}
