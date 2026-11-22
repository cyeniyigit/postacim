#!/usr/bin/env python3
"""Randevu kaydetme (yeni kayıt / güncelleme) testleri — ağ gerektirmez.

Kapsar:
- "ekle" işlevinde seçilen takvim kaynağının doğru okunması
  (regresyon: islev[2] başlangıç datetime'ine bakıyordu → kaynak
   yanlış çözülüyor, "datetime.datetime object is not subscriptable")
- CalDAV ve EWS hedeflerinin doğru seçilmesi
- Zamanların (gece yarısı, tüm gün) aynen aktarılması

Kullanim:  python3 tests/randevu_ekle_test.py
"""
from __future__ import annotations

import os
import sys
from datetime import date, datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from postacim import ui  # noqa: E402

HATALAR = []


def kontrol(kosul, mesaj):
    if kosul:
        print(f"  ✓ {mesaj}")
    else:
        HATALAR.append(mesaj)
        print(f"  !! {mesaj}")


class SahteCalDav:
    """CalDAV istemcisi taklidi — çağrıları kaydeder."""

    def __init__(self):
        self.eklenen = []
        self.guncellenen = []

    def randevu_ekle(self, baslik, baslangic, bitis, konum="", aciklama="",
                     tum_gun=False, rrule=""):
        self.eklenen.append({
            "baslik": baslik, "baslangic": baslangic, "bitis": bitis,
            "konum": konum, "aciklama": aciklama, "tum_gun": tum_gun,
            "rrule": rrule,
        })

    def randevu_guncelle(self, r):
        self.guncellenen.append(r)


class SahteEws:
    """EWS istemcisi taklidi."""

    def __init__(self):
        self.eklenen = []
        self.guncellenen = []

    def randevu_ekle(self, baslik, baslangic, bitis, konum="", aciklama="",
                     tum_gun=False, rrule=""):
        self.eklenen.append({
            "baslik": baslik, "baslangic": baslangic, "bitis": bitis,
            "konum": konum, "aciklama": aciklama, "tum_gun": tum_gun,
            "rrule": rrule,
        })

    def randevu_guncelle(self, r):
        self.guncellenen.append(r)


class SahteAyarlar:
    def __init__(self, hesap):
        self._hesap = hesap

    def aktif_hesap(self):
        return self._hesap


class SahteAna:
    """RandevuPenceresi'nin ihtiyaç duyduğu arayüz taklidi."""

    def __init__(self, kaynaklar):
        self._kaynaklar = kaynaklar
        self._caldav = SahteCalDav()
        self._ews = SahteEws()
        self.aktif_hesap = {"tur": "ews", "id": "ews1"}
        self.ayarlar = SahteAyarlar(self.aktif_hesap)
        self.aktif_id = "ews1"
        self._istemciler = {"ews1": self._ews}

    def _takvim_kaynaklari(self):
        return self._kaynaklar

    def _caldav_istemci(self, takvim):
        return self._caldav

    def _kaynak_caldav(self, kaynak_id=""):
        for tur, veri in self._kaynaklar:
            if tur == "caldav" and (not kaynak_id or veri.get("id") == kaynak_id):
                return veri
        return None


class SahteRandevu:
    def __init__(self, url="", item_id="", kaynak_id=""):
        self.url = url
        self.item_id = item_id
        self.kaynak_id = kaynak_id
        self.baslik = "başlık"
        self.baslangic = "2026-11-24T22:00:00Z"
        self.bitis = "2026-11-24T22:30:00Z"
        self.konum = ""
        self.aciklama = ""
        self.tum_gun = False
        self.rrule = ""


def kaydet_cek(ana, islev):
    """RandevuPenceresi._kaydet_cek'i sahte `ana` ile çağırır."""
    sahte = ui.RandevuPenceresi.__new__(ui.RandevuPenceresi)
    sahte.ana = ana
    return ui.RandevuPenceresi._kaydet_cek(sahte, islev)


