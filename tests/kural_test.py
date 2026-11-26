"""Gelen kutusu kuralları testleri (çevrimdışı)."""

import os
import sys
import unittest
from unittest import mock

os.environ["POSTACIM_GUNCELLEME"] = "0"  # gerçek ağ denetimi asla başlamasın

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, KOK)

from postacim.ews import Mesaj  # noqa: E402
from postacim.ui import _kural_eslesir  # noqa: E402


def _mesaj(item_id="1", konu="Selam", gonderen="a@b.c", gonderen_ad="Ali"):
    return Mesaj(
        item_id=item_id, change_key="", konu=konu, gonderen=gonderen,
        gonderen_ad=gonderen_ad, tarih="26.11.2026 10:00", okundu=True,
        klasor="inbox", tariham="2026-11-26T10:00:00",
    )


class EslesmeTest(unittest.TestCase):
    def test_gonderen(self):
        kural = {"alan": "gonderen", "desen": "bulten@site.com"}
        self.assertTrue(_kural_eslesir(_mesaj(gonderen="bulten@site.com"), kural))
        self.assertTrue(_kural_eslesir(_mesaj(
            gonderen="x@y.z", gonderen_ad="Bulten@site.com Dergi"), kural))
        self.assertFalse(_kural_eslesir(_mesaj(gonderen="baska@site.com"), kural))

    def test_konu_kucuk_harf_duyarsiz(self):
        kural = {"alan": "konu", "desen": "Fatura"}
        self.assertTrue(_kural_eslesir(_mesaj(konu="Kasım FATURASI"), kural))
        self.assertFalse(_kural_eslesir(_mesaj(konu="Kargo bilgisi"), kural))

    def test_bos_desen_eslesmez(self):
        self.assertFalse(_kural_eslesir(_mesaj(), {"alan": "konu", "desen": "  "}))
        self.assertFalse(_kural_eslesir(_mesaj(), {}))


class _SahteAyarlar:
    def __init__(self, veri=None):
        self.veri = dict(veri or {})

    def al(self, anahtar, varsayilan=None):
        return self.veri.get(anahtar, varsayilan)

    def ayarla(self, anahtar, deger):
        self.veri[anahtar] = deger

    def kaydet(self):
        pass


class UygulamaTest(unittest.TestCase):
    """_kurallari_uygula: taban çizgisi + yeni iletilerde taşıma."""

    def _govde(self, kurallar, gelen, taban=None, tam=True):
        import types

        istemci = types.SimpleNamespace()
        istemci.mesajlar = mock.Mock(return_value=(list(gelen), len(gelen)))
        istemci.tasi = mock.Mock()
        istemci.guncelle = mock.Mock(return_value={})
        g = types.SimpleNamespace()
        g.ayarlar = _SahteAyarlar({"posta_kurallari": kurallar})
        g.aktif_id = "h1"
        g.istemci = istemci
        g._kural_tabani = {"h1": taban}
        g._gelen_tam_mi = lambda i: tam
        return g

    KURAL = [{
        "alan": "konu", "desen": "bülten", "klasor": "k9",
        "klasor_ad": "Bültenler", "hesap": "h1",
    }]

    def test_kural_yoksa_hicbir_sey_yapilmaz(self):
        from postacim.ui import Postacim

        g = self._govde([], [_mesaj()])
        self.assertIsNone(Postacim._kurallari_uygula(g))
        g.istemci.tasi.assert_not_called()

    def test_ilk_turda_taban_alinir_tasinmaz(self):
        from postacim.ui import Postacim

        eski = _mesaj("1", konu="bülten eski")
        g = self._govde(self.KURAL, [eski], taban=None, tam=True)
        self.assertEqual(Postacim._kurallari_uygula(g), [])
        g.istemci.tasi.assert_not_called()  # taban çizgisi: taşıma YOK
        self.assertEqual(g._kural_tabani["h1"], {"1"})

    def test_oznbellek_tam_degilse_taban_alinmaz(self):
        from postacim.ui import Postacim

        g = self._govde(self.KURAL, [_mesaj("1", konu="bülten")],
                        taban=None, tam=False)
        self.assertIsNone(Postacim._kurallari_uygula(g))
        self.assertIsNone(g._kural_tabani["h1"])

    def test_yeni_iletisi_tasinir(self):
        from postacim.ui import Postacim

        eski = _mesaj("1", konu="normal")
        yeni = _mesaj("2", konu="Haftalık bülten")
        g = self._govde(self.KURAL, [eski, yeni], taban={"1"})
        sonuc = Postacim._kurallari_uygula(g)
        self.assertEqual(sonuc, [("Haftalık bülten", "Bültenler")])
        g.istemci.tasi.assert_called_once_with(yeni, "k9")
        g.istemci.guncelle.assert_called_once_with(["inbox"])

    def test_eslesmeyen_yeni_tasinmaz(self):
        from postacim.ui import Postacim

        g = self._govde(self.KURAL, [_mesaj("5", konu="Kargo bilgisi")],
                        taban=set())
        self.assertEqual(Postacim._kurallari_uygula(g), [])
        g.istemci.tasi.assert_not_called()

    def test_diger_hesabin_kurali_atlanir(self):
        from postacim.ui import Postacim

        kural = dict(self.KURAL[0], hesap="h2")
        g = self._govde([kural], [_mesaj("7", konu="bülten")], taban=set())
        self.assertIsNone(Postacim._kurallari_uygula(g))
        g.istemci.tasi.assert_not_called()

    def test_tasima_hatasi_sessiz_gecer(self):
        from postacim.ui import Postacim

        g = self._govde(self.KURAL, [_mesaj("9", konu="bülten")], taban=set())
        g.istemci.tasi = mock.Mock(side_effect=Exception("sunucu reddi"))
        self.assertEqual(Postacim._kurallari_uygula(g), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
