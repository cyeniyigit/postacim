#!/usr/bin/env python3
"""Tekrarlayan olay (RRULE) testi: kural ayrıştırma/üretimi, CalDAV iCalendar
ve EWS Recurrence dönüşümü, arayüzde genişletme.

Kullanim:
    .venv/bin/python tests/tekrar_test.py
    xvfb-run -a .venv/bin/python tests/tekrar_test.py   # arayüz testleri dahil
"""
from __future__ import annotations

import os
import sys
import time
from datetime import date, datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from postacim import tekrar  # noqa: E402
from postacim.caldav import RandevuKaydi, ics_randevulari  # noqa: E402
from postacim.ews import _rrule_uret  # noqa: E402

HATALAR = []


def kontrol(kosul, mesaj):
    if kosul:
        print(f"  ✓ {mesaj}")
    else:
        HATALAR.append(mesaj)
        print(f"  !! {mesaj}")


def tarihler(kural, bas, pencere=(date(2026, 1, 1), date(2026, 12, 31)), **kw):
    """Kuraldan üretilen başlangıç tarihleri (ISO dize olarak)."""
    sonuc = tekrar.tekrar_baslangiclar(
        datetime(*bas), tekrar.kural_ayikla(kural),
        pencere[0], pencere[1], **kw
    )
    return [d.strftime("%Y-%m-%d %H:%M") for d in sonuc]


# ---------------------------------------------------------------- kural ayrıştırma

def test_ayikla():
    print("— kural ayrıştırma —")
    k = tekrar.kural_ayikla("FREQ=WEEKLY;BYDAY=MO,WE;COUNT=10")
    kontrol(k.get("FREQ") == "WEEKLY", "FREQ okundu")
    kontrol(k.get("BYDAY") == "MO,WE", "BYDAY okundu")
    kontrol(k.get("COUNT") == "10", "COUNT okundu")
    kontrol(tekrar.kural_ayikla("") == {}, "bozuk kural boş sözlük verir")
    kontrol(
        tekrar.byday_ayikla("2MO,-1FR") == [(2, 0), (-1, 4)],
        "sıralı BYDAY ayrıştırma",
    )


# ---------------------------------------------------------------- tekrar üretimi

