"""Global arama testleri (çevrimdışı).

- EWS: onbellekli tüm klasörlerde istemci tarafı arama (birleştirme +
  en-yeni-başa sıralama + en_fazla sınırı; klasör bilgisi taşınır)
- IMAP: klasör başına sahte sunucu araması + birleştirme
- Arayüz: "Tüm klasörler" kapsamında Klasör sütunu görünür, satıra
  klasör adı yazılır; kapsam tercihi kaydedilir.
"""

import json
import os
import sys
import tempfile
import unittest
from unittest import mock

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, KOK)

from postacim.ews import Mesaj, Klasor, EwsHata  # noqa: E402
from postacim import imap as imap_mod  # noqa: E402
from postacim import ews as ews_mod  # noqa: E402


def _mesaj(kimlik, konu, tarih, klasor, gonderen="a@b.c"):
    return Mesaj(
        item_id=kimlik, change_key="", konu=konu, gonderen=gonderen,
        gonderen_ad="Gönderen", tarih=tarih, okundu=True,
        onizleme="", klasor=klasor, tariham=tarih.replace(".", ""),
    )


class EwsGlobalAramaTest(unittest.TestCase):
    def setUp(self):
        self.istemci = ews_mod.EwsIstemci.__new__(ews_mod.EwsIstemci)
        # Yalnız önbellek/dizin parçaları kullanılır (ağ yok)
        self.istemci._senkronizasyon = {
            "inbox": {"sirali": [
                _mesaj("1", "Fatura bilgisi", "25.11.2026 09:00", "inbox"),
                _mesaj("2", "Hoş geldiniz", "20.11.2026 08:00", "inbox"),
            ], "tam": True},
            "sentitems": {"sirali": [
                _mesaj("3", "Fatura cevabı", "24.11.2026 12:00", "sentitems"),
            ], "tam": True},
        }
        self.istemci._ozel_klasor_onbellek = None

    def test_birlestirir_ve_siralar(self):
        with mock.patch.object(ews_mod.EwsIstemci, "klasor_listesi",
                               return_value=[
                                   Klasor(kimlik="inbox", ad="Gelen"),
                                   Klasor(kimlik="sentitems", ad="Gönderilmiş"),
                               ]), \
             mock.patch.object(ews_mod.EwsIstemci, "_senkronize"):
            sonuc = self.istemci.global_arama("fatura")
        # En yeni önce: 25.11 (inbox) > 24.11 (sentitems)
        self.assertEqual([m.item_id for m in sonuc], ["1", "3"])
        self.assertEqual(sonuc[0].klasor, "inbox")
        self.assertEqual(sonuc[1].klasor, "sentitems")

    def test_hatali_klasor_atlanir(self):
        self.istemci._senkronizasyon["bozuk"] = {
            "sirali": [_mesaj("9", "Fatura eski", "01.10.2026 09:00", "bozuk")],
            "tam": True,
        }
        def senkronize(k):
            if k == "bozuk":
                raise EwsHata("sunucu hatası")
        with mock.patch.object(ews_mod.EwsIstemci, "klasor_listesi",
                               return_value=[Klasor(kimlik=k, ad=k) for k in
                                             ("inbox", "bozuk", "sentitems")]), \
             mock.patch.object(ews_mod.EwsIstemci, "_senkronize", side_effect=senkronize):
            sonuc = self.istemci.global_arama("fatura")
        self.assertEqual(len(sonuc), 2)  # bozuk klasör düşer, diğerleri gelir

    def test_en_fazla_siniri(self):
        with mock.patch.object(ews_mod.EwsIstemci, "klasor_listesi",
                               return_value=[Klasor(kimlik="inbox", ad="Gelen")]), \
             mock.patch.object(ews_mod.EwsIstemci, "_senkronize"):
            sonuc = self.istemci.global_arama("hoş", en_fazla=0)
        self.assertEqual(sonuc, [])

    def test_gonderen_alani(self):
        with mock.patch.object(ews_mod.EwsIstemci, "klasor_listesi",
                               return_value=[Klasor(kimlik="inbox", ad="Gelen")]), \
             mock.patch.object(ews_mod.EwsIstemci, "_senkronize"):
            sonuc = self.istemci.global_arama("a@b.c", alan="gonderen")
        self.assertEqual(len(sonuc), 2)


class ImapGlobalAramaTest(unittest.TestCase):
    def test_birlestirir_ve_siralar(self):
        istemci = imap_mod.ImapIstemci({
            "tur": "imap", "kullanici": "deneme@gmail.com",
            "gelen_sunucu": "127.0.0.1", "gelen_port": 1,
        })
        istemci._onbellek = {
            "inbox": {"sirali_arama": [
                _mesaj("10", "Fatura bilgisi", "25.11.2026 09:00", "inbox"),
            ]},
            "sentitems": {"sirali_arama": [
                _mesaj("20", "Fatura cevabı", "24.11.2026 12:00", "sentitems"),
            ]},
        }
        def sahte_arama_yap(klasor, arama, alan, tam=False):
            pass
        with mock.patch.object(
                imap_mod.ImapIstemci, "klasor_listesi",
                return_value=[
                    Klasor(kimlik="inbox", ad="Gelen"),
                    Klasor(kimlik="sentitems", ad="Gönderilmiş"),
                ]), \
             mock.patch.object(imap_mod.ImapIstemci, "_arama_yap",
                               side_effect=sahte_arama_yap):
            sonuc = istemci.global_arama("fatura")
        self.assertEqual([m.item_id for m in sonuc], ["10", "20"])
        self.assertEqual(sonuc[1].klasor, "sentitems")


