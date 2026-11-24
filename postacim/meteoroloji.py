"""Meteoroloji Genel Müdürlüğü hava durumu servisi (servis.mgm.gov.tr/web).

mgm.gov.tr'nin "il-ve-ilceler" sayfasının kullandığı resmî servis uç
noktaları:
    /web/merkezler/iller                      → iller + plaka
    /web/merkezler/ililcesi?il=…              → il/ilçe istasyon listesi
    /web/merkezler?il=…&ilce=…                → merkez seçimi (ilce boşsa
                                                öncelikli merkez döner)
    /web/sondurumlar?merkezid=…               → anlık ölçüm
    /web/tahminler/gunluk?istno=…             → 5 günlük tahmin

Tüm işlevler hata durumunda `MeteorolojiHatasi` fırlatır; ağ yoksa
çağıran sessizce atlayabilir (hava durumu açılışı engellememeli).
"""
from __future__ import annotations

import requests

TABAN = "https://servis.mgm.gov.tr/web"
# CDN'ler ve MGM servisleri UA'sız istekleri reddedebilir.
BASLIK = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Origin": "https://mgm.gov.tr",
    "Referer": "https://mgm.gov.tr/",
}

# MGM fenomen kodları → (gösterim simgesi, Türkçe ad)
# Kaynak: mgm.gov.tr/Images_Sys/hadiseler/<kod>.svg
HADISELER = {
    "A": ("☀️", "Açık"),
    "AB": ("🌤️", "Az bulutlu"),
    "PB": ("⛅", "Parçalı bulutlu"),
    "CB": ("☁️", "Çok bulutlu"),
    "CB-A": ("🌦️", "Çok bulutlu, aralıklı açık"),
    "Y": ("🌧️", "Yağmurlu"),
    "YY": ("🌦️", "Hafif yağmurlu"),
    "YB": ("🌧️", "Yağışlı"),
    "K": ("🌨️", "Karlı"),
    "HK": ("❄️", "Hafif karlı"),
    "KY": ("🌨️", "Karla karışık yağmurlu"),
    "HS": ("🌨️", "Sağanaklı kar"),
    "SHRA": ("🌧️", "Sağanak yağışlı"),
    "TS": ("⛈️", "Gök gürültülü sağanak"),
    "TSG": ("⛈️", "Gök gürültülü sağanak"),
    "S": ("🌫️", "Sisli"),
    "PUS": ("🌫️", "Puslu"),
    "MLY": ("🌫️", "Dumanlı"),
    "LY": ("🌫️", "Dumanlı"),
}


class MeteorolojiHatasi(Exception):
    """MGM servisi sorgusu başarısız oldu."""


def hadise_goster(kod: str) -> tuple[str, str]:
    """Fenomen kodunu (simgе, Türkçe ad) ikilisine çevirir; bilinmiyorsa
    kodun kendisini ad olarak kullanır."""
    return HADISELER.get((kod or "").strip().upper(),
                         ("❔", (kod or "").strip() or "Bilinmiyor"))


def _get(yol: str, **parametreler) -> list | dict:
    try:
        yanit = requests.get(
            f"{TABAN}/{yol}", params=parametreler or None,
            headers=BASLIK, timeout=15,
        )
        yanit.raise_for_status()
        return yanit.json()
    except requests.RequestException as exc:
        raise MeteorolojiHatasi(f"MGM servisine ulaşılamadı: {exc}") from exc
    except ValueError as exc:
        raise MeteorolojiHatasi(f"MGM yanıtı geçersiz: {exc}") from exc


def iller() -> list[dict]:
    """İl listesi (il, ilPlaka, ilce, merkezId…)."""
    return _get("merkezler/iller")


def ililcesi(il: str) -> list[dict]:
    """Bir ilin ilçe/istasyon listesi."""
    return _get("merkezler/ililcesi", il=_il_temizle(il))


def merkez(il: str, ilce: str = "") -> dict:
    """il(+ilçe) için ölçüm merkezini döner (ilce boşsa öncelikli merkez)."""
    listesi = _get("merkezler", il=_il_temizle(il),
                   ilce=(ilce or "").strip())
    if not listesi:
        raise MeteorolojiHatasi(f"Merkez bulunamadı: {il} / {ilce or '(merkez)'}")
    return listesi[0]


def sondurum(merkezid) -> dict:
    """Anlık ölçüm (sicaklik, nem, ruzgarHiz, hadiseKodu…)."""
    liste = _get("sondurumlar", merkezid=merkezid)
    if not liste:
        raise MeteorolojiHatasi("Anlık ölçüm yok.")
    return liste[0]


def gunluk_tahmin(istno) -> dict:
    """5 günlük tahmin (enYuksekGun1…, hadiseGun1…, tarihGun1…)."""
    liste = _get("tahminler/gunluk", istno=istno)
    if not liste:
        raise MeteorolojiHatasi("Günlük tahmin yok.")
    return liste[0]


def _il_temizle(il: str) -> str:
    """'İstanbul' → 'istanbul' (servis küçük harfli Türkçe arama bekler)."""
    k = (il or "").strip().replace("İ", "i").replace("I", "ı")
    return k.lower()
