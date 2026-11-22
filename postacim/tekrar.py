"""Tekrarlayan olay (RRULE) desteği.

iCalendar (RFC 5545) tekrarlama kurallarını ayrıştırır ve bir olayın
başlangıç tarihlerini verilen pencereye göre üretir. Bağımlılığı yoktur.

Desteklenenler:
- FREQ: DAILY, WEEKLY, MONTHLY, YEARLY
- INTERVAL, COUNT, UNTIL
- BYDAY (sıralı: "2MO", "-1FR"), BYMONTHDAY, BYMONTH, BYSETPOS, WKST
- EXDATE (hariç tutulanlar) ve RDATE (eklenenler)

Örnek:
    kural = tekrar.kural_ayikla("FREQ=WEEKLY;BYDAY=MO,WE;COUNT=10")
    bas = tekrar.tekrar_baslangiclar(datetime(2026,1,5,9,0), kural,
                                      date(2026,1,1), date(2026,3,1))
"""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta

# Haftanın günleri (Pzt = 0 … Paz = 6)
GUN_KODU = {"MO": 0, "TU": 1, "WE": 2, "TH": 3, "FR": 4, "SA": 5, "SU": 6}
GUN_KODU_TERS = {v: k for k, v in GUN_KODU.items()}
GUN_ADLARI = ("Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz")
AY_KODU = {
    "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
    "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12,
}

# Döngü koruması (patolojik kurallarda sonsuz döngü olmasın)
AZAMI_PERIYOT = 5000
AZAMI_SONUC = 2000


# ------------------------------------------------------------------ ayrıştırma

def kural_ayikla(rrule: str) -> dict:
    """'FREQ=WEEKLY;BYDAY=MO,WE' → {'FREQ': 'WEEKLY', 'BYDAY': 'MO,WE'}."""
    kural: dict[str, str] = {}
    for parca in (rrule or "").replace("\r\n", "").split(";"):
        if "=" not in parca:
            continue
        anahtar, _, deger = parca.partition("=")
        anahtar = anahtar.strip().upper()
        deger = deger.strip()
        if anahtar:
            kural[anahtar] = deger
    return kural


def _sayi(deger: str, varsayilan: int = 0) -> int:
    try:
        return int(str(deger).strip())
    except (TypeError, ValueError):
        return varsayilan


def byday_ayikla(deger: str) -> list[tuple[int, int]]:
    """'MO,-1FR' → [(0, 4), (-1, 4)]  (sıra, hafta günü)."""
    sonuc: list[tuple[int, int]] = []
    for parca in (deger or "").split(","):
        parca = parca.strip().upper()
        if not parca:
            continue
        m = re.match(r"^([+-]?\d+)?([A-Z]{2})$", parca)
        if not m:
            continue
        sira = _sayi(m.group(1), 0) if m.group(1) else 0
        gun = GUN_KODU.get(m.group(2))
        if gun is not None:
            sonuc.append((sira, gun))
    return sonuc


def _sayi_listesi(deger: str) -> list[int]:
    sonuc = []
    for parca in (deger or "").split(","):
        parca = parca.strip()
        if parca:
            sonuc.append(_sayi(parca))
    return sonuc


def until_coz(deger: str) -> datetime | None:
    """'20260101' / '20260101T103000Z' → datetime (yerel, naive)."""
    deger = (deger or "").strip()
    if not deger:
        return None
    if deger.endswith("Z"):
        deger = deger[:-1]
    m = re.match(r"^(\d{4})(\d{2})(\d{2})(?:T(\d{2})(\d{2})(\d{2}))?$", deger)
    if not m:
        return None
    y, a, g = int(m.group(1)), int(m.group(2)), int(m.group(3))
    sa = int(m.group(4) or 0)
    dk = int(m.group(5) or 0)
    sn = int(m.group(6) or 0)
    try:
        return datetime(y, a, g, sa, dk, sn)
    except ValueError:
        return None


# ------------------------------------------------------------------ özet

