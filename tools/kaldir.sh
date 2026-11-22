#!/usr/bin/env bash
# Postacım — kaldırıcı (kur.sh tarafından ~/.local/bin/postacim-kaldir
# olarak kurulur; **kaynak klasörü olmadan da** çalışır).
#
#   postacim-kaldir          → uygulamayı kaldırır, ayarları sorar
#   postacim-kaldir --tumu   → ayarlar dahil her şeyi siler
#   postacim-kaldir --ayarlar→ yalnız ayarları (hesaplar/parolalar) siler
#
# Kaldırılanlar:
#   ~/.local/bin/postacim              başlatıcı
#   ~/.local/bin/postacim-kaldir       bu betiğin kendisi
#   ~/.local/share/applications/postacim.desktop   menü girdisi
#   ~/.local/share/icons/hicolor/*/apps/postacim.*  simgeler
#   ~/.local/share/postacim/           sanal ortam + uygulama
#   ~/.config/postacim/                hesaplar, ayarlar (parola içerir!)
set -u

AD="postacim"
BINDIR="$HOME/.local/bin"
MASAUSTU="$HOME/.local/share/applications"
IKONLAR="$HOME/.local/share/icons/hicolor"
KURUM="$HOME/.local/share/$AD"
AYARLAR="$HOME/.config/$AD"

mod=uygulama
for arg in "$@"; do
    case "$arg" in
        --tumu)    mod=tumu ;;
        --ayarlar) mod=ayarlar ;;
        -h|--help) sed -n '2,16p' "$0"; exit 0 ;;
        *) echo "Bilinmeyen seçenek: $arg" >&2; exit 2 ;;
    esac
done

sil_sayac=0

if [ "$mod" = "ayarlar" ]; then
    if [ -d "$AYARLAR" ]; then
        rm -rf "$AYARLAR"
        echo "✓ Ayarlar silindi: $AYARLAR"
        echo "  (hesaplar ve kayıtlı parolalar bu klasördeydi)"
    else
        echo "• Ayarlar yok: $AYARLAR"
    fi
    exit 0
fi

echo "Postacım kaldırılıyor…"

# Başlatıcılar ve menü girdisi
for dosya in "$BINDIR/$AD" "$BINDIR/$AD-kaldir" "$MASAUSTU/$AD.desktop"; do
    if [ -e "$dosya" ]; then
        rm -f "$dosya" && sil_sayac=$((sil_sayac + 1))
    fi
done

# Simgeler (hicolor temasındaki postacim.* dosyaları)
if [ -d "$IKONLAR" ]; then
    while IFS= read -r -d '' dosya; do
        rm -f "$dosya" && sil_sayac=$((sil_sayac + 1))
    done < <(find "$IKONLAR" -name "$AD.*" -print0 2>/dev/null)
    # Simge önbelleğini tazele
    if command -v gtk-update-icon-cache >/dev/null 2>&1; then
        gtk-update-icon-cache -f -t "$IKONLAR" >/dev/null 2>&1 || true
    fi
fi

# Sanal ortam + uygulama dosyaları
if [ -d "$KURUM" ]; then
    rm -rf "$KURUM" && sil_sayac=$((sil_sayac + 1))
fi

echo "✓ Uygulama kaldırıldı ($sil_sayac öğe silindi)."

# Ayarlar: parola içerebilir → kullanıcıya sor
if [ -d "$AYARLAR" ]; then
    if [ "$mod" = "tumu" ]; then
        rm -rf "$AYARLAR"
        echo "✓ Ayarlar da silindi: $AYARLAR"
    elif [ -t 0 ]; then
        echo
        printf "Hesaplar ve ayarlar da silinsin mi? (%s) [e/H] " "$AYARLAR"
        yanit=""
        read -r yanit || true
        case "$yanit" in
            e|E|evet|EVET)
                rm -rf "$AYARLAR"
                echo "✓ Ayarlar silindi."
                ;;
            *)
                echo "• Ayarlar korundu: $AYARLAR"
                echo "  (silmek için: postacim-kaldir --ayarlar)"
                ;;
        esac
    else
        echo "• Ayarlar korundu: $AYARLAR"
        echo "  (silmek için: postacim-kaldir --ayarlar)"
    fi
else
    echo "• Ayarlar yok: $AYARLAR"
fi

echo
echo "Kaldırma tamamlandı. Teşekkürler!"
