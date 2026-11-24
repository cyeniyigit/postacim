#!/usr/bin/env python3
"""Tema testi: "mavi" (Visual Studio tarzı koyu lacivert) teması.

Kapsar:
- hesap.json'da "tema": "mavi" → açılışta palet uygulanır (Treeview
  zemini lacivert, seçim vurgusu mavi)
- tema_degistir("light") → eski açık temaya dönüş + tercih kaydı
- Ayarlar penceresinde "Mavi" seçeneği var ve mevcut temayı gösterir

Kullanim:  xvfb-run -a .venv/bin/python tests/tema_test.py
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import time

os.environ["POSTACIM_GUNCELLEME"] = "0"  # gerçek ağ denetimi asla başlamasın

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

    def klasor_listesi(self):
        return [Klasor(kimlik="inbox", ad="Gelen Kutusu", toplam=0,
                       okunmamis=0)]

    def mesajlar(self, klasor="inbox", sayfa_boyutu=50, offset=0, arama="",
                 alan="konu", tam=False, tazele=True):
        ms = [
            Mesaj(item_id="m1", konu="deneme", gonderen="a@b.c",
                  tarih="24.11.2026 10:00", okundu=True, klasor=klasor,
                  tariham="2026-11-24T10:00:00"),
        ]
        return ms[offset:offset + sayfa_boyutu], len(ms)

    def guncelle(self, klasorler=None):
        return {}

    def cozumle(self, metin, en_fazla=20):
        return []

    def mesaj_detay(self, mesaj):
        return mesaj

    def okundu_isaretle(self, mesaj, okundu=True):
        mesaj.okundu = okundu

    def tasi(self, mesaj, hedef="deleteditems"):
        pass

    def mesaj_mime(self, mesaj_id):
        return b"From: x\r\n\r\n"


def bekle(uygulama, saniye):
    bitis = time.time() + saniye
    while time.time() < bitis:
        uygulama.update()
        time.sleep(0.05)


def main() -> int:
    dizin = tempfile.mkdtemp(prefix="tema_test_")
    yol = os.path.join(dizin, "hesap.json")
    with open(yol, "w", encoding="utf-8") as f:
        json.dump({
            "hesaplar": [
                {"id": "kurum001", "ad": "Kurum", "tur": "ews",
                 "sunucu": "mail.ornek.gov.tr", "kullanici": "KURUM\\kisi",
                 "parola": "sifre", "yontem": "ntlm", "son_klasor": "inbox"},
            ],
            "aktif": "kurum001",
            "tema": "mavi", "otomatik_yenile": 0,
        }, f, ensure_ascii=False, indent=2)

    eski_ayarlar, eski_kur = ui_mod.Ayarlar, ui_mod.Postacim._istemci_kur
    ui_mod.Ayarlar = lambda: Ayarlar(yol)
    ui_mod.Postacim._istemci_kur = lambda self, hesap: SahteIstemci(hesap)

    uygulama = ui_mod.Postacim()
    try:
        bekle(uygulama, 2)

        # --- mavi palet açılışta uygulanmış ---
        kontrol(uygulama.tema == "mavi", f"tema tercihi 'mavi' "
                f"({uygulama.tema!r})")
        kontrol(uygulama.style.lookup("Treeview", "background") == "#143653",
                f"Treeview zemini lacivert "
                f"({uygulama.style.lookup('Treeview', 'background')})")
        kontrol(uygulama.cget("background") == "#0d2137",
                "kök pencere zemini lacivert")
        secili = dict(uygulama.style.map("Treeview", "background")).get("selected")
        kontrol(secili == "#2b6cb0", f"seçim vurgusu mavi ({secili})")

        # --- açık temaya dönüş + tercih kaydı ---
        uygulama._tema_degistir("light")
        bekle(uygulama, 0.5)
        kontrol(uygulama.tema == "light", "tema 'light' olarak değişti")
        kontrol(uygulama.style.lookup("Treeview", "background") != "#143653",
                "lacivert palet kalktı")
        tercih = json.load(open(yol, encoding="utf-8"))
        kontrol(tercih.get("tema") == "light", "tercih hesap.json'a yazıldı")

        # --- maviye geri dönüş ---
        uygulama._tema_degistir("mavi")
        bekle(uygulama, 0.5)
        kontrol(uygulama.style.lookup("Treeview", "background") == "#143653",
                "mavi temaya geri dönüş çalışıyor")

        # --- Ayarlar penceresinde dropdown her zaman geçerli temayı gösterir ---
        ayarlar = ui_mod.AyarlarPenceresi(uygulama)
        kontrol(ayarlar.tema_degisken.get() == "Mavi",
                f"dropdown mevcut temayı gösterir "
                f"({ayarlar.tema_degisken.get()!r})")
        kontrol(ayarlar.tema_combo.cget("values") == ("Açık", "Koyu", "Mavi")
                and ayarlar.tema_combo.winfo_class() == "TCombobox",
                f"tema seçimi dropdown'da ({ayarlar.tema_combo.cget('values')})")
        kontrol(not any(r.winfo_class() == "TRadiobutton"
                        for r in [ayarlar.tema_combo]),
                "tema seçimi artık radyo düğmesi değil")
        ayarlar.destroy()
    finally:
        uygulama.destroy()

    # --- Varsayılan tema: tercih yoksa "Koyu" (dark) olmalı ---
    dizin2 = tempfile.mkdtemp(prefix="tema_test_default_")
    yol2 = os.path.join(dizin2, "hesap.json")
    with open(yol2, "w", encoding="utf-8") as f:
        json.dump({
            "hesaplar": [
                {"id": "kurum001", "ad": "Kurum", "tur": "ews",
                 "sunucu": "mail.ornek.gov.tr", "kullanici": "KURUM\\kisi",
                 "parola": "sifre", "yontem": "ntlm", "son_klasor": "inbox"},
            ],
            "aktif": "kurum001", "otomatik_yenile": 0,
        }, f, ensure_ascii=False, indent=2)
    ui_mod.Ayarlar = lambda: Ayarlar(yol2)
    uygulama = ui_mod.Postacim()
    try:
        kontrol(uygulama.tema == "dark",
                f"tercih yokken varsayılan tema Koyu ({uygulama.tema!r})")
        ayarlar = ui_mod.AyarlarPenceresi(uygulama)
        kontrol(ayarlar.tema_degisken.get() == "Koyu",
                f"dropdown varsayılan 'Koyu' gösterir "
                f"({ayarlar.tema_degisken.get()!r})")
        ayarlar.destroy()
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
