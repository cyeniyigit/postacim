"""Exchange Web Services (EWS) istemcisi.

Kurumlarda IMAP (143/993) ve SMTP (25/465/587) portlari disaridan
kapalidir; bu yuzden Thunderbird / Evolution / Outlook gibi istemciler
baglanamaz. EWS ise HTTPS uzerinden (443) acik kalir ve ayni Exchange
hesabini NTLM ile sunar.

Bu modul yalnizca SOAP/HTTP detaylariyla ilgilenir; arayuz `ui.py`dedir.
"""

from __future__ import annotations

import base64
import email.utils
import html as html_mod
import os
import re
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from email import policy as mime_policy
from email.parser import BytesParser
from typing import Iterable

import requests
from requests_ntlm import HttpNtlmAuth

NS = {
    "soap": "http://schemas.xmlsoap.org/soap/envelope/",
    "t": "http://schemas.microsoft.com/exchange/services/2006/types",
    "m": "http://schemas.microsoft.com/exchange/services/2006/messages",
}

# Exchange surumleri: eski sunucularda daha dusuk surum gerekebilir.
SURUMLER = ("Exchange2013", "Exchange2010_SP2", "Exchange2010_SP1", "Exchange2010")

# Sunucu kendi surumunu "15.2" gibi bildirir; EWS bunu kabul etmez,
# istemcinin gonderdigi "Exchange2013" gibi bir sema surumu gerekir.
SURUM_ESLESME = {
    "8": "Exchange2007_SP1",
    "9": "Exchange2007_SP1",
    "14": "Exchange2010",
    "15": "Exchange2013",
    "16": "Exchange2016",
}
SURUM_KUCUK_ESLESME = {
    ("14", "1"): "Exchange2010_SP1",
    ("14", "2"): "Exchange2010_SP2",
    ("15", "1"): "Exchange2013_SP1",
}

KLASORLER = {
    "inbox": ("Gelen Kutusu", "📥"),
    "sentitems": ("Gönderilmiş", "📤"),
    "drafts": ("Taslaklar", "📝"),
    "deleteditems": ("Silinmiş Öğeler", "🗑"),
    "junkemail": ("Önemsiz", "🚫"),
    "archive": ("Arşiv", "🗄"),
    "outbox": ("Giden Kutusu", "📮"),
}

ETIKETLER = {
    "inbox": "Gelen Kutusu",
    "sentitems": "Gönderilmiş",
    "drafts": "Taslaklar",
    "deleteditems": "Silinmiş Öğeler",
    "junkemail": "Önemsiz",
    "archive": "Arşiv",
    "outbox": "Giden Kutusu",
}

# FindFolder msgfolderroot, varsayılan klasörleri de (kendi FolderId'leriyle)
# döndürür; bunlar zaten GetFolder ile alındığından ada göre elenir
# (sunucu dili İngilizce ya da Türkçe olabilir).
VARSAYILAN_KLASOR_ADLARI = {
    "inbox", "gelen kutusu", "sent items", "gönderilmiş öğeler",
    "gönderilmiş", "drafts", "taslaklar", "deleted items",
    "silinmiş öğeler", "junk email", "junk e-mail", "önemsiz e-posta",
    "önemsiz", "archive", "arşiv", "outbox", "giden kutusu", "conflicts",
    "çakışmalar", "local failures", "yerel hatalar", "server failures",
    "sunucu hataları", "sync issues", "eşitleme sorunları",
    "conversation history", "yazışma geçmişi", "journal", "günlük",
    "notes", "notlar", "tasks", "görevler", "contacts", "kişiler",
    "calendar", "takvim", "rss feeds", "rss akışları",
}


class EwsHata(Exception):
    """EWS istegi basarisiz oldu."""


class EwsYetkiHatasi(EwsHata):
    """Kimlik dogrulama basarisiz (401)."""


@dataclass
class Klasor:
    """Posta kutusu klasoru (sayaclar sunucudan gelir)."""

    kimlik: str = ""
    ad: str = ""
    toplam: int = 0
    okunmamis: int = 0

    @property
    def etiket(self) -> str:
        if self.okunmamis:
            return f"{self.ad} ({self.okunmamis})"
        return self.ad


@dataclass
class Mesaj:
    item_id: str = ""
    change_key: str = ""
    konu: str = ""
    gonderen: str = ""
    gonderen_ad: str = ""
    tarih: str = ""
    okundu: bool = False
    onizleme: str = ""
    govde: str = ""
    govde_html: str = ""
    ekler: list = field(default_factory=list)
    resimler: list = field(default_factory=list)
    klasor: str = ""
    tariham: str = ""
    ek_var: bool = False
    alici: str = ""
    bilgi: str = ""

    @property
    def etiket(self) -> str:
        return f"{self.gonderen_ad or self.gonderen} — {self.konu}"


@dataclass
class Ek:
    ek_id: str = ""
    ad: str = ""
    tur: str = ""
    boyut: int = 0
    icerik: bytes = b""
    mesaj_id: str = ""
    content_id: str = ""


@dataclass
class Resim:
    """Gövde HTML'indeki bir <img> ögesi (satır içi gömülü resim)."""

    ad: str = ""          # yer tutucuda gösterilecek dosya adı
    kaynak: str = ""      # <img src>: cid:..., http(s):..., data:..., dosya adı
    yer_tutucu: str = ""  # gövde metnine yazılan yer tutucu metni


@dataclass
class Randevu:
    """Takvim ogesi (EWS CalendarItem)."""

    item_id: str = ""
    change_key: str = ""
    baslik: str = ""
    baslangic: str = ""    # ISO: 2025-05-07T12:00:00Z
    bitis: str = ""
    konum: str = ""
    tum_gun: bool = False
    organizator: str = ""
    tur: str = "Single"    # Single | RecurringMaster | Occurrence ...
    aciklama: str = ""
    tamamlandi: bool = False  # yerel işaret (hesap.json → tamamlanan_randevular)
    rrule: str = ""        # tekrarlama kuralı (RFC 5545)
    exdate: str = ""       # hariç tutulan tarihler (virgüllü)
    rdate: str = ""        # eklenen tarihler (virgüllü)
    kaynak_id: str = ""    # kaynak hesabın kimliği (çoklu hesap)
    kaynak_tur: str = ""   # "ews" | "caldav"
    occurrence_id: str = ""  # tekrar kopyasının benzersiz kimliği

    @property
    def gun(self) -> str:
        """Yerel güne göre YYYY-AA-GG (UTC damgası yerel saate çevrilir)."""
        yerel = _iso_yerel(self.baslangic)
        if yerel is None:
            return (self.baslangic or "")[:10]
        return yerel.strftime("%Y-%m-%d")

    @property
    def kimlik(self) -> str:
        """Seçim/işaret için benzersiz kimlik (tekrar kopyaları ayrışır)."""
        return self.occurrence_id or self.item_id


def _iso_yerel(ts: str) -> datetime | None:
    """EWS ISO zaman damgasını yerel datetime'a çevirir (Z = UTC)."""
    if not ts:
        return None
    try:
        if ts.endswith("Z"):
            dt = datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(
                tzinfo=timezone.utc
            )
        else:
            # Ofsetli: 2025-05-07T12:00:00+03:00
            dt = datetime.fromisoformat(ts)
            if dt.tzinfo is None:
                return dt
        return dt.astimezone()
    except ValueError:
        return None


def _iso_utc(dt: datetime) -> str:
    """Yerel datetime'u EWS ISO (UTC Z) biçimine çevirir.

    Farksız (naive) datetime yerel saat varsayılır.
    """
    if dt.tzinfo is None:
        dt = dt.astimezone()  # sistem yerel dilimi
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# Arayüz için açık ad
iso_yerel = _iso_yerel


# --- Takvim tekrar (RRULE) ------------------------------------------------

_EWS_GUNLER = {
    "Monday": "MO", "Tuesday": "TU", "Wednesday": "WE", "Thursday": "TH",
    "Friday": "FR", "Saturday": "SA", "Sunday": "SU",
}
_EWS_AYLAR = {
    "January": 1, "February": 2, "March": 3, "April": 4, "May": 5, "June": 6,
    "July": 7, "August": 8, "September": 9, "October": 10, "November": 11,
    "December": 12,
}
_EWS_INDEKS = {"First": 1, "Second": 2, "Third": 3, "Fourth": 4, "Last": -1}
_EWS_GUNLER_ADI = {
    0: "Monday", 1: "Tuesday", 2: "Wednesday", 3: "Thursday",
    4: "Friday", 5: "Saturday", 6: "Sunday",
}
_EWS_AY_ADI = {
    1: "January", 2: "February", 3: "March", 4: "April", 5: "May", 6: "June",
    7: "July", 8: "August", 9: "September", 10: "October", 11: "November",
    12: "December",
}


def _recurrence_xml(rrule: str) -> str:
    """RRULE dizesini EWS `t:Recurrence` XML'ine çevirir.

    Karşılığı olmayan kurallar (örn. RDATE) yok sayılır.
    """
    if not rrule:
        return ""
    from . import tekrar

    kural = tekrar.kural_ayikla(rrule)
    freq = str(kural.get("FREQ", "")).upper()
    if freq not in ("DAILY", "WEEKLY", "MONTHLY", "YEARLY"):
        return ""
    aralik = int(kural.get("INTERVAL", "1") or 1)
    adet = int(kural.get("COUNT", "0") or 0)
    until = tekrar.until_coz(kural.get("UNTIL", ""))
    byday = tekrar.byday_ayikla(kural.get("BYDAY", ""))
    gunler = [_EWS_GUNLER_ADI[g] for _, g in byday]
    gun_etiketleri = "".join(f"<t:Day>{g}</t:Day>" for g in gunler)

    if freq == "DAILY":
        desen = f"<t:DailyPattern><t:Interval>{aralik}</t:Interval></t:DailyPattern>"
    elif freq == "WEEKLY":
        desen = (
            f"<t:WeeklyPattern><t:Interval>{aralik}</t:Interval>"
            f"<t:DaysOfWeek>{gun_etiketleri}</t:DaysOfWeek></t:WeeklyPattern>"
        )
    elif freq == "MONTHLY":
        if byday and byday[0][0]:  # göreli (2. pazartesi gibi)
            sira = byday[0][0]
            indeks = {1: "First", 2: "Second", 3: "Third", 4: "Fourth", -1: "Last"}
            desen = (
                f"<t:RelativeMonthlyPattern><t:DaysOfWeek>{gun_etiketleri}"
                f"</t:DaysOfWeek><t:Index>{indeks.get(sira, 'First')}</t:Index>"
                f"</t:RelativeMonthlyPattern>"
            )
        else:
            gun = kural.get("BYMONTHDAY", "1")
            desen = (
                f"<t:AbsoluteMonthlyPattern><t:DayOfMonth>{gun}"
                f"</t:DayOfMonth></t:AbsoluteMonthlyPattern>"
            )
    else:  # YEARLY
        ay = int(kural.get("BYMONTH", "1") or 1)
        gun = kural.get("BYMONTHDAY", "1")
        desen = (
            f"<t:YearlyPattern><t:Interval>{aralik}</t:Interval>"
            f"<t:DayOfMonth>{gun}</t:DayOfMonth><t:Month>{_EWS_AY_ADI[ay]}"
            f"</t:Month></t:YearlyPattern>"
        )

    if adet:
        aralik_el = f"<t:NumberOfOccurrences>{adet}</t:NumberOfOccurrences>"
    elif until:
        aralik_el = f"<t:EndDate>{_iso_utc(until)}</t:EndDate>"
    else:
        aralik_el = "<t:NoEnd>true</t:NoEnd>"

    return (
        "<t:Recurrence><t:Pattern>" + desen + "</t:Pattern>"
        "<t:Range>" + aralik_el + "</t:Range></t:Recurrence>"
    )


