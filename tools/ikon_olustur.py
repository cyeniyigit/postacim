#!/usr/bin/env python3
"""Uygulama simgesini üretir (Postacım).

Zarf motifli, mavi gradyanlı yuvarlatılmış kare simge. Ana dosya (256×256)
`postacim/ikonlar/uygulama.png` olarak yazılır; `kur.sh` bunu kullanarak
boyutları üretip `~/.local/share/icons/hicolor/` altına kurar.

Çalıştırma:
    python3 tools/ikon_olustur.py
"""
from __future__ import annotations

import os
import sys

from PIL import Image, ImageDraw

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HEDEF = os.path.join(KOK, "postacim", "ikonlar", "uygulama.png")

BOYUT = 256
OLCEK = 4          # 4 kat çizip küçült (kenar yumuşatma)
S = BOYUT * OLCEK

# Renkler
UST = (74, 140, 224)     # mavi üst
ALT = (23, 66, 141)      # mavi alt
ZARF = (255, 255, 255)
ZARF_KENAR = (219, 231, 247)
KANAT = (176, 205, 240)
GOLD = (255, 196, 61)    # pull (damga) sarısı
GOLD_KENAR = (214, 148, 22)


def yuvarlak_dikdortgen(cizim, kutu, yaricap, fill=None, outline=None, width=0):
    """Yuvarlatılmış dikdörtgen çiz (yeni Pillow API'ları da desteklenir)."""
    try:
        cizim.rounded_rectangle(kutu, radius=yaricap, fill=fill,
                                outline=outline, width=width)
    except TypeError:  # eski Pillow
        cizim.rounded_rectangle(kutu, radius=yaricap, fill=fill,
                                outline=outline)


def gradyan(zemin, ust, alt):
    """Dikey gradyan (yukarıdan aşağı)."""
    c = Image.new("RGB", (1, S))
    p = c.load()
    for y in range(S):
        t = y / (S - 1)
        p[0, y] = (
            int(ust[0] + (alt[0] - ust[0]) * t),
            int(ust[1] + (alt[1] - ust[1]) * t),
            int(ust[2] + (alt[2] - ust[2]) * t),
        )
    return c.resize((S, S))


def olustur() -> Image.Image:
    # --- zemin: gradyan + yuvarlatılmış köşeler
    zemin = gradyan(None, UST, ALT).convert("RGBA")
    maske = Image.new("L", (S, S), 0)
    ImageDraw.Draw(maske).rounded_rectangle(
        (0, 0, S - 1, S - 1), radius=int(S * 0.225), fill=255
    )
    zemin.putalpha(maske)
    cizim = ImageDraw.Draw(zemin)

    # üstte hafif parlaklık
    parlak = Image.new("RGBA", (S, S), (255, 255, 255, 0))
    pd = ImageDraw.Draw(parlak)
    pd.ellipse((-S * 0.35, -S * 0.75, S * 1.35, S * 0.45),
               fill=(255, 255, 255, 30))
    parlak.putalpha(Image.composite(parlak.getchannel("A"), Image.new("L", (S, S), 0),
                                    maske))
    zemin = Image.alpha_composite(zemin, parlak)
    cizim = ImageDraw.Draw(zemin)

    # --- zarf gövdesi (gölge + gövde)
    zx1, zx2 = int(S * 0.165), int(S * 0.835)
    zy1, zy2 = int(S * 0.285), int(S * 0.735)
    yuvarlak_dikdortgen(cizim, (zx1 + int(S * 0.018), zy1 + int(S * 0.022),
                                zx2 + int(S * 0.018), zy2 + int(S * 0.022)),
                        int(S * 0.055), fill=(12, 40, 88, 90))
    yuvarlak_dikdortgen(cizim, (zx1, zy1, zx2, zy2), int(S * 0.055), fill=ZARF)

    # --- zarf kapağı: üst köşelerden ortaya inen V (açık mavi)
    orta = ((zx1 + zx2) // 2, zy1 + int((zy2 - zy1) * 0.62))
    kapak = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    kd = ImageDraw.Draw(kapak)
    kd.polygon([(zx1, zy1), (zx2, zy1), orta], fill=KANAT)
    kapak.putalpha(Image.composite(kapak.getchannel("A"), Image.new("L", (S, S), 0), maske))
    zemin = Image.alpha_composite(zemin, kapak)
    cizim = ImageDraw.Draw(zemin)

    # --- alt kıvrımlar: alt köşelerden ortaya çizgiler
    cizim.line([(zx1, zy2), orta], fill=ZARF_KENAR, width=int(S * 0.013))
    cizim.line([(zx2, zy2), orta], fill=ZARF_KENAR, width=int(S * 0.013))
    # kapak konturu (üst köşelerden ortaya)
    cizim.line([(zx1, zy1), orta, (zx2, zy1)], fill=(255, 255, 255, 235),
               width=int(S * 0.013), joint="curve")

    # --- pull (damga) — sağ üst köşede
    px, py = int(S * 0.735), int(S * 0.235)
    r = int(S * 0.072)
    cizim.ellipse((px - r - int(S * 0.012), py - r - int(S * 0.012),
                   px + r + int(S * 0.012), py + r + int(S * 0.012)),
                  fill=GOLD_KENAR)
    cizim.ellipse((px - r, py - r, px + r, py + r), fill=GOLD)
    cizim.ellipse((px - r + int(S * 0.012), py - r + int(S * 0.012),
                   px + r - int(S * 0.012), py + r - int(S * 0.012)),
                  outline=(255, 236, 190), width=int(S * 0.008))

    return zemin.resize((BOYUT, BOYUT), Image.LANCZOS)


def main() -> int:
    try:
        resim = olustur()
    except ImportError:
        print("!! Pillow gerekli: pip install Pillow", file=sys.stderr)
        return 1
    os.makedirs(os.path.dirname(HEDEF), exist_ok=True)
    resim.save(HEDEF, "PNG", optimize=True)
    print(f"✓ {HEDEF} ({BOYUT}×{BOYUT})")

    # Başlık çubuğu (64), görev çubuğu (48) ve Hakkında penceresi (128)
    dizin = os.path.dirname(HEDEF)
    for boyut in (128, 64, 48):
        yol = os.path.join(dizin, f"uygulama_{boyut}.png")
        resim.resize((boyut, boyut), Image.LANCZOS).save(yol, "PNG", optimize=True)
        print(f"✓ {yol} ({boyut}×{boyut})")

    # Küçük önizleme (README için)
    onizleme = os.path.join(KOK, "belge", "simge.png")
    if os.path.isdir(os.path.dirname(onizleme)):
        resim.resize((128, 128), Image.LANCZOS).save(onizleme, "PNG", optimize=True)
        print(f"✓ {onizleme} (128×128)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
