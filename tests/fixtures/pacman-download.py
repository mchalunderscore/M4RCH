#!/usr/bin/python3
"""Exercise the real pacman downloader offline inside a disposable QEMU root."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import argparse
import subprocess
import tempfile
import threading


def checked(command, timeout=90):
    result = subprocess.run(command, check=False, text=True, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, timeout=timeout)
    print(result.stdout, end="", flush=True)
    result.check_returncode()
    return result.stdout


def validate_configuration(configuration, remote_siglevel, download_user):
    active = [line.split("#", 1)[0].strip() for line in configuration.splitlines()]
    if any(line.split("=", 1)[0].strip().startswith("DisableSandbox") for line in active):
        raise ValueError("Smoke requires pacman's default sandbox")
    if download_user.strip() != "alpm":
        raise ValueError("Smoke requires pacman's unprivileged alpm downloader")
    levels = {level.removeprefix("Package") for level in remote_siglevel.split()
              if not level.startswith("Database")}
    if not {"Required", "TrustedOnly"}.issubset(levels) or levels & {"Optional", "Never", "TrustAll"}:
        raise ValueError("Smoke requires trusted signatures for remote packages")


def package_server(files, requested):
    # Only these immutable test inputs can be fetched. No network interface
    # outside the guest loopback is used, and directory traversal cannot expose
    # other files from the root filesystem.
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            data = files.get(self.path)
            if data is None:
                self.send_error(404)
                return
            requested.add(self.path)
            self.send_response(200)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    return ThreadingHTTPServer(("127.0.0.1", 0), Handler)


def sync_configuration(resolved, port):
    """Keep real global policy and paths; replace only the remote repositories."""
    options = []
    in_options = False
    for line in resolved.splitlines():
        if line.strip().startswith("["):
            if line.strip() != "[options]":
                break
            in_options = True
        if in_options:
            options.append(line)
    if not in_options:
        raise ValueError("Resolved pacman configuration has no options section")
    return "\n".join(options) + ("\n[arch-m4-smoke]\n"
                                f"Server = http://127.0.0.1:{port}\n")


def sync_package(package, signature, user):
    # repo-add embeds the package's existing trusted signature in its database.
    # DatabaseOptional is inherited from the installed pacman policy; this
    # ephemeral fixture has no signing key and never changes the trusted keyring.
    with tempfile.TemporaryDirectory(prefix="arch-m4-sync-", dir="/var/cache") as temporary:
        work = Path(temporary)
        work.chmod(0o755)
        database = work / "arch-m4-smoke.db.tar.gz"
        checked(["/usr/bin/repo-add", str(database), str(package)])
        files = {"/arch-m4-smoke.db": database.read_bytes(),
                 "/" + package.name: package.read_bytes(),
                 "/" + signature.name: signature.read_bytes()}
        requested = set()
        with package_server(files, requested) as server:
            worker = threading.Thread(target=server.serve_forever, daemon=True)
            worker.start()
            try:
                configuration = work / "pacman.conf"
                configuration.write_text(sync_configuration(
                    checked(["/usr/bin/pacman-conf"]), server.server_port))
                configuration.chmod(0o644)
                cache = work / "cache"
                cache.mkdir(mode=0o755)
                # Use Alice's real sudo/paru route and the real pacman DBPath.
                # -yy forces the /var/lib/pacman/sync/download-* path on both
                # boots; -u tests upgrade resolution, and the explicit target
                # forces reinstall/download even when the version is unchanged.
                checked(["/usr/bin/runuser", "-u", user, "--", "/usr/bin/paru",
                         "--repo", "--config", str(configuration), "--cachedir", str(cache),
                         "--noconfirm", "-Syyu", "default-cursors"], timeout=180)
            finally:
                server.shutdown()
                worker.join()
        if not {"/arch-m4-smoke.db", "/" + package.name}.issubset(requested):
            raise ValueError("Paru did not download both the sync database and package")
        checked(["/usr/bin/pacman", "-Q", "default-cursors"])
        print("ARCHM4_PACMAN_SYNC_PASS", flush=True)


def main(sync_as=None):
    if Path("/dev/kvm").exists():
        raise ValueError("The experimental M4 kernel must not expose unusable KVM")
    remote_siglevel = checked(["/usr/bin/pacman-conf", "RemoteFileSigLevel"])
    if not remote_siglevel.strip():
        # An unset override inherits the global signature policy.
        remote_siglevel = checked(["/usr/bin/pacman-conf", "SigLevel"])
    validate_configuration(
        Path("/etc/pacman.conf").read_text(),
        remote_siglevel,
        checked(["/usr/bin/pacman-conf", "DownloadUser"]),
    )
    # This follows the documented first-boot initialization. The builder's
    # private key is intentionally absent from the installed root image.
    checked(["/usr/bin/pacman-key", "--init"])
    checked(["/usr/bin/pacman-key", "--populate", "archlinuxarm"])
    directory = Path("/usr/share/arch-m4-smoke-package")
    packages = [p for p in directory.iterdir() if not p.name.endswith(".sig")]
    if len(packages) != 1:
        raise ValueError("Smoke package fixture is ambiguous")
    package = packages[0]
    signature = package.with_name(package.name + ".sig")
    files = {"/" + file.name: file.read_bytes() for file in (package, signature)}
    requested = set()
    with package_server(files, requested) as server:
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            # A new cache on each boot forces HTTP download, sandbox setup and
            # signature verification even though the package is a reinstall.
            with tempfile.TemporaryDirectory(prefix="arch-m4-smoke-", dir="/var/cache") as cache:
                Path(cache).chmod(0o755)
                url = f"http://127.0.0.1:{server.server_port}/{package.name}"
                checked(["/usr/bin/pacman", "-U", "--noconfirm", "--cachedir", cache, url])
        finally:
            server.shutdown()
            worker.join()
    if requested != set(files):
        raise ValueError("Pacman did not download both the package and its required signature")
    checked(["/usr/bin/pacman", "-Q", "default-cursors"])
    if sync_as is not None:
        sync_package(package, signature, sync_as)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sync-as", metavar="USER",
                        help="also refresh a loopback repository and install through paru as USER")
    main(parser.parse_args().sync_as)
