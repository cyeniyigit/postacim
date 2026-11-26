"""Kandilli Rasathanesi son depremler (KOERI) istemcisi.

http://www.koeri.boun.edu.tr/scripts/lst0.asp sayfası HTTPS sunulmayan,
windows-1254 kodlu düz bir HTML'dir. Buradaki ayrıştırıcı, aynı veriyi
okuyan GNOME "kandilli-quake" eklentisiyle aynı kuralları izler:

- Satır biçimi: Tarih Saat Enlem Boylam Derinlik MD ML Mw Yer  Çözüm Niteliği
- Yer ile Çözüm Niteliği arasında en az 2 boşluk; Yer'in kendi içinde
  tek boşluk olabilir ("ONIKI ADALAR (EGE DENIZI)").
- Büyüklük önce ML'den; yoksa ("-.-") Mw'dan, o da yoksa MD'den okunur.
- Virgüller ondalık ayracı olduğundan sayfada önce virgül → nokta yapılır.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import datetime

import requests

KANDILLI_URL = "http://www.koeri.boun.edu.tr/scripts/lst0.asp"


@dataclass
class Deprem:
    tarih: str   # 2026.11.26
    saat: str    # 20:38:53
    ml: float
    yer: str


# <pre> bloğu (sayfada tek)
_PRE = re.compile(r"<pre[^>]*>([\s\S]*?)</pre>", re.IGNORECASE)

# Tarih Saat Enlem Boylam Derinlik MD ML Mw Yer (gerisi serbest)
_SATIR = re.compile(
    r"^(\d{4}\.\d{2}\.\d{2})\s+(\d{2}:\d{2}:\d{2})\s+"
    r"(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(.+)$"
)


def ayristir(html, bugun=None):
    """Sayfa metnindeki bugünkü satırları Deprem listesine çevirir.

    Liste sayfadaki sırayla (en yeniden eskiye) döner. `bugun` verilmezse
    yerel tarih kullanılır ("2026.11.26" biçiminde verilir).
    """
    bugun = bugun or datetime.now().strftime("%Y.%m.%d")
    eslesme = _PRE.search(html)
    if not eslesme:
        return []
    liste = []
    for satir in eslesme.group(1).split("\n"):
        m = _SATIR.match(satir.strip())
        if not m or m[1] != bugun:
            continue
        # Önce ML; yoksa Mw, o da yoksa MD ("-.-" değerler atlanır)
        ml = float("nan")
        for deger in (m[7], m[8], m[6]):
            try:
                olcek = float(deger)
            except ValueError:
                continue
            ml = olcek
            break
        if math.isnan(ml) or ml > 10.0:
            continue
        yer = re.split(r"\s{2,}", m[9])[0].strip()
        liste.append(Deprem(tarih=m[1], saat=m[2], ml=ml, yer=yer))
    return liste


def depremler():
    """Bugünkü depremleri Kandilli'den çeker; ağ/sayfa hatasında istisna verir."""
    yanit = requests.get(KANDILLI_URL, timeout=20)
    yanit.raise_for_status()
    html = yanit.content.decode("windows-1254", errors="replace")
    return ayristir(html.replace(",", "."))


def konum_anahtari(yer):
    """'KOY-ILCE (IL)' → 'ILCE (IL)'; 'KOY-(IL)' → 'MERKEZ (IL)'.

    "AKDENIZ" / "EGE DENIZI" gibi tek parçalı adlar ve tire içermeyen
    adlar olduğu gibi döner.
    """
    parantez = yer.find("(")
    bas = yer if parantez < 0 else yer[:parantez]
    tire = bas.find("-")
    if tire < 0:
        return yer
    kalan = yer[tire + 1:].strip()
    return f"MERKEZ {kalan}" if kalan.startswith("(") else kalan


def konum_istatistikleri(depremler, en_cok=10):
    """Konum başına deprem sayısı ve en yüksek büyüklük; çoktan aza sıralı."""
    sayac = {}
    for d in depremler:
        anahtar = konum_anahtari(d.yer)
        kayit = sayac.setdefault(
            anahtar, {"ad": anahtar, "sayi": 0, "en_buyuk": 0.0})
        kayit["sayi"] += 1
        kayit["en_buyuk"] = max(kayit["en_buyuk"], d.ml)
    sirali = sorted(
        sayac.values(), key=lambda k: (-k["sayi"], -k["en_buyuk"]))
    return sirali[:en_cok]
