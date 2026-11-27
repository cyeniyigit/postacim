"""Gazete haberleri (RSS/Atom beslemeleri) istemcisi.

Kullanıcı bir site adresi girer; besleme şu sırayla bulunur:
1. Adresin kendisi beslemeyse doğrudan kullanılır (root: rss/atom/feed).
2. Sayfadaki `<link rel="alternate" type="application/rss+xml|atom+xml">`
   keşif bağlantısı okunur (sabah.com.tr böyle veriyor).
3. Yaygın besleme yolları tek tek denenir (hurriyet.com.tr için
   /rss/anasayfa/ gibi — ana sayfada keşif bağlantısı yok, canlı
   doğrulandı).

Haber başlıkları RSS 2.0 + Atom'dan ayrıştırılır; resim/video bağlantıları
yalnız ADRES olarak toplanır — indirme kullanıcı sorduktan sonra yapılır.
"""

from __future__ import annotations

import email.utils
import html as html_mod
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

import requests

KULLANICI_AGENTI = "Mozilla/5.0 (X11; Linux x86_64) Postacim/0.1"

# Site adresinden besleme bulunamadığında denenen yaygın yollar
YAYGIN_YOLLAR = (
    "/rss", "/rss/", "/rss.xml", "/feed", "/feed/", "/feed.xml",
    "/atom.xml", "/rss/anasayfa/", "/rss/anasayfa.xml",
)

# Medya indirme üst sınırı (bayt) — kaza sonucu dev dosya indirmeyi önler
MEDYA_EN_FAZLA = 25 * 1024 * 1024


@dataclass
class Haber:
    kaynak: str
    baslik: str
    baglanti: str = ""
    ozet: str = ""
    tarih: datetime | None = None
    resim: str | None = None
    video: str | None = None
    ek_resimler: list[str] = field(default_factory=list)


def _get(url: str, zaman_asimi: int = 20) -> requests.Response:
    yanit = requests.get(
        url, timeout=zaman_asimi, headers={"User-Agent": KULLANICI_AGENTI}
    )
    yanit.raise_for_status()
    return yanit


def _url_duzelt(adres: str) -> str:
    adres = (adres or "").strip()
    if adres and "://" not in adres:
        adres = "https://" + adres
    return adres


def _besleme_mi(yanit: requests.Response) -> bool:
    """Yanıt bir RSS/Atom belgesi mi (root öğesine bakar)?"""
    tur = (yanit.headers.get("Content-Type") or "").lower()
    if "html" in tur:
        return False
    try:
        kok = ET.fromstring(yanit.content)
    except ET.ParseError:
        return False
    etiket = kok.tag.rsplit("}", 1)[-1].lower()
    return etiket in ("rss", "rdf", "feed")


def _html_besleme_baglantisi(html: str, temel: str) -> str | None:
    """HTML içindeki <link rel="alternate" ... rss/atom+xml> adresi."""
    for m in re.finditer(r"<link\b[^>]*>", html, re.IGNORECASE):
        etiket = m.group(0)
        if not re.search(r'rel=["\']alternate["\']', etiket, re.IGNORECASE):
            continue
        tur = re.search(r'type=["\']([^"\']+)["\']', etiket, re.IGNORECASE)
        adres = re.search(r'href=["\']([^"\']+)["\']', etiket, re.IGNORECASE)
        if not tur or not adres:
            continue
        if re.search(r"(rss|atom)\+xml", tur.group(1), re.IGNORECASE):
            return urljoin(temel, adres.group(1).strip())
    return None


