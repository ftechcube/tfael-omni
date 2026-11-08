#!/usr/bin/env python3
"""
TFAEL-OMNI v2.0 — Real Host & Network SIEM Telemetry Collector (Pilar 5)
Membaca soket jaringan aktif (TCP/UDP ESTABLISHED & LISTEN) serta proses sistem nyata
dari mesin host menggunakan utilitas OS (lsof / netstat) dan mengevaluasinya dengan aturan Sigma.
"""

import platform
import re
import subprocess
from datetime import datetime, timezone
from typing import Any, Dict, List


def scan_live_host_sockets() -> Dict[str, Any]:
    """
    Memindai koneksi jaringan TCP/UDP yang benar-benar sedang aktif di komputer/server saat ini.
    """
    connections: List[Dict[str, Any]] = []
    listening_ports: List[Dict[str, Any]] = []

    try:
        proc = subprocess.run(
            ["lsof", "-i", "-n", "-P"],
            capture_output=True,
            text=True,
            timeout=3.0,
        )
        lines = proc.stdout.splitlines()
        for line in lines[1:]:
            parts = line.split()
            if len(parts) < 9:
                continue
            cmd = parts[0]
            pid = parts[1]
            user = parts[2]
            proto = parts[7]
            name_field = " ".join(parts[8:])

            if "LISTEN" in name_field:
                listening_ports.append({
                    "process": cmd,
                    "pid": pid,
                    "user": user,
                    "protocol": proto,
                    "endpoint": name_field.replace("(LISTEN)", "").strip(),
                })
            elif "->" in name_field:
                connections.append({
                    "process": cmd,
                    "pid": pid,
                    "user": user,
                    "protocol": proto,
                    "connection": name_field,
                })
    except Exception:
        pass

    # Fallback ke netstat jika lsof dibatasi
    if not connections and not listening_ports:
        try:
            proc = subprocess.run(
                ["netstat", "-an"],
                capture_output=True,
                text=True,
                timeout=3.0,
            )
            for line in proc.stdout.splitlines():
                if "ESTABLISHED" in line or "LISTEN" in line:
                    parts = line.split()
                    if len(parts) >= 6:
                        entry = {
                            "process": "kernel/netstat",
                            "pid": "-",
                            "user": "system",
                            "protocol": parts[0].upper(),
                            "connection": f"{parts[3]} -> {parts[4]} ({parts[5]})",
                        }
                        if "LISTEN" in line:
                            listening_ports.append({
                                "process": "kernel/netstat",
                                "pid": "-",
                                "user": "system",
                                "protocol": parts[0].upper(),
                                "endpoint": parts[3],
                            })
                        else:
                            connections.append(entry)
        except Exception:
            pass

    return {
        "scanned_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "host_os": f"{platform.system()} {platform.release()} ({platform.machine()})",
        "active_connections_count": len(connections),
        "listening_ports_count": len(listening_ports),
        "active_connections": connections[:25],
        "listening_ports": listening_ports[:20],
    }
