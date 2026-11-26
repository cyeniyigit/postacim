"""Randevu hatırlatıcısı testleri (çevrimdışı, Tk'süz)."""

import os
import sys
import unittest
from datetime import datetime, timedelta, timezone
from unittest import mock

os.environ["POSTACIM_GUNCELLEME"] = "0"  # gerçek ağ denetimi asla başlamasın

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, KOK)

from postacim.ews import Randevu  # noqa: E402


class _SahteAyarlar:
    def __init__(self, veri=None):
        self.veri = dict(veri or {})

    def al(self, anahtar, varsayilan=None):
        return self.veri.get(anahtar, varsayilan)

    def ayarla(self, anahtar, deger):
        self.veri[anahtar] = deger

    def kaydet(self):
        pass


def _govde(randevular, dakika=10, yuklendi=True, tamamlanmis=False):
    import types

    g = types.SimpleNamespace()
    g.ayarlar = _SahteAyarlar({"hatirlatici_dakika": dakika})
    g.takvim_yuklendi = yuklendi
    g.randevular = list(randevular)
    g._genis_randevular = []
    g._hatirlatilan = {}
    g._bildirim_gonder = mock.Mock(return_value=True)
    g.durum = mock.Mock()
    if randevular and tamamlanmis:
        randevular[0].tamamlandi = True
    return g


class HatirlaticiTest(unittest.TestCase):
    def test_yaklasan_randevu_uyarilir(self):
        from postacim.ui import Postacim

        bas = (datetime.now() + timedelta(minutes=5)).strftime(
            "%Y-%m-%dT%H:%M:%S")
        r = Randevu(item_id="a1", baslik="Boyun Mr", baslangic=bas)
        g = _govde([r])
        Postacim._hatirlaticlari_denle(g)
        g._bildirim_gonder.assert_called_once()
        baslik, govde = g._bildirim_gonder.call_args.args
        self.assertIn("hatırlat", baslik.lower())
        self.assertIn("Boyun Mr", govde)

    def test_zli_damga_uyarilir(self):
        """EWS/Google'ın Z'li (bilinçli) damgalarıyla çökmemeli (0.1.39)."""
        from postacim.ui import Postacim

        bas = (datetime.now(timezone.utc) + timedelta(minutes=5)).strftime(
            "%Y-%m-%dT%H:%M:%SZ")
        r = Randevu(item_id="a1", baslik="Boyun Mr", baslangic=bas)
        g = _govde([r])
        Postacim._hatirlaticlari_denle(g)
        g._bildirim_gonder.assert_called_once()

    def test_ofsetli_damga_uyarilir(self):
        from postacim.ui import Postacim

        yerel = datetime.now().astimezone()
        bas = (yerel + timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%S%z")
        r = Randevu(item_id="a1", baslik="Deneme", baslangic=bas)
        g = _govde([r])
        Postacim._hatirlaticlari_denle(g)
        g._bildirim_gonder.assert_called_once()

    def test_bir_randevu_iki_kez_uyarilmaz(self):
        from postacim.ui import Postacim

        bas = (datetime.now() + timedelta(minutes=5)).strftime(
            "%Y-%m-%dT%H:%M:%S")
        r = Randevu(item_id="a1", baslik="Deneme", baslangic=bas)
        g = _govde([r])
        Postacim._hatirlaticlari_denle(g)
        Postacim._hatirlaticlari_denle(g)
        self.assertEqual(g._bildirim_gonder.call_count, 1)

    def test_pencere_disindakiler_uyarilmaz(self):
        from postacim.ui import Postacim

        gecmis = (datetime.now() - timedelta(minutes=2)).strftime(
            "%Y-%m-%dT%H:%M:%S")
        uzak = (datetime.now() + timedelta(minutes=45)).strftime(
            "%Y-%m-%dT%H:%M:%S")
        r1 = Randevu(item_id="a1", baslik="Başlamış", baslangic=gecmis)
        r2 = Randevu(item_id="a2", baslik="Uzak", baslangic=uzak)
        g = _govde([r1, r2], dakika=10)
        Postacim._hatirlaticlari_denle(g)
        g._bildirim_gonder.assert_not_called()

    def test_tamamlanmis_uyarilmaz(self):
        from postacim.ui import Postacim

        bas = (datetime.now() + timedelta(minutes=5)).strftime(
            "%Y-%m-%dT%H:%M:%S")
        r = Randevu(item_id="a1", baslik="Bitmiş", baslangic=bas,
                    tamamlandi=True)
        g = _govde([r])
        Postacim._hatirlaticlari_denle(g)
        g._bildirim_gonder.assert_not_called()

    def test_kapali_ken_uyarilmaz(self):
        from postacim.ui import Postacim

        bas = (datetime.now() + timedelta(minutes=5)).strftime(
            "%Y-%m-%dT%H:%M:%S")
        r = Randevu(item_id="a1", baslik="Deneme", baslangic=bas)
        g = _govde([r], dakika=0)
        Postacim._hatirlaticlari_denle(g)
        g._bildirim_gonder.assert_not_called()

    def test_takvim_yuklenmemisken_uyarilmaz(self):
        from postacim.ui import Postacim

        bas = (datetime.now() + timedelta(minutes=5)).strftime(
            "%Y-%m-%dT%H:%M:%S")
        r = Randevu(item_id="a1", baslik="Deneme", baslangic=bas)
        g = _govde([r], yuklendi=False)
        Postacim._hatirlaticlari_denle(g)
        g._bildirim_gonder.assert_not_called()


if __name__ == "__main__":
    unittest.main(verbosity=2)
