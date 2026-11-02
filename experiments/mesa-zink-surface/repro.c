/* Exercise actual Wayland/EGL drawable destruction and surface reuse. */
#define _POSIX_C_SOURCE 200809L
#include <EGL/egl.h>
#include <EGL/eglext.h>
#include <GLES2/gl2.h>
#include <wayland-client.h>
#include <wayland-egl.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "xdg-shell-client-protocol.h"

static struct wl_compositor *compositor;
static struct xdg_wm_base *wm;
static int configured;

static void ping(void *d, struct xdg_wm_base *w, uint32_t serial) { (void)d; xdg_wm_base_pong(w, serial); }
static const struct xdg_wm_base_listener wm_listener = { .ping = ping };
static void registry_global(void *d, struct wl_registry *r, uint32_t n, const char *iface, uint32_t v)
{
   (void)d;
   if (!strcmp(iface, wl_compositor_interface.name))
      compositor = wl_registry_bind(r, n, &wl_compositor_interface, v < 4 ? v : 4);
   else if (!strcmp(iface, xdg_wm_base_interface.name)) {
      wm = wl_registry_bind(r, n, &xdg_wm_base_interface, 1);
      xdg_wm_base_add_listener(wm, &wm_listener, NULL);
   }
}
static void registry_remove(void *d, struct wl_registry *r, uint32_t n) { (void)d; (void)r; (void)n; }
static const struct wl_registry_listener registry_listener = { registry_global, registry_remove };
static void surface_configure(void *d, struct xdg_surface *s, uint32_t serial)
{ (void)d; xdg_surface_ack_configure(s, serial); configured = 1; }
static const struct xdg_surface_listener surface_listener = { .configure = surface_configure };
static void toplevel_configure(void *d, struct xdg_toplevel *t, int32_t w, int32_t h, struct wl_array *a)
{ (void)d; (void)t; (void)w; (void)h; (void)a; }
static void toplevel_close(void *d, struct xdg_toplevel *t) { (void)d; (void)t; }
static const struct xdg_toplevel_listener toplevel_listener = {
   .configure = toplevel_configure, .close = toplevel_close,
};

static int fail(struct wl_display *display, const char *where)
{
   const struct wl_interface *iface = NULL;
   uint32_t object = 0, protocol = wl_display_get_protocol_error(display, &iface, &object);
   fprintf(stderr, "%s: EGL 0x%x, Wayland error %d, protocol %s@%u code %u\n",
           where, eglGetError(), wl_display_get_error(display), iface ? iface->name : "none", object, protocol);
   return 1;
}

