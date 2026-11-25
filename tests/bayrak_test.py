"""Takip (bayrak) işareti testleri (çevrimdışı).

- EWS: item:Flag UpdateItem XML üretimi + onbellek güncelleme
- IMAP: STORE \\Flagged tel denetimi (yerel mini sunucu) + okuma
- Arayüz: sağ tuş menüsünde "Takip" alt menüsü + liste konu önünde ⚑
"""

import os
import sys
import unittest
from unittest import mock

os.environ["POSTACIM_GUNCELLEME"] = "0"  # gerçek ağ denetimi asla başlamasın

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, KOK)

from postacim.ews import Mesaj, EwsHata  # noqa: E402
from postacim import ews as ews_mod  # noqa: E402
from postacim import imap as imap_mod  # noqa: E402


def _mesaj(kimlik="1", klasor="inbox", bayrak=False):
    return Mesaj(
        item_id=kimlik, change_key="ck1", konu="test", gonderen="a@b.c",
        tarih="25.11.2026 10:00", okundu=True, klasor=klasor,
        tariham="2026-11-25T10:00:00", bayrak=bayrak,
    )


class EwsBayrakTest(unittest.TestCase):
    def setUp(self):
        self.istemci = ews_mod.EwsIstemci.__new__(ews_mod.EwsIstemci)
        self.istemci._senkronizasyon = {
            "inbox": {"sirali": [], "mesajlar": {"1": _mesaj()}, "tam": True},
        }
        self.yakalanan = {}

        def sahte_istek(govde):
            self.yakalanan["govde"] = govde
            return mock.Mock(**{
                "find.return_value": None,
                "findtext.return_value": "",
                "findall.return_value": [],
            })

        self.istemci.istek = sahte_istek

    def test_bayrak_xml(self):
        self.istemci.bayrakla(_mesaj(), True, "2026-11-26")
        govde = self.yakalanan["govde"]
        self.assertIn("<t:FlagStatus>Flagged</t:FlagStatus>", govde)
        self.assertIn("item:Flag", govde)
        self.assertIn("2026-11-26T00:00:00Z", govde)
        self.assertIn('ChangeKey="ck1"', govde)

    def test_bayrak_kaldirma_xml(self):
        self.istemci.bayrakla(_mesaj(bayrak=True), False)
        self.assertIn("NotFlagged", self.yakalanan["govde"])
        self.assertNotIn("DueDate", self.yakalanan["govde"])

    def test_onbellek_guncellenir(self):
        mesaj = self.istemci._senkronizasyon["inbox"]["mesajlar"]["1"]
        self.istemci.bayrakla(mesaj, True, "2026-11-26")
        self.assertTrue(mesaj.bayrak)

    def test_sunucu_hatasi(self):
        import xml.etree.ElementTree as ET
        ET_ = ET
        yanit_xml = (
            '<s:Envelope xmlns:m="http://schemas.microsoft.com/exchange/'
            'services/2006/messages"'
            ' xmlns:t="http://schemas.microsoft.com/exchange/services/2006/types"'
            ' xmlns:s="http://www.w3.org/2003/05/soap-envelope">'
            "<s:Body><m:UpdateItemResponseMessage"
            ' ResponseClass="Error">'
            "<m:MessageText>sunucu reddi</m:MessageText>"
            "</m:UpdateItemResponseMessage></s:Body></s:Envelope>"
        )
        self.istemci.istek = lambda govde: ET_.fromstring(yanit_xml)
        with self.assertRaises(EwsHata):
            self.istemci.bayrakla(_mesaj(), True)


class ImapBayrakTest(unittest.TestCase):
    def test_onbellek_okuma(self):
        from postacim.imap import _zarf_mesaji
        m = _zarf_mesaji(b"From: a\r\nSubject: t\r\n\r\n", 5, "inbox",
                         "\\Flagged")
        self.assertTrue(m.bayrak)
        m2 = _zarf_mesaji(b"From: a\r\nSubject: t\r\n\r\n", 6, "inbox",
                          "\\Seen")
        self.assertFalse(m2.bayrak)

    def test_bayrakla_store(self):
        # Sahte _komut ile STORE komutunun tel denetimi
        istemci = imap_mod.ImapIstemci({
            "tur": "imap", "kullanici": "a@b.c",
            "gelen_sunucu": "127.0.0.1", "gelen_port": 1,
        })
        istemci._klasor_adlari = {"inbox": "INBOX"}
        komutlar = []

        def sahte_komut(ad, *args, **kwargs):
            komutlar.append((ad,) + tuple(args))
            return "OK", [b""]

        istemci._komut = sahte_komut
        istemci._secili = "INBOX"
        istemci._onbellek = {
            "inbox": {"mesajlar": {5: _mesaj("5")}, "sirali": [],
                      "sirali_arama": [], "tam": True, "uidler": {5},
                      "arama": None},
        }
        m = _mesaj("5")
        istemci.bayrakla(m, True)
        self.assertIn(("uid", "store", "5", "+FLAGS", "(\\Flagged)"),
                      komutlar)
        self.assertTrue(m.bayrak)
        istemci.bayrakla(m, False)
        self.assertIn(("uid", "store", "5", "-FLAGS", "(\\Flagged)"),
                      komutlar)
        self.assertFalse(m.bayrak)