def kural_olustur(
    freq: str,
    aralik: int = 1,
    adet: int = 0,
    gunler: list[int] | None = None,
) -> str:
    """Kullanıcı seçiminden RRULE dizesi üretir.

    `adet` 0 (veya boş) ise sınırsız tekrar.
    """
    parcalar = [f"FREQ={str(freq).upper()}"]
    if aralik > 1:
        parcalar.append(f"INTERVAL={int(aralik)}")
    if gunler:
        parcalar.append(
            "BYDAY=" + ",".join(
                GUN_KODU_TERS[g] for g in gunler if g in GUN_KODU_TERS
            )
        )
    if adet:
        parcalar.append(f"COUNT={int(adet)}")
    return ";".join(p for p in parcalar if p)


def kural_ozeti(kural: dict) -> str:
    """Kuralı kısa Türkçe metne çevirir (arayüz ipucu)."""
    if not kural:
        return ""
    freq = str(kural.get("FREQ", "")).upper()
    aralik = _sayi(kural.get("INTERVAL", "1"), 1) or 1
    byday = byday_ayikla(kural.get("BYDAY", ""))
    sayi = _sayi(kural.get("COUNT", ""))
    until = until_coz(kural.get("UNTIL", ""))

    gunler = ", ".join(GUN_ADLARI[g] for _, g in byday)
    if freq == "DAILY":
        temel = "Her gün" if aralik == 1 else f"Her {aralik} günde bir"
    elif freq == "WEEKLY":
        temel = "Her hafta" if aralik == 1 else f"Her {aralik} haftada bir"
        if gunler:
            temel += f" ({gunler})"
    elif freq == "MONTHLY":
        temel = "Her ay" if aralik == 1 else f"Her {aralik} ayda bir"
        bymd = _sayi_listesi(kural.get("BYMONTHDAY", ""))
        if bymd:
            temel += " (" + ", ".join(str(x) for x in bymd) + ". gün)"
        elif gunler:
            temel += f" ({gunler})"
    elif freq == "YEARLY":
        temel = "Her yıl" if aralik == 1 else f"Her {aralik} yılda bir"
    else:
        temel = freq or "Tekrarlı"

    ek = []
    if sayi:
        ek.append(f"{sayi} kez")
    if until:
        ek.append(f"{until.strftime('%d.%m.%Y')} tarihine kadar")
    if ek:
        temel += " — " + ", ".join(ek)
    return temel


# ------------------------------------------------------------------ üretim

def _ay_gunleri(yil: int, ay: int, byday, bymonthday, varsayilan_gun: int) -> list[date]:
    """Bir ay içindeki uygun günleri (takvim günü sırasıyla) döndürür."""
    import calendar

    gun_sayi = calendar.monthrange(yil, ay)[1]
    sonuc: list[date] = []

    if byday:
        for sira, hafta_gunu in byday:
            eslesen = [
                date(yil, ay, g)
                for g in range(1, gun_sayi + 1)
                if date(yil, ay, g).weekday() == hafta_gunu
            ]
            if not eslesen:
                continue
            if sira > 0:
                if sira <= len(eslesen):
                    sonuc.append(eslesen[sira - 1])
            elif sira < 0:
                if -sira <= len(eslesen):
                    sonuc.append(eslesen[sira])
            else:
                sonuc.extend(eslesen)
    elif bymonthday:
        for gun in bymonthday:
            if gun > 0:
                if gun <= gun_sayi:
                    sonuc.append(date(yil, ay, gun))
            elif gun < 0:
                geri = gun_sayi + 1 + gun  # -1 → son gün
                if 1 <= geri <= gun_sayi:
                    sonuc.append(date(yil, ay, geri))
    else:
        if 1 <= varsayilan_gun <= gun_sayi:
            sonuc.append(date(yil, ay, varsayilan_gun))

    return sorted(set(sonuc))


def _ay_ekle(yil: int, ay: int, ek: int) -> tuple[int, int]:
    """(yıl, ay) + ek ay → (yıl, ay)."""
    toplam = (yil * 12 + (ay - 1)) + ek
    return toplam // 12, toplam % 12 + 1


