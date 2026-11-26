#!/usr/bin/env python3
"""Kandilli deprem paneli ikonlarını üretir (18×18 + 48×48 PNG).

kandilli-quake GNOME eklentisinin büyüklüğe göre seçtiği tema ikonlarının
(St.Icon) Postacım'daki karşılıkları — Tk, GTK tema ikonunu okuyamadığı
için aynı anlamda benzerleri çizilir:

- deprem_dusuk.png   ← dialog-information-symbolic  (ML < 5 / deprem yok)
- deprem_orta.png    ← dialog-warning-symbolic      (ML ≥ 5)
- deprem_yuksek.png  ← emblem-important-symbolic    (ML ≥ 6)
- deprem_konum.png   ← konum işaretçisi (ayrıntı penceresi başlığı)

48×48 varyantlar (_48 son eki) ayrıntı penceresindeki büyük özet içindir.

Çalıştırma:
    python3 tools/deprem_ikon_olustur.py
"""
from __future__ import annotations

import os

from PIL import Image, ImageDraw

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HEDEF = os.path.join(KOK, "postacim", "ikonlar")

BOYUT = 18
OLCEK = 4          # 4 kat çizip küçült (kenar yumuşatma)
S = BOYUT * OLCEK

MAVI = (53, 132, 228, 255)      # GNOME bilgi mavisi
SARI = (229, 165, 10, 255)      # GNOME uyarı sarısı/amber
KIRMIZI = (224, 27, 36, 255)    # GNOME önemli kırmızısı
BEYAZ = (255, 255, 255, 255)


def yeni():
    return Image.new("RGBA", (S, S), (0, 0, 0, 0))


def bar(cizim, x_orta, y1, y2, genislik):
    cizim.rounded_rectangle(
        (x_orta - genislik // 2, y1, x_orta + genislik // 2, y2),
        radius=genislik // 2, fill=BEYAZ)


def daire(cizim, x_orta, y_orta, yaricap):
    cizim.ellipse(
        (x_orta - yaricap, y_orta - yaricap,
         x_orta + yaricap, y_orta + yaricap), fill=BEYAZ)


def bilgi() -> Image.Image:
    """dialog-information-symbolic: içi dolu daire + beyaz 'i'."""
    img = yeni()
    cizim = ImageDraw.Draw(img)
    cizim.ellipse((2, 2, S - 3, S - 3), fill=MAVI)
    orta = S // 2
    daire(cizim, orta, int(S * 0.30), int(S * 0.055))
    bar(cizim, orta, int(S * 0.42), int(S * 0.74), int(S * 0.11))
    return img


def uyari() -> Image.Image:
    """dialog-warning-symbolic: içi dolu üçgen + beyaz '!'."""
    img = yeni()
    cizim = ImageDraw.Draw(img)
    cizim.polygon(
        [(S // 2, 1), (S - 1, S - 2), (1, S - 2)], fill=SARI)
    orta = S // 2
    bar(cizim, orta, int(S * 0.36), int(S * 0.66), int(S * 0.11))
    daire(cizim, orta, int(S * 0.80), int(S * 0.06))
    return img


def onemli() -> Image.Image:
    """emblem-important-symbolic: 8 köşeli rozet (yıldız) + beyaz '!'."""
    img = yeni()
    cizim = ImageDraw.Draw(img)
    import math
    dis, ic = S * 0.48, S * 0.36
    noktalar = []
    for i in range(16):
        r = dis if i % 2 == 0 else ic
        a = math.pi * i / 8
        noktalar.append((S / 2 + r * math.sin(a), S / 2 - r * math.cos(a)))
    cizim.polygon(noktalar, fill=KIRMIZI)
    orta = S // 2
    bar(cizim, orta, int(S * 0.30), int(S * 0.62), int(S * 0.11))
    daire(cizim, orta, int(S * 0.76), int(S * 0.06))
    return img


def konum() -> Image.Image:
    """Konum işaretçisi (pin): daire + alt sivri uç, ortası boş."""
    img = yeni()
    cizim = ImageDraw.Draw(img)
    import math
    r = S * 0.30
    cx, cy = S / 2, S * 0.36
    cizim.ellipse((cx - r, cy - r, cx + r, cy + r), fill=MAVI)
    # alt sivri uç: dairenin altından tek noktaya üçgen
    cizim.polygon(
        [(cx - r * 0.62, cy + r * 0.55),
         (cx + r * 0.62, cy + r * 0.55),
         (cx, S * 0.97)], fill=MAVI)
    daire(cizim, cx, cy, r * 0.42)  # ortadaki boşluk zemin renginde değil:
    # şeffaf olması için daireyi sil (yalnız içi boş görünsün)
    maske = Image.new("L", (S, S), 0)
    ImageDraw.Draw(maske).ellipse(
        (cx - r * 0.42, cy - r * 0.42, cx + r * 0.42, cy + r * 0.42),
        fill=255)
    alfa = img.getchannel("A")
    from PIL import ImageChops
    img.putalpha(ImageChops.subtract(alfa, maske))
    return img


def main():
    ciktilar = (
        ("deprem_dusuk.png", bilgi()),
        ("deprem_orta.png", uyari()),
        ("deprem_yuksek.png", onemli()),
        ("deprem_konum.png", konum()),
    )
    for ad, img in ciktilar:
        ad_kok = ad[:-4]
        for boyut in (18, 48):
            ek = "" if boyut == 18 else "_48"
            yol = os.path.join(HEDEF, f"{ad_kok}{ek}.png")
            img.resize((boyut, boyut), Image.LANCZOS).save(yol)
            print(f"yazıldı: {yol}")


if __name__ == "__main__":
    main()
