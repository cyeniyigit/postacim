#!/usr/bin/env python3
"""Postacim EWS backend smoke testi (kayitli kimlik bilgileriyle).

Kullanim:  .venv/bin/python tests/test_ews.py
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
    print(f"→ {istemci.adres}")
    baslangic = time.time()
    try:
        klasorler = istemci.klasor_listesi()
    except EwsHata as exc:
        print(f"BAŞARISIZ: {exc}")
        return 1
    print(f"✓ Bağlantı başarılı (sunucu sürümü: {istemci.surum}, {time.time() - baslangic:.1f} sn)")
    for klasor in klasorler:
        print(f"   • {klasor.ad:22} toplam={klasor.toplam:<6} okunmamış={klasor.okunmamis}")

    for kimlik in ("inbox", "sentitems"):
        baslangic = time.time()
        try:
            mesajlar, toplam = istemci.mesajlar(kimlik, sayfa_boyutu=50, tam=True)
        except EwsHata as exc:
            print(f"✗ {kimlik}: {exc}")
            continue
        print(f"\n✓ {kimlik}: {toplam} mesaj ({time.time() - baslangic:.1f} sn)")
        for m in mesajlar[:5]:
            print(f"   • {m.tarih}  {(m.gonderen_ad or m.gonderen)[:30]:32} {m.konu[:55]}")

        # Sayfalama
        sayfa2, _ = istemci.mesajlar(kimlik, sayfa_boyutu=50, offset=50)
        print(f"   2. sayfa: {len(sayfa2)} mesaj, ilk={sayfa2[0].konu[:40] if sayfa2 else '-'}")

        # Arama
        _, bulunan = istemci.mesajlar(kimlik, sayfa_boyutu=10, arama="e-posta")
        print(f"   arama ('e-posta'): {bulunan} eşleşme")

    # Tek mesaj okuma
    mesajlar, _ = istemci.mesajlar("inbox", sayfa_boyutu=1)
    if mesajlar:
        detay = istemci.mesaj_detay(mesajlar[0])
        print(f"\n✓ Mesaj gövdesi: {len(detay.govde)} karakter, {len(detay.ekler)} ek")
        print(f"   ilk 120: {detay.govde[:120]!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