def besleme_bul(adres: str) -> tuple[str, str]:
    """Site adresinden besleme adresi + besleme başlığını bulur.

    Döndürür: (besleme_url, baslik). Bulamazsa ValueError verir.
    """
    adres = _url_duzelt(adres)
    if not adres:
        raise ValueError("Site adresi boş")
    yanit = _get(adres)
    if _besleme_mi(yanit):
        return str(yanit.url), besleme_basligi(yanit.content) or _alan_adi(adres)
    html = yanit.text
    baglanti = _html_besleme_baglantisi(html, str(yanit.url))
    if baglanti:
        besleme = _get(baglanti)
        if _besleme_mi(besleme):
            return str(besleme.url), besleme_basligi(besleme.content) or _alan_adi(adres)
    temel = f"{urlparse(str(yanit.url)).scheme}://{urlparse(str(yanit.url)).netloc}"
    for yol in YAYGIN_YOLLAR:
        aday = temel + yol
        try:
            besleme = _get(aday)
        except requests.RequestException:
            continue
        if _besleme_mi(besleme):
            return str(besleme.url), besleme_basligi(besleme.content) or _alan_adi(adres)
    raise ValueError(f"Site adresinde besleme bulunamadı: {adres}")


def medya_indir(url: str, en_fazla: int = MEDYA_EN_FAZLA) -> bytes:
    """Resim/video baytlarını indirir; en_fazla aşılırsa hata verir."""
    yanit = requests.get(
        url, timeout=(10, 60), stream=True,
        headers={"User-Agent": KULLANICI_AGENTI},
    )
    yanit.raise_for_status()
    parcalar, toplam = [], 0
    for parca in yanit.iter_content(chunk_size=65536):
        toplam += len(parca)
        if toplam > en_fazla:
            raise ValueError(f"Dosya çok büyük ({en_fazla // (1024 * 1024)} MB sınırı)")
        parcalar.append(parca)
    return b"".join(parcalar)


def besleme_basligi(bayt: bytes) -> str:
    """Besleme XML'indeki kanal/besleme başlığı (kaynak adı olarak)."""
    try:
        kok = ET.fromstring(bayt)
    except ET.ParseError:
        return ""
    for kok_cocugu in kok.iter():
        etiket = kok_cocugu.tag.rsplit("}", 1)[-1].lower()
        if etiket == "title" and kok_cocugu.text and kok_cocugu.text.strip():
            return kok_cocugu.text.strip()
    return ""


def _alan_adi(adres: str) -> str:
    return urlparse(adres).netloc.removeprefix("www.")


def tarih_coz(metin: str) -> datetime | None:
    """RSS (RFC 822) ya da Atom (ISO 8601) tarihi → yerel saat, naive."""
    metin = (metin or "").strip()
    if not metin:
        return None
    deger = None
    try:
        deger = email.utils.parsedate_to_datetime(metin)
    except (TypeError, ValueError):
        try:
            deger = datetime.fromisoformat(metin.replace("Z", "+00:00"))
        except ValueError:
            return None
    if deger is None:
        return None
    if deger.tzinfo is not None:
        deger = deger.astimezone().replace(tzinfo=None)
    return deger


def metin_temizle(html_metni: str) -> str:
    """HTML özetini düz metne çevirir (etiketler atılır, varlıklar çözülür)."""
    metin = re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", html_metni or "")
    metin = re.sub(r"(?s)<[^>]+>", " ", metin)
    metin = html_mod.unescape(metin)
    return re.sub(r"\s+", " ", metin).strip()


def _ilki(oge: ET.Element, *adlar: str) -> str:
    """Öğenin çocuğu olan ilk eşleşen etiketin metni (ad alanı fark etmez)."""
    for cocuk in oge:
        yerel = cocuk.tag.rsplit("}", 1)[-1].lower()
        if yerel in adlar and (cocuk.text or "").strip():
            return cocuk.text.strip()
    return ""


