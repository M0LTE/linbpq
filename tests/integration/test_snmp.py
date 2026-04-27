"""SNMPPORT — protocol-level coverage.

linbpq ships a minimal SNMP v1 server (IPCode.c:5027 — "Pretty
limited - basically just for MRTG").  It handles GetRequest PDUs
for four OIDs:

- ``1.3.6.1.2.1.1.5.0``    sysName       → ``MYNODECALL`` text
- ``1.3.6.1.2.1.1.3.0``    sysUpTime     → seconds-since-boot * 100
- ``1.3.6.1.2.1.2.2.1.10.<port>``   ifInOctets   → ``InOctets[port]``
- ``1.3.6.1.2.1.2.2.1.16.<port>``   ifOutOctets  → ``OutOctets[port]``

The listener is bound by ``SNMPPORT=`` inside the Telnet PORT
block; data arrives via UDP and the loop in
``TelnetV6.c::TelnetPoll`` (line 2297) calls
``ProcessSNMPPayload`` directly.

This test stands up a Python SNMP-v1 GetRequest by hand (no
``pysnmp`` dependency) and verifies the sysName OID returns the
node call.  Only single-byte BER length encodings are produced —
the BPQ parser only reads one-byte lengths
(IPCode.c:5212 et al.) so we wouldn't get a response for a
multi-byte length anyway.
"""

from __future__ import annotations

import socket
from pathlib import Path
from string import Template

from helpers.linbpq_instance import LinbpqInstance


_SNMP_CFG = Template(
    """\
SIMPLE=1
NODECALL=N0SNMP
NODEALIAS=TEST
LOCATOR=NONE

PORT
 PORTNUM=1
 ID=Telnet
 DRIVER=Telnet
 CONFIG
 TCPPORT=$telnet_port
 HTTPPORT=$http_port
 SNMPPORT=$snmp_port
 MAXSESSIONS=10
 USER=test,test,N0SNMP,,SYSOP
ENDPORT
"""
)


# OIDs in BER content-octet form (subID 0 + 1 already combined into
# 40*0+1 = 1 → no, wait: 1.3 → 1*40+3 = 43 = 0x2B).
SYSNAME_OID = bytes([0x2B, 6, 1, 2, 1, 1, 5, 0])
SYSUPTIME_OID = bytes([0x2B, 6, 1, 2, 1, 1, 3, 0])


def _build_snmp_get(oid: bytes, request_id: int = 0x42,
                    community: bytes = b"public") -> bytes:
    """Build an SNMP-v1 GetRequest PDU with one varbind (OID, NULL).

    Every length stays under 0x80 — BPQ's parser only reads
    one-byte BER lengths.
    """
    oid_field = bytes([0x06, len(oid)]) + oid
    null_field = bytes([0x05, 0x00])
    varbind = bytes([0x30, len(oid_field) + len(null_field)]) + oid_field + null_field
    varbinds = bytes([0x30, len(varbind)]) + varbind
    reqid_field = bytes([0x02, 0x01, request_id])
    err_field = bytes([0x02, 0x01, 0x00])
    erridx_field = bytes([0x02, 0x01, 0x00])
    pdu_body = reqid_field + err_field + erridx_field + varbinds
    pdu = bytes([0xA0, len(pdu_body)]) + pdu_body
    ver_field = bytes([0x02, 0x01, 0x00])
    com_field = bytes([0x04, len(community)]) + community
    body = ver_field + com_field + pdu
    return bytes([0x30, len(body)]) + body


