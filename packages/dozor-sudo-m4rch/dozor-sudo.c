/* Root-owned PAM bridge based on Dozor's dozor-sudo.sh (GPL-3.0-or-later).
 * No command context is written: the Noctalia agent does not consume it.
 */
#define _GNU_SOURCE
#include <errno.h>
#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <unistd.h>

static int proc_info(pid_t pid, pid_t *parent, unsigned long long *start)
{
    char path[64], buf[4096], *p, *end;
    FILE *f;
    snprintf(path, sizeof(path), "/proc/%ld/stat", (long)pid);
    if (!(f = fopen(path, "re"))) return -1;
    if (!fgets(buf, sizeof(buf), f)) { fclose(f); return -1; }
    fclose(f);
    p = strrchr(buf, ')');
    if (!p || p[1] != ' ') return -1;
    p += 2;
    for (int field = 3; field <= 22; field++) {
        while (*p == ' ') p++;
        if (!*p) return -1;
        end = p;
        while (*end && *end != ' ' && *end != '\n') end++;
        if (field == 4 || field == 22) {
            char save = *end;
            *end = 0;
            errno = 0;
            char *tail;
            unsigned long long n = strtoull(p, &tail, 10);
            if (errno || *tail || n == 0) return -1;
            if (field == 4) { if (n > INT_MAX) return -1; *parent = (pid_t)n; }
            else *start = n;
            *end = save;
        }
        p = end;
    }
    return 0;
}

int main(void)
{
    char path[64], exe[PATH_MAX], subject[128];
    pid_t sudo_pid = getppid(), caller, ignored;
    unsigned long long ignored_start, start;
    struct stat caller_dir;
    unsigned int uid, effective;
    FILE *f;
    char line[512];
    int found = 0;

    /* pam_exec must use seteuid; otherwise an unprivileged user can tamper
       with the helper whose exit status sudo treats as authentication. */
    if (geteuid() != 0 || sudo_pid <= 1) return 1;
    snprintf(path, sizeof(path), "/proc/%ld/exe", (long)sudo_pid);
    ssize_t n = readlink(path, exe, sizeof(exe) - 1);
    if (n < 0 || n >= (ssize_t)sizeof(exe) - 1) return 1;
    exe[n] = 0;
    if (strcmp(exe, "/usr/bin/sudo") != 0) return 1;
    snprintf(path, sizeof(path), "/proc/%ld/status", (long)sudo_pid);
    if (!(f = fopen(path, "re"))) return 1;
    while (fgets(line, sizeof(line), f)) {
        if (sscanf(line, "Uid: %u %u", &uid, &effective) == 2) { found = 1; break; }
    }
    fclose(f);
    if (!found || uid == 0 || effective != 0) return 1;
    if (proc_info(sudo_pid, &caller, &ignored_start) || caller <= 1) return 1;
    snprintf(path, sizeof(path), "/proc/%ld", (long)caller);
    if (stat(path, &caller_dir) || caller_dir.st_uid != uid) return 1;
    if (proc_info(caller, &ignored, &start)) return 1;
    snprintf(path, sizeof(path), "/run/user/%u/bus", uid);
    struct stat bus;
    if (lstat(path, &bus) || !S_ISSOCK(bus.st_mode) || bus.st_uid != uid) return 1;
    snprintf(subject, sizeof(subject), "%ld,%llu,%u", (long)caller, start, uid);

    /* Do not pass PAM's potentially user-influenced environment to pkcheck. */
    char *const args[] = {"/usr/bin/timeout", "120", "/usr/bin/pkcheck",
        "--action-id", "ru.toxblh.dozor.sudo", "--process", subject,
        "--allow-user-interaction", NULL};
    char *const env[] = {"PATH=/usr/bin", "LC_ALL=C", NULL};
    execve(args[0], args, env);
    return 1;
}