def _medya(oge: ET.Element) -> tuple[str | None, str | None, list[str]]:
    """Öğedeki resim/video bağlantıları: (resim, video, ek_resimler).

    Sıra: media:content → media:thumbnail → enclosure; açıklamadaki ilk
    <img> yedeğe yazılır.
    """
    resim = video = None
    ekler: list[str] = []
    for cocuk in oge.iter():
        yerel = cocuk.tag.rsplit("}", 1)[-1].lower()
        if yerel not in ("content", "thumbnail", "enclosure"):
            continue
        adres = cocuk.get("url") or cocuk.get("href") or ""
        tur = (cocuk.get("type") or cocuk.get("medium") or "").lower()
        if not adres or "://" not in adres:
            continue
        resim_mi = tur.startswith("image") or tur == "image"
        video_mu = tur.startswith("video") or tur == "video"
        if not resim_mi and not video_mu and yerel == "content":
            # media:content'te tür yoksa uzantıya bak (tahmin yok; yalnız netse)
            yol = urlparse(adres).path.lower()
            if yol.endswith((".jpg", ".jpeg", ".png", ".gif", ".webp")):
                resim_mi = True
            elif yol.endswith((".mp4", ".webm", ".mov", ".m4v")):
                video_mu = True
        if resim_mi:
            ekler.append(adres)
        elif video_mu:
            video = video or adres
    resim = ekler[0] if ekler else None
    if not resim:
        # açıklamadaki ilk <img src>
        aciklama = _ilki(oge, "description", "summary", "content")
        m = re.search(r'<img\b[^>]*\bsrc=["\']([^"\']+)["\']', aciklama or "",
                      re.IGNORECASE)
        if m and "://" in m.group(1):
            resim = m.group(1)
            ekler.append(resim)
    return resim, video, ekler


def _rss_ayristir(bayt: bytes, kaynak: str, en_fazla: int) -> list[Haber]:
    kok = ET.fromstring(bayt)
    liste: list[Haber] = []
    for oge in kok.iter():
        etiket = oge.tag.rsplit("}", 1)[-1].lower()
        if etiket != "item":
            continue
        baslik = html_mod.unescape(_ilki(oge, "title"))
        if not baslik:
            continue
        baglanti = _ilki(oge, "link")
        ozet = metin_temizle(
            _ilki(oge, "description") or _ilki(oge, "encoded"))
        resim, video, ekler = _medya(oge)
        liste.append(Haber(
            kaynak=kaynak, baslik=baslik, baglanti=baglanti, ozet=ozet,
            tarih=tarih_coz(_ilki(oge, "pubdate", "date")),
            resim=resim, video=video, ek_resimler=ekler,
        ))
        if len(liste) >= en_fazla:
            break
    return liste


def _atom_ayristir(bayt: bytes, kaynak: str, en_fazla: int) -> list[Haber]:
    kok = ET.fromstring(bayt)
    liste: list[Haber] = []
    for oge in kok.iter():
        etiket = oge.tag.rsplit("}", 1)[-1].lower()
        if etiket != "entry":
            continue
        baslik = html_mod.unescape(_ilki(oge, "title"))
        if not baslik:
            continue
        baglanti = ""
        for cocuk in oge:
            if cocuk.tag.rsplit("}", 1)[-1].lower() != "link":
                continue
            iliski = (cocuk.get("rel") or "alternate").lower()
            adres = (cocuk.get("href") or "").strip()
            if adres and (iliski == "alternate" or not baglanti):
                baglanti = adres
        ozet = metin_temizle(_ilki(oge, "summary") or _ilki(oge, "content"))
        resim, video, ekler = _medya(oge)
        liste.append(Haber(
            kaynak=kaynak, baslik=baslik, baglanti=baglanti, ozet=ozet,
            tarih=tarih_coz(_ilki(oge, "published", "updated")),
            resim=resim, video=video, ek_resimler=ekler,
        ))
        if len(liste) >= en_fazla:
            break
    return liste


