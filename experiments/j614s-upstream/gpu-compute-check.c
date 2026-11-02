/* Exercise the actual GPU compute path and compare every result with the CPU. */
#define EGL_EGLEXT_PROTOTYPES
#include <EGL/egl.h>
#include <EGL/eglext.h>
#include <GLES3/gl31.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

enum { ITEMS = 262144, ROUNDS = 64 };
static const char *shader =
    "#version 310 es\n"
    "layout(local_size_x=64) in;\n"
    "layout(std430,binding=0) buffer Output { uint value[]; };\n"
    "void main() { uint x=gl_GlobalInvocationID.x;"
    "for(uint i=0u;i<64u;i++) x=(x^((x<<13)|(x>>19)))*1664525u+1013904223u+i;"
    "value[gl_GlobalInvocationID.x]=x; }\n";

static void die(const char *msg) { fprintf(stderr, "%s (EGL %#x, GL %#x)\n", msg, eglGetError(), glGetError()); exit(1); }

int main(void)
{
    PFNEGLGETPLATFORMDISPLAYEXTPROC get_display =
        (PFNEGLGETPLATFORMDISPLAYEXTPROC)eglGetProcAddress("eglGetPlatformDisplayEXT");
    if (!get_display) die("No surfaceless EGL platform");
    EGLDisplay dpy = get_display(EGL_PLATFORM_SURFACELESS_MESA, EGL_DEFAULT_DISPLAY, NULL);
    if (dpy == EGL_NO_DISPLAY || !eglInitialize(dpy, NULL, NULL) || !eglBindAPI(EGL_OPENGL_ES_API))
        die("EGL initialization failed");
    EGLint attrs[] = { EGL_SURFACE_TYPE, EGL_PBUFFER_BIT, EGL_RENDERABLE_TYPE, EGL_OPENGL_ES3_BIT, EGL_NONE };
    EGLConfig cfg; EGLint n;
    if (!eglChooseConfig(dpy, attrs, &cfg, 1, &n) || n != 1) die("No EGL config");
    EGLint ctxattrs[] = { EGL_CONTEXT_CLIENT_VERSION, 3, EGL_NONE };
    EGLContext ctx = eglCreateContext(dpy, cfg, EGL_NO_CONTEXT, ctxattrs);
    if (ctx == EGL_NO_CONTEXT || !eglMakeCurrent(dpy, EGL_NO_SURFACE, EGL_NO_SURFACE, ctx)) die("No EGL context");
    const char *renderer = (const char *)glGetString(GL_RENDERER);
    const char *version = (const char *)glGetString(GL_VERSION);
    if (!renderer || !version || !strstr(renderer, "zink") || !strstr(renderer, "M4 Pro"))
        die("Expected Zink on the M4 Pro, not a software renderer");
    printf("Renderer: %s\nVersion: %s\n", renderer, version);
    GLuint cs = glCreateShader(GL_COMPUTE_SHADER);
    glShaderSource(cs, 1, &shader, NULL); glCompileShader(cs);
    GLint ok; glGetShaderiv(cs, GL_COMPILE_STATUS, &ok);
    if (!ok) { char log[4096]; glGetShaderInfoLog(cs, sizeof(log), NULL, log); fprintf(stderr, "%s\n", log); die("Compute shader failed to compile"); }
    GLuint program = glCreateProgram(); glAttachShader(program, cs); glLinkProgram(program);
    glGetProgramiv(program, GL_LINK_STATUS, &ok); if (!ok) die("Compute program failed to link");
    GLuint buffer; glGenBuffers(1, &buffer); glBindBuffer(GL_SHADER_STORAGE_BUFFER, buffer);
    glBufferData(GL_SHADER_STORAGE_BUFFER, ITEMS * sizeof(uint32_t), NULL, GL_DYNAMIC_READ);
    glBindBufferBase(GL_SHADER_STORAGE_BUFFER, 0, buffer); glUseProgram(program);
    glDispatchCompute(ITEMS / 64, 1, 1);
    glMemoryBarrier(GL_BUFFER_UPDATE_BARRIER_BIT | GL_SHADER_STORAGE_BARRIER_BIT);
    uint32_t *values = glMapBufferRange(GL_SHADER_STORAGE_BUFFER, 0, ITEMS * sizeof(uint32_t), GL_MAP_READ_BIT);
    if (!values) die("Compute result map failed");
    for (uint32_t i = 0; i < ITEMS; i++) {
        uint32_t x = i;
        for (uint32_t j = 0; j < ROUNDS; j++) x = (x ^ ((x << 13) | (x >> 19))) * 1664525u + 1013904223u + j;
        if (values[i] != x) { fprintf(stderr, "Mismatch at %u: got %#x expected %#x\n", i, values[i], x); return 1; }
    }
    if (!glUnmapBuffer(GL_SHADER_STORAGE_BUFFER) || glGetError() != GL_NO_ERROR) die("Compute GL error");
    printf("PASS: %u compute results, %u rounds each\n", ITEMS, ROUNDS);
    glDeleteBuffers(1, &buffer); glDeleteProgram(program); glDeleteShader(cs);
    eglMakeCurrent(dpy, EGL_NO_SURFACE, EGL_NO_SURFACE, EGL_NO_CONTEXT); eglDestroyContext(dpy, ctx); eglTerminate(dpy);
    return 0;
}
