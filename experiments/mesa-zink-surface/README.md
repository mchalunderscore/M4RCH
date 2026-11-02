# Wayland surface reuse and Zink

On a J614s M4 Pro using Umbriel, the standalone Wayland/EGL client in this
directory reproduces a Zink failure without Noctalia. It creates a real
xdg-shell surface, renders through EGL/GLES, unbinds and destroys its EGL
surface and native window, destroys the Wayland objects, and synchronizes
with the compositor. It repeats with the same EGL display and context, logging
whether a new `wl_surface` client pointer reuses a previously freed address.

`sh run.sh 15` runs the single-drawable case using the selected Mesa libraries.
`sh run.sh 15 shared` additionally creates multiple separate EGL drawables on
the same Wayland surface and recreates one while another remains alive. The
client uses the real compositor and may briefly show small windows. It needs
`wayland-scanner`, `wayland-protocols`, Wayland client/EGL and GLES2 headers,
and a working Wayland session. Select a non-system Mesa build with
`LD_LIBRARY_PATH` and `LIBGL_DRIVERS_PATH` before running the script.

## Evidence, 1 November 2026

- The signed stock Aurora `mesa-aurora` package at Mesa
  `c208afc352e9d4c10ee71c883a369a9079dd7d84` failed five of five runs. The
  new surface reused the first surface's address at iteration 2, followed by
  `wp_linux_drm_syncobj_surface_v1: The surface has been destroyed`.
- The locally patched package completed five of five runs (15 iterations
  each, 13 reused addresses per run).
- A smaller candidate that evicts the cached Wayland target whenever *any*
  drawable is destroyed passed a basic shared-drawable test, but failed once
  a third drawable was created while the second still existed: the compositor
  rejected a second syncobj for the same surface. This demonstrates why the
  patch tracks the last live drawable instead of evicting on every destroy.
- The submission candidate removes diagnostic logging from the installed
  patch. It completed five of five address-reuse runs and five of five
  shared-drawable runs on this GPU. It was built from the pinned Mesa source;
  the eight affected source files are byte-identical to Aurora's `aurora-wip`
  tip `8990cdb219b296b713b41350bcb1f6522ce062fb` as checked on 1 November.

The patch protects cache lookup/refcount and last-reference removal under the
existing lock; short single-process runs do not establish complete threaded
correctness. These tests do not prove every possible EGL or compositor
lifetime. Mesa upstream's GitLab issue/MR pages were unavailable behind an
access challenge, so a matching upstream report cannot be ruled out. Aurora's
GitHub issue and PR searches did not identify a matching surface-lifetime fix.
At the time of those tests, the submission candidate had not replaced the
installed Mesa. The fork-based candidate was installed subsequently; see
[current status](../../docs/status.md).

The signed stock and locally patched
Gallium library SHA-256 values are respectively
`8f969c3da2d0719daed14b9f638be2ca355b7ff7bc0bd43e5ca9d36dc0127a8a` and
`044b9985772dc424226381d05fd8a8f97984ab7e95d072287c95018caad48887`.

The reproducer, candidate patch, results and limitations were submitted to
[Aurora Mesa issue #137](https://github.com/aurora-silicon/mesa/issues/137).
The candidate is also submitted for review as [draft PR #138](https://github.com/aurora-silicon/mesa/pull/138).
