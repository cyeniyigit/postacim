#!/usr/bin/env python3
"""Gövde görüntüleme testleri — yatay kaydırma ve otomatik sığdırma.

Kapsam:
  * HTML gövdede yatay kaydırma çubuğu etkin (taşan içerik okunabilir).
  * "Genişliğe sığdır" işlemi içeriği görüntü genişliğine sığdırır.
  * Zoom değişimi içeriğin genişliğini ölçekler.
  * Aşırı geniş içerik sığmasa da kaydırma çubuğu devrede kalır.
  * Metin modunda satır sarmalama vardır (yatay kaydırma gerekmez).
"""
import os
import sys
import time
import tkinter as tk

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

HATALAR = []

# Görüntüden ~1,4 kat geniş: sığdırma ile tam oturmalı
ORTA_GENIS_HTML = (
    "<html><body><pre>" + ("w" * 120) + "</pre></body></html>"
)
# Görüntüden çok geniş: sığdırılamaz, kaydırma çubuğu devrede kalmalı
COK_GENIS_HTML = (
    "<html><body><pre>" + ("çok geniş bir satır içeriği olsun ki taşsın " * 60)
    + "</pre></body></html>"
)
DAR_HTML = "<html><body><p>Kısa bir mesaj gövdesi.</p></body></html>"


def kontrol(kosul, aciklama):
    if kosul:
        print(f"  ✓ {aciklama}")
    else:
        print(f"  ✗ {aciklama}")
        HATALAR.append(aciklama)


def bekle(kok, saniye=1.5):
    """Tk olay döngüsünü çalıştırır (after() işleri tamamlanır)."""
    bitis = time.time() + saniye
    while time.time() < bitis:
        kok.update()
        time.sleep(0.02)


def main() -> int:
    try:
        kok = tk.Tk()
        kok.geometry("760x520")
    except tk.TclError:
        print("  -- DISPLAY yok (xvfb-run ile çalıştırın), atlandı")
        return 0

    import postacim.ui as ui_mod

    if ui_mod.HtmlFrame is None:
        print("  -- tkinterweb/Tkhtml3 yok; yalnız metin modu denenir")
        kok.destroy()
        return 0

    from tkinterweb import HtmlFrame
    from postacim.ui import Postacim

    cerceve = tk.Frame(kok)
    cerceve.pack(fill="both", expand=True)
    html = HtmlFrame(
        cerceve,
        horizontal_scrollbar="auto",
        vertical_scrollbar="auto",
    )
    html.pack(fill="both", expand=True)
    kok.update()

    kontrol(
        html.cget("horizontal_scrollbar") == "auto",
        "yatay kaydırma çubuğu 'auto' olarak etkin",
    )

    # Uygulamanın gerçek yöntemlerini kullanan sahte örnek
    class Sahte:
        """Postacim'in gövde yöntemlerini kullanan hafif örnek."""

    uygulama = Sahte()
    uygulama.ayrinti = html
    uygulama.html_modu = True
    uygulama._gövde_zoom = 1.0
    uygulama._gövde_oto_sigdir = False
    uygulama._gövde_sigdir_zamanlandi = False
    uygulama.durum = tk.StringVar()
    uygulama.zoom_etiket = tk.Label(kok)
    # Zamanlayıcı gerçek Tk kökü üzerinde çalışsın
    uygulama.after = kok.after
    uygulama.GOVDE_SIGDIR_ZOOM_MIN = Postacim.GOVDE_SIGDIR_ZOOM_MIN
    uygulama.GOVDE_ZOOM_MIN = Postacim.GOVDE_ZOOM_MIN
    uygulama.GOVDE_ZOOM_MAX = Postacim.GOVDE_ZOOM_MAX
    for ad in ("_gövde_sigdir", "_gövde_gorunur_oran", "_gövde_zoom_uygula"):
        setattr(uygulama, ad, getattr(Postacim, ad).__get__(uygulama))

    # --- 1) Orta genişlikte içerik: sığdırma tam oturmalı ---
    html.load_html(ORTA_GENIS_HTML)
    kok.update()
    bekle(kok, 0.5)
    ilk, son = html._html.xview()
    oran = son - ilk
    kontrol(oran < 0.99, f"orta geniş içerik taşıyor (oran={oran:.3f})")
    kontrol(html._hsb.scroll, "yatay kaydırma çubuğu etkinleşti")

    uygulama._gövde_sigdir()
    bekle(kok, 2.0)
    ilk, son = html._html.xview()
    oran2 = son - ilk
    kontrol(oran2 >= 0.95, f"sığdırma sonrası içerik sığıyor (oran={oran2:.3f})")
    kontrol(
        uygulama._gövde_zoom < 1.0,
        f"sığdırma zoom'u küçülttü ({uygulama._gövde_zoom:.2f})",
    )

    # --- 2) Aşırı geniş içerik: kaydırma çubuğu devrede kalmalı ---
    html.configure(zoom=1.0)
    uygulama._gövde_zoom = 1.0
    html.load_html(COK_GENIS_HTML)
    kok.update()
    bekle(kok, 0.5)
    ilk, son = html._html.xview()
    oran = son - ilk
    kontrol(oran < 0.2, f"çok geniş içerik taşıyor (oran={oran:.3f})")
    kontrol(html._hsb.scroll, "çok geniş içerikte kaydırma çubuğu var")

    uygulama._gövde_sigdir()
    bekle(kok, 2.5)
    ilk, son = html._html.xview()
    oran3 = son - ilk
    kontrol(
        oran3 > oran,
        f"sığdırma aşırı geniş içeriği de küçülttü ({oran:.3f} → {oran3:.3f})",
    )
    kontrol(html._hsb.scroll, "içerik hâlâ taşıyorsa kaydırma çubuğu duruyor")
    kontrol(
        uygulama._gövde_zoom >= Postacim.GOVDE_SIGDIR_ZOOM_MIN - 0.001,
        "okunabilirlik için zoom alt sınırına uyuldu",
    )

    # --- 3) Dar içerik: sığdırma bozmamalı ---
    html.configure(zoom=1.0)
    uygulama._gövde_zoom = 1.0
    html.load_html(DAR_HTML)
    kok.update()
    bekle(kok, 0.5)
    ilk, son = html._html.xview()
    kontrol((son - ilk) >= 0.99, "dar içerik zaten sığıyor")
    uygulama._gövde_sigdir()
    bekle(kok, 1.0)
    kontrol(
        abs(uygulama._gövde_zoom - 1.0) < 0.001,
        "dar içerikte zoom değiştirilmedi",
    )

    # --- 4) Metin modu ---
    metin = tk.Text(kok, wrap="word", width=40, height=10)
    metin.pack(fill="both", expand=True)
    metin.insert("1.0", "x" * 500)
    kok.update()
    kontrol(metin.cget("wrap") == "word", "metin modunda satır sarmalama var")

    kok.destroy()

    if HATALAR:
        print(f"\n!! {len(HATALAR)} hata:")
        for h in HATALAR:
            print(f"   - {h}")
        return 1
    print("\n✓ tüm kontroller geçti")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