def _rrule_uret(el: ET.Element) -> str:
    """`t:Recurrence` öğesini RRULE dizesine çevirir.

    Exchange'in tekrarlama deseni (DailyPattern, WeeklyPattern…) RFC 5545
    kuralına çevrilir; arayüzdeki genişletici bunu okur.
    """
    if el is None:
        return ""
    desen = el.find("t:Pattern", NS)
    if desen is None:
        return ""
    parcalar: list[str] = []

    def _ara(ad: str) -> ET.Element | None:
        return desen.find(f"t:{ad}", NS)

    daily = _ara("DailyPattern")
    weekly = _ara("WeeklyPattern")
    monthly = _ara("MonthlyPattern")
    abs_monthly = _ara("AbsoluteMonthlyPattern")
    rel_monthly = _ara("RelativeMonthlyPattern")
    yearly = _ara("YearlyPattern")
    abs_yearly = _ara("AbsoluteYearlyPattern")
    rel_yearly = _ara("RelativeYearlyPattern")

    def _aralik(oge: ET.Element | None) -> str:
        if oge is None:
            return ""
        deger = oge.findtext("t:Interval", "", NS)
        try:
            n = int(deger or 1)
        except ValueError:
            n = 1
        return f";INTERVAL={n}" if n > 1 else ""

    def _gunler(oge: ET.Element | None) -> str:
        if oge is None:
            return ""
        gunler = [
            _EWS_GUNLER[g.text.strip()]
            for g in oge.findall("t:DaysOfWeek/t:Day", NS)
            if g.text and g.text.strip() in _EWS_GUNLER
        ]
        return f";BYDAY={','.join(gunler)}" if gunler else ""

    if daily is not None:
        parcalar = ["FREQ=DAILY", _aralik(daily).lstrip(";")]
    elif weekly is not None:
        parcalar = ["FREQ=WEEKLY", _aralik(weekly).lstrip(";")]
        gunler = _gunler(weekly).lstrip(";")
        if gunler:
            parcalar.append(gunler)
    elif monthly is not None:
        parcalar = ["FREQ=MONTHLY", _aralik(monthly).lstrip(";")]
        gun = monthly.findtext("t:DayOfMonth", "", NS)
        if gun:
            parcalar.append(f"BYMONTHDAY={gun}")
    elif abs_monthly is not None:
        parcalar = ["FREQ=MONTHLY"]
        gun = abs_monthly.findtext("t:DayOfMonth", "", NS)
        if gun:
            parcalar.append(f"BYMONTHDAY={gun}")
    elif rel_monthly is not None:
        parcalar = ["FREQ=MONTHLY"]
        indeks = rel_monthly.findtext("t:Index", "First", NS) or "First"
        sira = _EWS_INDEKS.get(indeks.strip(), 1)
        gunler = [
            _EWS_GUNLER[g.text.strip()]
            for g in rel_monthly.findall("t:DaysOfWeek/t:Day", NS)
            if g.text and g.text.strip() in _EWS_GUNLER
        ]
        if gunler:
            parcalar.append("BYDAY=" + ",".join(f"{sira}{g}" for g in gunler))
    elif yearly is not None:
        parcalar = ["FREQ=YEARLY", _aralik(yearly).lstrip(";")]
        ay = yearly.findtext("t:Month", "", NS)
        if ay and ay.strip() in _EWS_AYLAR:
            parcalar.append(f"BYMONTH={_EWS_AYLAR[ay.strip()]}")
        gun = yearly.findtext("t:DayOfMonth", "", NS)
        if gun:
            parcalar.append(f"BYMONTHDAY={gun}")
    elif abs_yearly is not None:
        parcalar = ["FREQ=YEARLY"]
        ay = abs_yearly.findtext("t:Month", "", NS)
        if ay and ay.strip() in _EWS_AYLAR:
            parcalar.append(f"BYMONTH={_EWS_AYLAR[ay.strip()]}")
        gun = abs_yearly.findtext("t:DayOfMonth", "", NS)
        if gun:
            parcalar.append(f"BYMONTHDAY={gun}")
    elif rel_yearly is not None:
        parcalar = ["FREQ=YEARLY"]
        indeks = rel_yearly.findtext("t:Index", "First", NS) or "First"
        sira = _EWS_INDEKS.get(indeks.strip(), 1)
        gunler = [
            _EWS_GUNLER[g.text.strip()]
            for g in rel_yearly.findall("t:DaysOfWeek/t:Day", NS)
            if g.text and g.text.strip() in _EWS_GUNLER
        ]
        if gunler:
            parcalar.append("BYDAY=" + ",".join(f"{sira}{g}" for g in gunler))

    if not parcalar:
        return ""

    aralik_el = el.find("t:Range", NS)
    if aralik_el is not None:
        adet = aralik_el.findtext("t:NumberOfOccurrences", "", NS)
        if adet:
            parcalar.append(f"COUNT={adet.strip()}")
        else:
            bitis = aralik_el.findtext("t:EndDate", "", NS)
            if bitis:
                parcalar.append(f"UNTIL={_ics_utc_tarih(bitis)}")
    return ";".join(p for p in parcalar if p)


def _ics_utc_tarih(ts: str) -> str:
    """'2026-01-05T00:00:00' → '20260105T000000Z' (RFC 5545 biçimi)."""
    ts = (ts or "").strip()
    if not ts:
        return ""
    dt = _iso_yerel(ts)
    if dt is None:
        return ""
    return dt.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _kacis(deger: str) -> str:
    """XML metnine guvenli sekilde yazilacak metin."""
    return (
        str(deger)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _klasor_id_xml(kimlik: str) -> str:
    """Klasör kimliğini SOAP gövdesine yazılacak XML'e çevirir.

    Bilinen 7 klasör DistinguishedFolderId ile (sunucu yerelleştirmesinden
    etkilenmez); kullanıcı klasörleri ham `FolderId` ile belirtilir.
    """
    if kimlik in KLASORLER:
        return f'<t:DistinguishedFolderId Id="{kimlik}"/>'
    return f'<t:FolderId Id="{_kacis(kimlik)}"/>'


def _zaman(ts: str) -> str:
    """EWS tarihini (2011-01-01T...) yerel okunur bicime cevirir."""
    if not ts:
        return ""
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})", ts)
    if not m:
        return ts
    y, ay, g, sa, dk, sn = m.groups()
    return f"{int(g):02d}.{int(ay):02d}.{y} {sa}:{dk}"


def _ews_surumu(buyuk: str, kucuk: str) -> str:
    """Sunucu surumunu (15.2) EWS sema surumune (Exchange2013) cevirir.

    Sunucu '15.2' gibi ham bir surum bildirir; EWS bunu kabul etmez.
    Bilinmeyen surumlerde mevcut degistirilmez.
    """
    buyuk = str(buyuk)
    kucuk = str(kucuk)
    if (buyuk, kucuk) in SURUM_KUCUK_ESLESME:
        return SURUM_KUCUK_ESLESME[(buyuk, kucuk)]
    if buyuk in SURUM_ESLESME:
        return SURUM_ESLESME[buyuk]
    return SURUMLER[0]


def _okundu_govde(item_id: str, change_key: str, okundu: bool) -> str:
    """Okundu/okunmadı işaretleme isteğinin SOAP gövdesi.

    DİKKAT: `ItemChange` elemanı **t:** (types) ad alanında olmalı;
    `m:ItemChange` yazılırsa Exchange "ErrorInvalidArgument — The request is
    invalid." döner ve işaret kaydedilmez.
    """
    return (
        "<m:UpdateItem ConflictResolution=\"AutoResolve\" MessageDisposition=\"SaveOnly\">"
        "<m:ItemChanges><t:ItemChange>"
        f"<t:ItemId Id=\"{_kacis(item_id)}\" ChangeKey=\"{_kacis(change_key)}\"/>"
        "<t:Updates><t:SetItemField>"
        "<t:FieldURI FieldURI=\"message:IsRead\"/>"
        f"<t:Message><t:IsRead>{'true' if okundu else 'false'}</t:IsRead></t:Message>"
        "</t:SetItemField></t:Updates>"
        "</t:ItemChange></m:ItemChanges></m:UpdateItem>"
    )