class ArayuzTest(unittest.TestCase):
    """Kapsam combobox + Klasör sütunu davranışı (Xvfb, sahte istemci)."""

    @classmethod
    def setUpClass(cls):
        cls.dizin = tempfile.mkdtemp(prefix="global_arama_ui_")
        cls.yol = os.path.join(cls.dizin, "hesap.json")
        with open(cls.yol, "w", encoding="utf-8") as f:
            json.dump({
                "hesaplar": [
                    {"id": "g1", "ad": "GMail", "tur": "imap",
                     "kullanici": "deneme@gmail.com", "parola": "p",
                     "yontem": "parola", "gelen_sunucu": "127.0.0.1",
                     "gelen_port": 1, "giden_sunucu": "127.0.0.1",
                     "giden_port": 1, "guvenli": "ssl",
                     "son_klasor": "inbox"},
                ],
                "aktif": "g1", "tema": "light", "otomatik_yenile": 0,
            }, f)
        import postacim.ui as ui_mod
        cls.ui_mod = ui_mod
        cls.eski_ayarlar = ui_mod.Ayarlar
        cls.eski_kur = ui_mod.Postacim._istemci_kur
        ui_mod.Ayarlar = lambda: __import__(
            "postacim.config", fromlist=["Ayarlar"]).Ayarlar(cls.yol)

        class SahteIstemci:
            def __init__(self, hesap): self.hesap = hesap
            def klasor_listesi(self): return []
            def mesajlar(self, *a, **k): return [], 0
            def cozumle(self, *a, **k): return []
            def mesaj_detay(self, m): return m
            def okundu_isaretle(self, m, o=True): pass
            def guncelle(self, k=None): return {}
            def global_arama(self, arama, alan="konu"):
                return [_mesaj("99", f"{arama} sonucu",
                               "25.11.2026 10:00", "sentitems")]
            def detay_hazirla(self): pass
            def taslağa_kaydet(self, *a, **k): return ""
            def gonder(self, *a, **k): return ""
            def mesaj_mime(self, mid): return b"From: x\r\n\r\n"
            def ek_indir(self, ek): return b""
        ui_mod.Postacim._istemci_kur = lambda self, h: SahteIstemci(h)

    @classmethod
    def tearDownClass(cls):
        cls.ui_mod.Ayarlar = cls.eski_ayarlar
        cls.ui_mod.Postacim._istemci_kur = cls.eski_kur

    def test_global_arama_akisi(self):
        app = self.ui_mod.Postacim()
        hatalar = []
        def kontrol(kosul, mesaj):
            if not kosul:
                hatalar.append(mesaj)
        def bekle(saniye=0.6):
            bitis = __import__("time").time() + saniye
            while __import__("time").time() < bitis:
                app.update()
                import time; time.sleep(0.03)
        try:
            bekle(0.8)
            kontrol("Tüm klasörler" in app.arama_kapsam_degisken.get()
                    or "Bu klasör" in app.arama_kapsam_degisken.get(),
                    "kapsam combobox mevcut")
            # "Tüm klasörler" seç + ara
            app.arama_kapsam_degisken.set("Tüm klasörler")
            bekle(0.3)
            kontrol(app.ayarlar.al("arama_kapsam") == "tum",
                    "kapsam tercihi kaydedildi")
            app.arama.set("fatura")
            app._arama_yap()
            bekle(1.2)
            kontrol(app._global_sonuc is not None
                    and len(app._global_sonuc) == 1,
                    "global sonuç önbelleğe alındı")
            kontrol(app.liste.winfo_viewable() and
                    "klasor" in [str(c) for c in app.liste["displaycolumns"]],
                    "Klasör sütunu görünür")
            satirlar = app.liste.get_children()
            kontrol(len(satirlar) == 1, "1 sonuç listelendi")
            degerler = app.liste.item(satirlar[0])["values"]
            kontrol(degerler[4] == "Gönderilmiş",
                    f"klasör adı sütunda: {degerler}")
            # Kapsam "Bu klasör"e dönünce sütun gizlenir
            app._global_sonuc = None
            app.arama_kapsam_degisken.set("Bu klasör")
            bekle(0.3)
            kontrol("klasor" not in [str(c) for c in app.liste["displaycolumns"]],
                    "Klasör sütunu normal görünümde gizli")
        finally:
            app.destroy()
        if hatalar:
            self.fail("; ".join(hatalar))


if __name__ == "__main__":
    unittest.main(verbosity=2)
