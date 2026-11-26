"""CalDAV istemcisi (açık standart takvim protokolü).

Nextcloud, iCloud, Yahoo, Fastmail, Gmail (uygulama şifresi) gibi
herhangi bir CalDAV sunucusuna bağlanır. Yalnızca gerekli olan
minimum kapsama sahiptir: keşif, randevu okuma/yazma/silme.

iCalendar (RFC 5545) ayrıştırma/üretme bu dosyada basitçe yapılır;
harici bağımlılık yoktur.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Iterable
from urllib.parse import urljoin, urlparse

import requests

from . import google_oturum

NS_DAV = "DAV:"
NS_CALENDAR = "urn:ietf:params:xml:ns:caldav"
NS_ICS = "http://calendarserver.org/ns/"

# Tamamlandı işareti olayın kendisine yazılır (tüm makinelarda geçerli);
# RFC 5545 özel X- alanı — sunucular (Google dahil) bunu koruyor.
TAMAMLANDI_ALANI = "X-POSTACIM-TAMAMLANDI"

HEADERS_BASE = {
    "User-Agent": "Postacim/1.0",
    "Content-Type": "application/xml; charset=utf-8",
}


class CalDavHata(Exception):
    """CalDAV isteği başarısız."""


@dataclass
class CalDavTakvim:
    """Uzak takvim koleksiyonu."""

    url: str = ""           # koleksiyon URL'i (PUT/REPORT hedefi)
    ad: str = ""
    renk: str = ""
    tanim: str = ""
    destekli: bool = True


@dataclass
class RandevuKaydi:
    """CalDAV VEVENT kaydı (takvim_ews.Randevu ile uyumlu alanlar)."""

    uid: str = ""
    url: str = ""           # kayıt URL'i (PUT/DELETE hedefi)
    etag: str = ""
    baslik: str = ""
    baslangic: str = ""     # ISO: YYYY-MM-DDTHH:MM:SS (yerel ya da UTC)
    bitis: str = ""
    konum: str = ""
    tum_gun: bool = False
    aciklama: str = ""
    organizator: str = ""
    tur: str = "Single"
    ics: str = ""           # ham iCalendar (güncelleme için)
    tamamlandi: bool = False  # sunucudaki X-POSTACIM-TAMAMLANDI alanından
    rrule: str = ""         # tekrarlama kuralı (RFC 5545)
    exdate: str = ""        # hariç tutulan tarihler (virgüllü)
    rdate: str = ""         # eklenen tarihler (virgüllü)
    kaynak_id: str = ""     # kaynak takvim hesabının kimliği (çoklu hesap)
    kaynak_tur: str = ""    # "caldav" | "ews"
    occurrence_id: str = "" # tekrar kopyasının benzersiz kimliği

    @property
    def item_id(self) -> str:
        return self.uid

    @property
    def change_key(self) -> str:
        return self.etag

    @property
    def kimlik(self) -> str:
        """Seçim/işaret için benzersiz kimlik (tekrar kopyaları ayrışır)."""
        return self.occurrence_id or self.uid

    @property
    def gun(self) -> str:
        from .ews import iso_yerel

        yerel = iso_yerel(self.baslangic)
        if yerel is None:
            return (self.baslangic or "")[:10]
        return yerel.strftime("%Y-%m-%d")


# ---------------------------------------------------------------- iCalendar

def _ics_satirlari_bol(ics: str) -> list[str]:
    """Katlanmış iCalendar satırlarını açar (RFC 5545 §3.1)."""
    ham = ics.replace("\r\n", "\n").replace("\r", "\n")
    satirlar: list[str] = []
    for parca in ham.split("\n"):
        if parca.startswith((" ", "\t")) and satirlar:
            satirlar[-1] += parca[1:]
        else:
            satirlar.append(parca)
    return satirlar


def _ics_alan(satir: str) -> tuple[str, dict, str]:
    """'KEY;PARAM=değer:metin' → (anahtar, parametreler, metin)."""
    if ":" not in satir:
        return "", {}, ""
    # Noktalı virgül anahtar/parametre bölgesi (değerlerde ':' olabilir)
    sol, _, sag = satir.partition(":")
    parcalar = sol.split(";")
    anahtar = parcalar[0].upper()
    parametreler: dict[str, str] = {}
    for p in parcalar[1:]:
        if "=" in p:
            k, _, v = p.partition("=")
            parametreler[k.upper()] = v.strip('"')
    return anahtar, parametreler, sag


def _tzid_coz(y: int, a: int, g: int, sa: int, dk: int, sn: int, tzid: str):
    """TZID (örn. 'Europe/Istanbul') → saat dilimi bilgisi.

    VTIMEZONE içinde tanımlanan özel dilimler çözülemez; bu durumda
    None döner ve zaman yerel saat olarak yorumlanır.
    """
    try:
        from zoneinfo import ZoneInfo

        return datetime(y, a, g, sa, dk, sn, tzinfo=ZoneInfo(tzid))
    except Exception:
        return None


def _ics_zaman(deger: str, parametreler: dict) -> str:
    """iCalendar zamanını ISO string'e çevirir (UTC Z ya da yerel).

    TZID verilmişse o saat dilimindeki yerel saat UTC'ye çevrilir;
    çözülemeyen TZID'de yerel saat varsayılır.
    """
    deger = deger.strip()
    if not deger:
        return ""
    # DATE (tüm gün): 20260101
    if len(deger) == 8 and deger.isdigit():
        return f"{deger[:4]}-{deger[4:6]}-{deger[6:]}T00:00:00"
    # YYYYMMDDTHHMMSS[Z]
    m = re.match(
        r"^(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})(Z?)$", deger
    )
    if not m:
        return deger
    y, a, g, sa, dk, sn, z = m.groups()
    iso = f"{y}-{a}-{g}T{sa}:{dk}:{sn}"
    if z:
        return iso + "Z"
    tzid = (parametreler or {}).get("TZID", "")
    if tzid:
        dt = _tzid_coz(int(y), int(a), int(g), int(sa), int(dk), int(sn), tzid)
        if dt is not None:
            return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return iso


def _ics_kacis_coz(deger: str) -> str:
    """iCalendar kaçışlarını çözer (\\; \\, \\n \\\\)."""
    return (
        deger.replace("\\n", "\n")
        .replace("\\N", "\n")
        .replace("\\,", ",")
        .replace("\\;", ";")
        .replace("\\\\", "\\")
    )


def _tarihler_birlestir(kayitlar: list[tuple[str, dict]]) -> str:
    """EXDATE/RDATE satırlarını tek bir ISO tarih dizesine çevirir.

    Her satır (değer, parametreler) çifti; virgülle ayrılmış değerler
    tek tek ele alınır. TZID verilmişse UTC'ye çevrilir.
    """
    parcalar: list[str] = []
    for deger, parametreler in kayitlar or []:
        for parca in (deger or "").split(","):
            parca = parca.strip()
            if not parca:
                continue
            parcalar.append(_ics_zaman(parca, parametreler))
    return ",".join(parcalar)


def ics_randevulari(ics: str, kaynak_url: str = "", etag: str = "") -> list[RandevuKaydi]:
    """iCalendar metninden VEVENT kayıtlarını çıkarır."""
    sonuc: list[RandevuKaydi] = []
    icinde = False
    kayit: dict = {}
    aciklama_satirlari: list[str] = []
    aciklama_modu = False

    def kapat():
        nonlocal kayit, aciklama_satirlari
        if kayit.get("UID"):
            aciklama = "\n".join(aciklama_satirlari).strip()
            aciklama = _ics_kacis_coz(aciklama)
            sonuc.append(
                RandevuKaydi(
                    uid=kayit.get("UID", ""),
                    url=kaynak_url,
                    etag=etag,
                    baslik=_ics_kacis_coz(kayit.get("SUMMARY", "")) or "(başlıksız)",
                    baslangic=_ics_zaman(
                        kayit.get("DTSTART", ""),
                        kayit.get("_dtstart_param", {}),
                    ),
                    bitis=_ics_zaman(
                        kayit.get("DTEND", ""),
                        kayit.get("_dtend_param", {}),
                    ),
                    konum=_ics_kacis_coz(kayit.get("LOCATION", "")),
                    tum_gun=kayit.get("_dtstart_param", {}).get("VALUE") == "DATE"
                    or (
                        len(kayit.get("DTSTART", "")) == 8
                        and kayit.get("DTSTART", "").isdigit()
                    ),
                    aciklama=aciklama,
                    organizator=_ics_kacis_coz(
                        kayit.get("ORGANIZER", "")
                    ).replace("mailto:", ""),
                    tur=kayit.get("RRULE", "") and "Recurring" or "Single",
                    ics=kayit.get("_ics", ""),
                    tamamlandi=(kayit.get(TAMAMLANDI_ALANI, "")
                                .strip().upper() == "TRUE"),
                    rrule=kayit.get("RRULE", ""),
                    exdate=_tarihler_birlestir(kayit.get("_EXDATE", [])),
                    rdate=_tarihler_birlestir(kayit.get("_RDATE", [])),
                )
            )
        kayit = {}
        aciklama_satirlari = []

    ic_derinlik = 0  # VEVENT içine gömülü alt bileşenler (VALARM vb.)
    for satir in _ics_satirlari_bol(ics):
        kelime = satir.strip()
        if kelime == "BEGIN:VEVENT":
            icinde = True
            kayit = {}
            aciklama_satirlari = []
            aciklama_modu = False
            ic_derinlik = 0
            continue
        if not icinde:
            continue
        if kelime == "END:VEVENT" and ic_derinlik == 0:
            kayit["_ics"] = ics  # tam metin; güncelleme için yeterli
            kapat()
            icinde = False
            continue
        if kelime.startswith("BEGIN:"):
            # Alt bileşen (VALARM vb.): içeriği olay verisi değildir —
            # Google hatırlatıcı DESCRIPTION'ını buraya koyar.
            ic_derinlik += 1
            aciklama_modu = False
            continue
        if kelime.startswith("END:"):
            if ic_derinlik:
                ic_derinlik -= 1
            aciklama_modu = False
            continue
        if ic_derinlik:
            continue
        anahtar, parametreler, deger = _ics_alan(satir)
        if anahtar == "DESCRIPTION":
            aciklama_modu = True
            aciklama_satirlari.append(deger)
        elif anahtar in ("EXDATE", "RDATE"):
            aciklama_modu = False
            kayit.setdefault("_" + anahtar, []).append((deger, parametreler))
        elif anahtar in (
            "UID", "SUMMARY", "DTSTART", "DTEND", "LOCATION",
            "ORGANIZER", "RRULE", "STATUS", "RECURRENCE-ID",
            TAMAMLANDI_ALANI,
        ):
            aciklama_modu = False
            kayit[anahtar] = deger
            if anahtar in ("DTSTART", "DTEND", "RECURRENCE-ID"):
                kayit["_" + anahtar.lower() + "_param"] = parametreler
        elif aciklama_modu and satir.startswith((" ", "\t")):
            aciklama_satirlari.append(satir)
    return sonuc


def randevu_ics(
    baslik: str,
    baslangic: datetime,
    bitis: datetime,
    konum: str = "",
    aciklama: str = "",
    tum_gun: bool = False,
    uid: str = "",
    rrule: str = "",
) -> str:
    """Basit bir VEVENT üretir."""
    uid = uid or f"{uuid.uuid4().hex}@postacim"
    now = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    def _dt(dt: datetime) -> str:
        if dt.tzinfo is None:
            dt = dt.astimezone()
        return dt.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    if tum_gun:
        ds = baslangic.strftime("%Y%m%d")
        de = (bitis - timedelta(days=1)).strftime("%Y%m%d") if bitis > baslangic else ds
        dtstart = f"DTSTART;VALUE=DATE:{ds}"
        dtend = f"DTEND;VALUE=DATE:{de}"
    else:
        dtstart = f"DTSTART:{_dt(baslangic)}"
        dtend = f"DTEND:{_dt(bitis)}"

    def _esc(s: str) -> str:
        return (
            s.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")
        )

    satirlar = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Postacim//TR",
        "CALSCALE:GREGORIAN",
        "BEGIN:VEVENT",
        f"UID:{uid}",
        f"DTSTAMP:{now}",
        dtstart,
        dtend,
        f"SUMMARY:{_esc(baslik or '(başlıksız)')}",
    ]
    if konum:
        satirlar.append(f"LOCATION:{_esc(konum)}")
    if aciklama:
        satirlar.append(f"DESCRIPTION:{_esc(aciklama)}")
    if rrule:
        satirlar.append(f"RRULE:{rrule}")
    satirlar += ["END:VEVENT", "END:VCALENDAR"]
    return "\r\n".join(satirlar) + "\r\n"


# ---------------------------------------------------------------- CalDAV

class CalDavIstemci:
    """Basic-auth CalDAV istemcisi."""

    def __init__(
        self,
        taban_url: str,
        kullanici: str,
        parola: str,
        zaman_asimi: int = 30,
        oauth: dict | None = None,
        token_sakla=None,
    ):
        """CalDAV istemcisi.

        `oauth` verilirse **Google OAuth2** ile bağlanılır (Bearer token;
        Basic auth yerine), 401'de token sessizce yenilenir. Verilmezse
        klasik kullanıcı-adı/parola (Basic) kimlik doğrulama çalışır.
        """
        self.taban_url = taban_url.rstrip("/") + "/"
        self.kullanici = kullanici
        self.parola = parola
        self.zaman_asimi = zaman_asimi
        self.oauth = dict(oauth) if oauth else None
        self.token_sakla = token_sakla
        self.oturum = requests.Session()
        self.oturum.auth = None if self.oauth else (kullanici, parola)
        self.oturum.headers.update(HEADERS_BASE)
        self._koleksiyonlar: list[CalDavTakvim] = []
        self._ana_koleksiyon: str = ""

    # ---- HTTP yardımcıları

    def _token(self) -> str:
        """Geçerli Google erişim token'ı (süresi geçtiyse yeniler)."""
        try:
            return google_oturum.token_al(
                self.oauth, tazele_islevi=self.token_sakla
            )
        except google_oturum.YetkiHatasi as exc:
            raise CalDavHata(
                f"Google yetkilendirmesi geçersiz: {exc} — takvim hesabını "
                "yeniden yetkilendirin."
            ) from exc
        except google_oturum.OturumHatasi as exc:
            raise CalDavHata(f"Google oturumu hatası: {exc}") from exc

    def _istek(
        self,
        method: str,
        url: str,
        veri: bytes | str | None = None,
        ek_basliklar: dict | None = None,
        kabul: str | None = None,
        _yenile_iddia: bool = True,
    ) -> requests.Response:
        basliklar = dict(ek_basliklar or {})
        if kabul:
            basliklar["Depth"] = kabul
        if self.oauth:
            basliklar["Authorization"] = "Bearer " + self._token()
        try:
            yanit = self.oturum.request(
                method,
                url,
                data=veri,
                headers=basliklar,
                timeout=self.zaman_asimi,
            )
        except requests.RequestException as exc:
            raise CalDavHata(f"Bağlantı hatası: {exc}") from exc
        if yanit.status_code in (401, 403):
            if self.oauth and _yenile_iddia:
                # Token bayat olabilir: zorla yenile, bir kez daha dene
                try:
                    self.oauth = google_oturum.tazele(self.oauth)
                except google_oturum.OturumHatasi as exc:
                    raise CalDavHata(
                        f"Google yetkilendirmesi geçersiz: {exc}"
                    ) from exc
                if self.token_sakla is not None:
                    try:
                        self.token_sakla(self.oauth)
                    except Exception:
                        pass
                return self._istek(
                    method, url, veri, ek_basliklar, kabul,
                    _yenile_iddia=False,
                )
            raise CalDavHata("Kimlik doğrulama başarısız (401/403).")
        if yanit.status_code >= 400 and yanit.status_code not in (404, 409, 410, 412):
            raise CalDavHata(
                f"CalDAV {yanit.status_code}: {yanit.text[:200]}"
            )
        return yanit

    def _propfind(self, url: str, govde: str, derinlik: str = "0") -> requests.Response:
        return self._istek(
            "PROPFIND",
            url,
            veri=govde,
            ek_basliklar={"Depth": derinlik},
        )

    def _etag_al(self, url: str) -> str:
        """Kaydın ETag'ini PROPFIND ile sorar.

        Bazı sunucular (Google) PUT cevabında ETag başlığı göndermez;
        sonraki güncellemede `If-Match` için ETag gerekir.
        """
        govde = (
            f'<?xml version="1.0" encoding="utf-8"?>'
            f'<D:propfind xmlns:D="{NS_DAV}"><D:prop>'
            f"<D:getetag/></D:prop></D:propfind>"
        )
        try:
            yanit = self._propfind(url, govde, "0")
        except CalDavHata:
            return ""
        m = re.search(r"<[^>]*:?getetag[^>]*>([^<]+)</", yanit.text, re.I)
        return m.group(1).strip().strip('"') if m else ""

    # ---- Keşif

    def kesfet(self) -> list[CalDavTakvim]:
        """Sunucuda takvim koleksiyonlarını keşfeder."""
        # 1) current-user-principal
        govde = (
            f'<?xml version="1.0" encoding="utf-8"?>'
            f'<D:propfind xmlns:D="{NS_DAV}"><D:prop>'
            f"<D:current-user-principal/>"
            f"</D:prop></D:propfind>"
        )
        yanit = self._propfind(self.taban_url, govde, "0")
        principal = self._ilk_metin(yanit.text, "current-user-principal")
        if not principal:
            # Bazı sunucular (Google eski uç) current-user-principal vermez:
            # doğrudan başlangıç adresini koleksiyon olarak dene.
            home = self.taban_url
        else:
            # 2) calendar-home-set
            govde2 = (
                f'<?xml version="1.0" encoding="utf-8"?>'
                f'<D:propfind xmlns:D="{NS_DAV}" xmlns:C="{NS_CALENDAR}"><D:prop>'
                f"<C:calendar-home-set/>"
                f"</D:prop></D:propfind>"
            )
            yanit2 = self._propfind(principal, govde2, "0")
            home = self._ilk_metin(yanit2.text, "calendar-home-set") or principal

        # 3) koleksiyonlar
        koleksiyonlar = self._koleksiyonlari_listele(home)
        if not koleksiyonlar:
            # Google: /user başlangıcında alt koleksiyonlar dönmez;
            # olaylar /events koleksiyonundadır.
            adaylar: list[str] = []
            for kaynak in (home, self.taban_url):
                if kaynak.rstrip("/").endswith("/user"):
                    adaylar.append(
                        kaynak.rstrip("/")[: -len("/user")] + "/events/"
                    )
            for aday in adaylar:
                koleksiyonlar = self._koleksiyonlari_listele(aday)
                if koleksiyonlar:
                    break
        return koleksiyonlar

    @staticmethod
    def _ilk_metin(xml: str, etiket: str) -> str:
        """XML içinde etiketin href/metin değerini bulur."""
        m = re.search(
            rf"<(?:[A-Za-z0-9]+:)?{re.escape(etiket)}[^>]*>\s*"
            rf"(?:<(?:[A-Za-z0-9]+:)?href[^>]*>)?([^<]+)",
            xml,
            re.I,
        )
        if m:
            deger = m.group(1).strip()
            if deger.startswith("/"):
                return deger  # göreli; çağıran birleştirir
            return deger
        return ""

    def _koleksiyonlari_listele(self, home: str) -> list[CalDavTakvim]:
        if home.startswith("/"):
            p = urlparse(self.taban_url)
            home = f"{p.scheme}://{p.netloc}{home}"
        govde = (
            f'<?xml version="1.0" encoding="utf-8"?>'
            f'<D:propfind xmlns:D="{NS_DAV}" xmlns:C="{NS_CALENDAR}"><D:prop>'
            f"<D:resourcetype/><D:displayname/>"
            f"<C:supported-calendar-component-set/>"
            f"</D:prop></D:propfind>"
        )
        yanit = self._propfind(home, govde, "1")
        koleksiyonlar: list[CalDavTakvim] = []
        # Her <D:response> bloğu
        for blok in re.split(r"(?=<[^>]*:?response[ >])", yanit.text, flags=re.I):
            if "calendar" not in blok.lower() or "resourcetype" not in blok.lower():
                continue
            if not re.search(r"<[^>]*:?calendar\s*/?>", blok, re.I):
                # <D:calendar/> içermiyor
                if "<calendar" not in blok.lower():
                    continue
            href = self._ilk_metin(blok, "href")
            ad = self._ilk_metin(blok, "displayname")
            if not href:
                continue
            if href.startswith("/"):
                p = urlparse(self.taban_url)
                href = f"{p.scheme}://{p.netloc}{href}"
            elif not href.startswith("http"):
                href = urljoin(home, href)
            if not href.rstrip("/").endswith(home.rstrip("/").split("/")[-1]) and home.rstrip("/") not in href:
                pass  # yine de ekle; bazı sunucular farklı yollar verir
            koleksiyonlar.append(
                CalDavTakvim(url=href.rstrip("/") + "/", ad=ad or href.rstrip("/").split("/")[-1])
            )
        # Tek koleksiyon varsa onu ana koleksiyon yap
        if koleksiyonlar:
            self._ana_koleksiyon = koleksiyonlar[0].url
        self._koleksiyonlar = koleksiyonlar
        return koleksiyonlar

    def takvimler(self) -> list[CalDavTakvim]:
        if not self._koleksiyonlar:
            return self.kesfet()
        return self._koleksiyonlar

    # ---- Randevular

    def randevular(
        self,
        baslangic: date | None = None,
        bitis: date | None = None,
        koleksiyon: str = "",
    ) -> list[RandevuKaydi]:
        """Takvimden randevuları çeker (tümü ya da tarih aralığı)."""
        hedef = koleksiyon or self._ana_koleksiyon
        if not hedef:
            self.kesfet()
            hedef = self._ana_koleksiyon
        if not hedef:
            raise CalDavHata("Takvim koleksiyonu bulunamadı.")

        if baslangic is None:
            bas = "00010101T000000Z"
        else:
            bas = baslangic.strftime("%Y%m%dT000000Z")
        if bitis is None:
            bit = "99991231T235959Z"
        else:
            bit = (bitis + timedelta(days=1)).strftime("%Y%m%dT000000Z")

        govde = (
            f'<?xml version="1.0" encoding="utf-8"?>'
            f'<C:calendar-query xmlns:D="{NS_DAV}" xmlns:C="{NS_CALENDAR}">'
            f"<D:prop><D:getetag/><C:calendar-data/></D:prop>"
            f"<C:filter>"
            f'<C:comp-filter name="VCALENDAR">'
            f'<C:comp-filter name="VEVENT">'
            f'<C:time-range start="{bas}" end="{bit}"/>'
            f"</C:comp-filter></C:comp-filter>"
            f"</C:filter></C:calendar-query>"
        )
        yanit = self._istek(
            "REPORT",
            hedef,
            veri=govde,
            ek_basliklar={"Depth": "1"},
        )
        return self._yanittan_randevular(yanit.text)

    def _yanittan_randevular(self, xml: str) -> list[RandevuKaydi]:
        sonuc: list[RandevuKaydi] = []
        # Her response bloğu: href + etag + calendar-data
        for blok in re.split(r"(?=<[^>]*:?response[ >])", xml, flags=re.I)[1:]:
            href = self._ilk_metin(blok, "href")
            etag = ""
            m_et = re.search(r"<[^>]*:?getetag[^>]*>([^<]+)</", blok, re.I)
            if m_et:
                etag = m_et.group(1).strip().strip('"')
            # calendar-data içeriği (CDATA ya da düz metin)
            m_data = re.search(
                r"<[^>]*:?calendar-data[^>]*>(.*?)</[^>]*:?calendar-data>",
                blok,
                re.I | re.S,
            )
            if not m_data:
                continue
            ics = m_data.group(1)
            if ics.startswith("<![CDATA["):
                ics = ics[9:]
                if ics.endswith("]]>"):
                    ics = ics[:-3]
            ics = (
                ics.replace("&lt;", "<")
                .replace("&gt;", ">")
                .replace("&quot;", '"')
                .replace("&amp;", "&")
            )
            if href.startswith("/"):
                p = urlparse(self.taban_url)
                href = f"{p.scheme}://{p.netloc}{href}"
            for r in ics_randevulari(ics, kaynak_url=href, etag=etag):
                sonuc.append(r)
        return sonuc

    # ---- Yazma

    def randevu_ekle(
        self,
        baslik: str,
        baslangic: datetime,
        bitis: datetime,
        konum: str = "",
        aciklama: str = "",
        tum_gun: bool = False,
        koleksiyon: str = "",
        rrule: str = "",
    ) -> RandevuKaydi:
        hedef = koleksiyon or self._ana_koleksiyon
        if not hedef:
            self.kesfet()
            hedef = self._ana_koleksiyon
        if not hedef:
            raise CalDavHata("Takvim koleksiyonu bulunamadı.")
        ics = randevu_ics(
            baslik, baslangic, bitis, konum, aciklama, tum_gun, rrule=rrule
        )
        uid = re.search(r"UID:([^\r\n]+)", ics).group(1)
        url = hedef.rstrip("/") + f"/{uid}.ics"
        yanit = self._istek(
            "PUT",
            url,
            veri=ics.encode("utf-8"),
            ek_basliklar={"Content-Type": "text/calendar; charset=utf-8"},
        )
        if yanit.status_code not in (200, 201, 204):
            raise CalDavHata(f"Randevu kaydedilemedi ({yanit.status_code}).")
        etag = (yanit.headers.get("ETag") or "").strip('"')
        if not etag:
            etag = self._etag_al(url)
        return RandevuKaydi(
            uid=uid, url=url, etag=etag, baslik=baslik,
            baslangic=baslangic.strftime("%Y-%m-%dT%H:%M:%S"),
            bitis=bitis.strftime("%Y-%m-%dT%H:%M:%S"),
            konum=konum, tum_gun=tum_gun, aciklama=aciklama, ics=ics,
        )

    def randevu_guncelle(self, r: RandevuKaydi) -> None:
        if not r.url:
            raise CalDavHata("Güncelleme için kayıt URL'i yok.")
        ics = r.ics or randevu_ics(
            r.baslik,
            _iso_yerel_dt(r.baslangic),
            _iso_yerel_dt(r.bitis) or _iso_yerel_dt(r.baslangic) + timedelta(hours=1),
            r.konum, r.aciklama, r.tum_gun, uid=r.uid,
        )
        # Eski alanları tazele
        ics = _ics_alan_degistir(ics, "SUMMARY", r.baslik)
        if r.konum:
            ics = _ics_alan_degistir(ics, "LOCATION", r.konum)
        else:
            ics = re.sub(r"(?m)^LOCATION:.*\r?\n", "", ics)
        if r.aciklama:
            ics = _ics_alan_degistir(ics, "DESCRIPTION", r.aciklama)
        else:
            ics = re.sub(r"(?m)^DESCRIPTION:.*\r?\n", "", ics)
        # Başlangıç/bitiş (VALUE=DATE korunur)
        ics = _ics_zaman_degistir(ics, "DTSTART", r.baslangic)
        ics = _ics_zaman_degistir(ics, "DTEND", r.bitis)
        # Tekrarlama kuralı
        if r.rrule:
            ics = _ics_alan_degistir(ics, "RRULE", r.rrule, kacis=False)
        else:
            ics = re.sub(r"(?m)^RRULE:.*\r?\n", "", ics)
        # Tamamlandı işareti (düzenlemede korunur/yazılır)
        ics = tamamlandi_ics(ics, r.tamamlandi)
        ek_basliklar = {"Content-Type": "text/calendar; charset=utf-8"}
        if r.etag:
            ek_basliklar["If-Match"] = f'"{r.etag}"'
        yanit = self._istek(
            "PUT", r.url, veri=ics.encode("utf-8"), ek_basliklar=ek_basliklar
        )
        if yanit.status_code not in (200, 201, 204):
            raise CalDavHata(f"Randevu güncellenemedi ({yanit.status_code}).")
        r.ics = ics
        yeni_etag = (yanit.headers.get("ETag") or "").strip('"')
        if not yeni_etag:
            yeni_etag = self._etag_al(r.url)
        r.etag = yeni_etag or r.etag

    def tamamlandi_yaz(self, r: RandevuKaydi, tamamlandi: bool) -> None:
        """Tamamlandı işaretini olayın kendisine yazar (X- alanı + PUT).

        İşaret sunucuda saklandığı için tüm makinelarda aynı görünür;
        tekrar kopyası başına yazılamaz (Google, override PUT'unu atıyor).
        """
        if not r.url:
            raise CalDavHata("Güncelleme için kayıt URL'i yok.")
        ics = r.ics or randevu_ics(
            r.baslik,
            _iso_yerel_dt(r.baslangic),
            _iso_yerel_dt(r.bitis) or _iso_yerel_dt(r.baslangic) + timedelta(hours=1),
            r.konum, r.aciklama, r.tum_gun, uid=r.uid,
        )
        ics = tamamlandi_ics(ics, tamamlandi)
        ek_basliklar = {"Content-Type": "text/calendar; charset=utf-8"}
        if r.etag:
            ek_basliklar["If-Match"] = f'"{r.etag}"'
        yanit = self._istek(
            "PUT", r.url, veri=ics.encode("utf-8"), ek_basliklar=ek_basliklar
        )
        if yanit.status_code not in (200, 201, 204):
            raise CalDavHata(
                f"Tamamlandı işareti yazılamadı ({yanit.status_code})."
            )
        r.ics = ics
        r.tamamlandi = tamamlandi
        yeni_etag = (yanit.headers.get("ETag") or "").strip('"')
        if not yeni_etag:
            yeni_etag = self._etag_al(r.url)
        r.etag = yeni_etag or r.etag

    def randevu_sil(self, r: RandevuKaydi) -> None:
        if not r.url:
            raise CalDavHata("Silme için kayıt URL'i yok.")
        ek = {}
        if r.etag:
            ek["If-Match"] = f'"{r.etag}"'
        yanit = self._istek("DELETE", r.url, ek_basliklar=ek)
        if yanit.status_code not in (200, 202, 204, 404):
            raise CalDavHata(f"Randevu silinemedi ({yanit.status_code}).")


