#!/usr/bin/python3
"""Forward raw DNS requests using the host's current resolv.conf."""
import concurrent.futures
import ipaddress
import os
from pathlib import Path
import socket
import struct
import threading

TIMEOUT = 1.5
MAX_DNS = 65535


def recv_exact(sock, size):
    data = bytearray()
    while len(data) < size:
        part = sock.recv(size - len(data))
        if not part:
            raise EOFError('short DNS stream')
        data.extend(part)
    return bytes(data)


def servers(path='/etc/resolv.conf'):
    try:
        lines = Path(path).read_text().splitlines()
    except OSError:
        return []
    result = []
    for line in lines:
        fields = line.split('#', 1)[0].split(';', 1)[0].split()
        if len(fields) < 2 or fields[0] != 'nameserver':
            continue
        address, _, zone = fields[1].partition('%')
        try:
            ip = ipaddress.ip_address(address)
            if ip.version == 4 and zone:
                continue
            scope = int(zone) if zone.isdigit() else socket.if_nametoindex(zone) if zone else 0
            result.append((socket.AF_INET if ip.version == 4 else socket.AF_INET6,
                           (address, 53) if ip.version == 4 else (address, 53, 0, scope)))
        except (ValueError, OSError):
            continue
    return result


def query(payload, tcp=False, resolver='/etc/resolv.conf'):
    for family, endpoint in servers(resolver):
        try:
            with socket.socket(family, socket.SOCK_STREAM if tcp else socket.SOCK_DGRAM) as upstream:
                upstream.settimeout(TIMEOUT)
                upstream.connect(endpoint)
                if tcp:
                    upstream.sendall(struct.pack('!H', len(payload)) + payload)
                    response = recv_exact(upstream, struct.unpack('!H', recv_exact(upstream, 2))[0])
                else:
                    upstream.send(payload)
                    response = upstream.recv(MAX_DNS)
                if len(response) >= 12 and response[:2] == payload[:2]:
                    return response
        except (OSError, EOFError, struct.error):
            continue
    if len(payload) < 12:
        return b''
    # Preserve transaction ID, opcode, RD, question; return SERVFAIL.
    flags = (int.from_bytes(payload[2:4], 'big') & 0x7900) | 0x8002
    return payload[:2] + flags.to_bytes(2, 'big') + payload[4:6] + b'\0' * 4 + payload[10:]


def handle(client):
    with client:
        client.settimeout(5)
        try:
            header = recv_exact(client, 3)
            size = struct.unpack('!H', header[1:])[0]
            if header[0] == 2 and size == 0:
                client.sendall(b'\x00\x02ok')
                return
            if size < 12:
                return
            response = query(recv_exact(client, size), header[0] == 1)
            client.sendall(struct.pack('!H', len(response)) + response)
        except (OSError, EOFError, struct.error):
            return


def main():
    runtime = Path(os.environ['XDG_RUNTIME_DIR'])
    portfile = runtime / 'muvm-dns-forward.port'
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0))
        listener.listen(64)
        tmp = runtime / ('muvm-dns-forward.' + str(os.getpid()))
        tmp.write_text(str(listener.getsockname()[1]))
        os.replace(tmp, portfile)
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=32) as pool:
                while True:
                    client, _ = listener.accept()
                    pool.submit(handle, client)
        finally:
            portfile.unlink(missing_ok=True)

if __name__ == '__main__':
    main()