def test_uretimi():
    print("— tekrar üretimi —")
    kontrol(
        tarihler("FREQ=DAILY;COUNT=3", (2026, 1, 5, 9, 0))
        == ["2026-01-05 09:00", "2026-01-06 09:00", "2026-01-07 09:00"],
        "DAILY + COUNT",
    )
    kontrol(
        tarihler("FREQ=WEEKLY;BYDAY=MO,WE;COUNT=4", (2026, 1, 5, 9, 0))
        == [
            "2026-01-05 09:00", "2026-01-07 09:00",
            "2026-01-12 09:00", "2026-01-14 09:00",
        ],
        "WEEKLY + BYDAY",
    )
    kontrol(
        tarihler("FREQ=MONTHLY;BYMONTHDAY=15;COUNT=3", (2026, 1, 15, 10, 0))
        == ["2026-01-15 10:00", "2026-02-15 10:00", "2026-03-15 10:00"],
        "MONTHLY + BYMONTHDAY",
    )
    kontrol(
        tarihler("FREQ=MONTHLY;BYDAY=2MO;COUNT=3", (2026, 1, 12, 8, 0))
        == ["2026-01-12 08:00", "2026-02-09 08:00", "2026-03-09 08:00"],
        "MONTHLY + sıralı BYDAY (2. pazartesi)",
    )
    kontrol(
        tarihler("FREQ=MONTHLY;BYDAY=-1FR;COUNT=3", (2026, 1, 30, 8, 0))
        == ["2026-01-30 08:00", "2026-02-27 08:00", "2026-03-27 08:00"],
        "MONTHLY + son cuma",
    )
    kontrol(
        tarihler(
            "FREQ=YEARLY;COUNT=2", (2026, 3, 14, 8, 0),
            pencere=(date(2026, 1, 1), date(2027, 12, 31)),
        )
        == ["2026-03-14 08:00", "2027-03-14 08:00"],
        "YEARLY",
    )
    kontrol(
        tarihler("FREQ=DAILY;UNTIL=20260108T000000Z", (2026, 1, 5, 9, 0))
        == [
            "2026-01-05 09:00", "2026-01-06 09:00", "2026-01-07 09:00",
        ],
        "UNTIL (saat sınırı dahil)",
    )
    kontrol(
        tarihler(
            "FREQ=DAILY;COUNT=4", (2026, 1, 5, 9, 0),
            exdate={datetime(2026, 1, 6, 9, 0)},
        )
        == ["2026-01-05 09:00", "2026-01-07 09:00", "2026-01-08 09:00"],
        "EXDATE (tekrar atlanır)",
    )
    kontrol(
        tarihler(
            "FREQ=DAILY;COUNT=2", (2026, 1, 5, 9, 0),
            rdate=[datetime(2026, 1, 10, 9, 0)],
        )
        == ["2026-01-05 09:00", "2026-01-06 09:00", "2026-01-10 09:00"],
        "RDATE (ek tarih)",
    )
    # Uzak pencere: hızlı ileri atlama doğru sonucu vermeli
    kontrol(
        tarihler(
            "FREQ=WEEKLY;BYDAY=TU", (2026, 1, 6, 9, 0),
            pencere=(date(2027, 6, 1), date(2027, 6, 30)),
        )
        == [
            "2027-06-01 09:00", "2027-06-08 09:00", "2027-06-15 09:00",
            "2027-06-22 09:00", "2027-06-29 09:00",
        ],
        "sınırsız kural uzak pencerede de doğru üretilir",
    )
    kontrol(
        len(tarihler("FREQ=DAILY", (2020, 1, 1, 9, 0),
                     pencere=(date(2026, 3, 1), date(2026, 3, 31)))) == 31,
        "uzun süredir devam eden günlük tekrar (pencere sınırlı)",
    )
    kontrol(
        tekrar.kural_ozeti(tekrar.kural_ayikla("FREQ=WEEKLY;BYDAY=MO,WE;COUNT=10"))
        == "Her hafta (Pzt, Çar) — 10 kez",
        "kural özeti",
    )


# ---------------------------------------------------------------- CalDAV / iCalendar