class EwsIstemci:
    """EWS uzerinden Exchange posta kutusu."""

    def __init__(
        self,
        sunucu: str = "",
        kullanici: str = "",
        parola: str = "",
        yontem: str = "ntlm",
        zaman_asimi: int = 60,
        gonderen: str = "",
    ):
        self.sunucu = (sunucu or "").strip()
        self.kullanici = kullanici
        self.parola = parola
        self.yontem = yontem
        self.zaman_asimi = zaman_asimi
        # Gönderen (From) adresi — SMTP başlığı için; boşsa kullanıcıdan türetilir
        self.gonderen = (gonderen or "").strip()
        self.surum = SURUMLER[0]
        self.oturum = requests.Session()
        self._senkronizasyon: dict = {}
        self._takvim_onbellek: dict | None = None  # {"durum", "randevular", "tam"}
        self._mime_onbellek: dict[str, bytes] = {}
        self._getattachment_calismiyor = False
        # Kullanıcı klasörleri (FindFolder): 60 sn önbellek — her yenilemede
        # ek istek atılmasın; klasor_olustur önbelleği düşürür.
        self._ozel_klasor_onbellek: list = None
        self._ozel_klasor_zaman: float = 0.0
        self.oturum.headers.update(
            {
                "User-Agent": "Postacim/1.0",
                "Content-Type": 'text/xml; charset="utf-8"',
                "Accept": "text/xml",
            }
        )
        if yontem == "ntlm":
            self.oturum.auth = HttpNtlmAuth(kullanici, parola)
        elif yontem == "basic":
            self.oturum.auth = (kullanici, parola)
        if not self.sunucu:
            raise EwsHata(
                "Exchange sunucu adresi girilmemiş. "
                "Hesaplar → Hesap Düzenle… ile sunucuyu yazın."
            )
        self.adres = f"https://{self.sunucu}/EWS/Exchange.asmx"

    # ------------------------------------------------------------------ HTTP

    def _zarf(self, govde: str) -> str:
        return (
            '<?xml version="1.0" encoding="utf-8"?>'
            '<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"'
            ' xmlns:t="http://schemas.microsoft.com/exchange/services/2006/types"'
            ' xmlns:m="http://schemas.microsoft.com/exchange/services/2006/messages">'
            f"<soap:Header><t:RequestServerVersion Version=\"{self.surum}\"/></soap:Header>"
            f"<soap:Body>{govde}</soap:Body>"
            "</soap:Envelope>"
        )

    def istek(self, govde: str, tekrar: int = 3) -> ET.Element:
        """SOAP istegi gonderir, <Envelope> kokunu dondurur.

        Gecici hatalarda (5xx, zaman asimi) kademeli bekleyerek yeniden dener.
        """
        veri = self._zarf(govde)
        son_hata: Exception | None = None
        for deneme in range(tekrar):
            if deneme:
                time.sleep(1.5 * deneme)
            try:
                yanit = self.oturum.post(
                    self.adres, data=veri.encode("utf-8"), timeout=self.zaman_asimi
                )
            except requests.RequestException as exc:
                son_hata = exc
                continue
            if yanit.status_code == 401:
                raise EwsYetkiHatasi(
                    "Kimlik doğrulama başarısız (401). "
                    "Kullanıcı adı 'KURUM\\kullanici' biçiminde olmalı; "
                    "parola büyük/küçük harf duyarlıdır."
                )
            if yanit.status_code == 503:
                son_hata = EwsHata("Sunucu meşgul (503) — biraz sonra tekrar deneyin.")
                continue
            try:
                kok = ET.fromstring(yanit.content)
            except ET.ParseError:
                yanit.raise_for_status()
                raise EwsHata(f"Parse edilemeyen yanıt (HTTP {yanit.status_code}).")
            # Exchange, SOAP hatalarini HTTP 500 ile dondurur: once zarfi oku.
            hata = kok.find(".//soap:Fault", NS)
            if hata is not None:
                kod = hata.find(".//m:ResponseCode", NS)
                ayrinti = hata.find(".//m:Message", NS)
                metin = hata.find(".//faultstring", NS)
                ilke = (
                    "EWS hatası: "
                    + (kod.text if kod is not None and kod.text else "?")
                    + " — "
                    + (ayrinti.text if ayrinti is not None and ayrinti.text else "")
                    + ((" | " + metin.text) if metin is not None and metin.text else "")
                )
                # 500 + "internal server error" gecici sayilir; yeniden deneyelim.
                if "internal server error" in ilke.lower() and deneme < tekrar - 1:
                    son_hata = EwsHata(ilke)
                    continue
                raise EwsHata(ilke)
            if yanit.status_code >= 400:
                if yanit.status_code >= 500 and deneme < tekrar - 1:
                    son_hata = EwsHata(f"Sunucu hatası (HTTP {yanit.status_code}).")
                    continue
                yanit.raise_for_status()
            # Sunucu surumu ilk cevapta bildirilir.
            surum = kok.find(".//t:ServerVersionInfo", NS)
            if surum is not None:
                buyuk = surum.get("MajorVersion")
                kucuk = surum.get("MinorVersion")
                if buyuk and kucuk:
                    self.surum = _ews_surumu(buyuk, kucuk)
            yanit_kodu = kok.find(".//m:ResponseCode", NS)
            if yanit_kodu is not None and yanit_kodu.text not in (None, "NoError"):
                raise EwsHata(f"EWS yanıt kodu: {yanit_kodu.text}")
            return kok
        if son_hata is not None:
            raise son_hata
        raise EwsHata("İstek tekrarları tükendi.")

    # --------------------------------------------------------------- Klasorler

    def klasor_listesi(self) -> list:
        """Kullanilabilir posta kutularini dondurur: [Klasor].

        7 GetFolder yerine TEK istek (çoklu FolderIds): 0.78s → ~0.4s.
        Yanıt sırası istek sırasıyla eşleşir; eşleşmezse ad eşleşmesi denenir.
        """
        kimlikler = list(KLASORLER.items())
        ids = "".join(
            f'<t:DistinguishedFolderId Id="{kimlik}"/>' for kimlik, _ in kimlikler
        )
        govde = (
            "<m:GetFolder>"
            "<m:FolderShape><t:BaseShape>Default</t:BaseShape></m:FolderShape>"
            f"<m:FolderIds>{ids}</m:FolderIds>"
            "</m:GetFolder>"
        )
        try:
            kok = self.istek(govde)
        except EwsYetkiHatasi:
            raise
        except EwsHata:
            # Tek istek başarısızsa eski yolu (seri) dene
            return self._ozel_klasorler(self._klasor_listesi_seri())

        klasorler = kok.findall(".//m:Folders/*", NS)
        liste: list = []
        if len(klasorler) == len(kimlikler):
            # Sıralı eşleşme (istek sırası korunur)
            for (kimlik, (ad, _)), el in zip(kimlikler, klasorler):
                ad2 = el.find("t:DisplayName", NS)
                liste.append(
                    Klasor(
                        kimlik=kimlik,
                        ad=ad2.text if ad2 is not None and ad2.text else ad,
                        toplam=int(el.findtext("t:TotalCount", "0", NS) or 0),
                        okunmamis=int(el.findtext("t:UnreadCount", "0", NS) or 0),
                    )
                )
        else:
            # Sayı uyuşmuyor: ad eşleşmesiyle doldur, kalanları seri çek
            bulunan: dict = {}
            for el in klasorler:
                ad2 = el.find("t:DisplayName", NS)
                ad = ad2.text if ad2 is not None and ad2.text else ""
                bulunan[ad] = el
            for kimlik, (varsayilan, _) in kimlikler:
                el = bulunan.get(varsayilan)
                if el is None:
                    # sunucu adı farklı olabilir; sıradan denk geleni al
                    continue
                ad2 = el.find("t:DisplayName", NS)
                liste.append(
                    Klasor(
                        kimlik=kimlik,
                        ad=ad2.text if ad2 is not None and ad2.text else varsayilan,
                        toplam=int(el.findtext("t:TotalCount", "0", NS) or 0),
                        okunmamis=int(el.findtext("t:UnreadCount", "0", NS) or 0),
                    )
                )
            if len(liste) != len(kimlikler):
                return self._ozel_klasorler(self._klasor_listesi_seri())
        return self._ozel_klasorler(liste)

    def _ozel_klasorler(self, liste: list) -> list:
        """Kullanıcı klasörlerini FindFolder ile listeye ekler.

        Başarısız olursa (sunucu desteklemiyorsa) sessizce mevcut listeyi
        döndürür — 7 varsayılan klasör her koşulda görünür. Sonuçlar 60 sn
        önbelleklenir (otomatik yenileme ek istek atmasın).
        """
        simdi = time.time()
        if self._ozel_klasor_onbellek is not None and \
                simdi - self._ozel_klasor_zaman < 60:
            return liste + list(self._ozel_klasor_onbellek)
        govde = (
            '<m:FindFolder Traversal="Shallow">'
            '<m:FolderShape><t:BaseShape>Default</t:BaseShape></m:FolderShape>'
            '<m:ParentFolderIds>'
            '<t:DistinguishedFolderId Id="msgfolderroot"/>'
            "</m:ParentFolderIds>"
            "</m:FindFolder>"
        )
        try:
            kok = self.istek(govde)
        except EwsYetkiHatasi:
            raise
        except (EwsHata, requests.RequestException, ValueError):
            return liste
        var = {k.ad.casefold() for k in liste} | VARSAYILAN_KLASOR_ADLARI
        ozel: list = []
        for el in kok.findall(".//m:Folders/t:Folder", NS):
            fid = el.find("t:FolderId", NS)
            ad = (el.findtext("t:DisplayName", "", NS) or "").strip()
            if fid is None or not fid.get("Id") or not ad:
                continue
            if ad.casefold() in var:
                continue  # varsayılan klasör zaten listede
            sinif = el.findtext("t:FolderClass", "", NS) or ""
            if sinif and not sinif.startswith("IPF.Note"):
                continue  # takvim/kişiler/görevler gibi posta klasörü değil
            ozel.append(
                Klasor(
                    kimlik=fid.get("Id"),
                    ad=ad,
                    toplam=int(el.findtext("t:TotalCount", "0", NS) or 0),
                    okunmamis=int(el.findtext("t:UnreadCount", "0", NS) or 0),
                )
            )
            var.add(ad.casefold())
        ozel.sort(key=lambda k: k.ad.casefold())
        self._ozel_klasor_onbellek = ozel
        self._ozel_klasor_zaman = simdi
        return liste + ozel

    def _klasor_listesi_seri(self) -> list:
        """Yedek yol: klasör başına ayrı GetFolder (eski davranış)."""
        liste = []
        for kimlik, (ad, _ikon) in KLASORLER.items():
            try:
                govde = (
                    "<m:GetFolder>"
                    "<m:FolderShape><t:BaseShape>AllProperties</t:BaseShape></m:FolderShape>"
                    f"<m:FolderIds><t:DistinguishedFolderId Id=\"{kimlik}\"/></m:FolderIds>"
                    "</m:GetFolder>"
                )
                kok = self.istek(govde)
                klasor = kok.find(".//m:Folders/t:Folder", NS)
                if klasor is None:
                    continue
                ad2 = klasor.find("t:DisplayName", NS)
                liste.append(
                    Klasor(
                        kimlik=kimlik,
                        ad=ad2.text if ad2 is not None and ad2.text else ad,
                        toplam=int(klasor.findtext("t:TotalCount", "0", NS) or 0),
                        okunmamis=int(klasor.findtext("t:UnreadCount", "0", NS) or 0),
                    )
                )
            except EwsYetkiHatasi:
                raise
            except EwsHata:
                continue
        return liste

    # --------------------------------------------------------------- Takvim

    def takvim_var(self) -> bool:
        """Bu istemcide takvim (EWS) var mı? IMAP'ta yoktur."""
        return True

    def takvim_randevulari(self, tam: bool = False) -> list:
        """Takvim klasöründeki randevuları SyncFolderItems ile çeker.

        FindItem kurum sunucusunda bozuk; SyncFolderItemsCalendarItem
        öğelerini de verir (varsayılan biçimde Subject/Start/End/Location).
        Sonuç önbelleklenir; tam=True önbelleği sıfırlar.
        """
        if self._takvim_onbellek is None or tam:
            self._takvim_onbellek = {
                "durum": "",
                "randevular": {},
                "tam": False,
            }
        kayit = self._takvim_onbellek
        if tam:
            kayit["durum"] = ""
            kayit["randevular"] = {}
            kayit["tam"] = False
        elif kayit["tam"]:
            kayit["tam"] = False  # artımlı güncelleme için devam et

        tur = 0
        while not kayit["tam"] and tur < 200:
            tur += 1
            govde = (
                "<m:SyncFolderItems>"
                "<m:ItemShape><t:BaseShape>Default</t:BaseShape>"
                "<t:Recurrence/></m:ItemShape>"
                '<m:SyncFolderId><t:DistinguishedFolderId Id="calendar"/></m:SyncFolderId>'
                f"<m:SyncState>{_kacis(kayit['durum'])}</m:SyncState>"
                "<m:Ignore/><m:MaxChangesReturned>512</m:MaxChangesReturned>"
                "</m:SyncFolderItems>"
            )
            kok = self.istek(govde)
            durum_el = kok.find(".//m:SyncState", NS)
            if durum_el is not None and durum_el.text:
                kayit["durum"] = durum_el.text
            son_el = kok.find(".//m:IncludesLastItemInRange", NS)
            kayit["tam"] = son_el is not None and (son_el.text or "").lower() == "true"

            for degis in kok.findall(".//m:Changes/*", NS):
                etiket = degis.tag.split("}")[-1]
                if etiket in ("Create", "Update"):
                    el = degis.find("t:CalendarItem", NS)
                    if el is None:
                        continue
                    r = self._randevu(el)
                    if r.item_id:
                        kayit["randevular"][r.item_id] = r
                elif etiket == "Delete":
                    kimlik_el = degis.find("t:CalendarItemId", NS)
                    if kimlik_el is None:
                        kimlik_el = degis.find("t:ItemId", NS)
                    if kimlik_el is not None:
                        kayit["randevular"].pop(kimlik_el.get("Id", ""), None)

        # Başlangıç zamanına göre sırala
        liste = sorted(
            kayit["randevular"].values(),
            key=lambda r: r.baslangic or "",
        )
        return liste

    def _randevu(self, el: ET.Element) -> Randevu:
        item_id = el.find("t:ItemId", NS)
        baslangic = el.find("t:Start", NS)
        bitis = el.find("t:End", NS)
        konum = el.find("t:Location", NS)
        tum_gun = el.find("t:IsAllDay", NS)
        organizator = el.find("t:Organizer/t:Mailbox/t:Name", NS)
        if organizator is None:
            organizator = el.find("t:Organizer/t:Mailbox/t:EmailAddress", NS)
        tur = el.find("t:CalendarItemType", NS)
        aciklama = el.find("t:Body", NS)
        if aciklama is None:
            aciklama = el.find("t:TextBody", NS)
        rrule = ""
        tekrarlama = el.find("t:Recurrence", NS)
        if tekrarlama is not None:
            rrule = _rrule_uret(tekrarlama)
        return Randevu(
            item_id=item_id.get("Id", "") if item_id is not None else "",
            change_key=item_id.get("ChangeKey", "") if item_id is not None else "",
            baslik=(
                (el.findtext("t:Subject", default="", namespaces=NS) or "").strip()
                or "(başlıksız)"
            ),
            baslangic=baslangic.text if baslangic is not None else "",
            bitis=bitis.text if bitis is not None else "",
            konum=(konum.text or "") if konum is not None else "",
            tum_gun=(tum_gun.text == "true") if tum_gun is not None else False,
            organizator=(organizator.text or "") if organizator is not None else "",
            tur=(tur.text or "Single") if tur is not None else "Single",
            aciklama=(aciklama.text or "") if aciklama is not None else "",
            rrule=rrule,
        )


    def randevu_ekle(
        self,
        baslik: str,
        baslangic: datetime,
        bitis: datetime,
        konum: str = "",
        aciklama: str = "",
        tum_gun: bool = False,
        rrule: str = "",
    ) -> str:
        """Takvim klasörüne yeni randevu ekler; item_id döner."""
        govde = (
            "<m:CreateItem SendMeetingInvitations=\"SendToNone\" "
            "MessageDisposition=\"SaveOnly\">"
            "<m:SavedItemFolderId>"
            '<t:DistinguishedFolderId Id="calendar"/>'
            "</m:SavedItemFolderId>"
            "<m:Items><t:CalendarItem>"
            f"<t:Subject>{_kacis(baslik or '(başlıksız)')}</t:Subject>"
            f"<t:Start>{_iso_utc(baslangic)}</t:Start>"
            f"<t:End>{_iso_utc(bitis)}</t:End>"
            f"<t:IsAllDay>{'true' if tum_gun else 'false'}</t:IsAllDay>"
            f"<t:Location>{_kacis(konum)}</t:Location>"
            f"<t:Body BodyType=\"Text\">{_kacis(aciklama)}</t:Body>"
            f"{_recurrence_xml(rrule)}"
            "</t:CalendarItem></m:Items></m:CreateItem>"
        )
        kok = self.istek(govde)
        kimlik = kok.find(".//m:Items/t:CalendarItem/t:ItemId", NS)
        return kimlik.get("Id", "") if kimlik is not None else ""

    def randevu_guncelle(self, r: Randevu) -> None:
        """Randevunun alanlarını günceller.

        Kurum sunucusunda `UpdateItem` + `SetItemField` (calendar:*)
        `ErrorInvalidArgument` veriyor; bunun yerine sil + yeniden
        oluştur kullanılır (item_id değişir, arayüz yeniden çizer).
        """
        bas = _iso_yerel(r.baslangic)
        bit = _iso_yerel(r.bitis)
        if bas is None:
            raise EwsHata("Randevu başlangıç zamanı geçersiz.")
        if bit is None:
            bit = bas + timedelta(hours=1)
        eski = Randevu(item_id=r.item_id, change_key=r.change_key)
        self.randevu_sil(eski)
        yeni_id = self.randevu_ekle(
            r.baslik, bas, bit, r.konum, r.aciklama, r.tum_gun
        )
        r.item_id = yeni_id
        r.change_key = ""

    def randevu_sil(self, r: Randevu) -> None:
        """Randevuyu kalıcı olarak siler."""
        govde = (
            '<m:DeleteItem DeleteType="HardDelete" '
            'SendMeetingCancellations="SendToNone">'
            f'<m:ItemIds><t:ItemId Id="{_kacis(r.item_id)}"/></m:ItemIds>'
            "</m:DeleteItem>"
        )
        self.istek(govde)

    # --------------------------------------------------------------- Mesajlar

    def mesajlar(
        self,
        klasor: str = "inbox",
        sayfa_boyutu: int = 50,
        offset: int = 0,
        arama: str = "",
        alan: str = "konu",
        tam: bool = False,
        tazele: bool = True,
    ) -> tuple:
        """(mesajlar, toplam_sayi) dondurur.

        Listeleme `SyncFolderItems` ile yapilir: Exchange 2013'te `FindItem`
        sunucu tarafinda "internal server error" veriyor, senkronizasyon
        ise 512'şer adetlik gruplar halinde tum klasoru veriyor.

        `tam=True` onbellegi sifirlar ve klasoru bastan ceker.
        `tazele=False` yalnizca onbellegi okur (sayfalama icin; ag yok).
        """
        if tazele:
            self._senkronize(klasor, tam=tam)
        kayit = self._senkronizasyon.get(klasor, {})
        mesajlar = list(kayit.get("sirali", []))

        if arama:
            arama = arama.strip().lower()
            if alan == "gonderen":
                mesajlar = [
                    m for m in mesajlar
                    if arama in (m.gonderen or "").lower()
                    or arama in (m.gonderen_ad or "").lower()
                ]
            else:
                mesajlar = [
                    m for m in mesajlar
                    if arama in (m.konu or "").lower()
                    or arama in (m.onizleme or "").lower()
                    or arama in (m.gonderen_ad or m.gonderen or "").lower()
                ]

        toplam = len(mesajlar)
        sayfa = mesajlar[offset : offset + sayfa_boyutu]
        return sayfa, toplam

    def gelen_sayisi(self) -> int:
        """Gelen Kutusu'ndaki toplam mesaj sayısı (tek GetFolder isteği)."""
        govde = (
            "<m:GetFolder>"
            "<m:FolderShape><t:BaseShape>Default</t:BaseShape></m:FolderShape>"
            '<m:FolderIds><t:DistinguishedFolderId Id="inbox"/></m:FolderIds>'
            "</m:GetFolder>"
        )
        kok = self.istek(govde)
        el = kok.find(".//m:Folders/*", NS)
        if el is None:
            return 0
        return int(el.findtext("t:TotalCount", "0", NS) or 0)

    def guncelle(self, klasorler: Iterable[str] | None = None) -> dict:
        """Onbellekli klasorlerdeki degisiklikleri ceker (Gonder/Al).

        Her klasor icin mevcut SyncState ile tek bir artimli
        `SyncFolderItems` istegi yapilir; onbellegi olmayan klasorler
        atlanir (tum klasoru cekmek yerine sayac guncellemesi yeterlidir).
        {klasor: net_degisim} doner.
        """
        hedefler = (
            list(klasorler) if klasorler is not None else list(self._senkronizasyon)
        )
        sonuc = {}
        for klasor in hedefler:
            kayit = self._senkronizasyon.get(klasor)
            if not kayit:
                continue
            oncesi = len(kayit["mesajlar"])
            try:
                self._senkronize(klasor)
            except EwsHata:
                continue
            sonuc[klasor] = len(kayit["mesajlar"]) - oncesi
        return sonuc

    def _senkronize(self, klasor: str, tam: bool = False) -> None:
        """Klasoru senkronize eder; sonucu onbellekler."""
        kayit = self._senkronizasyon.setdefault(
            klasor, {"durum": "", "mesajlar": {}, "tam": False}
        )
        if tam:
            kayit["durum"] = ""
            kayit["mesajlar"] = {}
            kayit["tam"] = False
        elif kayit["tam"]:
            # Onbellek guncel: bastan cekmek yerine mevcut SyncState ile
            # yalnizca sonraki degisiklikleri al.
            kayit["tam"] = False

        tur = 0
        while not kayit["tam"] and tur < 200:
            tur += 1
            govde = (
                "<m:SyncFolderItems>"
                "<m:ItemShape><t:BaseShape>Default</t:BaseShape></m:ItemShape>"
                f"<m:SyncFolderId>{_klasor_id_xml(klasor)}</m:SyncFolderId>"
                f"<m:SyncState>{kayit['durum']}</m:SyncState>"
                "<m:Ignore/><m:MaxChangesReturned>512</m:MaxChangesReturned>"
                "</m:SyncFolderItems>"
            )
            kok = self.istek(govde)
            durum_el = kok.find(".//m:SyncState", NS)
            if durum_el is not None and durum_el.text:
                kayit["durum"] = durum_el.text
            son_el = kok.find(".//m:IncludesLastItemInRange", NS)
            kayit["tam"] = son_el is not None and (son_el.text or "").lower() == "true"

            for degis in kok.findall(".//m:Changes/*", NS):
                etiket = degis.tag.split("}")[-1]
                if etiket in ("Create", "Update"):
                    el = degis.find("t:Message", NS)
                    if el is None:
                        continue
                    mesaj = self._mesaj(el, klasor)
                    if mesaj.item_id:
                        kayit["mesajlar"][mesaj.item_id] = mesaj
                elif etiket == "Delete":
                    kimlik_el = degis.find("t:MessageId", NS)
                    if kimlik_el is not None:
                        kayit["mesajlar"].pop(kimlik_el.get("Id", ""), None)

        # En yeniden eskiye sirala (tarihi olmayanlar sona).
        liste = sorted(
            kayit["mesajlar"].values(),
            key=lambda m: m.tariham or "",
            reverse=True,
        )
        kayit["sirali"] = liste

    def _mesaj(self, el: ET.Element, klasor: str = "") -> Mesaj:
        item_id = el.find("t:ItemId", NS)
        gonderen = el.find("t:From/t:Mailbox/t:EmailAddress", NS)
        ad = el.find("t:From/t:Mailbox/t:Name", NS)
        konu = el.find("t:Subject", NS)
        # Senkronizasyon yanitinda DateTimeReceived yok; olustugu tarihi kullan.
        tarih = el.find("t:DateTimeReceived", NS)
        if tarih is None:
            tarih = el.find("t:DateTimeCreated", NS)
        if tarih is None:
            tarih = el.find("t:DateTimeSent", NS)
        okundu = el.find("t:IsRead", NS)
        onizleme = el.find("t:Preview", NS)
        if onizleme is None:
            onizleme = el.find("t:BodyPreview", NS)
        ek_var = el.find("t:HasAttachments", NS)
        return Mesaj(
            item_id=item_id.get("Id", "") if item_id is not None else "",
            change_key=item_id.get("ChangeKey", "") if item_id is not None else "",
            konu=konu.text or "(konu yok)" if konu is not None else "(konu yok)",
            # EWS'te adres, ogenin metnidir (oznitelik degil).
            gonderen=(gonderen.text or "") if gonderen is not None else "",
            gonderen_ad=(ad.text or "") if ad is not None else "",
            tarih=_zaman(tarih.text) if tarih is not None else "",
            okundu=(okundu.text == "true") if okundu is not None else False,
            onizleme=(onizleme.text or "") if onizleme is not None else "",
            klasor=klasor,
            tariham=(tarih.text or "") if tarih is not None else "",
            ek_var=(ek_var.text == "true") if ek_var is not None else False,
        )

    def mesaj_detay(self, mesaj: Mesaj) -> Mesaj:
        """Mesaj govdesini ve ek listesini doldurur."""
        govde = (
            "<m:GetItem>"
            "<m:ItemShape><t:BaseShape>AllProperties</t:BaseShape>"
            "<t:BodyType>Best</t:BodyType></m:ItemShape>"
            f"<m:ItemIds><t:ItemId Id=\"{_kacis(mesaj.item_id)}\"/></m:ItemIds>"
            "</m:GetItem>"
        )
        kok = self.istek(govde)
        el = kok.find(".//m:Items/t:Message", NS)
        if el is None:
            return mesaj
        # Alıcılar (Yanıtla Herkese için)
        mesaj.alici = _adres_metni(el.find("t:ToRecipients", NS))
        mesaj.bilgi = _adres_metni(el.find("t:CcRecipients", NS))
        # Ekler once toplanir: <img> yer tutuculari (cid:...) ek adlariyla
        # eslesir.
        mesaj.ekler = []
        for ek_el in el.findall("t:Attachments/t:FileAttachment", NS):
            ek = Ek()
            ek.ad = ek_el.findtext("t:Name", "", NS)
            ek.tur = ek_el.findtext("t:ContentType", "", NS)
            # AttachmentId, oznitelik olarak gelir (metin degil).
            kimlik_el = ek_el.find("t:AttachmentId", NS)
            ek.ek_id = kimlik_el.get("Id", "") if kimlik_el is not None else ""
            ek.boyut = int(ek_el.findtext("t:Size", "0", NS) or 0)
            ek.mesaj_id = mesaj.item_id
            # Satir ici resimler <img src="cid:..."> ile baglanir.
            ek.content_id = (
                ek_el.findtext("t:ContentId", "", NS)
                or ek_el.findtext("t:ContentLocation", "", NS)
            ).strip()
            mesaj.ekler.append(ek)
        govde_el = el.find("t:Body", NS)
        if govde_el is not None:
            tur = (govde_el.get("BodyType") or "Text").lower()
            if tur == "html":
                mesaj.govde_html = govde_el.text or ""
                mesaj.govde = html_metni(
                    mesaj.govde_html, mesaj.resimler, mesaj.ekler
                )
            else:
                mesaj.govde = govde_el.text or ""
        return mesaj

    def ek_indir(self, ek: Ek) -> bytes:
        """Eki indirir.

        Sirasiyla denenir:
        1) EWS `GetAttachment` (saglikli sunucularda en hizli yol)
        2) Mesajin MIME icerigi (GetItem + IncludeMimeContent) — kurumda
           `GetAttachment` sunucu tarafinda "internal server error" verdigi
           icin ana yol budur
        3) REST API (kimlikte '/' olmayan mesajlarda)
        """
        # 1) dogrudan EWS (calismiyorsa bir daha deneme; MIME yolu var)
        if not self._getattachment_calismiyor:
            govde = (
                "<m:GetAttachment>"
                "<t:AttachmentShape><t:IncludeContent>true</t:IncludeContent></t:AttachmentShape>"
                f"<t:AttachmentIds><t:AttachmentId Id=\"{_kacis(ek.ek_id)}\"/></t:AttachmentIds>"
                "</m:GetAttachment>"
            )
            try:
                # tekrar=1: bu islem sunucuda bozuksa uzun bekleme olmasin.
                kok = self.istek(govde, tekrar=1)
                icerik = kok.find(".//t:Content", NS)
                if icerik is not None and icerik.text:
                    return base64.b64decode(icerik.text)
            except EwsHata:
                self._getattachment_calismiyor = True

        # 2) MIME yolu
        veri = self._mime_ek(ek)
        if veri is not None:
            return veri

        # 3) REST yolu
        veri = self._rest_ek_indir(ek)
        if veri is not None:
            return veri

        raise EwsHata(
            "Ek indirilemedi: sunucu ek servisini (GetAttachment) desteklemiyor "
            "ve mesajın MIME içeriği alınamadı."
        )

    def _mime_icerik(self, mesaj_id: str) -> bytes | None:
        """Mesajin tam MIME icerigini indirir (onbellekli)."""
        if not mesaj_id:
            return None
        if mesaj_id in self._mime_onbellek:
            return self._mime_onbellek[mesaj_id]
        govde = (
            "<m:GetItem>"
            "<m:ItemShape><t:BaseShape>IdOnly</t:BaseShape>"
            "<t:IncludeMimeContent>true</t:IncludeMimeContent></m:ItemShape>"
            f"<m:ItemIds><t:ItemId Id=\"{_kacis(mesaj_id)}\"/></m:ItemIds>"
            "</m:GetItem>"
        )
        try:
            kok = self.istek(govde)
        except EwsHata:
            return None
        mime_el = kok.find(".//t:MimeContent", NS)
        if mime_el is None or not mime_el.text:
            return None
        ham = base64.b64decode(mime_el.text)
        self._mime_onbellek[mesaj_id] = ham
        # MIME'lar buyuk olabilir; onbellek sinirli tutulur.
        while len(self._mime_onbellek) > 8:
            self._mime_onbellek.pop(next(iter(self._mime_onbellek)))
        return ham

    def _mime_ek(self, ek: Ek) -> bytes | None:
        """MIME iceriginden istenen ekin dosyasini cikarir."""
        ham = self._mime_icerik(ek.mesaj_id)
        if not ham:
            return None
        return _mime_den_ek(ham, ek.ad)

    def mesaj_mime(self, mesaj_id: str) -> bytes:
        """Mesajin tam MIME icerigini (.eml) dondurur."""
        ham = self._mime_icerik(mesaj_id)
        if not ham:
            raise EwsHata("Mesajın MIME içeriği (eml) alınamadı.")
        return ham

    def _rest_ek_indir(self, ek: Ek) -> bytes | None:
        """REST API (/api/v2.0) ile ek indirir; olmuyorsa None."""
        if not ek.mesaj_id or not ek.ek_id:
            return None
        if "/" in ek.mesaj_id or "/" in ek.ek_id:
            return None
        temel = f"https://{self.sunucu}/api/v2.0"
        try:
            yanit = self.oturum.get(
                f"{temel}/me/messages/{ek.mesaj_id}/attachments/{ek.ek_id}/$value",
                timeout=self.zaman_asimi,
                headers={"Accept": "application/octet-stream"},
            )
            if yanit.status_code != 200 or not yanit.content:
                return None
            return yanit.content
        except requests.RequestException:
            return None

    # ------------------------------------------------------------------ Yazma

    def gonder(
        self,
        alici: str,
        konu: str,
        govde: str,
        ekler: Iterable[tuple[str, bytes, str]] = (),
        cc: str = "",
        bcc: str = "",
    ) -> str:
        """E-posta gonderir. ekler: (ad, icerik, mime) ucluleri.

        **Neden ham MIME gönderiliyor?** `<t:Subject>` ile CreateItem çağrısı
        Exchange'te *native* kayıt oluşturur; ama Exchange bu kaydı SMTP'ye
        teslim ederken yeniden MIME üretir ve Subject header'ını **taşımaz** —
        alıcıda konu boş görünür (sentitems'ta ise dolu görünür, yanıltıcı).
        `t:MimeContent` ile ham RFC 5322 gövde gönderilince başlıklar (Subject,
        To, Cc, From) korunur ve alıcıda doğru görünür.
        """
        alici_listesi = _adres_listesi(alici)
        cc_listesi = _adres_listesi(cc)
        bcc_listesi = _adres_listesi(bcc)

        # --- Ham MIME gövde (başlıklar + gövde + ekler) ---
        gonderen = self.gonderen or ""
        if not gonderen:
            gonderen = self.kullanici
            if "@" not in gonderen:
                # 'KURUM\\kullanici' biçiminden alan adı çıkarılamaz; From
                # boş bırakılırsa Exchange kendi kutusundan doldurur.
                gonderen = ""
        satirlar = [
            f"Subject: {konu or ''}",
            f"To: {', '.join(alici_listesi)}",
        ]
        if gonderen:
            satirlar.append(f"From: {gonderen}")
        if cc_listesi:
            satirlar.append(f"Cc: {', '.join(cc_listesi)}")
        if bcc_listesi:
            satirlar.append(f"Bcc: {', '.join(bcc_listesi)}")
        satirlar += [
            "MIME-Version: 1.0",
            f"Date: {email.utils.formatdate(localtime=True)}",
            f"Message-ID: {email.utils.make_msgid()}",
        ]
        if ekler:
            satirlar.append(
                'Content-Type: multipart/mixed; boundary="=PostacimEkin"'
            )
            satirlar.append("")
            satirlar.append("--=PostacimEkin")
            satirlar.append("Content-Type: text/plain; charset=utf-8")
            satirlar.append("Content-Transfer-Encoding: base64")
            satirlar.append("")
            satirlar.append(
                base64.b64encode((govde or "").encode("utf-8")).decode("ascii")
            )
            for ad, icerik, mime in ekler:
                satirlar.append("--=PostacimEkin")
                satirlar.append(
                    f"Content-Type: {mime or 'application/octet-stream'};"
                )
                satirlar.append(f' name="{ad}"')
                satirlar.append("Content-Transfer-Encoding: base64")
                satirlar.append(
                    f'Content-Disposition: attachment; filename="{ad}"'
                )
                satirlar.append("")
                satirlar.append(base64.b64encode(icerik).decode("ascii"))
            satirlar.append("--=PostacimEkin--")
        else:
            satirlar.append("Content-Type: text/plain; charset=utf-8")
            satirlar.append("Content-Transfer-Encoding: base64")
            satirlar.append("")
            satirlar.append(
                base64.b64encode((govde or "").encode("utf-8")).decode("ascii")
            )
        mime = "\r\n".join(satirlar)
        b64 = base64.b64encode(mime.encode("utf-8")).decode("ascii")

        govde_xml = (
            "<m:CreateItem SendMeetingInvitationsOrCancellations=\"SendToNone\" "
            "MessageDisposition=\"SendAndSaveCopy\">"
            "<m:SavedItemFolderId><t:DistinguishedFolderId Id=\"sentitems\"/></m:SavedItemFolderId>"
            "<m:Items><t:Message>"
            f"<t:MimeContent CharacterSet=\"UTF-8\">{b64}</t:MimeContent>"
            "</t:Message></m:Items></m:CreateItem>"
        )
        kok = self.istek(govde_xml)
        kimlik = kok.find(".//m:Items/t:Message/t:ItemId", NS)
        return kimlik.get("Id", "") if kimlik is not None else ""

    def cozumle(self, metin: str, en_fazla: int = 20) -> list:
        """Kısmi ad/e-postayı kurum dizininde çözer (EWS ResolveNames).

        Outlook'taki "kişi adını yazınca kurum e-postasını bulma" davranışının
        karşılığıdır. [(ad, eposta), ...] döner; eşleşme yoksa boş liste.
        """
        metin = (metin or "").strip()
        if not metin:
            return []
        # Önce kişiler + dizin, olmazsa yalnız dizin (bazı sunucular kapsamı reddeder)
        for kapsam in ("ContactsActiveDirectory", "ActiveDirectory"):
            govde = (
                "<m:ResolveNames ReturnFullContactData=\"false\" "
                f"SearchScope=\"{kapsam}\">"
                f"<m:UnresolvedEntry>{_kacis(metin)}</m:UnresolvedEntry>"
                "</m:ResolveNames>"
            )
            try:
                kok = self.istek(govde)
            except EwsHata as exc:
                if "ErrorNameResolutionNoResults" in str(exc):
                    return []  # eşleşme yok
                if kapsam == "ContactsActiveDirectory":
                    continue  # kapsam desteklenmiyor olabilir
                raise
            sonuc = []
            # ÖNEMLİ: sunucu <t:Resolution> (types alanı) döndürür; bazı
            # kurulumlar m: alanını kullanabilir → ikisine de bakılır.
            cozumler = (
                kok.findall(".//t:Resolution", NS)
                or kok.findall(".//m:Resolution", NS)
            )
            for cozum in cozumler:
                kutu = cozum.find("t:Mailbox", NS)
                if kutu is None:
                    continue
                ad_el = kutu.find("t:Name", NS)
                eposta_el = kutu.find("t:EmailAddress", NS)
                eposta = (eposta_el.text or "").strip() if eposta_el is not None else ""
                ad = ((ad_el.text or "").strip() if ad_el is not None else "") or eposta
                if eposta:
                    sonuc.append((ad, eposta))
                if len(sonuc) >= en_fazla:
                    break
            return sonuc
        return []

    def taslağa_kaydet(self, alici: str, konu: str, govde: str) -> str:
        """Taslak olusturur (Gonder dugmesi degil)."""
        alici_listesi = ""
        for adres in _adres_listesi(alici):
            alici_listesi += (
                "<t:Mailbox><t:EmailAddress>%s</t:EmailAddress></t:Mailbox>" % _kacis(adres)
            )
        govde = (
            "<m:CreateItem SendMeetingInvitationsOrCancellations=\"SendToNone\" "
            "MessageDisposition=\"SaveOnly\">"
            "<m:SavedItemFolderId><t:DistinguishedFolderId Id=\"drafts\"/></m:SavedItemFolderId>"
            "<m:Items><t:Message>"
            f"<t:Subject>{_kacis(konu)}</t:Subject>"
            f"<t:Body BodyType=\"Text\">{_kacis(govde)}</t:Body>"
            "<t:ToRecipients>" + alici_listesi + "</t:ToRecipients>"
            "</t:Message></m:Items></m:CreateItem>"
        )
        kok = self.istek(govde)
        kimlik = kok.find(".//m:Items/t:Message/t:ItemId", NS)
        return kimlik.get("Id", "") if kimlik is not None else ""

    def okundu_isaretle(self, mesaj: Mesaj, okundu: bool = True) -> None:
        """Mesajı okundu/okunmadı olarak işaretler."""
        self.istek(_okundu_govde(mesaj.item_id, mesaj.change_key, okundu))

    def tasi(self, mesaj: Mesaj, hedef: str = "deleteditems") -> None:
        """Mesaji tasir (silmek icin 'deleteditems' hedefi kullanilir)."""
        govde = (
            "<m:MoveItem>"
            f"<m:ToFolderId>{_klasor_id_xml(hedef)}</m:ToFolderId>"
            f"<m:ItemIds><t:ItemId Id=\"{_kacis(mesaj.item_id)}\"/></m:ItemIds>"
            "</m:MoveItem>"
        )
        self.istek(govde)

    def klasor_olustur(self, ad: str, ebeveyn: str = "msgfolderroot") -> str:
        """Yeni klasör oluşturur (CreateFolder); yeni FolderId döndürür.

        Klasör adı sunucunun olduğu gibi kaydedilir (Türkçe karakterler
        sorunsuzdur). Yeniden deneme yapılmaz (tekrar=1): geçici bir hatadan
        sonra aynı istek tekrarlanırsa sunucuda **iki** klasör oluşabilir.
        """
        ad = (ad or "").strip()
        if not ad:
            raise EwsHata("Klasör adı boş olamaz.")
        ebeveyn_xml = (
            f'<t:DistinguishedFolderId Id="{_kacis(ebeveyn)}"/>'
            if ebeveyn in ("msgfolderroot", "root") or ebeveyn in KLASORLER
            else f'<t:FolderId Id="{_kacis(ebeveyn)}"/>'
        )
        govde = (
            "<m:CreateFolder>"
            f"<m:ParentFolderId>{ebeveyn_xml}</m:ParentFolderId>"
            "<m:Folders>"
            "<t:Folder>"
            f"<t:DisplayName>{_kacis(ad)}</t:DisplayName>"
            "</t:Folder>"
            "</m:Folders>"
            "</m:CreateFolder>"
        )
        kok =         self.istek(govde, tekrar=1)
        el = kok.find(".//m:Folders/t:Folder/t:FolderId", NS)
        if el is None or not el.get("Id"):
            raise EwsHata("Klasör oluşturuldu ancak kimliği alınamadı.")
        # Yeni klasör listede hemen görünsün: FindFolder önbelleği düşer
        self._ozel_klasor_onbellek = None
        return el.get("Id")

    def klasor_yeniden_adlandir(self, kimlik: str, yeni_ad: str) -> str:
        """Klasörü yeniden adlandırır (UpdateFolder); kimlik değişmez.

        Exchange, yazma işleminde güncel ChangeKey ister; o yüzden önce
        tek GetFolder ile kimlik + ChangeKey tazelenir, sonra DisplayName
        alanı güncellenir. Varsayılan 7 klasör reddedilir. Tekrar edilmez
        (tekrar=1): geçici hatada iki kez yazılmasın.
        """
        yeni_ad = (yeni_ad or "").strip()
        if not yeni_ad:
            raise EwsHata("Klasör adı boş olamaz.")
        if kimlik in KLASORLER:
            raise EwsHata(
                "Varsayılan klasör (gelen kutusu, gönderilmiş, taslak, "
                "silinmiş, önemsiz, arşiv, giden kutusu) yeniden "
                "adlandırılamaz."
            )
        govde = (
            "<m:GetFolder>"
            '<m:FolderShape><t:BaseShape>Default</t:BaseShape></m:FolderShape>'
            f"<m:FolderIds>{_klasor_id_xml(kimlik)}</m:FolderIds>"
            "</m:GetFolder>"
        )
        kok = self.istek(govde, tekrar=1)
        el = kok.find(".//m:Folders/t:Folder/t:FolderId", NS)
        if el is None or not el.get("Id"):
            raise EwsHata("Klasörün güncel kimliği alınamadı.")
        degis_anahtari = el.get("ChangeKey", "")
        govde = (
            "<m:UpdateFolder>"
            "<m:FolderChanges>"
            "<t:FolderChange>"
            f'<t:FolderId Id="{_kacis(el.get("Id"))}"'
            f' ChangeKey="{_kacis(degis_anahtari)}"/>'
            "<m:Updates>"
            "<t:SetItemField>"
            '<t:FieldURI FieldURI="folder:DisplayName"/>'
            "<t:Folder>"
            f"<t:DisplayName>{_kacis(yeni_ad)}</t:DisplayName>"
            "</t:Folder>"
            "</t:SetItemField>"
            "</m:Updates>"
            "</t:FolderChange>"
            "</m:FolderChanges>"
            "</m:UpdateFolder>"
        )
        self.istek(govde, tekrar=1)
        # Ağaçta yeni ad hemen görünsün: FindFolder önbelleği düşer
        self._ozel_klasor_onbellek = None
        return kimlik

    def klasoru_bosalt(self, kimlik: str) -> int:
        """Klasördeki tüm mesajları kalıcı siler; silinen sayıyı döndürür.

        Yalnız çöp kutusu ve spam klasörüne izin verilir. `EmptyFolder`
        yerine SyncFolderItems + toplu `DeleteItem HardDelete` kullanılır:
        kurum sunucusunda SyncFolderItems/DeleteItem çalıştığı doğrulanmış
        işlemlerdir ve silinen mesaj sayısı sayılabilir kalır.
        """
        if kimlik not in ("deleteditems", "junkemail"):
            raise EwsHata(
                "Yalnız çöp kutusu ve spam klasörü bu yolla boşaltılabilir."
            )
        silinen = 0
        durum = ""
        deneme = 0
        while deneme < 400:  # güvenlik üst sınırı: sonsuz döngüye girme
            deneme += 1
            govde = (
                "<m:SyncFolderItems>"
                '<m:ItemShape><t:BaseShape>IdOnly</t:BaseShape></m:ItemShape>'
                f"<m:SyncFolderId>{_klasor_id_xml(kimlik)}</m:SyncFolderId>"
                f"<m:SyncState>{durum}</m:SyncState>"
                "<m:MaxChangesReturned>512</m:MaxChangesReturned>"
                "</m:SyncFolderItems>"
            )
            kok = self.istek(govde)
            durum_el = kok.find(".//m:SyncState", NS)
            if durum_el is not None and durum_el.text:
                durum = durum_el.text
            ogeler = [
                (el.get("Id"), el.get("ChangeKey") or "")
                for el in kok.findall(".//m:Changes//t:ItemId", NS)
                if el.get("Id")
            ]
            if ogeler:
                silinen += self._kalici_sil_coklu(ogeler)
            son = kok.find(".//m:IncludesLastItemInRange", NS)
            if son is not None and (son.text or "").lower() == "true":
                break
        # Klasör artık boş: senkron önbelleği düşür (ilk açılışta baştan)
        self._senkronizasyon.pop(kimlik, None)
        return silinen

    def _kalici_sil_coklu(self, ogeler: list) -> int:
        """Mesajları HardDelete ile topluca siler (istek başına ≤100).

        Toplu istek `ErrorItemNotFound` verirse (öğeler senkron ile
        silme arasında kaybolmuş olabilir) tek tek denenir; artık
        bulunmayan öğeler atlanır, diğer hatalar yükselir.
        """
        silinen = 0
        bulunamayan = 0
        for bas in range(0, len(ogeler), 100):
            grup = ogeler[bas : bas + 100]
            try:
                self.istek(self._kalici_sil_govdesi(grup))
                silinen += len(grup)
                continue
            except EwsHata as exc:
                if "ErrorItemNotFound" not in str(exc):
                    raise
            # Yolu A: bazı öğeler yok — tek tek dene, yokları atla
            for oge in grup:
                try:
                    self.istek(self._kalici_sil_govdesi([oge]))
                    silinen += 1
                except EwsHata as tek:
                    if "ErrorItemNotFound" in str(tek):
                        bulunamayan += 1
                    else:
                        raise
        if silinen == 0 and bulunamayan:
            raise EwsHata(
                f"Mesajlar silinemedi: {bulunamayan} öğe sunucuda "
                "bulunamadı (ErrorItemNotFound)."
            )
        return silinen

    @staticmethod
    def _kalici_sil_govdesi(ogeler: list) -> str:
        """HardDelete istek gövdesi (Id + ChangeKey)."""
        ids = "".join(
            (
                f'<t:ItemId Id="{_kacis(i)}" ChangeKey="{_kacis(k)}"/>'
                if k else f'<t:ItemId Id="{_kacis(i)}"/>'
            )
            for i, k in ogeler
        )
        return (
            '<m:DeleteItem DeleteType="HardDelete">'
            f"<m:ItemIds>{ids}</m:ItemIds>"
            "</m:DeleteItem>"
        )

    def kalici_sil(self, mesaj: Mesaj) -> None:
        govde = (
            "<m:DeleteItem DeleteType=\"HardDelete\">"
            f"<m:ItemIds><t:ItemId Id=\"{_kacis(mesaj.item_id)}\"/></m:ItemIds>"
            "</m:DeleteItem>"
        )
        self.istek(govde)


