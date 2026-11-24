#!/usr/bin/env python3
""""Orijinali göster" arayüz testi (çevrimdışı; sahte istemci).

Kapsar:
- Gövde araç çubuğunda "Orijinali göster" düğmesi var
- Düğme tıklanınca ham MIME arka planda çekilir, "Orijinal —" penceresi açılır
- Pencere metni ham MIME kaynağını gösterir
- Büyük mesaj sınırlanır (2 MB) ve not eklenir
- Mesaj seçili değilken tıklama hata vermez, durum çubuğu bilgilendirir

Kullanim:  xvfb-run -a .venv/bin/python tests/orijinal_goster_test.py
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from postacim.config import Ayarlar  # noqa: E402
from postacim.ews import Klasor, Mesaj  # noqa: E402
import postacim.ui as ui_mod  # noqa: E402

HATALAR = []


def kontrol(kosul, mesaj):
    if kosul:
        print(f"  ✓ {mesaj}")
    else:
        HATALAR.append(mesaj)
        print(f"  !! {mesaj}")


class SahteIstemci:
    def __init__(self, hesap: dict):
        self.hesap = hesap
        self.mime_istekleri: list = []

    def klasor_listesi(self):
        return [
            Klasor(kimlik="inbox", ad="Gelen Kutusu", toplam=2, okunmamis=1),
            Klasor(kimlik="sentitems", ad="Gönderilmiş", toplam=0, okunmamis=0),
            Klasor(kimlik="drafts", ad="Taslaklar", toplam=0, okunmamis=0),
        ]

    def mesajlar(self, klasor="inbox", sayfa_boyutu=50, offset=0, arama="",
                 alan="konu", tam=False, tazele=True):
        ms = [
            Mesaj(item_id="m1", konu="deneme mesajı",
                  gonderen="gonderen@ornek.gov.tr",
                  gonderen_ad="Gönderen Kişi", tarih="24.11.2026 10:00",
                  okundu=True, klasor=klasor, tariham="2026-11-24T10:00:00"),
            Mesaj(item_id="m2", konu="ikinci mesaj",
                  gonderen="ikinci@ornek.gov.tr", tarih="23.11.2026 09:00",
                  okundu=False, klasor=klasor, tariham="2026-11-23T09:00:00"),
        ]
        return ms[offset:offset + sayfa_boyutu], len(ms)

    def guncelle(self, klasorler=None):
        return {}

    def cozumle(self, metin, en_fazla=20):
        return []

    def mesaj_detay(self, mesaj):
        mesaj.govde = "Gövde (sahte)"
        return mesaj

    def okundu_isaretle(self, mesaj, okundu=True):
        mesaj.okundu = okundu

    def tasi(self, mesaj, hedef="deleteditems"):
        pass

    def mesaj_mime(self, mesaj_id):
        self.mime_istekleri.append(mesaj_id)
        return (b"From: gonderen@ornek.gov.tr\r\n"
                b"Subject: =?utf-8?q?deneme_mesaj=C4=B1?=\r\n"
                b"\r\n g\xc3\xb6vde\r\n")


def bekle(uygulama, saniye):
    bitis = time.time() + saniye
    while time.time() < bitis:
        uygulama.update()
        time.sleep(0.05)


def orijinal_penceresi(uygulama):
    for pencere in uygulama.winfo_children():
        if isinstance(pencere, ui_mod.tk.Toplevel) and \
                pencere.title().startswith("Orijinal"):
            return pencere
    return None


def main() -> int:
    dizin = tempfile.mkdtemp(prefix="orijinal_test_")
    yol = os.path.join(dizin, "hesap.json")
    with open(yol, "w", encoding="utf-8") as f:
        json.dump({
            "hesaplar": [
                {"id": "kurum001", "ad": "Kurum", "tur": "ews",
                 "sunucu": "mail.ornek.gov.tr", "kullanici": "KURUM\\kisi",
                 "parola": "sifre", "yontem": "ntlm", "son_klasor": "inbox"},
            ],
            "aktif": "kurum001",
            "tema": "light", "otomatik_yenile": 0,
        }, f, ensure_ascii=False, indent=2)

    eski_ayarlar, eski_kur = ui_mod.Ayarlar, ui_mod.Postacim._istemci_kur
    ui_mod.Ayarlar = lambda: Ayarlar(yol)
    ui_mod.Postacim._istemci_kur = lambda self, hesap: SahteIstemci(hesap)

    uygulama = ui_mod.Postacim()
    try:
        bekle(uygulama, 3)

        # --- Düğme var ---
        kontrol(hasattr(uygulama, "orijinal_dugme") and
                uygulama.orijinal_dugme.winfo_exists(),
                "gövde araç çubuğunda düğme var")
        kontrol(uygulama.orijinal_dugme.cget("text") == "Orijinali göster",
                "düğme yazısı 'Orijinali göster'")

        # --- Mesaj seçili değilken: hata vermez, durum bilgilendirir ---
        uygulama.orijinal_goster()
        kontrol("Önce bir mesaj seçin" in uygulama.durum.get(),
                f"mesaj yokken durum uyarısı ({uygulama.durum.get()!r})")
        kontrol(orijinal_penceresi(uygulama) is None,
                "mesaj yokken pencere açılmaz")

        # --- Mesaj seç → orijinal göster ---
        uygulama.klasor_listesi.selection_set("kurum001|inbox")
        uygulama.liste.selection_set(uygulama.liste.get_children()[0])
        uygulama.liste.event_generate("<<TreeviewSelect>>")
        bekle(uygulama, 3)
        kontrol(uygulama.secili is not None, "mesaj seçildi")

        istemci = uygulama.istemci
        uygulama.orijinal_goster()
        kontrol("Orijinal içerik alınıyor" in uygulama.durum.get() or
                "deneme" in uygulama.durum.get(),
                f"tıklamada durum 'alınıyor' ({uygulama.durum.get()!r})")
        bekle(uygulama, 3)

        kontrol(istemci.mime_istekleri == ["m1"],
                f"mesaj_mime istemciden çağrıldı ({istemci.mime_istekleri})")
        pencere = orijinal_penceresi(uygulama)
        kontrol(pencere is not None, "'Orijinal —' penceresi açıldı")
        if pencere:
            kontrol("deneme mesajı" in pencere.title(),
                    f"pencere başlığında konu ({pencere.title()!r})")
            metin = None
            for cocuk in pencere.winfo_children():
                for torun in cocuk.winfo_children():
                    if torun.winfo_class() == "Text":
                        metin = torun
            kontrol(metin is not None, "pencerede metin alanı var")
            if metin:
                icerik = metin.get("1.0", "end")
                kontrol("From: gonderen@ornek.gov.tr" in icerik,
                        "ham MIME başlıkları görünür")
                kontrol("gövde" in icerik, "ham MIME gövdesi görünür")
            pencere.destroy()

        # --- Büyük mesaj: sınırlanır, not eklenir ---
        buyuk = (b"X-Cizgi: 0123456789abcdef\r\n" * 200_000)  # ~5.2 MB
        uygulama._orijinal_pencere(uygulama.secili, buyuk)
        pencere = orijinal_penceresi(uygulama)
        kontrol(pencere is not None, "büyük mesajda pencere açıldı")
        if pencere:
            metin = None
            for cocuk in pencere.winfo_children():
                for torun in cocuk.winfo_children():
                    if torun.winfo_class() == "Text":
                        metin = torun
            if metin:
                icerik = metin.get("1.0", "end")
                kontrol(len(icerik) < 2_100_000,
                        f"içerik sınırlı ({len(icerik)} karakter)")
                kontrol("ilk 2000000 karakter gösterildi" in icerik,
                        "büyük mesajda açıklama notu var")
            pencere.destroy()

        hata = list(getattr(uygulama, "_orijinal_test_hata", []) or [])
    finally:
        uygulama.destroy()
        ui_mod.Ayarlar, ui_mod.Postacim._istemci_kur = eski_ayarlar, eski_kur

    if HATALAR:
        print(f"\n!! {len(HATALAR)} hata:")
        for h in HATALAR:
            print(f"  - {h}")
        return 1
    print("\n✓ tüm kontroller geçti")
    return 0


if __name__ == "__main__":
    sys.exit(main())