int main(int argc, char **argv)
{
   int count = argc > 1 ? atoi(argv[1]) : 250;
   int shared = argc > 2 && !strcmp(argv[2], "shared");
   if (count < 1 || count > 10000) return 2;
   struct wl_display *display = wl_display_connect(NULL);
   if (!display) { perror("wl_display_connect"); return 1; }
   struct wl_registry *registry = wl_display_get_registry(display);
   wl_registry_add_listener(registry, &registry_listener, NULL);
   if (wl_display_roundtrip(display) < 0 || !compositor || !wm) return fail(display, "registry");
   EGLDisplay egl = eglGetDisplay((EGLNativeDisplayType)display);
   EGLint major, minor, n;
   if (!eglInitialize(egl, &major, &minor) || !eglBindAPI(EGL_OPENGL_ES_API)) return fail(display, "eglInitialize");
   const EGLint cfgattr[] = { EGL_SURFACE_TYPE, EGL_WINDOW_BIT, EGL_RENDERABLE_TYPE, EGL_OPENGL_ES2_BIT,
      EGL_RED_SIZE, 8, EGL_GREEN_SIZE, 8, EGL_BLUE_SIZE, 8, EGL_NONE };
   EGLConfig cfg;
   if (!eglChooseConfig(egl, cfgattr, &cfg, 1, &n) || n != 1) return fail(display, "eglChooseConfig");
   const EGLint ctxattr[] = { EGL_CONTEXT_CLIENT_VERSION, 2, EGL_NONE };
   EGLContext ctx = eglCreateContext(egl, cfg, EGL_NO_CONTEXT, ctxattr);
   if (ctx == EGL_NO_CONTEXT) return fail(display, "eglCreateContext");
   uintptr_t previous = 0;
   uintptr_t *seen = calloc((size_t)count, sizeof(*seen));
   if (!seen) return 1;
   unsigned reused = 0;
   for (int i = 0; i < count; i++) {
      configured = 0;
      struct wl_surface *surface = wl_compositor_create_surface(compositor);
      if (!surface) return fail(display, "wl_surface create");
      for (int j = 0; j < i; j++) {
         if ((uintptr_t)surface == seen[j]) { reused++; break; }
      }
      fprintf(stderr, "iteration=%d surface=%p previous=%p reused=%u\n",
              i, (void *)surface, (void *)previous, reused);
      struct xdg_surface *xdg = xdg_wm_base_get_xdg_surface(wm, surface);
      xdg_surface_add_listener(xdg, &surface_listener, NULL);
      struct xdg_toplevel *top = xdg_surface_get_toplevel(xdg);
      xdg_toplevel_add_listener(top, &toplevel_listener, NULL);
      xdg_toplevel_set_title(top, "Mesa surface lifetime test");
      wl_surface_commit(surface);
      while (!configured)
         if (wl_display_dispatch(display) < 0) return fail(display, "configure");
      struct wl_egl_window *window = wl_egl_window_create(surface, 96, 96);
      EGLSurface es = eglCreateWindowSurface(egl, cfg, (EGLNativeWindowType)window, NULL);
      if (es == EGL_NO_SURFACE || !eglMakeCurrent(egl, es, es, ctx)) return fail(display, "make current");
      if (i == 0) printf("EGL %d.%d; renderer: %s\n", major, minor, glGetString(GL_RENDERER));
      glClearColor((i & 1) ? 0.2f : 0.8f, 0.3f, 0.4f, 1.0f);
      glClear(GL_COLOR_BUFFER_BIT);
      if (glGetError() != GL_NO_ERROR) return fail(display, "GL clear");
      if (!eglSwapBuffers(egl, es)) return fail(display, "swap");
      if (wl_display_dispatch_pending(display) < 0) return fail(display, "dispatch");
      if (shared) {
         struct wl_egl_window *window2 = wl_egl_window_create(surface, 96, 96);
         EGLSurface es2 = eglCreateWindowSurface(egl, cfg, (EGLNativeWindowType)window2, NULL);
         if (es2 == EGL_NO_SURFACE || !eglMakeCurrent(egl, es2, es2, ctx)) return fail(display, "shared make current");
         glClear(GL_COLOR_BUFFER_BIT);
         if (!eglSwapBuffers(egl, es2)) return fail(display, "shared swap");
         if (!eglDestroySurface(egl, es)) return fail(display, "shared destroy first surface");
         wl_egl_window_destroy(window);
         glClear(GL_COLOR_BUFFER_BIT);
         if (!eglSwapBuffers(egl, es2)) return fail(display, "shared swap after first destroy");
         /* A new drawable must reuse the still-live second drawable's
          * VkSurface; evicting the cache on every destroy creates two. */
         struct wl_egl_window *window3 = wl_egl_window_create(surface, 96, 96);
         EGLSurface es3 = eglCreateWindowSurface(egl, cfg, (EGLNativeWindowType)window3, NULL);
         if (es3 == EGL_NO_SURFACE || !eglMakeCurrent(egl, es3, es3, ctx)) return fail(display, "third shared make current");
         glClear(GL_COLOR_BUFFER_BIT);
         if (!eglSwapBuffers(egl, es3)) return fail(display, "third shared swap");
         if (!eglMakeCurrent(egl, es2, es2, ctx)) return fail(display, "restore second shared drawable");
         if (!eglDestroySurface(egl, es3)) return fail(display, "shared destroy third surface");
         wl_egl_window_destroy(window3);
         glClear(GL_COLOR_BUFFER_BIT);
         if (!eglSwapBuffers(egl, es2)) return fail(display, "second shared swap after third destroy");
         es = es2;
         window = window2;
      }
      if (!eglMakeCurrent(egl, EGL_NO_SURFACE, EGL_NO_SURFACE, EGL_NO_CONTEXT)) return fail(display, "unbind");
      if (!eglDestroySurface(egl, es)) return fail(display, "eglDestroySurface");
      wl_egl_window_destroy(window);
      xdg_toplevel_destroy(top);
      xdg_surface_destroy(xdg);
      previous = (uintptr_t)surface;
      seen[i] = previous;
      wl_surface_destroy(surface);
      if (wl_display_roundtrip(display) < 0) return fail(display, "roundtrip after destroy");
      if ((i + 1) % 25 == 0) { printf("iterations=%d address_reuse=%u\n", i + 1, reused); fflush(stdout); }
   }
   eglDestroyContext(egl, ctx);
   eglTerminate(egl);
   xdg_wm_base_destroy(wm);
   wl_compositor_destroy(compositor);
   wl_registry_destroy(registry);
   wl_display_disconnect(display);
   free(seen);
   printf("completed=%d address_reuse=%u\n", count, reused);
   return 0;
}
