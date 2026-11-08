#!/usr/bin/env bash
# ============================================================
# TFAEL-OMNI — Skrip start mode PRODUKSI (penguncian aktif)
# Memuat deploy/omni.env, membangkitkan rahasia acak bila kosong,
# lalu menjalankan server dengan env var yang benar-benar dipakai kode.
#
#   Pakai:  ./deploy/start-prod.sh [port]
#   Contoh: ./deploy/start-prod.sh 8080
# ============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
ENV_FILE="$SCRIPT_DIR/omni.env"
ENV_EXAMPLE="$SCRIPT_DIR/omni.env.example"
PORT="${1:-8080}"

# 1) Buat omni.env dari template bila belum ada.
if [[ ! -f "$ENV_FILE" ]]; then
    echo "[start-prod] deploy/omni.env belum ada — membuat dari template..."
    cp "$ENV_EXAMPLE" "$ENV_FILE"
fi

# 2) Isi rahasia acak bila masih kosong (hanya sekali).
gen() { python3 -c "import secrets;print(secrets.token_urlsafe($1))"; }

if grep -qE '^OMNI_AGENT_KEY=""$' "$ENV_FILE"; then
    KEY="FIELD-$(gen 24)"
    # sed in-place lintas-platform (BSD/macOS & GNU/Linux)
    sed -i.bak "s|^OMNI_AGENT_KEY=\"\"$|OMNI_AGENT_KEY=\"$KEY\"|" "$ENV_FILE"
    echo "[start-prod] OMNI_AGENT_KEY acak dibuat & disimpan ke omni.env."
fi
if grep -qE '^OMNI_BOOTSTRAP_PASSWORD=""$' "$ENV_FILE"; then
    PWD_GEN="$(gen 12)"
    sed -i.bak "s|^OMNI_BOOTSTRAP_PASSWORD=\"\"$|OMNI_BOOTSTRAP_PASSWORD=\"$PWD_GEN\"|" "$ENV_FILE"
    echo "[start-prod] OMNI_BOOTSTRAP_PASSWORD acak dibuat & disimpan ke omni.env."
fi
rm -f "$ENV_FILE.bak"

# 3) Muat semua variabel.
set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

echo "[start-prod] Mode produksi aktif. CORS origin: ${OMNI_ALLOWED_ORIGINS:-<kosong: tolak semua>}"
echo "[start-prod] Lockout: ${OMNI_LOGIN_MAX_FAILS} gagal / kunci ${OMNI_LOGIN_LOCK_SECONDS}s. Air-gap: ${OMNI_AIRGAP}"
echo "[start-prod] Menjalankan server di port $PORT ..."

# 4) Jalankan.
cd "$PROJECT_ROOT"
exec python3 backend/server.py "$PORT"