def _mime_den_ek(ham: bytes, ad: str) -> bytes | None:
    """MIME mesajindan dosya adina gore ekin icerigini cikarir.

    `GetAttachment` calismayan sunucularda ekler mesajin MIME iceriginden
    (GetItem + IncludeMimeContent) bu sekilde alinir.
    """
    if not ham:
        return None
    try:
        ilet = BytesParser(policy=mime_policy.default).parsebytes(ham)
    except Exception:
        return None

    adaylar: list[tuple[str, bytes]] = []
    for parca in ilet.walk():
        if parca.is_multipart():
            continue
        dosya = parca.get_filename() or ""
        if not dosya and parca.get_content_disposition() != "attachment":
            continue
        try:
            veri = parca.get_payload(decode=True)
        except Exception:
            veri = None
        if veri:
            adaylar.append((dosya, veri))
    if not adaylar:
        return None
    # Isme gore ara; bulunamazsa tek aday varsa onu ver.
    for dosya, veri in adaylar:
        if dosya and dosya == ad:
            return veri
    if len(adaylar) == 1:
        return adaylar[0][1]
    return None


def _adres_metni(el) -> str:
    """t:ToRecipients / t:CcRecipients ogelerini 'a@b.c, d@e.f' bicimine cevirir."""
    if el is None:
        return ""
    adresler = []
    for kutu in el.findall("t:Mailbox", NS):
        a = kutu.find("t:EmailAddress", NS)
        if a is not None and a.text:
            adresler.append(a.text.strip())
    return ", ".join(adresler)