def _hafta_baslangic(gun: date, wkst: int) -> date:
    return gun - timedelta(days=(gun.weekday() - wkst) % 7)


def tekrar_baslangiclar(
    baslangic: datetime,
    kural: dict,
    pencere_bas: date,
    pencere_bit: date,
    exdate: set[datetime] | None = None,
    rdate: list[datetime] | None = None,
) -> list[datetime]:
    """Verilen pencereye düşen tekrar başlangıçlarını üretir.

    `baslangic` olayın ilk başlangıcıdır (yerel, naive).
    `exdate`/`rdate` yerel naive datetime kümesi/listesi olmalıdır.
    """
    if not kural:
        return []
    freq = str(kural.get("FREQ", "")).upper()
    if freq not in ("DAILY", "WEEKLY", "MONTHLY", "YEARLY"):
        return []

    aralik = max(1, _sayi(kural.get("INTERVAL", "1"), 1))
    adet = _sayi(kural.get("COUNT", ""))
    until = until_coz(kural.get("UNTIL", ""))
    byday = byday_ayikla(kural.get("BYDAY", ""))
    bymonthday = _sayi_listesi(kural.get("BYMONTHDAY", ""))
    bymonth = _sayi_listesi(kural.get("BYMONTH", ""))
    bysetpos = _sayi_listesi(kural.get("BYSETPOS", ""))
    wkst = GUN_KODU.get(str(kural.get("WKST", "MO")).upper(), 0)

    exdate = exdate or set()
    rdate = rdate or []

    bas_tarih = baslangic.date()
    bas_saat = baslangic.time()

    def _uygun(gun: date) -> bool:
        if bymonth and gun.month not in bymonth:
            return False
        if byday and freq in ("DAILY", "WEEKLY") and gun.weekday() not in (
            g for _, g in byday
        ):
            return False
        return True

    # Pencereyi kapsayan periyot aralığı (hızlı ileri atlama).
    # COUNT varsa atlama yapılamaz: kaçıncı tekrar olduğu baştan sayılmalı.
    ilk_periyot = 0
    if pencere_bas and not adet:
        if freq == "DAILY":
            fark = (pencere_bas - bas_tarih).days
            ilk_periyot = max(0, fark // aralik - 2)
        elif freq == "WEEKLY":
            fark = (pencere_bas - _hafta_baslangic(bas_tarih, wkst)).days
            ilk_periyot = max(0, fark // (7 * aralik) - 2)
        elif freq == "MONTHLY":
            fark = (pencere_bas.year - bas_tarih.year) * 12 + (
                pencere_bas.month - bas_tarih.month
            )
            ilk_periyot = max(0, fark // aralik - 2)
        else:  # YEARLY
            fark = pencere_bas.year - bas_tarih.year
            ilk_periyot = max(0, fark // aralik - 2)

    sonuclar: list[datetime] = []
    sayac = 0  # DTSTART'tan itibaren kaçıncı tekrar (COUNT için)
    periyot = ilk_periyot
    en_fazla = AZAMI_PERIYOT

    while periyot < en_fazla:
        gunler: list[date] = []

        if freq == "DAILY":
            gun = bas_tarih + timedelta(days=periyot * aralik)
            gunler = [gun] if _uygun(gun) else []

        elif freq == "WEEKLY":
            hafta = _hafta_baslangic(bas_tarih, wkst) + timedelta(
                weeks=periyot * aralik
            )
            istenen = [g for _, g in byday] or [bas_tarih.weekday()]
            for g in sorted(set(istenen)):
                gun = hafta + timedelta(days=(g - wkst) % 7)
                if gun < bas_tarih:
                    continue
                if _uygun(gun):
                    gunler.append(gun)

        elif freq == "MONTHLY":
            yil, ay = _ay_ekle(bas_tarih.year, bas_tarih.month, periyot * aralik)
            gunler = _ay_gunleri(yil, ay, byday, bymonthday, bas_tarih.day)

        else:  # YEARLY
            yil = bas_tarih.year + periyot * aralik
            if bymonth:
                aylar = sorted(set(bymonth))
            elif byday or bymonthday:
                aylar = list(range(1, 13))
            else:
                aylar = [bas_tarih.month]
            for ay in aylar:
                gunler.extend(
                    _ay_gunleri(yil, ay, byday, bymonthday, bas_tarih.day)
                )
            gunler = sorted(set(gunler))

        if bysetpos and gunler:
            secili = []
            for sira in bysetpos:
                if 0 < sira <= len(gunler):
                    secili.append(gunler[sira - 1])
                elif sira < 0 and -sira <= len(gunler):
                    secili.append(gunler[sira])
            gunler = sorted(set(secili))

        for gun in gunler:
            if gun < bas_tarih:
                continue
            bas = datetime.combine(gun, bas_saat)
            sayac += 1
            if adet and sayac > adet:
                break
            if until and bas > until:
                return _sonuclari_tamamla(
                    sonuclar, rdate, exdate, pencere_bas, pencere_bit
                )
            if pencere_bit and bas.date() > pencere_bit:
                continue
            if bas in exdate:
                continue
            sonuclar.append(bas)
            if len(sonuclar) >= AZAMI_SONUC:
                break
        if adet and sayac >= adet:
            break
        if until and until.date() < bas_tarih:
            break
        if pencere_bit:
            if freq == "DAILY":
                sinir = bas_tarih + timedelta(days=periyot * aralik)
            elif freq == "WEEKLY":
                sinir = _hafta_baslangic(bas_tarih, wkst) + timedelta(
                    weeks=periyot * aralik
                )
            elif freq == "MONTHLY":
                y, _ = _ay_ekle(bas_tarih.year, bas_tarih.month, periyot * aralik)
                sinir = date(y, 1, 1)
            else:
                sinir = date(bas_tarih.year + periyot * aralik, 1, 1)
            if sinir > pencere_bit:
                break
        periyot += 1

    return _sonuclari_tamamla(sonuclar, rdate, exdate, pencere_bas, pencere_bit)


def _sonuclari_tamamla(
    sonuclar: list[datetime],
    rdate: list[datetime],
    exdate: set[datetime],
    pencere_bas: date | None,
    pencere_bit: date | None,
) -> list[datetime]:
    """RDATE ekler, EXDATE çıkarır, pencereye göre süzer."""
    tum = list(sonuclar)
    for d in rdate:
        if d not in tum:
            tum.append(d)
    tum = [d for d in tum if d not in exdate]
    if pencere_bas:
        tum = [d for d in tum if d.date() >= pencere_bas]
    if pencere_bit:
        tum = [d for d in tum if d.date() <= pencere_bit]
    tum.sort()
    return tum


def _iso_naive(deger: str) -> datetime | None:
    """ISO zaman dizesini yerel naive datetime'a çevirir.

    '...Z' (UTC) varsa sistem saat dilimine çevrilir; ofsetli ISO da
    desteklenir. Hatalıysa None.
    """
    deger = (deger or "").strip()
    if not deger:
        return None
    if deger.endswith("Z"):
        deger = deger[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(deger)
    except ValueError:
        return None
    if dt.tzinfo is not None:
        dt = dt.astimezone().replace(tzinfo=None)
    return dt


def exdate_ayikla(deger: str) -> set[datetime]:
    """'2026-01-05T09:00:00,2026-01-12T09:00:00' → {datetime(...)}."""
    sonuc: set[datetime] = set()
    for parca in (deger or "").split(","):
        dt = _iso_naive(parca)
        if dt:
            sonuc.add(dt)
    return sonuc


def rdate_ayikla(deger: str) -> list[datetime]:
    """'2026-01-05T09:00:00' → [datetime(...)]."""
    sonuc = []
    for parca in (deger or "").split(","):
        dt = _iso_naive(parca)
        if dt:
            sonuc.append(dt)
    return sonuc
