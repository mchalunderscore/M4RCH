# Graphical sudo authentication

This package adapts the sudo-to-polkit mechanism from [Dozor](https://github.com/Toxblh/dozor), upstream commit `228bc235c800f8e29541273d373d19bb73fb3654`. Its action policy is the upstream policy with the terminal icon removed, allowing Noctalia's shield fallback. Noctalia remains the polkit agent; the Dozor agent is not installed. Upstream's hook writes a user-readable command context for its own agent, which Noctalia does not use; this implementation writes no context file.

The statically linked helper must run as root via `pam_exec.so seteuid`: a helper running as the invoking user could be tampered with before PAM uses its exit status. It checks the sudo process and invoking user's process, and invokes `pkcheck` with an empty, controlled environment. The policy authenticates the invoking user, so this integration is unsuitable for sudoers configurations that expect `rootpw`, `targetpw` or `runaspw`, or for polkit rules that grant this action without authentication. Review policy changes accordingly. Sudo's authorization and account checks still apply, and normal sudo timestamp caching and NOPASSWD rules can bypass a fresh prompt.

On this machine `/etc/pam.d/sudo` starts with:

```
auth sufficient pam_exec.so quiet seteuid /usr/libexec/dozor-sudo-m4rch
```

The pre-existing fingerprint and password stack follows. If polkit cannot authorize, it falls through to that stack. A canceled dialog also falls through, so cancellation does not by itself cancel sudo. A GUI request may wait up to 120 seconds before fallback.

The prior sudo PAM file is saved at `/var/lib/m4rch/dozor-sudo-20261101/sudo.before`. To disable the bridge, restore that file with `run0 install -m 0644 /var/lib/m4rch/dozor-sudo-20261101/sudo.before /etc/pam.d/sudo`; then the package can be removed with pacman. Restore the PAM file **before** removing the package. The policy does not request retained polkit authorization. The GUI path, fingerprint and shield icon were confirmed through real sudo on 1 November 2026; GUI cancellation, password fallback, SSH, and noninteractive sudo have not been independently tested with this bridge.
