#!/usr/bin/python3
"""Expose the host DNS forwarder on guest loopback, for UDP and TCP."""
import concurrent.futures
import os
from pathlib import Path
import socket
import struct
import threading

GATEWAY = '169.254.2.2'
MAX_DNS = 65535

def recv_exact(sock, size):
    data = bytearray()
    while len(data) < size:
        part = sock.recv(size - len(data))
        if not part:
            raise EOFError()
        data.extend(part)
    return bytes(data)

def forward(payload, tcp):
    try:
        port = int(Path('/run/muvm-host/run/user/' + HOST_UID + '/muvm-dns-forward.port').read_text())
        with socket.create_connection((GATEWAY, port), timeout=5) as host:
            host.sendall(bytes([tcp]) + struct.pack('!H', len(payload)) + payload)
            return recv_exact(host, struct.unpack('!H', recv_exact(host, 2))[0])
    except (OSError, ValueError, EOFError, struct.error):
        if len(payload) < 12:
            return b''
        flags = (int.from_bytes(payload[2:4], 'big') & 0x7900) | 0x8002
        return payload[:2] + flags.to_bytes(2, 'big') + payload[4:6] + b'\0' * 4 + payload[10:]

def tcp_client(client):
    with client:
        client.settimeout(10)
        try:
            while True:
                size = struct.unpack('!H', recv_exact(client, 2))[0]
                if size < 12:
                    return
                response = forward(recv_exact(client, size), True)
                client.sendall(struct.pack('!H', len(response)) + response)
        except (OSError, EOFError, struct.error):
            return

def udp_query(sock, payload, addr):
    response = forward(payload, False)
    if response:
        try:
            sock.sendto(response, addr)
        except OSError:
            pass

def main():
    # The VM's root UID differs from the host user; get the user id from the
    # owner of the shared /home directory via the value passed at startup.
    global HOST_UID
    HOST_UID = os.environ['MUVM_DNS_HOST_UID']
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as udp, socket.socket() as tcp:
        udp.bind(('127.0.0.1', 53))
        tcp.bind(('127.0.0.1', 53))
        tcp.listen(64)
        ready = Path('/run/muvm-dns-proxy.ready')
        def heartbeat():
            import time
            while True:
                try:
                    port = int(Path('/run/muvm-host/run/user/' + HOST_UID + '/muvm-dns-forward.port').read_text())
                    with socket.create_connection((GATEWAY, port), timeout=1) as host:
                        host.sendall(b'\x02\x00\x00')
                        if recv_exact(host, 4) != b'\x00\x02ok':
                            raise OSError('bad handshake')
                    ready.write_text(str(os.getpid()))
                except (OSError, EOFError, ValueError):
                    ready.unlink(missing_ok=True)
                time.sleep(2)
        threading.Thread(target=heartbeat, daemon=True).start()
        with concurrent.futures.ThreadPoolExecutor(max_workers=32) as pool:
            def accept_tcp():
                while True:
                    client, _ = tcp.accept()
                    pool.submit(tcp_client, client)
            threading.Thread(target=accept_tcp, daemon=True).start()
            while True:
                payload, addr = udp.recvfrom(MAX_DNS)
                pool.submit(udp_query, udp, payload, addr)

if __name__ == '__main__':
    main()
