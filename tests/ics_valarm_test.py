"""iCalendar alt bileşen (VALARM) ayrıştırma testleri (çevrimdışı).

Google, olayların içine hatırlatıcı bloğu (BEGIN:VALARM…END:VALARM)
gömer; bloğun kendi "DESCRIPTION:This is an event reminder" satırı
olay açıklamasına KATILMAMALI (bkz. istekler.md 2026-11-26).
"""

import os
import sys
import unittest

os.environ["POSTACIM_GUNCELLEME"] = "0"  # gerçek ağ denetimi asla başlamasın

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, KOK)

from postacim.caldav import ics_randevulari  # noqa: E402

GOOGLE_ICS = """BEGIN:VCALENDAR
PRODID:-//Google Inc//Google Calendar 70.9054//EN
VERSION:2.0
CALSCALE:GREGORIAN
X-WR-CALNAME:deneme@gmail.com
X-WR-TIMEZONE:Europe/Istanbul
BEGIN:VEVENT
DTSTART:20261124T220000Z
DTEND:20261124T230000Z
DTSTAMP:20261122T184147Z
UID:e4ad9aa58461466aaf7b3836224caf91@postacim
CREATED:20261122T184147Z
DESCRIPTION:Boyun MR ı çekilecek
LAST-MODIFIED:20261122T184147Z
LOCATION:
SEQUENCE:0
STATUS:CONFIRMED
SUMMARY:Boyun Mr
TRANSP:OPAQUE
BEGIN:VALARM
ACTION:DISPLAY
DESCRIPTION:This is an event reminder
TRIGGER:-P0DT0H30M0S
END:VALARM
END:VEVENT
END:VCALENDAR
""".replace("\n", "\r\n")


class ValarmTest(unittest.TestCase):
    def setUp(self):
        self.kayitlar = ics_randevulari(GOOGLE_ICS)
        self.assertEqual(len(self.kayitlar), 1)
        self.r = self.kayitlar[0]

    def test_aciklama_temiz(self):
        self.assertEqual(self.r.aciklama, "Boyun MR ı çekilecek")

    def test_diger_alanlar_dokunulmaz(self):
        self.assertEqual(self.r.baslik, "Boyun Mr")
        self.assertEqual(self.r.baslangic, "2026-11-24T22:00:00Z")
        self.assertFalse(self.r.tamamlandi)

    def test_iki_hatirlatici(self):
        ics = GOOGLE_ICS.replace(
            "END:VALARM",
            "END:VALARM\r\nBEGIN:VALARM\r\nACTION:DISPLAY\r\n"
            "DESCRIPTION:Bu da ikinci hatırlatıcı\r\nTRIGGER:-P0DT1H0M0S\r\n"
            "END:VALARM")
        self.assertEqual(ics_randevulari(ics)[0].aciklama,
                         "Boyun MR ı çekilecek")

    def test_tamamlandi_alani_hatirlaticidan_etkilenmez(self):
        ics = GOOGLE_ICS.replace(
            "DESCRIPTION:This is an event reminder",
            "DESCRIPTION:This is an event reminder\r\n"
            "X-POSTACIM-TAMAMLANDI:TRUE")
        # X- alanı VALARM içinde — olay verisi sayılmaz
        self.assertFalse(ics_randevulari(ics)[0].tamamlandi)
        ics2 = GOOGLE_ICS.replace(
            "SUMMARY:Boyun Mr",
            "SUMMARY:Boyun Mr\r\nX-POSTACIM-TAMAMLANDI:TRUE")
        # X- alanı VEVENT düzeyinde — okunur
        self.assertTrue(ics_randevulari(ics2)[0].tamamlandi)


if __name__ == "__main__":
    unittest.main(verbosity=2)