def tamamlandi_ics(ics: str, tamamlandi: bool) -> str:
    """iCalendar metninde X-POSTACIM-TAMAMLANDI alanını yazar/kaldırır."""
    if tamamlandi:
        return _ics_alan_degistir(
            ics, TAMAMLANDI_ALANI, "TRUE", kacis=False
        )
    return re.sub(
        rf"(?m)^{TAMAMLANDI_ALANI}(?:;[^:]*)?:.*(?:\r?\n|$)", "", ics
    )


def _iso_yerel_dt(ts: str) -> datetime:
    from .ews import iso_yerel

    dt = iso_yerel(ts)
    if dt is None:
        return datetime.now()
    return dt.replace(tzinfo=None)


def _ics_alan_degistir(ics: str, anahtar: str, deger: str, kacis: bool = True) -> str:
    """VEVENT içindeki bir alanı değiştirir (varsa).

    `kacis` False ise değer olduğu gibi yazılır (RRULE gibi ";" ayraçlı
    alanlarda kaçış bozulur).
    """
    def _esc(s: str) -> str:
        return s.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")

    deger = _esc(deger) if kacis else deger
    deseni = re.compile(rf"(?m)^{anahtar}(?:;[^:]*)?:.*$")
    if deseni.search(ics):
        return deseni.sub(f"{anahtar}:{deger}", ics, count=1)
    # VEVENT sonuna ekle
    return ics.replace(
        "END:VEVENT", f"{anahtar}:{deger}\r\nEND:VEVENT", 1
    )


def _ics_zaman_degistir(ics: str, anahtar: str, iso: str) -> str:
    """DTSTART/DTEND alanını ISO değerle değiştirir.

    `VALUE=DATE` (tüm gün) parametresi korunur; parametreli alanlarda
    yalnız değer değişir.
    """
    dt = _iso_yerel_dt(iso)
    if dt is None:
        return ics
    yeni = dt.strftime("%Y%m%dT%H%M%S")
    deseni = re.compile(rf"(?m)^{anahtar}(;[^:\r\n]*)?:.*$")
    eslesme = deseni.search(ics)
    if not eslesme:
        return ics.replace(
            "END:VEVENT", f"{anahtar}:{yeni}\r\nEND:VEVENT", 1
        )
    parametre = eslesme.group(1) or ""
    if "VALUE=DATE" in parametre.upper():
        yeni = yeni[:8]
    return deseni.sub(f"{anahtar}{parametre}:{yeni}", ics, count=1)