_AD_DUZEN = re.compile(r"<([^<>]+)>\s*$")


def _adres_listesi(metin: str) -> list:
    """'a@b.c, Ad Soyad <d@e.f>' -> ['a@b.c', 'd@e.f']"""
    if not metin:
        return []
    parcalar = re.split(r"[;,]", metin)
    sonuc = []
    for parca in parcalar:
        parca = parca.strip()
        if not parca:
            continue
        eslesme = _AD_DUZEN.search(parca)
        if eslesme:  # "Ad Soyad <adres>" biçiminden adresi al
            parca = eslesme.group(1).strip()
        if parca:
            sonuc.append(parca)
    return sonuc


_IMG_DUZEN = re.compile(r"(?is)<img\b[^>]*>")
_OZELLIK_DUZEN = r'{ad}\s*=\s*(?:"([^"]*)"|\'([^\']*)\'|([^\s>]+))'


def _img_ozellik(etiket: str, ad: str) -> str:
    """<img ...> etiketindeki bir özniteliğin değerini okur."""
    m = re.search(_OZELLIK_DUZEN.format(ad=re.escape(ad)), etiket, re.I)
    if not m:
        return ""
    deger = next((g for g in m.groups() if g is not None), "")
    return html_mod.unescape(deger).strip()


def _url_dosya_adi(kaynak: str) -> str:
    """http(s)://.../dosya.png?x=1 → dosya.png"""
    yol = kaynak.split("?", 1)[0].split("#", 1)[0].rstrip("/")
    ad = os.path.basename(yol)
    try:
        from urllib.parse import unquote

        ad = unquote(ad)
    except Exception:
        pass
    return ad


