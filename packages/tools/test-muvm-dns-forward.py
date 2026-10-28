#!/usr/bin/env python3
"""Test wire forwarding, UDP/TCP, host loopback, and IPv6 scope handling."""
import importlib.util
import socket
import struct
import tempfile
import threading
from pathlib import Path

root = Path(__file__).resolve().parents[2]
def load(name):
    spec = importlib.util.spec_from_file_location(name.replace('-', '_'), root / 'packages/muvm-m4rch' / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
host, guest = load('muvm-dns-forward'), load('muvm-dns-proxy')
original_servers = host.servers
request = bytes.fromhex('1234010000010000000000000161076578616d706c650000010001')
response = request[:2] + b'\x81\x80' + request[4:]
with tempfile.TemporaryDirectory() as tmp:
    resolv = Path(tmp) / 'resolv.conf'
    resolv.write_text('nameserver 127.0.0.53\nnameserver fe80::1234%lo\nnameserver ::1\n')
    endpoints = host.servers(str(resolv))
    assert endpoints[0] == (socket.AF_INET, ('127.0.0.53', 53))
    assert endpoints[1][1][3] == socket.if_nametoindex('lo')
    assert endpoints[2] == (socket.AF_INET6, ('::1', 53, 0, 0))
    udp = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
    udp.bind(('::1', 0))
    tcp = socket.socket(socket.AF_INET6)
    tcp.bind(('::1', 0))
    tcp.listen()
    def answer_udp():
        packet, sender = udp.recvfrom(65535)
        assert packet == request
        udp.sendto(response, sender)
    def answer_tcp():
        conn, _ = tcp.accept()
        with conn:
            length = struct.unpack('!H', host.recv_exact(conn, 2))[0]
            assert host.recv_exact(conn, length) == request
            conn.sendall(struct.pack('!H', len(response)) + response)
    host.servers = lambda path='/etc/resolv.conf': [(socket.AF_INET6, ('::1', udp.getsockname()[1], 0, 0))]
    thread = threading.Thread(target=answer_udp); thread.start()
    assert host.query(request) == response
    thread.join(2)
    host.servers = lambda path='/etc/resolv.conf': [(socket.AF_INET6, ('::1', tcp.getsockname()[1], 0, 0))]
    thread = threading.Thread(target=answer_tcp); thread.start()
    assert host.query(request, True) == response
    thread.join(2)
    udp.close(); tcp.close()
    loopback = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    loopback.bind(('127.0.0.53', 0))
    def loopback_answer():
        packet, sender = loopback.recvfrom(65535)
        assert packet == request
        loopback.sendto(response, sender)
    host.servers = lambda path='/etc/resolv.conf': [(socket.AF_INET, ('127.0.0.53', loopback.getsockname()[1]))]
    thread = threading.Thread(target=loopback_answer, daemon=True); thread.start()
    assert host.query(request) == response
    thread.join(2)
    loopback.close()
    # Exercise a real link-local address and interface scope when available.
    for row in Path('/proc/net/if_inet6').read_text().splitlines():
        address, index, _, scope, _, interface = row.split()
        if scope != '20' or interface == 'lo':
            continue
        import ipaddress
        scoped = str(ipaddress.IPv6Address(int(address, 16)))
        listener = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
        try:
            listener.bind((scoped, 0, 0, int(index, 16)))
            resolv.write_text(f'nameserver {scoped}%{interface}\n')
            family, endpoint = original_servers(str(resolv))[0]
            host.servers = lambda path='/etc/resolv.conf': [(family, (endpoint[0], listener.getsockname()[1], 0, endpoint[3]))]
            def scoped_answer():
                packet, sender = listener.recvfrom(65535)
                assert packet == request
                listener.sendto(response, sender)
            thread = threading.Thread(target=scoped_answer, daemon=True); thread.start()
            assert host.query(request) == response
            thread.join(2)
            print('PASS: DNS through a real interface-scoped IPv6 socket')
            break
        finally:
            listener.close()
    host.servers = lambda path='/etc/resolv.conf': []
    assert host.query(request)[3] & 15 == 2
print('PASS: host loopback and scoped IPv6 parsing, UDP and TCP forwarding, DNS failure response')