class ArayuzTest(unittest.TestCase):
    """Sağ tuş "Takip" alt menüsü + liste ⚑ öneki (sahte istemci)."""

    @classmethod
    def setUpClass(cls):
        cls.eski = {}
        import postacim.ui as ui_mod
        cls.ui = ui_mod

    def test_menu_ve_on_ek(self):
        import json, tempfile, time
        dizin = tempfile.mkdtemp(prefix="bayrak_ui_")
        yol = os.path.join(dizin, "hesap.json")
        with open(yol, "w", encoding="utf-8") as f:
            json.dump({
                "hesaplar": [{"id": "g1", "ad": "GMail", "tur": "imap",
                              "kullanici": "deneme@gmail.com",
                              "parola": "p", "yontem": "parola",
                              "gelen_sunucu": "127.0.0.1", "gelen_port": 1,
                              "giden_sunucu": "127.0.0.1", "giden_port": 1,
                              "guvenli": "ssl", "son_klasor": "inbox"}],
                "aktif": "g1", "tema": "light", "otomatik_yenile": 0,
            }, f)
        ui = self.ui
        eski_ayarlar = ui.Ayarlar
        ui.Ayarlar = lambda: __import__(
            "postacim.config", fromlist=["Ayarlar"]).Ayarlar(yol)

        test = self
        bayraklar = []

        class SahteIstemci:
            def __init__(self, hesap): self.hesap = hesap
            def klasor_listesi(self):
                from postacim.ews import Klasor as K
                return [K(kimlik="inbox", ad="Gelen Kutusu", toplam=2,
                          okunmamis=0)]
            def mesajlar(self, *a, **k):
                from postacim.ews import Mesaj as M
                ms = [
                    M(item_id="1", change_key="", konu="Normal mesaj",
                      gonderen="a@b.c", gonderen_ad="G", tarih="25.11.2026",
                      okundu=True, klasor="inbox",
                      tariham="2026-11-25T10:00:00", bayrak=False),
                    M(item_id="2", change_key="", konu="Takipli mesaj",
                      gonderen="a@b.c", gonderen_ad="G", tarih="25.11.2026",
                      okundu=True, klasor="inbox",
                      tariham="2026-11-25T09:00:00", bayrak=True),
                ]
                return ms[::], 2
            def cozumle(self, *a, **k): return []
            def mesaj_detay(self, m): return m
            def bayrakla(self, mesaj, bayrak=True, son_tarih=""):
                test.__dict__.setdefault("bayrak_cagrilari", []).append(
                    (mesaj.item_id, bayrak, son_tarih))
            def detay_hazirla(self): pass
            def guncelle(self, k=None): return {}
            def okundu_isaretle(self, m, o=True): pass
            def tasi(self, m, h="deleteditems"): pass
            def taslağa_kaydet(self, *a, **k): return ""
            def gonder(self, *a, **k): return ""
            def mesaj_mime(self, mid): return b"From: x\r\n\r\n"
            def ek_indir(self, ek): return b""
        eski_kur = ui.Postacim._istemci_kur
        ui.Postacim._istemci_kur = lambda self, h: SahteIstemci(h)

        hatalar = []
        app = None
        try:
            app = ui.Postacim()
            bitis = time.time() + 1.2
            while time.time() < bitis:
                app.update()
                time.sleep(0.03)
            # "Takip" alt menüsü mevcut mu?
            menu = app._mesaj_menu_olustur()
            etiketler = []
            def topla(m, on):
                son = m.index("end")
                for i in range(son):
                    try:
                        etiketler.append(m.entrycget(i, "label"))
                    except Exception:
                        etiketler.append(str(m.type(i)))
            topla(menu, "")
            if not any("Takip" in str(e) for e in etiketler):
                hatalar.append("Takip alt menüsü yok")
            # Liste: ⚑ öneki (açılış akışı oturana dek bekle)
            for _deneme in range(60):
                satirlar = app.liste.get_children()
                if satirlar:
                    break
                app.update()
                time.sleep(0.05)
            satirlar = app.liste.get_children()
            if len(satirlar) != 2:
                hatalar.append(f"satır sayısı: {len(satirlar)}")
            else:
                d1 = app.liste.item(satirlar[0])["values"]
                d2 = app.liste.item(satirlar[1])["values"]
                if "⚑" in str(d1[2]):
                    hatalar.append("bayraksız mesaja ⚑ kondu")
                if "⚑" not in str(d2[2]):
                    hatalar.append(f"bayraklı mesajda ⚑ yok: {d2}")
            # takip_iaretle akışı (sağ tuş komutları)
            ilk = app.liste.get_children()[0]
            app.liste.selection_set(ilk)
            app.takip_iaretle("yarın")
            bitis = time.time() + 1.0
            while time.time() < bitis:
                app.update()
                time.sleep(0.03)
            cagri = getattr(self, "bayrak_cagrilari", [])
            if not cagri:
                hatalar.append("bayrakla çağrılmadı")
            elif cagri[0][1] is not True:
                hatalar.append(f"bayrak değeri: {cagri[0]}")
        finally:
            if app is not None:
                app.destroy()
            ui.Ayarlar = eski_ayarlar
            ui.Postacim._istemci_kur = eski_kur
        if hatalar:
            self.fail("; ".join(hatalar))


if __name__ == "__main__":
    unittest.main(verbosity=2)