def _resim_adi(kaynak: str, alt: str, ekler: list | None) -> str:
    """<img> için gösterilecek dosya adını seçer.

    Öncelik: eşleşen ek (Content-Id / ad) → alt metni → URL/cid dosya adı.
    """
    if kaynak.lower().startswith("data:"):
        return _ad_temizle(alt) or "yerleşik resim"
    hedef = kaynak.strip()
    if hedef.lower().startswith("cid:"):
        hedef = hedef[4:]
    hedef_ad = _url_dosya_adi(hedef)
    for ek in ekler or []:
        if not ek.ad:
            continue
        cid = (ek.content_id or "").strip().strip("<>")
        if (hedef and (hedef == cid or hedef == ek.ad)) or (
            hedef_ad and hedef_ad == ek.ad
        ):
            return ek.ad
    if alt and alt.lower() not in ("resim", "image", "logo", "photo"):
        return _ad_temizle(alt)
    if hedef_ad:
        return _ad_temizle(hedef_ad)
    return _ad_temizle(alt) or "resim"


def _ad_temizle(ad: str) -> str:
    """Yer tutucu metnine güvenle girecek ad (etiket sözdizimi bozulmasın)."""
    ad = re.sub(r"[\x00-\x1f<>]", " ", ad or "")
    return re.sub(r"\s+", " ", ad).strip()