def haber_cek(besleme: str, kaynak_ad: str = "", en_fazla: int = 80) -> list[Haber]:
    """Beslemedeki haberleri en yeniden eskiye döndürür.

    Kaynak adı verilmediyse beslemenin kendi başlığı kullanılır.
    Ağ/çözümleme hatasında istisna verir.
    """
    yanit = _get(_url_duzelt(besleme))
    yanit.raise_for_status()
    bayt = yanit.content
    if kaynak_ad == "":
        kaynak_ad = besleme_basligi(bayt) or _alan_adi(str(yanit.url))
    kok = ET.fromstring(bayt)
    kok_etiket = kok.tag.rsplit("}", 1)[-1].lower()
    if kok_etiket == "feed":
        liste = _atom_ayristir(bayt, kaynak_ad, en_fazla)
    else:
        liste = _rss_ayristir(bayt, kaynak_ad, en_fazla)
    return sirala(liste)


def sirala(haberler: list[Haber]) -> list[Haber]:
    """Tarihe göre en yeniden eskiye; tarihsizler sona (kararsızlık korunsun)."""
    sirali = sorted(
        enumerate(haberler),
        key=lambda cift: (
            -(cift[1].tarih.timestamp()) if cift[1].tarih else float("inf"),
            cift[0],
        ),
    )
    return [cift[1] for cift in sirali]


# ---------------------------------------------------------------- makale metni

# Makale gövdesi taşıyabilecek kapların ad/class kalıbı (canlı doğrulandı:
# Hürriyet "news-content", Sabah "newsDetailText")
_MAKALE_KABI = re.compile(
    r"detail|news[-_]?(content|text|body)|haber[-_]?(metin|detay|icerik)|"
    r"article[-_]?(body|content|text)|icerik|entry[-_]?content",
    re.IGNORECASE,
)
# Makale gövdeleri İÇİNDE OLMAYACAK kaplar (menü/yorum/yan sütun)
_ATILAN_KAP = re.compile(
    r"menu|footer|header|sidebar|side[-_]?bar|yorum|comment|paylas|share|"
    r"related|reklam|advert|slider|bulten|newsletter|form|tag|kategor|"
    r"arac|toolbar|social|breadcrumb|sondakika[-_]?bar|nav\b",
    re.IGNORECASE,
)
_ATILAN_PARAGRAF = re.compile(
    r"devamı için|devami icin|okumak için|okumak icin|tıklayınız|"
    r"tiklayiniz|abone ol|uygulamamızı|uygulamamizi|kye? (gönder|gonder)|"
    r"reklam| editör: |kaynak: ",
    re.IGNORECASE,
)
_EN_AZ_PARAGRAF = 30   # karakter; menü/künye kırpıntıları düşer


