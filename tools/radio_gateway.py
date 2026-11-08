#!/usr/bin/env python3
"""
Jembatan RADIO → server TFAEL-OMNI (Paket Radio, tanpa internet/seluler).

Membaca paket posisi dari penerima radio di pos komando lalu meneruskannya ke
endpoint /api/v2/telemetry/offgrid. Server men-decode & memetakan tiap callsign
sebagai unit tersendiri (biru). Satu mesin ini saja yang butuh link lokal ke
server; agen lapangan cukup memancarkan radio — nol pulsa, nol internet.

Sumber paket (pilih salah satu):
  --source stdin                 baca baris dari stdin (uji / pipa dari tool lain)
  --source file   --path f.log   ikuti file log (mode `tail -f`)
  --source tcp    --host H --port P   sambung ke TCP (mis. keluaran teks TNC/direwolf)
  --source serial --path /dev/ttyUSB0 --baud 9600   baca dari TNC/Meshtastic serial

Format baris otomatis terdeteksi:
  - diawali '{'  → JSON LoRa Meshtastic  (channel LORA_MESH)
  - selain itu   → APRS AX.25/TNC2       (channel APRS_VHF)

Contoh:
  # Uji cepat tanpa hardware:
  echo 'YB0TFL-9>APRS,WIDE1-1:!0610.52S/10649.63E>180/032/A=000145 Patroli' \\
    | python3 tools/radio_gateway.py --server http://localhost:8080 --source stdin

  # APRS via direwolf (keluaran teks TNC2 ke TCP):
  python3 tools/radio_gateway.py --server http://localhost:8080 \\
    --agent-key RAHASIA --source tcp --host 127.0.0.1 --port 8001

  # Meshtastic via serial:
  python3 tools/radio_gateway.py --server http://localhost:8080 \\
    --source serial --path /dev/ttyUSB0 --baud 115200
"""
import argparse
import json
import sys
import time
import urllib.request


def detect_channel(line: str) -> str:
    return "LORA_MESH" if line.lstrip().startswith("{") else "APRS_VHF"


def forward(server: str, agent_key: str, line: str) -> dict:
    channel = detect_channel(line)
    body = json.dumps({"channel": channel, "raw_packet": line}).encode()
    req = urllib.request.Request(
        server.rstrip("/") + "/api/v2/telemetry/offgrid",
        data=body, method="POST",
        headers={"Content-Type": "application/json",
                 **({"X-Agent-Key": agent_key} if agent_key else {})},
    )
    with urllib.request.urlopen(req, timeout=8) as resp:
        return json.loads(resp.read())


def iter_lines(args):
    src = args.source
    if src == "stdin":
        for line in sys.stdin:
            yield line.rstrip("\n")
    elif src == "file":
        with open(args.path, "r", errors="replace") as fh:
            fh.seek(0, 2)  # mulai dari ujung (tail -f)
            while True:
                line = fh.readline()
                if line:
                    yield line.rstrip("\n")
                else:
                    time.sleep(0.4)
    elif src == "tcp":
        import socket
        with socket.create_connection((args.host, args.port), timeout=10) as s:
            buf = b""
            while True:
                chunk = s.recv(4096)
                if not chunk:
                    break
                buf += chunk
                while b"\n" in buf:
                    line, buf = buf.split(b"\n", 1)
                    yield line.decode(errors="replace").rstrip("\r")
    elif src == "serial":
        try:
            import serial  # pyserial (opsional, hanya untuk mode serial)
        except ImportError:
            sys.exit("Mode serial butuh pyserial: pip install pyserial")
        with serial.Serial(args.path, args.baud, timeout=1) as ser:
            while True:
                raw = ser.readline()
                if raw:
                    yield raw.decode(errors="replace").rstrip("\r\n")


def main() -> int:
    ap = argparse.ArgumentParser(description="Jembatan radio → TFAEL-OMNI")
    ap.add_argument("--server", default="http://localhost:8080")
    ap.add_argument("--agent-key", default="")
    ap.add_argument("--source", choices=["stdin", "file", "tcp", "serial"], default="stdin")
    ap.add_argument("--path", help="berkas (file) atau port serial")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8001)
    ap.add_argument("--baud", type=int, default=9600)
    args = ap.parse_args()

    print(f"[radio-gateway] sumber={args.source} → {args.server}  (Ctrl+C untuk berhenti)", flush=True)
    sent = 0
    try:
        for line in iter_lines(args):
            line = (line or "").strip()
            if not line:
                continue
            try:
                res = forward(args.server, args.agent_key, line)
            except Exception as e:
                print(f"  ✗ gagal kirim: {e}", flush=True)
                continue
            if res.get("ok"):
                d = res.get("decoded", {})
                sent += 1
                print(f"  ✓ {res.get('unit_id')}  ({d.get('lat')}, {d.get('lon')})  {res.get('channel')}  [{sent}]", flush=True)
            else:
                print(f"  ⚠ ditolak: {res.get('error')}  | {line[:60]}", flush=True)
    except KeyboardInterrupt:
        print(f"\n[radio-gateway] berhenti. Total diteruskan: {sent}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