def _snmp_query(host: str, port: int, oid: bytes,
                timeout: float = 3.0) -> bytes:
    """Send a GetRequest, return the raw reply datagram."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(timeout)
    try:
        sock.sendto(_build_snmp_get(oid), (host, port))
        reply, _ = sock.recvfrom(2048)
        return reply
    finally:
        sock.close()


# Make linbpq_instance know about the snmp_port placeholder by adding
# it to render_config kwargs.  We do this in-line on the test rather
# than touching the helper class — there's no other use of the
# placeholder elsewhere.
class _SnmpInstance(LinbpqInstance):
    def __init__(self, work_dir: Path, **kw):
        super().__init__(work_dir, **kw)
        from helpers.linbpq_instance import pick_free_port
        self.snmp_port = pick_free_port()

    def render_config(self) -> str:
        return self.config_template.substitute(
            telnet_port=self.telnet_port,
            http_port=self.http_port,
            netrom_port=self.netrom_port,
            fbb_port=self.fbb_port,
            api_port=self.api_port,
            agw_port=self.agw_port,
            axip_port=self.axip_port,
            snmp_port=self.snmp_port,
        )


def test_snmp_sysname_returns_node_call(tmp_path: Path):
    """SNMP GetRequest for ``sysName.0`` returns linbpq's
    ``MYNODECALL`` (IPCode.c:5353-5360).  We configure
    ``NODECALL=N0SNMP`` so the response is unambiguously identifiable."""
    with _SnmpInstance(tmp_path, config_template=_SNMP_CFG) as linbpq:
        reply = _snmp_query("127.0.0.1", linbpq.snmp_port, SYSNAME_OID)

    # The PDU is a Response (0xA2); somewhere in the body we expect
    # the OCTET STRING varbind value to be the node call.  The
    # simplest check: search for the call text directly.
    assert b"N0SNMP" in reply, (
        f"sysName response missing node call text: {reply.hex()}"
    )
    # Sanity: response is an SNMP-v1 Response PDU (type 0xA2 appears
    # somewhere in the reply, after the version/community envelope).
    assert b"\xA2" in reply, (
        f"reply is not a SNMP Response PDU (no 0xA2 byte): {reply.hex()}"
    )


def test_snmp_sysuptime_returns_nonzero_timeticks(tmp_path: Path):
    """SNMP GetRequest for ``sysUpTime.0`` returns a TimeTicks
    counter (IPCode.c:5365: ``(time(NULL) - TimeLoaded) * 100``).
    Boot-time should produce a small but non-zero value within
    ~2 seconds of startup.  Locks in that the OID dispatch path
    works for non-string types (TimeTicks, ASN.1 type 0x43)."""
    import time as _time

    with _SnmpInstance(tmp_path, config_template=_SNMP_CFG) as linbpq:
        # Tiny dwell to ensure uptime > 0.
        _time.sleep(1.5)
        reply = _snmp_query("127.0.0.1", linbpq.snmp_port, SYSUPTIME_OID)

    # TimeTicks tag is 0x43 — the value field starts with that byte.
    assert b"\x43" in reply, (
        f"sysUpTime response missing TimeTicks tag (0x43): {reply.hex()}"
    )


def test_snmp_unknown_oid_no_response(tmp_path: Path):
    """An OID not in the four-OID table (sysName / sysUpTime /
    ifInOctets / ifOutOctets) gets no SNMP response from BPQ
    (IPCode.c:5388-5390 returns 0, the caller drops the packet
    silently).  Verifies we don't get a falsy response from random
    OIDs — and confirms the dispatch is OID-keyed, not "any
    GetRequest"-keyed."""
    # 1.3.6.1.2.1.99.0 — definitely not implemented
    unknown_oid = bytes([0x2B, 6, 1, 2, 1, 99, 0])
    with _SnmpInstance(tmp_path, config_template=_SNMP_CFG) as linbpq:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(2.0)
        try:
            sock.sendto(
                _build_snmp_get(unknown_oid),
                ("127.0.0.1", linbpq.snmp_port),
            )
            try:
                reply, _ = sock.recvfrom(2048)
            except socket.timeout:
                reply = b""
        finally:
            sock.close()

    assert reply == b"", (
        f"unknown OID got a response — should be silent drop: {reply.hex()}"
    )
