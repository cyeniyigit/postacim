#!/usr/bin/env bash
# Postacım — başlatıcı (kur.sh tarafından ~/.local/bin/postacim olarak kurulur).
#
# Neden böyle bir betik gerekiyor?
#   GNOME'da masaüstü girdisinden başlatılan bir uygulama çöktüğünde hata
#   çıktısı ekrana basılmaz; yalnızca oturum günlüğüne (journal) düşer.
#   Kullanıcı "uygulama kurulu görünüyor ama hiçbir şey olmuyor" görür ve
#   nedenini öğrenemez. Bu betik:
#     * hata çıktısını ~/.local/state/postacim/hata.log dosyasına yazar,
#     * varsa zenity/kdialog/xmessage ile anlaşılır bir iletişim kutusu gösterir,
#     * tanıdığı hatalara (eksik tkinter, bozuk sanal ortam, kaynak klasörün
#       taşınmış olması) doğrudan çözüm önerir.
set -uo pipefail

VPY="__VPY__"
AD="postacim"
DURUM_KOK="${XDG_STATE_HOME:-$HOME/.local/state}"

# Günlük dizini; yazılamıyorsa geçici dizine düşülür.
if ! mkdir -p "$DURUM_KOK/$AD" 2>/dev/null; then
    DURUM_KOK="$(mktemp -d 2>/dev/null || echo /tmp)"
    mkdir -p "$DURUM_KOK/$AD" 2>/dev/null || true
fi
GUNLUK="$DURUM_KOK/$AD/hata.log"

# --------------------------------------------------------------- yardımcılar
gunluk_ekle() {
    {
        printf '\n=== %s ===\n' "$(date '+%Y-%m-%d %H:%M:%S')"
        printf '%s\n' "$1"
    } >> "$GUNLUK" 2>/dev/null || true
}

# İletişim kutusu: kullanıcı gerçekten ne olduğunu görsün.
kutu_goster() {
    local baslik="$1" govde="$2"
    if command -v zenity >/dev/null 2>&1; then
        zenity --error --no-markup --title="$baslik" --text="$govde" >/dev/null 2>&1 || true
    elif command -v kdialog >/dev/null 2>&1; then
        kdialog --error "$govde" --title "$baslik" >/dev/null 2>&1 || true
    elif command -v xmessage >/dev/null 2>&1; then
        xmessage -center -buttons Ok -default ok "$baslik" "$govde" >/dev/null 2>&1 || true
    fi
}

# Hata metnini okuyup kullanıcıya ne yapması gerektiğini söyle.
tani_yokla() {
    local metin="$1"
    case "$metin" in
        *"No module named 'tkinter'"*|*"No module named tkinter"*)
            printf 'Postacım arayüzü için Tk (tkinter) gerekli ama sistemde yok.\n\nÇözüm:\n  sudo apt install python3-tk\n\nArdından uygulamayı yeniden başlatın.'
            ;;
        *"No module named postacim"*|*"No module named 'postacim'"*)
            printf 'Uygulama dosyaları bulunamadı (kurulum kaynak klasörüne bağlıymış).\n\nÇözüm:\n  Postacım klasöründe yeniden kurun:  ./kur.sh\n\nKlasör taşınmış/silinmişse Postacım deposundan yeniden indirin.'
            ;;
        *"No such file or directory"*|*"cannot execute"*)
            printf 'Sanal ortam bulunamadı veya bozuk (Python sürümü değişmiş olabilir).\n\nÇözüm:\n  Postacım klasöründe yeniden kurun:  ./kur.sh'
            ;;
        *"ModuleNotFoundError: No module named"*)
            printf 'Bir Python paketi eksik.\n\nÇözüm:\n  Postacım klasöründe yeniden kurun:  ./kur.sh'
            ;;
        *)
            printf 'Uygulama başlatılamadı. Ayrıntılar:\n\n%s\n\nGünlük: %s' "$metin" "$GUNLUK"
            ;;
    esac
}

# --------------------------------------------------------------- başlatma
if [ ! -x "$VPY" ]; then
    metin="Sanal ortam bulunamadı: $VPY\n\nÇözüm:\n  Postacım klasöründe yeniden kurun:  ./kur.sh"
    gunluk_ekle "$metin"
    kutu_goster "Postacım başlatılamadı" "$metin"
    exit 1
fi

# Hata çıktısı geçici dosyaya alınır: hem günlüğe yazılır, hem terminale
# basılır, hem de iletişim kutusunda gösterilir.
GECICI="$(mktemp 2>/dev/null || echo /tmp/postacim_hata_$$.txt)"
trap 'rm -f "$GECICI" 2>/dev/null' EXIT

BASLANGIC="$(date +%s)"
"$VPY" -m "$AD" "$@" 2>"$GECICI"
kod=$?
SURE=$(( $(date +%s) - BASLANGIC ))

if [ -s "$GECICI" ]; then
    cat "$GECICI" >> "$GUNLUK" 2>/dev/null || true
    [ -t 2 ] && cat "$GECICI" >&2
fi

# 128+n çıkış kodu: uygulama sinyal ile sonlandırıldı (ör. kapatıldı).
# Bu bir başlatma hatası değildir; "başlatılamadı" uyarısı yanlış olur.
if [ "$kod" -ge 128 ]; then
    exit "$kod"
fi

if [ "$kod" -ne 0 ]; then
    ozet="$(tail -n 25 "$GECICI" 2>/dev/null)"
    if [ "$SURE" -lt 5 ]; then
        kutu_goster "Postacım başlatılamadı" "$(tani_yokla "$ozet")"
    else
        kutu_goster "Postacım beklenmeyen şekilde kapandı" \
            "$(tani_yokla "$ozet")"
    fi
fi

exit "$kod"