def ekle_test():
    print("\n== yeni randevu ekleme ==")
    kaynaklar = [
        ("ews", {"tur": "ews", "id": "ews1", "ad": "Kurum"}),
        ("caldav", {"tur": "caldav", "id": "cal1", "ad": "Gmail",
                    "url": "https://ornek/dav/"}),
    ]
    bas = datetime(2026, 11, 25, 1, 0)
    bit = datetime(2026, 11, 25, 1, 30)

    # --- CalDAV hedefi
    ana = SahteAna(kaynaklar)
    kaydet_cek(ana, ("ekle", "Not", bas, bit, "", "", False,
                      kaynaklar[1], ""))
    kontrol(len(ana._caldav.eklenen) == 1, "CalDAV hedefi: randevu eklendi")
    kontrol(not ana._ews.eklenen, "CalDAV hedefi: EWS'e yazılmadı")
    if ana._caldav.eklenen:
        k = ana._caldav.eklenen[0]
        kontrol(k["baslik"] == "Not", "başlık aktarıldı")
        kontrol(k["baslangic"] == bas, "başlangıç saati aktarıldı (gece 01:00)")
        kontrol(k["bitis"] == bit, "bitiş saati aktarıldı (01:30)")
        kontrol(k["rrule"] == "", "tekrarlama kuralı boş")

    # --- EWS hedefi
    ana = SahteAna(kaynaklar)
    kaydet_cek(ana, ("ekle", "Not", bas, bit, "", "", False,
                      kaynaklar[0], ""))
    kontrol(len(ana._ews.eklenen) == 1, "EWS hedefi: randevu eklendi")
    kontrol(not ana._caldav.eklenen, "EWS hedefi: CalDAV'a yazılmadı")
    if ana._ews.eklenen:
        k = ana._ews.eklenen[0]
        kontrol(k["baslangic"] == bas and k["bitis"] == bit,
                "EWS: saatler aktarıldı")

    # --- Kaynak seçilmediyse ilk kaynak kullanılır
    ana = SahteAna(kaynaklar)
    try:
        kaydet_cek(ana, ("ekle", "Not", bas, bit, "", "", False, None, ""))
        kontrol(len(ana._ews.eklenen) == 1, "kaynak yok → ilk kaynak (EWS)")
    except Exception as exc:  # noqa: BLE001
        kontrol(False, f"kaynak yokken hata: {exc}")

    # --- Tüm gün + tekrarlama kuralı
    ana = SahteAna(kaynaklar)
    kaydet_cek(ana, ("ekle", "Her hafta", bas, bit, "Oda", "not", True,
                      kaynaklar[1], "FREQ=WEEKLY;BYDAY=WE;COUNT=5"))
    if ana._caldav.eklenen:
        k = ana._caldav.eklenen[0]
        kontrol(k["tum_gun"] is True, "tüm gün bilgisi aktarıldı")
        kontrol(k["rrule"] == "FREQ=WEEKLY;BYDAY=WE;COUNT=5", "RRULE aktarıldı")
        kontrol(k["aciklama"] == "not", "açıklama aktarıldı")


def guncelle_test():
    print("\n== randevu güncelleme ==")
    kaynaklar = [
        ("caldav", {"tur": "caldav", "id": "cal1", "ad": "Gmail"}),
    ]
    ana = SahteAna(kaynaklar)

    # CalDAV kaydı (url var) → CalDAV'da güncellenir
    r = SahteRandevu(url="https://ornek/dav/x.ics", kaynak_id="cal1")
    kaydet_cek(ana, ("guncelle", r, kaynaklar[0]))
    kontrol(len(ana._caldav.guncellenen) == 1, "CalDAV kaydı CalDAV'da güncellendi")
    kontrol(not ana._ews.guncellenen, "CalDAV kaydı EWS'e gitmedi")

    # EWS kaydı (item_id var) → EWS'de güncellenir
    ana2 = SahteAna(kaynaklar + [("ews", {"tur": "ews", "id": "ews1"})])
    r2 = SahteRandevu(item_id="abc", kaynak_id="ews1")
    kaydet_cek(ana2, ("guncelle", r2, ("ews", {"tur": "ews", "id": "ews1"})))
    kontrol(len(ana2._ews.guncellenen) == 1, "EWS kaydı EWS'te güncellendi")


def main() -> int:
    ekle_test()
    guncelle_test()
    if HATALAR:
        print(f"\n!! {len(HATALAR)} HATA:")
        for h in HATALAR:
            print("   ", h)
        return 1
    print("\n✓ tüm testler geçti")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
