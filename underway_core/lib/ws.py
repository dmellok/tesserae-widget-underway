"""A small WebSocket client on the standard library alone (RFC 6455): the
handshake, masked text frames out, text and binary frames in with pings
answered and fragments joined. Enough for a stream such as aisstream.io;
not a general client. Loaded by path."""

from __future__ import annotations

import base64
import os
import socket
import ssl
import struct
import urllib.parse

OP_CONT, OP_TEXT, OP_BINARY, OP_CLOSE, OP_PING, OP_PONG = 0, 1, 2, 8, 9, 10
MAX_FRAME = 8_000_000


class WebSocketError(Exception):
    pass


class WebSocket:
    def __init__(
        self, url: str, *, timeout: float = 10.0, ua: str = "", origin: str = ""
    ) -> None:
        u = urllib.parse.urlsplit(url)
        if u.scheme not in ("ws", "wss"):
            raise WebSocketError(f"not a websocket url: {url}")
        secure = u.scheme == "wss"
        host = u.hostname or ""
        port = u.port or (443 if secure else 80)
        path = (u.path or "/") + (f"?{u.query}" if u.query else "")
        raw = socket.create_connection((host, port), timeout=timeout)
        self.sock: socket.socket = (
            ssl.create_default_context().wrap_socket(raw, server_hostname=host)
            if secure
            else raw
        )
        self.sock.settimeout(timeout)
        key = base64.b64encode(os.urandom(16)).decode()
        lines = [
            f"GET {path} HTTP/1.1",
            f"Host: {host}" + ("" if port in (80, 443) else f":{port}"),
            "Upgrade: websocket",
            "Connection: Upgrade",
            f"Sec-WebSocket-Key: {key}",
            "Sec-WebSocket-Version: 13",
        ]
        if ua:
            lines.append(f"User-Agent: {ua}")
        if origin:
            lines.append(f"Origin: {origin}")
        self.sock.sendall(("\r\n".join(lines) + "\r\n\r\n").encode())
        head = b""
        while b"\r\n\r\n" not in head:
            chunk = self.sock.recv(4096)
            if not chunk:
                raise WebSocketError("the server closed the handshake")
            head += chunk
            if len(head) > 65536:
                raise WebSocketError("handshake too long")
        header, _, rest = head.partition(b"\r\n\r\n")
        status = header.split(b"\r\n", 1)[0].decode("latin-1", "replace")
        if " 101 " not in status:
            raise WebSocketError(f"handshake refused: {status.strip()[:120]}")
        self._buf = rest
        self._partial: list[bytes] = []
        self._partial_op = 0
        self.closed = False

    # -- out ----------------------------------------------------------------

    def send_text(self, text: str) -> None:
        self._send(OP_TEXT, text.encode("utf-8"))

    def _send(self, op: int, payload: bytes) -> None:
        mask = os.urandom(4)
        n = len(payload)
        head = bytes([0x80 | op])
        if n < 126:
            head += bytes([0x80 | n])
        elif n < 65536:
            head += bytes([0x80 | 126]) + struct.pack("!H", n)
        else:
            head += bytes([0x80 | 127]) + struct.pack("!Q", n)
        masked = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
        self.sock.sendall(head + mask + masked)

    def close(self) -> None:
        if not self.closed:
            self.closed = True
            try:
                self._send(OP_CLOSE, struct.pack("!H", 1000))
            except OSError:
                pass
            try:
                self.sock.close()
            except OSError:
                pass

    # -- in -----------------------------------------------------------------

    def _read(self, n: int) -> bytes:
        while len(self._buf) < n:
            chunk = self.sock.recv(max(4096, n - len(self._buf)))
            if not chunk:
                raise WebSocketError("the connection closed")
            self._buf += chunk
        out, self._buf = self._buf[:n], self._buf[n:]
        return out

    def recv(self) -> tuple[int, bytes] | None:
        """The next whole message as (opcode, payload); None once the server
        has closed. Pings are answered here. Raises socket.timeout when
        nothing arrives within the timeout."""
        while True:
            b1, b2 = self._read(2)
            fin, op = b1 & 0x80, b1 & 0x0F
            masked, n = b2 & 0x80, b2 & 0x7F
            if n == 126:
                n = struct.unpack("!H", self._read(2))[0]
            elif n == 127:
                n = struct.unpack("!Q", self._read(8))[0]
            if n > MAX_FRAME:
                raise WebSocketError("frame too large")
            mask = self._read(4) if masked else b""
            payload = self._read(n)
            if mask:
                payload = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
            if op == OP_PING:
                try:
                    self._send(OP_PONG, payload)
                except OSError:
                    pass
                continue
            if op == OP_PONG:
                continue
            if op == OP_CLOSE:
                self.closed = True
                return None
            if op == OP_CONT:
                self._partial.append(payload)
                if not fin:
                    continue
                whole = b"".join(self._partial)
                op, self._partial = self._partial_op, []
                return op, whole
            if not fin:
                self._partial, self._partial_op = [payload], op
                continue
            return op, payload