ICS_TEKRAR = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Test//TR
BEGIN:VEVENT
UID:tekrar-1@postacim
DTSTAMP:20251101T090000Z
DTSTART;TZID=Europe/Istanbul:20260105T100000
DTEND;TZID=Europe/Istanbul:20260105T110000
RRULE:FREQ=WEEKLY;BYDAY=MO;COUNT=5
SUMMARY:Haftalık toplantı
LOCATION:Salon A
END:VEVENT
END:VCALENDAR
"""

ICS_EXDATE = """BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
UID:tekrar-2@postacim
DTSTART:20260105T100000
DTEND:20260105T110000
RRULE:FREQ=DAILY;COUNT=4
EXDATE;TZID=Europe/Istanbul:20260106T100000
SUMMARY:Günlük
END:VEVENT
END:VCALENDAR
"""


def test_ics():
    print("— iCalendar ayrıştırma —")
    kayitlar = ics_randevulari(ICS_TEKRAR)
    kontrol(len(kayitlar) == 1, "bir VEVENT okundu")
    k = kayitlar[0]
    kontrol(k.rrule == "FREQ=WEEKLY;BYDAY=MO;COUNT=5", "RRULE alındı")
    kontrol(k.tur == "Recurring", "tekrarlı olarak işaretlendi")
    kontrol(k.baslik == "Haftalık toplantı", "başlık okundu")
    kontrol(k.konum == "Salon A", "konum okundu")
    # TZID: 10:00 Europe/Istanbul → 07:00 UTC (yaz saati UTC+3)
    kontrol(
        k.baslangic.endswith("Z") and k.baslangic.startswith("2026-01-05T07:00"),
        f"TZID → UTC dönüşümü ({k.baslangic})",
    )
    kontrol(k.bitis.startswith("2026-01-05T08:00"), "DTEND TZID dönüşümü")

    kayitlar2 = ics_randevulari(ICS_EXDATE)
    k2 = kayitlar2[0]
    kontrol(bool(k2.exdate), "EXDATE alındı")
    kontrol(
        k2.exdate.startswith("2026-01-06T07:00"),
        f"EXDATE TZID dönüşümü ({k2.exdate})",
    )


# ---------------------------------------------------------------- EWS Recurrence

def test_ews_rrule():
    print("— EWS Recurrence → RRULE —")
    import xml.etree.ElementTree as ET

    from postacim.ews import NS

    def _xml(metin):
        return ET.fromstring(
            f'<t:Recurrence xmlns:t="http://schemas.microsoft.com/exchange/services/2006/types">'
            f"{metin}</t:Recurrence>"
        )

    haftalik = _xml(
        "<t:Pattern><t:WeeklyPattern><t:Interval>2</t:Interval>"
        "<t:DaysOfWeek><t:Day>Monday</t:Day><t:Day>Wednesday</t:Day>"
        "</t:DaysOfWeek></t:WeeklyPattern></t:Pattern>"
        "<t:Range><t:NumberOfOccurrences>10</t:NumberOfOccurrences></t:Range>"
    )
    kontrol(
        _rrule_uret(haftalik) == "FREQ=WEEKLY;INTERVAL=2;BYDAY=MO,WE;COUNT=10",
        f"haftalık desen ({_rrule_uret(haftalik)})",
    )

    gunluk = _xml(
        "<t:Pattern><t:DailyPattern><t:Interval>1</t:Interval></t:DailyPattern>"
        "</t:Pattern><t:Range><t:NoEnd>true</t:NoEnd></t:Range>"
    )
    kontrol(_rrule_uret(gunluk) == "FREQ=DAILY", "günlük desen (sınırsız)")

    aylik = _xml(
        "<t:Pattern><t:RelativeMonthlyPattern><t:DaysOfWeek>"
        "<t:Day>Monday</t:Day></t:DaysOfWeek><t:Index>Second</t:Index>"
        "</t:RelativeMonthlyPattern></t:Pattern>"
        "<t:Range><t:EndDate>2026-12-31T00:00:00</t:EndDate></t:Range>"
    )
    kural = _rrule_uret(aylik)
    kontrol(kural.startswith("FREQ=MONTHLY;BYDAY=2MO"), f"göreli aylık ({kural})")
    kontrol("UNTIL=" in kural, "bitiş tarihi UNTIL'e çevrildi")

    yillik = _xml(
        "<t:Pattern><t:YearlyPattern><t:Interval>1</t:Interval>"
        "<t:DayOfMonth>14</t:DayOfMonth><t:Month>March</t:Month>"
        "</t:YearlyPattern></t:Pattern>"
    )
    kontrol(
        _rrule_uret(yillik) == "FREQ=YEARLY;BYMONTH=3;BYMONTHDAY=14",
        f"yıllık desen ({_rrule_uret(yillik)})",
    )
    kontrol(_rrule_uret(_xml("<t:Pattern/>")) == "", "desen yoksa boş kural")


def test_olusturma():
    print("— tekrarlı randevu oluşturma —")
    from postacim.caldav import randevu_ics
    from postacim.ews import _recurrence_xml

    kontrol(
        tekrar.kural_olustur("DAILY", adet=5) == "FREQ=DAILY;COUNT=5",
        "kural üretimi (günlük)",
    )
    kontrol(
        tekrar.kural_olustur("WEEKLY", adet=0, gunler=[0, 2])
        == "FREQ=WEEKLY;BYDAY=MO,WE",
        "kural üretimi (haftalık)",
    )
    kontrol(
        tekrar.kural_olustur("MONTHLY") == "FREQ=MONTHLY",
        "kural üretimi (aylık)",
    )

    ics = randevu_ics(
        "Toplantı", datetime(2026, 1, 5, 10, 0), datetime(2026, 1, 5, 11, 0),
        rrule="FREQ=WEEKLY;BYDAY=MO;COUNT=5",
    )
    kontrol("RRULE:FREQ=WEEKLY;BYDAY=MO;COUNT=5" in ics, "ICS içine RRULE yazıldı")

    xml = _recurrence_xml("FREQ=WEEKLY;BYDAY=MO,WE;COUNT=10")
    kontrol("WeeklyPattern" in xml and "<t:Day>Monday</t:Day>" in xml, "EWS haftalık desen")
    kontrol("<t:NumberOfOccurrences>10</t:NumberOfOccurrences>" in xml, "EWS tekrar sayısı")
    xml2 = _recurrence_xml("FREQ=DAILY")
    kontrol("DailyPattern" in xml2 and "NoEnd" in xml2, "EWS günlük sınırsız desen")
    kontrol(_recurrence_xml("") == "", "kural yoksa XML üretilmez")


# ---------------------------------------------------------------- arayüz

def test_arayuz():
    print("— arayüz: tekrarların genişletilmesi —")
    try:
        import tkinter as tk
        import tkinter.messagebox as messagebox
    except Exception as exc:
        print(f"  -- tkinter yok, atlandı ({exc})")
        return
    try:
        kok = tk.Tk()
        kok.withdraw()
        kok.destroy()
    except tk.TclError:
        print("  -- DISPLAY yok (xvfb-run ile çalıştırın), atlandı")
        return

    import postacim.ui as ui_mod

    messagebox.showerror = lambda *a, **k: HATALAR.append(f"showerror {a}")
    messagebox.showinfo = lambda *a, **k: None
    messagebox.showwarning = lambda *a, **k: HATALAR.append(f"showwarning {a}")

    from postacim.ui import Postacim

    bos = lambda *a, **k: None  # noqa: E731
    Postacim.yenile = bos
    Postacim._ilk_baglanti = bos
    Postacim._diger_hesaplari_yukle = bos
    Postacim._otomatik_baslat = bos
    Postacim._hesap_ekle_penceresi = bos
    Postacim._kimlik_sor = lambda self, *a, **k: False

    uygulama = None
    try:
        uygulama = Postacim()

        def bekle(saniye):
            bitis = time.time() + saniye
            while time.time() < bitis:
                uygulama.update()
                time.sleep(0.02)

        # Sahte tekrarlayan kayıt (CalDAV biçiminde)
        tekrar_kayit = RandevuKaydi(
            uid="tekrar-1",
            url="https://ornek/tekrar-1.ics",
            etag="123",
            baslik="Haftalık toplantı",
            baslangic="2026-01-05T10:00:00",
            bitis="2026-01-05T11:00:00",
            konum="Salon A",
            rrule="FREQ=WEEKLY;BYDAY=MO;COUNT=5",
            kaynak_id="hesap-1",
            kaynak_tur="caldav",
        )
        tek_kez = RandevuKaydi(
            uid="tek-1",
            baslik="Tek seferlik",
            baslangic="2026-01-07T14:00:00",
            bitis="2026-01-07T15:00:00",
            kaynak_id="hesap-1",
            kaynak_tur="caldav",
        )

        uygulama.takvim_gorunum = "ay"
        uygulama.takvim_ay = (2026, 1)
        uygulama.takvim_gun = date(2026, 1, 5)
        uygulama._takvim_sonuc([tekrar_kayit, tek_kez])

        gun5 = uygulama._gun_randevulari(date(2026, 1, 5))
        kontrol(len(gun5) == 1, "5 Ocak: 1 randevu (ilk tekrar)")
        kontrol(gun5[0].baslik == "Haftalık toplantı", "5 Ocak: tekrarlı kayıt")
        kontrol(gun5[0].occurrence_id != "", "tekrar kopyasının kimliği var")

        gun12 = uygulama._gun_randevulari(date(2026, 1, 12))
        kontrol(len(gun12) == 1, "12 Ocak: 1 randevu (ikinci tekrar)")
        kontrol(
            gun12[0].baslangic == "2026-01-12T10:00:00",
            f"12 Ocak başlangıç saati ({gun12[0].baslangic})",
        )
        kontrol(gun12[0].bitis == "2026-01-12T11:00:00", "12 Ocak bitiş saati")

        gun19 = uygulama._gun_randevulari(date(2026, 1, 19))
        kontrol(len(gun19) == 1, "19 Ocak: 1 randevu (üçüncü tekrar)")

        gun26 = uygulama._gun_randevulari(date(2026, 1, 26))
        kontrol(len(gun26) == 1, "26 Ocak: 1 randevu (dördüncü tekrar)")

        gun9 = uygulama._gun_randevulari(date(2026, 2, 9))
        kontrol(len(gun9) == 0, "9 Şubat: COUNT sonrası tekrar yok")

        gun7 = uygulama._gun_randevulari(date(2026, 1, 7))
        kontrol(len(gun7) == 1, "7 Ocak: tek seferlik randevu")
        kontrol(gun7[0].baslik == "Tek seferlik", "7 Ocak: tekrarsız kayıt")

        # Ay görünümü: ızgara hücrelerinde etiket var mı
        uygulama._takvim_ciz()
        bekle(0.2)
        dolu = 0
        for kayit in uygulama._gun_hucreleri.values():
            if kayit["gun"] and uygulama._gun_randevulari(kayit["gun"]):
                dolu += 1
        kontrol(dolu >= 5, f"ay ızgarasında tekrar içeren gün var ({dolu})")

        # Tamamlandı işareti tekrar kopyasına uygulanmalı
        uygulama._randevu_tamamla(gun12[0])
        kontrol(gun12[0].tamamlandi, "tekrar kopyası tamamlandı işaretlendi")
        bekle(0.1)
        tekrar_tekrar = uygulama._gun_randevulari(date(2026, 1, 12))
        kontrol(tekrar_tekrar[0].tamamlandi, "işaret yeniden çizimde korundu")
        uygulama._randevu_tamamla(gun12[0])  # işareti kaldır

        # Kaynak takibi: silme/güncelleme doğru hesaba gitmeli
        kontrol(
            gun12[0].kaynak_id == "hesap-1" and gun12[0].kaynak_tur == "caldav",
            "tekrar kopyası kaynak hesabı bilgisini taşıyor",
        )

        # Yeni randevu penceresinde hesap seçimi olmalı
        from postacim.ui import RandevuPenceresi

        Postacim._arka_plan = lambda self, *a, **k: None

        pencere = RandevuPenceresi(uygulama)
        uygulama.update()
        etiketler = list(pencere.kaynak_combo["values"])
        kontrol(len(etiketler) >= 1, "yeni randevu penceresinde takvim hesabı seçimi var")
        kontrol(
            any("CalDAV" in e for e in etiketler),
            f"hesap listesi CalDAV hesabını içeriyor ({etiketler})",
        )
        pencere.destroy()
        uygulama.update()

        # Tekrar kopyası düzenlenirken seri kaymamalı (ana kaydın tarihi korunur)
        kopya = uygulama._gun_randevulari(date(2026, 1, 19))[0]
        kontrol(kopya.occurrence_id != "", "düzenlenen kayıt bir tekrar kopyası")
        pencere = RandevuPenceresi(uygulama, randevu=kopya)
        uygulama.update()
        kontrol(
            pencere.tekrar_var.get() == "Her hafta",
            f"mevcut kural seçime yansıdı ({pencere.tekrar_var.get()})",
        )
        kontrol(pencere.tekrar_adet.get() == "5", "tekrar sayısı kuraldan okundu")
        pencere.bas_saat.set("14:00")
        pencere.baslik_var.set("Yeni başlık")
        pencere._kaydet()
        uygulama.update()
        from postacim.ui import _iso_utc_yerel

        beklenen = _iso_utc_yerel(datetime(2026, 1, 5, 14, 0))  # ana tarih + yeni saat
        kontrol(
            kopya.baslangic == beklenen,
            f"tekrar düzenlenince ana tarih korundu ({kopya.baslangic} ≠ {beklenen})",
        )
        kontrol(kopya.baslik == "Yeni başlık", "başlık güncellendi")
        kontrol(
            kopya.rrule == "FREQ=WEEKLY;BYDAY=MO;COUNT=5",
            f"kural değiştirilmediyse korundu ({kopya.rrule})",
        )

        uygulama.destroy()
    except Exception as exc:  # noqa: BLE001
        import traceback

        traceback.print_exc()
        HATALAR.append(f"arayüz testi: {exc}")


def main():
    test_ayikla()
    test_uretimi()
    test_ics()
    test_ews_rrule()
    test_olusturma()
    test_arayuz()
    print()
    if HATALAR:
        print(f"!! {len(HATALAR)} hata:")
        for h in HATALAR:
            print("   -", h)
        sys.exit(1)
    print("✓ tüm kontroller geçti")


if __name__ == "__main__":
    main()
