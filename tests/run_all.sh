#!/usr/bin/env bash
# Tüm çevrimdışı testleri sırayla çalıştırır.
#
#   ./tests/run_all.sh
#
# Arayüz testleri için Xvfb gerekir (yoksa xvfb-run kurulmalı).
# Canlı sunucu testleri (test_ews.py, ui_smoke.py, takvim_ui_test.py)
# gerçek hesap gerektirdiği için burada çalıştırılmaz.
set -u

DIZIN="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
KOK="$(dirname "$DIZIN")"
PY="${PY:-$KOK/.venv/bin/python}"
[ -x "$PY" ] || PY="$(command -v python3)"

CALISTIR=""
for t in coklu_hesap_test hesap_ui_test imap_yerel_sunucu_test ews_klasor_test silme_sayfa_test resim_test tekrar_test randevu_ekle_test bildirim_test govde_test dosya_secici_test ek_indir_test; do
    CALISTIR="$CALISTIR $DIZIN/$t.py"
done

# Xvfb varsa arayüz testleri başsız da çalışır
if command -v xvfb-run >/dev/null 2>&1; then
    KOSUL="xvfb-run -a"
else
    KOSUL=""
    echo "!! xvfb-run bulunamadı — arayüz testleri ekran gerektirebilir"
fi

basari=0
for betik in $CALISTIR; do
    ad="$(basename "$betik")"
    printf "%-32s" "$ad"
    if $KOSUL "$PY" "$betik" >/tmp/postacim_test.log 2>&1; then
        echo "✓"
    else
        echo "✗"
        tail -20 /tmp/postacim_test.log
        basari=1
    fi
done

if [ "$basari" -eq 0 ]; then
    echo "✓ tüm testler geçti"
else
    echo "!! bazı testler başarısız"
fi
exit "$basari"
