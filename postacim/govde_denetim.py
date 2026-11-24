"""HTML gövdeyi Tkhtml3'e yüklemeden önce alt süreçte çökme denetimi.

Tkhtml3 (C) bozuk e-posta HTML'inde segfault üretebilir; çökme tüm
uygulamayı düşürür. Bu modül üretilen gösterim HTML'ini önce ayrı bir
alt süreçte (gizli pencere, dış istekler kapalı) yükler: süreç hayatta
kalırsa gösterime güvenlidir; çökürse arayüz metin görünümüne döner.

Sonuç, çağıran tarafın oturum içi önbelleğine yazılır (anahtarı
mesaj + gösterim türü); böylece her ileti için denetim bir kez çalışır.
"""

import os
import re
import subprocess
import sys
import tempfile
import time

_TABLO_ADI = re.compile(r"<table[\s>/]", re.I)


def denetim_gerekmez(html: str) -> bool:
    """HTML tablo içermiyorsa denetim gerekmez (True döner).

    Tkhtml3'te bugüne dek gözlenen segfault sınıflarının hepsi tablo
    yapısına bağlıdır (kapanmamış tablo/tbody, hücresiz iç içe tablo,
    yorum içindeki hayalet tablo etiketleri). Tablosuz HTML bilinen
    çökme desenlerinden etkilenmez; alt süreç denetimi atlanıp HTML
    doğrudan gösterilir (bekleme/flaş olmaz).
    """
    return not _TABLO_ADI.search(html or "")

# Alt süreçte koşan denetçi: HTML'i tkinterweb'in aynı ayarlarıyla
# (dış istekler kapalı, script yok) gizli pencerede yükler; `sure`
# boyunca olay döngüsünü besler, sonra HAYATTA basar. Segfault çökerse
# çıktı gelmez. tkinterweb kurulu değilse KURULU_DEGIL basar (sonuç
# belirsiz sayılır; gösterim engellenmez).
_DENETCI_KODU = """\
import sys, time
html_yolu, sure = sys.argv[1], float(sys.argv[2])
try:
    from tkinterweb import HtmlFrame
except ImportError:
    print("KURULU_DEGIL")
    raise SystemExit(0)
import tkinter as tk
html = open(html_yolu, encoding="utf-8", errors="replace").read()
kok = tk.Tk()
kok.withdraw()
c = HtmlFrame(kok, messages_enabled=False, javascript_enabled=False,
              forms_enabled=False, objects_enabled=False,
              request_func=lambda u, *a, **k: (u, b"", "text/html", 404))
c.load_html(html)
bitis = time.time() + sure
while time.time() < bitis:
    kok.update(); time.sleep(0.03)
print("HAYATTA")
"""


def html_guvenli_mi(
    html: str, sure: float = 1.0, zaman_asimi: float = 15.0
) -> bool | None:
    """HTML'i alt süreçte yükleyip çökme üretip üretmediğini döndürür.

    Dönüş: True (hayatta kaldı), False (segfault/çökme), None
    (denetlenemedi: tkinterweb yok, görüntü yok ya da süreç cevap
    vermedi). None durumunda gösterim engellenmez — davranış
    denetimsiz eskisiyle aynı kalır.

    `sure`: yükleme sonrası gözlem penceresi. Bilinen çökertilier
    yüklemeyi izleyen ~0,4 sn içinde ölüyor; 1 sn marj yeterlidir.
    """
    if not html:
        return True
    try:
        fd, yol = tempfile.mkstemp(suffix=".html", prefix="postacim-denetim-")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(html)
    except OSError:
        return None
    try:
        r = subprocess.run(
            [sys.executable, "-c", _DENETCI_KODU, yol, str(sure)],
            capture_output=True,
            text=True,
            timeout=zaman_asimi,
        )
    except (subprocess.TimeoutExpired, OSError):
        return None
    finally:
        try:
            os.unlink(yol)
        except OSError:
            pass
    cikti = r.stdout or ""
    if "KURULU_DEGIL" in cikti:
        return None
    return "HAYATTA" in cikti


def cokme_logla(aciklama: str, cikti_hata: str = "") -> str | None:
    """Alt süreç çökmesini ~/.local/state/postacim/hata.log'a ekler.

    Dönüş: yazılan dosyanın yolu (yazılamadıysa None). Uygulamanın
    _tk_hata_yakala kaydıyla aynı biçimde, tarih başlıklı eklenir.
    """
    satir = (
        f"\n===== {time.strftime('%Y-%m-%d %H:%M:%S')} =====\n"
        f"Gövde HTML denetiminde alt süreç çökmesi\n{aciklama}\n"
    )
    if cikti_hata:
        satir += cikti_hata[:2000] + "\n"
    try:
        gunluk_dizin = os.path.join(
            os.environ.get("XDG_STATE_HOME", "")
            or os.path.join(os.path.expanduser("~"), ".local", "state"),
            "postacim",
        )
        os.makedirs(gunluk_dizin, exist_ok=True)
        gunluk = os.path.join(gunluk_dizin, "hata.log")
        if os.path.exists(gunluk) and os.path.getsize(gunluk) > 400_000:
            os.remove(gunluk)
        with open(gunluk, "a", encoding="utf-8") as f:
            f.write(satir)
        return gunluk
    except OSError:
        return None
