#!/usr/bin/env bash
# Postacım — kurulum betiği.
#
#   ./kur.sh                 → kullanıcı dizinine kurar (~/.local)
#   ./kur.sh --gelistirici   → yalnız sanal ortam + bağımlılıklar (geliştirme)
#   ./kur.sh --kaldir        → kurulumu kaldırır (kurulmuş kaldırıcı varsa o çalışır)
#
# Sanal ortam (venv) depoya dâhil edilmez: kurulum betiği onu kullanıcının
# dizininde oluşturur, böylece proje klasörü salt-okunur olsa bile kurulur.
set -euo pipefail

AD="postacim"
DIZIN="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
KURUM="$HOME/.local/share/$AD"
VENV="$KURUM/venv"
BINDIR="$HOME/.local/bin"
MASAUSTU="$HOME/.local/share/applications"
DESKTOP="$MASAUSTU/$AD.desktop"
BASLATICI="$BINDIR/$AD"
KALDIRICI="$BINDIR/$AD-kaldir"
BASLATICI_KAYNAK="$DIZIN/tools/baslatici.sh"

yesno=1
gelistirici=0
kaldir=0
EK_ARG=""
for arg in "$@"; do
    case "$arg" in
        --gelistirici) gelistirici=1; yesno=0 ;;
        --kaldir)      kaldir=1 ;;
        -h|--help)     sed -n '2,9p' "$0"; exit 0 ;;
        *) EK_ARG="$EK_ARG $arg" ;;
    esac
done

# ------------------------------------------------------------------ kaldırma
if [ "$kaldir" -eq 1 ]; then
    # Kurulmuş kaldırıcı varsa onu kullan (kaynak klasörü silinmiş olabilir)
    if [ -x "$KALDIRICI" ]; then
        # shellcheck disable=SC2086
        exec "$KALDIRICI" $EK_ARG
    fi
    # Yoksa betiği kaynaktan çalıştır
    if [ -f "$DIZIN/tools/kaldir.sh" ]; then
        # shellcheck disable=SC2086
        exec bash "$DIZIN/tools/kaldir.sh" $EK_ARG
    fi
    echo "!! Kaldırıcı bulunamadı. Elle silebilirsiniz:" >&2
    echo "   rm -f $BASLATICI $DESKTOP" >&2
    echo "   rm -rf $KURUM" >&2
    exit 1
fi

# ------------------------------------------------------------------ python
if [ "$(id -u)" -eq 0 ]; then
    echo "!! Kurulumu root (sudo) olarak yapmayın." >&2
    echo "   Postacım kullanıcı dizinine (~/.local) kurulur. sudo ile kurulursa" >&2
    echo "   dosyaların sahibi root olur ve uygulama sessizce açılmaz." >&2
    exit 1
fi

PY3="$(command -v python3 || true)"
if [ -z "$PY3" ]; then
    echo "!! Python 3 bulunamadı. Python 3.10+ kurun (Pardus: 'sudo apt install python3')." >&2
    exit 1
fi
PY_VER="$("$PY3" -c 'import sys; print("%d.%d" % sys.version_info[:2])')"
if ! "$PY3" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)'; then
    echo "!! Python 3.10+ gerekli (bulunan: $PY_VER)" >&2
    exit 1
fi
echo "→ Python $PY_VER ($PY3)"

# ------------------------------------------------------------------ sanal ortam
if [ ! -x "$VENV/bin/python" ]; then
    echo "→ Sanal ortam oluşturuluyor: $VENV"
    mkdir -p "$KURUM"
    "$PY3" -m venv "$VENV"
fi
VPY="$VENV/bin/python"

# Tk (tkinter) yoksa arayüz hiç açılmaz. Kurulum "başarılı" görünüp
# uygulama sonra sessizce öldüğü için burada erken uyarılır.
if ! "$VPY" -c "import tkinter" >/dev/null 2>&1; then
    echo "!! Tkinter (Tk) bulunamadı — Postacımın arayüzü için gerekli." >&2
    echo "   Pardus/Ubuntu/Debian:  sudo apt install python3-tk" >&2
    echo "   Fedora:                sudo dnf install python3-tkinter" >&2
    echo "   Arch:                 sudo pacman -S tk" >&2
    exit 1
fi

echo "→ Bağımlılıklar kuruluyor…"
"$VPY" -m pip install --quiet --upgrade pip
"$VPY" -m pip install --quiet -r "$DIZIN/requirements.txt"

# --------------------------------------------------------------- uygulama
echo "→ Postacım paketi kuruluyor…"
if [ "$gelistirici" -eq 1 ]; then
    # Geliştirici kurulumu: kaynak koda bağlı (kod değişiklikleri anında yansır).
    if ! "$VPY" -m pip install --quiet -e "$DIZIN" 2>/dev/null; then
        "$VPY" -m pip install --quiet --no-build-isolation -e "$DIZIN"
    fi
