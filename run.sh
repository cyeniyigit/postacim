#!/usr/bin/env bash
# Postacım başlatıcı.
# - Sanal ortam varsa ve çalışıyorsa onu kullanır
# - Kırıksa (yanlış Python sürümü, eksik paket) kendiliğinden yeniden kurar
set -e
DIZIN="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="$DIZIN/.venv"
PY="$VENV/bin/python"

gereken_paketler="import requests, requests_ntlm"

if [ ! -x "$PY" ] || ! "$PY" -c "$gereken_paketler" >/dev/null 2>&1; then
    echo "→ Sanal ortam kullanılamıyor; yeniden kuruluyor…"
    python3 -m venv "$VENV" 2>/dev/null || { rm -rf "$VENV"; python3 -m venv "$VENV"; }
    "$VENV/bin/python" -m pip install --quiet --upgrade pip
    "$VENV/bin/python" -m pip install --quiet -r "$DIZIN/requirements.txt"
    if ! "$PY" -c "$gereken_paketler" >/dev/null 2>&1; then
        echo "!! Paketler kurulamadı. İnternet bağlantısını kontrol edin veya:" >&2
        echo "   python3 -m pip install --user -r $DIZIN/requirements.txt" >&2
        PY="$(command -v python3)"
    fi
fi

cd "$DIZIN"
exec "$PY" -m postacim "$@"