def html_metni(html_kaynak: str, resimler: list | None = None, ekler: list | None = None) -> str:
    """HTML govdeyi okunabilir duz metne cevirir (harici bagimlilik yok).

    `<img>` ögeleri sessizce atılmaz; Evolution tarzı dosya adı yer
    tutucusu (`[resim: ad]`) bırakılır. `resimler` listesi verilirse her
    `<img>` için bir `Resim` kaydı eklenir (gösterimde tıklanabilir olur).
    """
    if not html_kaynak:
        return ""
    metin = re.sub(r"(?is)<(script|style|head)[^>]*>.*?</\1>", " ", html_kaynak)

    def _img_yerine(eslesme) -> str:
        etiket = eslesme.group(0)
        kaynak = _img_ozellik(etiket, "src")
        alt = _img_ozellik(etiket, "alt")
        ad = _resim_adi(kaynak, alt, ekler)
        yer = f"[resim: {ad}]"
        if resimler is not None:
            resimler.append(Resim(ad=ad, kaynak=kaynak, yer_tutucu=yer))
        return yer

    metin = _IMG_DUZEN.sub(_img_yerine, metin)
    metin = re.sub(r"(?i)<br\s*/?>", "\n", metin)
    metin = re.sub(r"(?i)</(p|div|tr|h[1-6]|li)>", "\n", metin)
    metin = re.sub(r"(?i)<li[^>]*>", " • ", metin)
    metin = re.sub(r"(?s)<[^>]+>", "", metin)
    metin = html_mod.unescape(metin)
    metin = metin.replace("\xa0", " ")
    metin = re.sub(r"[ \t]+", " ", metin)
    metin = re.sub(r"\n\s*\n\s*\n+", "\n\n", metin)
    return metin.strip()


def _data_uri_verisi(kaynak: str) -> bytes | None:
    """data:image/png;base64,AAA → baytlar; data: değilse None."""
    if not kaynak.lower().startswith("data:"):
        return
    try:
        baslik, veri = kaynak.split(",", 1)
    except ValueError:
        return
    if ";base64" in baslik.lower():
        try:
            return base64.b64decode(veri)
        except Exception:
            return
    from urllib.parse import unquote_to_bytes

    return unquote_to_bytes(veri)


def data_uri_verisi(kaynak: str) -> bytes | None:
    """`data:` URI'yi bayta çevirir; URI değilse None (arayüz gömme için)."""
    return _data_uri_verisi(kaynak)


def _mime_resim_bul(ham: bytes, hedef: str) -> bytes | None:
    """MIME icindeki resim parcasiini bulur (Content-Id ya da dosya adiyla)."""
    hedef = hedef.strip()
    if hedef.lower().startswith("cid:"):
        hedef = hedef[4:]
    hedef = hedef.strip().strip("<>")
    hedef_ad = os.path.basename(hedef.split("?", 1)[0])
    for parca in BytesParser(policy=mime_policy.default).parsebytes(ham).walk():
        if parca.is_multipart():
            continue
        cid = (parca.get("Content-ID") or "").strip().strip("<>")
        konum = (parca.get("Content-Location") or "").strip()
        ad = parca.get_filename() or ""
        adaylar = {cid, konum, ad, os.path.basename(konum)}
        if hedef and hedef in adaylar:
            try:
                return parca.get_payload(decode=True) or b""
            except Exception:
                return None
    return None


def resim_verisi(istemci, mesaj: Mesaj, resim: Resim,
                 ham: bytes | None = None) -> bytes:
    """Gövdedeki bir yer tutucunun resim baytlarını getirir.

    Sırasıyla denenir: `data:` gömülü, `http(s)` indirme, mesajın MIME
    içeriğinde Content-Id/dosya adı arama, ek listesinden `ek_indir`.
    `ham` verilmişse (önceden çekilmiş MIME) tekrar çekilmez — çok
    resimli mesajlarda sunucuya aynı MIME için defalarca gidilmez.
    """
    kaynak = (resim.kaynak or "").strip()
    if not kaynak:
        raise EwsHata("Resmin kaynağı (src) boş.")

    if kaynak.lower().startswith("data:"):
        veri = _data_uri_verisi(kaynak)
        if veri is not None:
            return veri
        raise EwsHata("Gömülü resim (data:) çözülemedi.")

    if kaynak.lower().startswith(("http://", "https://")):
        try:
            # Birçok CDN (ör. Hepsiburada) tarayıcı kimliği (User-Agent)
            # olmayan istekleri 403 ile reddedir; bu yüzden resim
            # indirmeleri tarayıcı kimliğiyle gönderilir.
            yanit = requests.get(kaynak, timeout=20, headers=TARAYICI_BASLIK)
            if yanit.status_code == 401 and getattr(istemci, "oturum", None) is not None:
                # Kurum içi barındırılan resimler NTLM isteyebilir.
                yanit = istemci.oturum.get(kaynak, timeout=20, headers=TARAYICI_BASLIK)
            yanit.raise_for_status()
            return yanit.content
        except requests.RequestException as exc:
            raise EwsHata(f"Resim indirilemedi: {exc}") from exc

    hedef = kaynak[4:] if kaynak.lower().startswith("cid:") else kaynak
    hedef = hedef.strip().strip("<>")
    if ham is None:
        try:
            ham = istemci.mesaj_mime(mesaj.item_id)
        except EwsHata:
            ham = None
    if ham:
        veri = _mime_resim_bul(ham, hedef)
        if veri:
            return veri

    for ek in mesaj.ekler:
        cid = (ek.content_id or "").strip().strip("<>")
        if hedef and hedef in (cid, ek.ad):
            return istemci.ek_indir(ek)

    raise EwsHata(f"Resim bulunamadı: {resim.ad or kaynak}")