else
    # Normal kurulum: paket sanal ortama kopyalanır. Böylece uygulama kaynak
    # klasörden bağımsız çalışır; Postacım klasörü taşınsa/silinse bile menüdeki
    # girdi çalışmaya devam eder (editable kurulumda sessizce bozulurdu).
    if ! "$VPY" -m pip install --quiet "$DIZIN" 2>/dev/null; then
        "$VPY" -m pip install --quiet --no-build-isolation "$DIZIN"
    fi
fi

if [ "$gelistirici" -eq 1 ]; then
    echo "✓ Geliştirici ortamı hazır."
    echo "  Çalıştırmak için:  $VPY -m $AD"
    exit 0
fi

# --------------------------------------------------------------- doğrulama
if ! "$VPY" -c "import tkinter, postacim" >/dev/null 2>&1; then
    echo "!! Kurulum doğrulanamadı: arayüz içe aktarılamadı." >&2
    echo "   Ayrıntı için:  $VPY -c 'import postacim.ui'" >&2
    exit 1
fi

# --------------------------------------------------------------- başlatıcı
mkdir -p "$BINDIR" "$MASAUSTU"
if [ -f "$BASLATICI_KAYNAK" ]; then
    # Hata yutmayan başlatıcı: hata günlüğe yazılır ve kullanıcıya iletişim
    # kutusuyla gösterilir (GNOME'da masaüstü girdisinden açılan uygulamanın
    # hata çıktısı ekrana basılmaz).
    sed "s|__VPY__|$VPY|g" "$BASLATICI_KAYNAK" > "$BASLATICI"
else
    cat > "$BASLATICI" <<EOF
#!/usr/bin/env bash
# Postacım başlatıcı (kur.sh ile oluşturuldu)
exec "$VPY" -m $AD "\$@"
EOF
fi
chmod +x "$BASLATICI"

# --------------------------------------------------------------- simge
SIMGE_DIZIN="$HOME/.local/share/icons/hicolor"
SIMGE_KAYNAK="$DIZIN/postacim/ikonlar/uygulama.png"
SIMGE_SVG="$DIZIN/data/icons/hicolor/scalable/apps/postacim.svg"
SIMGE_AD="postacim"

if [ -f "$SIMGE_KAYNAK" ]; then
    echo "→ Simge kuruluyor…"
    mkdir -p "$SIMGE_DIZIN"
    "$VPY" - "$SIMGE_KAYNAK" "$SIMGE_DIZIN" "$SIMGE_AD" <<'PY' || true
import os, sys
from PIL import Image

kaynak, hedef, ad = sys.argv[1], sys.argv[2], sys.argv[3]
try:
    resim = Image.open(kaynak).convert("RGBA")
except Exception as exc:
    print(f"   simge okunamadı: {exc}")
    raise SystemExit(0)
for boyut in (16, 24, 32, 48, 64, 128, 256):
    yol = os.path.join(hedef, f"{boyut}x{boyut}", "apps")
    os.makedirs(yol, exist_ok=True)
    resim.resize((boyut, boyut), Image.LANCZOS).save(os.path.join(yol, f"{ad}.png"))
print(f"   {len((16, 24, 32, 48, 64, 128, 256))} boyut üretildi")
PY
    if [ -f "$SIMGE_SVG" ]; then
        mkdir -p "$SIMGE_DIZIN/scalable/apps"
        cp -f "$SIMGE_SVG" "$SIMGE_DIZIN/scalable/apps/$SIMGE_AD.svg" 2>/dev/null || true
    fi
    # Simge önbelleğini tazele (varsa)
    if command -v gtk-update-icon-cache >/dev/null 2>&1; then
        gtk-update-icon-cache -f -t "$SIMGE_DIZIN" >/dev/null 2>&1 || true
    fi
fi

cat > "$DESKTOP" <<EOF
[Desktop Entry]
Type=Application
Name=Postacım
Comment=E-posta ve takvim istemcisi (Exchange/EWS, IMAP, CalDAV)
Exec=$BASLATICI
Icon=$SIMGE_AD
Terminal=false
Categories=Network;Email;
StartupNotify=true
StartupWMClass=postacim
EOF
chmod +x "$BASLATICI"

# --------------------------------------------------------------- kaldırıcı
# Kaynak klasörü silinse bile kaldırma yapılabilsin diye bağımsız kaldırıcı
# ~/.local/bin/postacim-kaldir olarak kurulur.
if [ -f "$DIZIN/tools/kaldir.sh" ]; then
    cp -f "$DIZIN/tools/kaldir.sh" "$KALDIRICI"
    chmod +x "$KALDIRICI"
fi

# Menüde görünmesi için (çoğu masaüstü ortamı bunu izler)
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$MASAUSTU" >/dev/null 2>&1 || true
fi

echo
echo "✓ Postacım kuruldu."
echo "  Başlatıcı : $BASLATICI"
echo "  Menü girdisi: Postacım"
echo "  Ayarlar   : ~/.config/$AD"
echo
echo "  Terminalden başlatmak için:  postacim"
echo "  Kaldırmak için             :  postacim-kaldir"
