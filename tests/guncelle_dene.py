#!/usr/bin/env python3
"""Gonder/Al (artimli guncelleme) denemesi: gercek sunucuya baglanir.

Tam senkron -> onbellekten okuma -> guncelle() (artimli) sirasini olcer;
artimli guncellemenin hizli ve tutarli oldugunu dogrular.

Kullanim:  .venv/bin/python tests/guncelle_dene.py
"""
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from postacim.config import Ayarlar
from postacim.ews import EwsHata, EwsIstemci


def main() -> int:
    ayarlar = Ayarlar()
    parola = ayarlar.al("parola", "")
    if not parola:
        print("Kayitli parola yok; once uygulamadan giris yapin.")
        return 1
    istemci = EwsIstemci(
        sunucu=ayarlar.al("sunucu", "mail.kurum.gov.tr"),
        kullanici=ayarlar.al("kullanici"),
        parola=parola,
    )

    baslangic = time.time()
    try:
        _, toplam = istemci.mesajlar("inbox", sayfa_boyutu=50, tam=True)
    except EwsHata as exc:
        print(f"BAŞARISIZ (tam senkron): {exc}")
        return 1
    print(f"✓ tam senkron   : {toplam} mesaj ({time.time() - baslangic:.1f} sn)")

    baslangic = time.time()
    sayfa, _ = istemci.mesajlar("inbox", sayfa_boyutu=50, tazele=False)
    print(f"✓ onbellek okuma: {len(sayfa)} mesaj ({time.time() - baslangic:.2f} sn)")

    for tur in (1, 2):
        baslangic = time.time()
        try:
            yeni = istemci.guncelle()
        except EwsHata as exc:
            print(f"BAŞARISIZ (guncelle #{tur}): {exc}")
            return 1
        print(f"✓ guncelle() #{tur}: {yeni} ({time.time() - baslangic:.1f} sn)")

    _, toplam2 = istemci.mesajlar("inbox", sayfa_boyutu=50, tazele=False)
    uyum = "sayi tutarli" if toplam == toplam2 else f"SAYI DEGISTI ({toplam} → {toplam2})"
    print(f"✓ son durum     : {toplam2} mesaj — {uyum}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