RESIM_SEMASI = "postacim-resim:"  # yer tutucu bağlantısı: postacim-resim:0

# Uzak resim indirmeleri için tarayıcı kimliği (CDN'ler UA'sız istekleri
# 403 ile reddeder; bkz. resim_verisi).
TARAYICI_BASLIK = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
}

_GOSTERIM_STILI = (
    "<style>"
    "body { font-family: sans-serif; font-size: 10pt; color: #1b1b1b;"
    " background: #ffffff; margin: 10px 16px; }"
    "a { color: #0b57d0; }"
    "img { max-width: 100%; }"
    "</style>"
)

# HTML'de kendiliğinden kapanan etiketler (kapanış yazılmaz)
_BOS_ETIKET = frozenset({
    "area", "base", "br", "col", "embed", "hr", "img", "input",
    "link", "meta", "source", "track", "wbr",
})
_ETIKET_DUZEN = re.compile(r"(?is)</?([a-zA-Z][a-zA-Z0-9]*)\b[^>]*?>")


_YORUM_DUZEN = re.compile(
    r"(?s)<!--.*?-->"                          # yorum (mso koşullu yorum dâhil)
    r"|<script\b[^>]*>.*?</script\s*>"          # script gövdesi
    r"|<style\b[^>]*>.*?</style\s*>",           # style gövdesi
    re.I,
)


def _opak_bolunmus(html: str) -> list[tuple[bool, str]]:
    """HTML'i (opak mı, metin) parçalarına ayırır.

    Yorumlar ile script/style gövdeleri opaktır: içindeki etiket
    benzeri metinler gerçek akışı etkilemez. AliExpress tipi e-posta
    `<table>` içeren `<!--[if mso | IE]>…<![endif]-->` yorumlarıyla
    doludur; bu hayalet etiketler onarım fonksiyonlarını yanıltıp
    gerçek tabloyu bozunca Tkhtml (C) segfault üretir.
    """
    parcalar: list[tuple[bool, str]] = []
    son = 0
    for eslesme in _YORUM_DUZEN.finditer(html):
        if eslesme.start() > son:
            parcalar.append((False, html[son:eslesme.start()]))
        parcalar.append((True, eslesme.group(0)))
        son = eslesme.end()
    if son < len(html):
        parcalar.append((False, html[son:]))
    return parcalar


def html_taglari_kapat(html: str) -> str:
    """Kapanmamış etiketleri yığınla kapatır.

    Tkhtml (C) kapanmamış `<table>`/`<tbody>` yapısına sonradan gelen
    yeni tabloyu işlerken segfault üretir (ör. Tivibu karşılama e-postası).
    `</body>`/`</html>` görülmeden önce yığındaki etiketler kapatılır.
    Yorumlar ve script/style gövdeleri dokunulmazdır.
    """
    yigin: list[str] = []
    parcalar: list[str] = []
    for opak, metin in _opak_bolunmus(html):
        if opak:
            parcalar.append(metin)
            continue
        son = 0
        for eslesme in _ETIKET_DUZEN.finditer(metin):
            parcalar.append(metin[son:eslesme.start()])
            son = eslesme.end()
            etiket = eslesme.group(1).lower()
            ham = eslesme.group(0)
            if ham.startswith("</"):
                if etiket in yigin:
                    kapanislar: list[str] = []
                    while yigin:
                        t = yigin.pop()
                        kapanislar.append(f"</{t}>")
                        if t == etiket:
                            break
                    # İçteki etiketleri önce kapat (yığın tepesi en içte),
                    # asıl kapanış yerinde dursun
                    parcalar.append("".join(kapanislar[:-1]))
                    parcalar.append(ham)
                else:
                    parcalar.append(ham)
            else:
                if etiket not in _BOS_ETIKET and not ham.endswith("/>"):
                    yigin.append(etiket)
                parcalar.append(ham)
        parcalar.append(metin[son:])
    if yigin:
        parcalar.append("".join(f"</{t}>" for t in reversed(yigin)))
    return "".join(parcalar)


_TABLO_ETIKET_DUZEN = re.compile(
    r"<(/?)(table|tbody|thead|tfoot|tr|td|th)\b[^>]*>", re.I
)


def html_tablolar_onar(html: str) -> str:
    """`<table>` çocuğu doğrudan `<table>` olan yapıları onarır.

    Kötü biçimli e-posta HTML'inde tablo, arada `<tr><td>` olmadan iç içe
    gelir: `<table><table>…</table></table>`. Tarayıcılar bunu sessizce
    sarar; **Tkhtml3 (C) yerli bileşeninde segfault üretir** (herhangi bir
    içerikte, boş tabloda bile). Bu geçiş her çıplak çocuğu
    `<table><tr><td><table>…</table></td></tr></table>` biçimine sarar;
    tarayıcıların uyguladığı kuralın aynısıdır.
    """
    yigin: list[dict] = []  # yalnız tablo çerçeveleri
    parcalar: list[str] = []
    for opak, metin in _opak_bolunmus(html):
        if opak:
            parcalar.append(metin)
            continue
        son = 0
        for eslesme in _TABLO_ETIKET_DUZEN.finditer(metin):
            parcalar.append(metin[son:eslesme.start()])
            son = eslesme.end()
            kapanis = eslesme.group(1) == "/"
            ad = eslesme.group(2).lower()
            if not kapanis:
                if ad == "table":
                    ust = yigin[-1] if yigin else None
                    sardi = ust is not None and not ust["hucre"]
                    if sardi:
                        # Hücresiz bölgede açılan çocuk tablo: sar
                        parcalar.append("<tr><td>")
                        ust["hucre"] = True
                    yigin.append({"hucre": False, "sardi": sardi})
                elif ad in ("td", "th"):
                    if yigin:
                        yigin[-1]["hucre"] = True
                elif ad == "tr":
                    if yigin:
                        yigin[-1]["hucre"] = False  # yeni satır, hücre açılmadı
                parcalar.append(eslesme.group(0))
            else:
                if ad == "table" and yigin:
                    ust = yigin.pop()
                    parcalar.append(eslesme.group(0))
                    if ust["sardi"]:
                        parcalar.append("</td></tr>")
                        if yigin:
                            yigin[-1]["hucre"] = False
                    continue
                if ad == "tr" and yigin:
                    yigin[-1]["hucre"] = False
                elif ad == "td" and yigin:
                    yigin[-1]["hucre"] = False  # hücre kapandı
                parcalar.append(eslesme.group(0))
        parcalar.append(metin[son:])
    if yigin:
        # Dosya sonu: açık tablolar kapatılırken sarmalama unutulmasın
        kapanislar = []
        while yigin:
            ust = yigin.pop()
            if ust["sardi"]:
                kapanislar.append("</table></td></tr>")
            else:
                kapanislar.append("</table>")
        parcalar.append("".join(kapanislar))
    return "".join(parcalar)


def govde_html_gosterim(mesaj: Mesaj, gecen: dict | None = None) -> str:
    """Gövdeyi HTML gösterimi için hazırlar (tkinterweb/Tkhtml3).

    Her `<img>` sırasıyla `mesaj.resimler` kayıtlarına denk gelir: `gecen`
    (sıra no → HTML parçası) içinde olan doğrudan yazılır (gömülü `data:`
    resim ya da "görüntülenemedi" notu); olmayan Evolution tarzı yer
    tutucu bağlantı olarak kalır (`[resim: ad]`, `RESIM_SEMASI` + sıra no).
    Dış kaynaklardan hiçbir şey yüklenmez; `script` etiketleri atılır.
    """
    gecen = gecen or {}
    kaynak = (mesaj.govde_html or "").strip()
    if not kaynak:
        metin = html_mod.escape(mesaj.govde or mesaj.onizleme or "(gövde yok)")
        return _GOSTERIM_STILI + f"<pre>{metin}</pre>"

    sayac = 0

    def _img_yerine(eslesme) -> str:
        nonlocal sayac
        i = sayac
        sayac += 1
        if i in gecen:
            return gecen[i]
        ad = mesaj.resimler[i].ad if i < len(mesaj.resimler) else "resim"
        ad = html_mod.escape(_ad_temizle(ad))
        return f'<a href="{RESIM_SEMASI}{i}">[resim: {ad}]</a>'

    govde = _IMG_DUZEN.sub(_img_yerine, kaynak)
    govde = re.sub(r"(?is)<script\b[^>]*>.*?</script\s*>", " ", govde)
    govde = re.sub(r"(?is)<script\b[^>]*/>", " ", govde)
    # Yönlendirme/temel URL'ler gösterimi şaşırtmasın.
    govde = re.sub(r"(?is)<base\b[^>]*>", " ", govde)
    govde = re.sub(r"(?is)<meta\b[^>]*http-equiv[^>]*>", " ", govde)
    # Kapanmamış tablo/tbody + sonradan gelen tablo Tkhtml'i çökertir.
    govde = html_taglari_kapat(govde)
    # `<table><table>` (hücresiz iç içe tablo) da Tkhtml'i çökertir.
    govde = html_tablolar_onar(govde)
    return _GOSTERIM_STILI + govde


def govde_metin_gosterim(mesaj: Mesaj, gecen: dict | None = None) -> str:
    """HTML gösterimi çökme üreten ileti için düz metin gösterimi.

    `govde_html_gosterim` çıktısı alt süreç denetiminde Tkhtml'i
    çökertiyorsa arayüz bu güvenli gösterime döner: gövde metni
    `<pre>` içinde kaçırılmış olarak basılır; resim yer tutucuları
    tıklanabilir bağlantıdır (RESIM_SEMASI + sıra no). `gecen`
    (sıra no → HTML parçası) içindeki resim, yer tutucunun
    yanında `<img>` olarak da belirir.
    """
    gecen = gecen or {}
    metin = mesaj.govde or mesaj.onizleme or "(gövde yok)"
    satirlar: list[str] = []
    resimler = mesaj.resimler or []
    kalan = metin
    for no, resim in enumerate(resimler):
        yer_tutucu = getattr(resim, "yer_tutucu", "")
        if not yer_tutucu or yer_tutucu not in kalan:
            continue
        ad = html_mod.escape(_ad_temizle(resim.ad))
        if no in gecen:
            parca = gecen[no]  # çözüldü: yer tutucu yerine resim/hata notu
        else:
            parca = f'<a href="{RESIM_SEMASI}{no}">[resim: {ad}]</a>'
        on, _, kalan = kalan.partition(yer_tutucu)
        satirlar.append(html_mod.escape(on))
        satirlar.append(parca)
    satirlar.append(html_mod.escape(kalan))
    return _GOSTERIM_STILI + "<pre>" + "".join(satirlar) + "</pre>"
