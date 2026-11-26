"""Tamamlandı işaretinin sunucuya yazılması testleri (çevrimdışı).

- CalDAV: X-POSTACIM-TAMAMLANDI alanının okunması/yazılması/kaldırılması
- EWS: PostacimTamamlandi ExtendedProperty okuması + yazımı
  (UpdateItem engelliyse sil + yeniden oluştur yedeği)
- Arayüz: işaret birleştirmesi (sunucu + yerel kopya + eski kayıt taşıma)
"""

import os
import sys
import unittest
import xml.etree.ElementTree as ET
from unittest import mock

os.environ["POSTACIM_GUNCELLEME"] = "0"  # gerçek ağ denetimi asla başlamasın

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, KOK)

from postacim import caldav as caldav_mod  # noqa: E402
from postacim import ews as ews_mod  # noqa: E402
from postacim.caldav import RandevuKaydi  # noqa: E402
from postacim.ews import Randevu  # noqa: E402

ICS_ORNEK = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Postacim//TR
BEGIN:VEVENT
UID:test-1@postacim
DTSTAMP:20261126T080000Z
DTSTART:20261126T100000Z
DTEND:20261126T110000Z
SUMMARY:Deneme randevu
END:VEVENT
END:VCALENDAR
"""


class CaldavOkumaTest(unittest.TestCase):
    def test_alan_yok(self):
        kayitlar = caldav_mod.ics_randevulari(ICS_ORNEK)
        self.assertEqual(len(kayitlar), 1)
        self.assertFalse(kayitlar[0].tamamlandi)

    def test_alan_var(self):
        ics = ICS_ORNEK.replace(
            "END:VEVENT", "X-POSTACIM-TAMAMLANDI:TRUE\r\nEND:VEVENT")
        kayitlar = caldav_mod.ics_randevulari(ics)
        self.assertTrue(kayitlar[0].tamamlandi)


class CaldavYazmaTest(unittest.TestCase):
    def test_ekleme(self):
        ics = caldav_mod.tamamlandi_ics(ICS_ORNEK, True)
        self.assertIn("X-POSTACIM-TAMAMLANDI:TRUE", ics)
        # alan okunabilir olmalı
        self.assertTrue(caldav_mod.ics_randevulari(ics)[0].tamamlandi)

    def test_kaldirma(self):
        ics = ICS_ORNEK.replace(
            "END:VEVENT", "X-POSTACIM-TAMAMLANDI:TRUE\r\nEND:VEVENT")
        ics = caldav_mod.tamamlandi_ics(ics, False)
        self.assertNotIn("X-POSTACIM-TAMAMLANDI", ics)
        self.assertFalse(caldav_mod.ics_randevulari(ics)[0].tamamlandi)

    def test_degistirme(self):
        ics = ICS_ORNEK.replace(
            "END:VEVENT", "X-POSTACIM-TAMAMLANDI:TRUE\r\nEND:VEVENT")
        ics = caldav_mod.tamamlandi_ics(ics, True)  # ikinci kez: çoğaltmaz
        self.assertEqual(ics.count("X-POSTACIM-TAMAMLANDI"), 1)

    def test_tamamlandi_yaz_put(self):
        istemci = caldav_mod.CalDavIstemci.__new__(
            caldav_mod.CalDavIstemci)
        istemci.taban_url = "https://x/"
        r = RandevuKaydi(
            uid="test-1@postacim", url="https://x/test-1.ics", etag="e1",
            baslik="Deneme", ics=ICS_ORNEK,
        )
        istemci._istek = mock.Mock(return_value=mock.Mock(
            status_code=204, headers={"ETag": '"e2"'}))
        istemci._etag_al = mock.Mock(return_value="e2")
        istemci.tamamlandi_yaz(r, True)
        govde = istemci._istek.call_args.kwargs["veri"].decode()
        self.assertIn("X-POSTACIM-TAMAMLANDI:TRUE", govde)
        self.assertTrue(r.tamamlandi)
        self.assertEqual(r.etag, "e2")
        # kaldırma
        istemci.tamamlandi_yaz(r, False)
        govde = istemci._istek.call_args.kwargs["veri"].decode()
        self.assertNotIn("X-POSTACIM-TAMAMLANDI", govde)
        self.assertFalse(r.tamamlandi)


class EwsOkumaTest(unittest.TestCase):
    def test_genisletilmis_ozellik_okunur(self):
        xml = (
            '<t:CalendarItem xmlns:t="http://schemas.microsoft.com/exchange/'
            'services/2006/types">'
            '<t:ItemId Id="i1" ChangeKey="ck1"/>'
            "<t:Subject>Deneme</t:Subject>"
            "<t:Start>2026-11-26T10:00:00Z</t:Start>"
            "<t:End>2026-11-26T11:00:00Z</t:End>"
            "<t:ExtendedProperty>"
            f'<t:ExtendedFieldURI PropertySetId="{ews_mod.TAMAMLANDI_PSID}" '
            'PropertyName="PostacimTamamlandi" PropertyType="Boolean"/>'
            "<t:Value>true</t:Value>"
            "</t:ExtendedProperty>"
            "</t:CalendarItem>"
        )
        r = ews_mod.EwsIstemci._randevu(
            mock.Mock(), ET.fromstring(xml))
        self.assertTrue(r.tamamlandi)

    def test_istek_sekli_alan_ister(self):
        # SyncFolderItems gövdesi AdditionalProperties ile alan ister
        istemci = ews_mod.EwsIstemci.__new__(ews_mod.EwsIstemci)
        istemci._takvim_onbellek = None
        istemci.istek = mock.Mock(return_value=ET.fromstring(
            '<m:SyncFolderItemsResponseMessage xmlns:m="http://schemas.'
            'microsoft.com/exchange/services/2006/messages" '
            'xmlns:t="http://schemas.microsoft.com/exchange/services/2006/'
            'types" ResponseClass="Success">'
            "<m:IncludesLastItemInRange>true</m:IncludesLastItemInRange>"
            "<m:SyncState></m:SyncState></m:SyncFolderItemsResponseMessage>"
        ))
        list(istemci.takvim_randevulari())
        govde = istemci.istek.call_args.args[0]
        self.assertIn("AdditionalProperties", govde)
        self.assertIn(ews_mod.TAMAMLANDI_ADI, govde)


class EwsYazmaTest(unittest.TestCase):
    def _istemci(self):
        istemci = ews_mod.EwsIstemci.__new__(ews_mod.EwsIstemci)
        istemci._takvim_updateitem_destekli = True
        return istemci

    def test_updateitem_yolu(self):
        istemci = self._istemci()
        r = Randevu(item_id="i1", change_key="ck1", baslik="Deneme")
        istemci.istek = mock.Mock(return_value=ET.fromstring(
            '<m:UpdateItemResponseMessage xmlns:m="http://schemas.'
            'microsoft.com/exchange/services/2006/messages" '
            'xmlns:t="http://schemas.microsoft.com/exchange/services/2006/'
            'types" ResponseClass="Success">'
            '<m:Items><t:ItemId Id="i1" ChangeKey="ck2"/></m:Items>'
            "</m:UpdateItemResponseMessage>"
        ))
        istemci.tamamlandi_yaz(r, True)
        govde = istemci.istek.call_args.args[0]
        self.assertIn("<m:UpdateItem", govde)
        self.assertIn(ews_mod.TAMAMLANDI_ADI, govde)
        self.assertIn("<t:Value>true</t:Value>", govde)
        self.assertTrue(r.tamamlandi)
        self.assertEqual(r.change_key, "ck2")

    def test_yedek_yol_sil_yeniden_olustur(self):
        istemci = self._istemci()
        r = Randevu(
            item_id="i1", change_key="ck1", baslik="Deneme",
            baslangic="2026-11-26T10:00:00Z", bitis="2026-11-26T11:00:00Z",
        )

        def hata_ver(govde):
            raise ews_mod.EwsHata(
                "EWS yanıt kodu: ErrorSendMeetingInvitationsOrCancellationsRequired")

        istemci.istek = mock.Mock(side_effect=hata_ver)
        silinen = []
        ekle_arglari = []

        istemci.randevu_sil = lambda x: silinen.append(x.item_id)
        istemci.randevu_ekle = lambda *a, **k: (
            ekle_arglari.append((a, k)) or "yeni-id")

        istemci.tamamlandi_yaz(r, True)
        self.assertEqual(silinen, ["i1"])
        self.assertEqual(r.item_id, "yeni-id")
        self.assertTrue(r.tamamlandi)
        self.assertFalse(istemci._takvim_updateitem_destekli)
        self.assertEqual(ekle_arglari[0][1].get("tamamlandi"), True)

        # oturum içi işaret düştü: ikinci yazım doğrudan yedek yolu
        # (UpdateItem hiç denenmez; istek sayısı 1'de kalır)
        istemci.tamamlandi_yaz(r, False)
        self.assertEqual(len(istemci.istek.call_args_list), 1)
        self.assertFalse(r.tamamlandi)


class _SahteAyarlar:
    def __init__(self, veri):
        self.veri = dict(veri)

    def al(self, anahtar, varsayilan=None):
        return self.veri.get(anahtar, varsayilan)

    def ayarla(self, anahtar, deger):
        self.veri[anahtar] = deger

    def kaydet(self):
        pass


class ArayuzBirlestirmeTest(unittest.TestCase):
    """_tamamlanmalari_uygula + _randevu_tamamla (Tk'süz, sahte gövde)."""

    def _govde(self, randevular, genis=None, liste=None):
        import types

        g = types.SimpleNamespace()
        g.ayarlar = _SahteAyarlar({"tamamlanan_randevular": list(liste or [])})
        g.randevular = randevular
        g._genis_randevular = list(genis or [])
        tasinen = []
        g._tamamlanmalari_tasi = lambda kayitlar: tasinen.extend(kayitlar)
        g.tasinen = tasinen
        return g

    def test_sunucu_isareti_esastir(self):
        from postacim.ui import Postacim

        ana = Randevu(item_id="a1", tamamlandi=True)  # sunucudan geldi
        g = self._govde([ana], liste=[])
        Postacim._tamamlanmalari_uygula(g)
        self.assertTrue(ana.tamamlandi)

    def test_kopya_yerel_isareti(self):
        from postacim.ui import Postacim

        ana = Randevu(item_id="a1", tamamlandi=False)
        kopya = Randevu(
            item_id="a1", tamamlandi=False, occurrence_id="a1#20261126T100000")
        g = self._govde([ana], genis=[kopya], liste=["a1#20261126T100000"])
        Postacim._tamamlanmalari_uygula(g)
        self.assertTrue(kopya.tamamlandi)
        self.assertFalse(ana.tamamlandi)  # ana kayıt işaretlenmemiş kalır
        self.assertEqual(g.tasinen, [])  # kopya sunucuya taşınmaz

    def test_eski_yerel_isaret_tasinir(self):
        from postacim.ui import Postacim

        ana = Randevu(item_id="a1", tamamlandi=False)
        g = self._govde([ana], liste=["a1"])
        Postacim._tamamlanmalari_uygula(g, tasi=True)
        self.assertTrue(ana.tamamlandi)  # iyimser işaret
        self.assertEqual([r.kimlik for r in g.tasinen], ["a1"])

    def test_kopya_seriyi_kapsayan_isareti_devralir(self):
        from postacim.ui import Postacim

        ana = Randevu(item_id="a1", tamamlandi=True)
        kopya = ana.__class__(
            item_id="a1", tamamlandi=False, occurrence_id="a1#20261126T100000")
        g = self._govde([ana], genis=[kopya], liste=[])
        Postacim._tamamlanmalari_uygula(g)
        self.assertTrue(kopya.tamamlandi)


class ArayuzIsaretlemeTest(unittest.TestCase):
    """_randevu_tamamla: kopya → yerel liste; ana kayıt → sunucu."""

    def _govde(self, r):
        import types

        g = types.SimpleNamespace()
        g.ayarlar = _SahteAyarlar({"tamamlanan_randevular": []})
        g.durum = mock.Mock()
        g._takvim_ciz = mock.Mock()
        yazilan = []
        g._tamamlanmi_sunucuya_yaz = lambda kayit: yazilan.append(kayit)
        g.randevu = r
        return g, yazilan

    def test_ana_kayit_sunucuya(self):
        from postacim.ui import Postacim

        r = Randevu(item_id="a1")
        g, yazilan = self._govde(r)
        Postacim._randevu_tamamla(g, r)
        self.assertTrue(r.tamamlandi)
        self.assertEqual(yazilan, [r])

    def test_kopya_yerel_listeye(self):
        from postacim.ui import Postacim

        kopya = Randevu(
            item_id="a1", occurrence_id="a1#20261126T100000")
        g, yazilan = self._govde(kopya)
        g.durum.set = mock.Mock()
        Postacim._randevu_tamamla(g, kopya)
        self.assertTrue(kopya.tamamlandi)
        self.assertEqual(yazilan, [])  # sunucuya yazılmaz
        self.assertEqual(
            g.ayarlar.al("tamamlanan_randevular"),
            ["a1#20261126T100000"],
        )
        Postacim._randevu_tamamla(g, kopya)  # ikinci kez: işaret kalkar
        self.assertFalse(kopya.tamamlandi)
        self.assertEqual(g.ayarlar.al("tamamlanan_randevular"), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