class _MakaleAyristirici(HTMLParser):
    """Haber sayfasındaki paragrafları, ait oldukları kaba göre toplar.

    Her <p>, içindeki EN İÇTEKİ eşleşen kabın imzasıyla kaydedilir; makale
    metni en uzun toplam metinli grubu verir (yan sütun/menü paragrafları
    düşer). Resimler de grup başına toplanır.
    """

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.gruplar: dict[str, dict] = {}   # anahtar → {"metin","p","resimler"}
        self.yigin: list[tuple[str, str | None]] = []
        self._p_anahtar = None
        self._p_parcalar: list[str] = []
        self._atla = 0                       # script/style derinliği

    def _grup(self, anahtar):
        kayit = self.gruplar.get(anahtar)
        if kayit is None:
            kayit = self.gruplar[anahtar] = {"metin": 0, "p": [], "resimler": []}
        return kayit

    def handle_starttag(self, etiket, nitelikler):
        etiket = etiket.lower()
        if etiket in ("script", "style"):
            self._atla += 1
            return
        if self._atla:
            return
        nit = {}
        for ad, deger in nitelikler:
            nit[ad.lower()] = deger or ""
        if etiket in ("div", "article", "main", "section"):
            kimlik = f"{nit.get('class', '')} {nit.get('id', '')}".strip()
            anahtar = None
            if kimlik and _MAKALE_KABI.search(kimlik) and \
                    not _ATILAN_KAP.search(kimlik):
                anahtar = f"{etiket}:{kimlik[:100]}"
            self.yigin.append((etiket, anahtar))
        elif etiket == "p":
            anahtar = next((k for _t, k in reversed(self.yigin) if k), "")
            self._p_anahtar = anahtar
            self._p_parcalar = []
        elif etiket == "img":
            adres = nit.get("src") or nit.get("data-src") or ""
            if adres and "://" in adres:
                anahtar = next((k for _t, k in reversed(self.yigin) if k), "")
                kayit = self._grup(anahtar)
                if adres not in kayit["resimler"]:
                    kayit["resimler"].append(adres)
        elif etiket == "br" and self._p_anahtar is not None:
            self._p_parcalar.append("\n")

    def handle_startendtag(self, etiket, nitelikler):
        if etiket.lower() == "img":
            self.handle_starttag(etiket, nitelikler)
            self.handle_endtag(etiket)
        elif etiket.lower() == "br":
            self.handle_starttag(etiket, nitelikler)
            self.handle_endtag(etiket)

    def handle_data(self, veri):
        if self._atla:
            return
        if self._p_anahtar is not None:
            self._p_parcalar.append(veri)

    def handle_endtag(self, etiket):
        etiket = etiket.lower()
        if etiket in ("script", "style"):
            if self._atla:
                self._atla -= 1
            return
        if self._atla:
            return
        if etiket == "p" and self._p_anahtar is not None:
            metin = re.sub(r"\s+", " ", " ".join(self._p_parcalar)).strip()
            if len(metin) >= _EN_AZ_PARAGRAF and \
                    not _ATILAN_PARAGRAF.search(metin):
                kayit = self._grup(self._p_anahtar)
                kayit["p"].append(metin)
                kayit["metin"] += len(metin)
            self._p_anahtar = None
            self._p_parcalar = []
            return
        # kapanan etiketi yığından düş (bozuk HTML'de en yakını bul)
        for i in range(len(self.yigin) - 1, -1, -1):
            if self.yigin[i][0] == etiket:
                del self.yigin[i:]
                break


def makale_ayristir(html_metni: str) -> tuple[list[str], list[str]]:
    """Haber sayfası HTML'inden (paragraflar, resimler) çıkarır.

    Paragraflar en uzun toplam metinli kabın grubundan gelir; en içteki
    eşleşen kap grubu yoksa uzun paragraflar birleşir. Bulunamazsa
    ([], []).
    """
    ayristirici = _MakaleAyristirici()
    try:
        ayristirici.feed(html_metni)
        ayristirici.close()
    except Exception:
        return [], []
    if not ayristirici.gruplar:
        return [], []
    anahtar, kayit = max(
        ayristirici.gruplar.items(), key=lambda cift: cift[1]["metin"])
    if len(kayit["p"]) < 2 or kayit["metin"] < 200:
        # kap grubu yetersiz: sayfadaki uzun paragraflar birleşir
        tumu = []
        for kayit2 in ayristirici.gruplar.values():
            for p in kayit2["p"]:
                if p not in tumu:
                    tumu.append(p)
        kayit["p"] = tumu
        resimler = []
        for kayit2 in ayristirici.gruplar.values():
            for r in kayit2["resimler"]:
                if r not in resimler:
                    resimler.append(r)
        kayit["resimler"] = resimler
    # ardışık yinelenen paragrafları at
    paragraflar = [p for i, p in enumerate(kayit["p"])
                   if i == 0 or p != kayit["p"][i - 1]]
    return paragraflar, kayit["resimler"][:6]


def makale_cek(baglanti: str) -> tuple[list[str], list[str]]:
    """Haber sayfasını indirip (paragraflar, resimler) döndürür."""
    yanit = _get(_url_duzelt(baglanti))
    yanit.raise_for_status()
    return makale_ayristir(yanit.text)
