"""Ayarların saklanması (çoklu hesap).

`hesap.json` içinde birden fazla hesap (Exchange EWS + Gmail/IMAP) ve aktif
hesap bulunur. Eski tek-hesap biçiminden otomatik göç yapılır.

Parola kullanıcının isteğiyle diskte tutulur; dosya izni 0600 yapılır.
"""

from __future__ import annotations

import json
import os
import stat
import uuid

VARSAYILAN_DIZIN = os.path.join(os.path.expanduser("~"), ".config", "postacim")
VARSAYILAN_DOSYA = os.path.join(VARSAYILAN_DIZIN, "hesap.json")
VARSAYILAN_KISILER = os.path.join(VARSAYILAN_DIZIN, "kisiler.json")

# Eski tek-hesap biçimindeki anahtarlar (göç için)
ESKI_ANAHTARLAR = ("sunucu", "kullanici", "parola", "yontem", "son_klasor")

# Yalnızca global tutulan tercihler
GLOBAL_ANAHTARLAR = (
    "tema", "otomatik_yenile", "klasor_ebeveyn", "son_arama", "takvim_gorunum",
    "takvim_stil", "tamamlanan_randevular",
)

# Yeni hesap için varsayılanlar (tür bazlı)
HESAP_VARSAYILAN = {
    "ews": {
        "tur": "ews",
        "sunucu": "",          # kullanıcı girer (örn. mail.kurum.gov.tr)
        "yontem": "ntlm",
        "son_klasor": "inbox",
    },
    "imap": {
        "tur": "imap",
        "gelen_sunucu": "imap.gmail.com",
        "gelen_port": 993,
        "giden_sunucu": "smtp.gmail.com",
        "giden_port": 465,
        "guvenli": "ssl",  # ssl | starttls
        "son_klasor": "inbox",
    },
}


def yeni_hesap_id() -> str:
    """Benzersiz hesap kimliği."""
    return uuid.uuid4().hex[:8]



class Ayarlar:
    def __init__(self, yol: str = VARSAYILAN_DOSYA):
        self.yol = yol
        self.veri: dict = {"hesaplar": [], "aktif": ""}
        self.yukle()

    def yukle(self) -> dict:
        try:
            with open(self.yol, "r", encoding="utf-8") as f:
                veri = json.load(f)
            if isinstance(veri, dict):
                self.veri = veri
        except (OSError, ValueError):
            pass
        self._duzelt()
        return self.veri

    def _duzelt(self) -> None:
        """Biçimi doğrular; eski tekli biçim varsa göç eder."""
        if "hesaplar" not in self.veri and any(
            k in self.veri for k in ESKI_ANAHTARLAR
        ):
            self._goc_et()
        if not isinstance(self.veri.get("hesaplar"), list):
            self.veri["hesaplar"] = []
        self.veri["hesaplar"] = [
            h for h in self.veri["hesaplar"] if isinstance(h, dict) and h.get("id")
        ]
        if not isinstance(self.veri.get("takvimler"), list):
            self.veri["takvimler"] = []
        self.veri["takvimler"] = [
            t for t in self.veri["takvimler"] if isinstance(t, dict) and t.get("id")
        ]
        # Aktif hesap geçerli değilse ilki
        aktif = self.veri.get("aktif")
        if not any(h["id"] == aktif for h in self.veri["hesaplar"]):
            ilk = self.veri["hesaplar"]
            self.veri["aktif"] = ilk[0]["id"] if ilk else ""

    def _goc_et(self) -> None:
        """Eski tek-hesap biçimini (düz kullanici/parola) çoklu biçime çevirir."""
        eski = dict(self.veri)
        hesap = dict(HESAP_VARSAYILAN["ews"])
        hesap["id"] = yeni_hesap_id()
        hesap["ad"] = "Exchange"
        hesap["kullanici"] = eski.get("kullanici", "") or ""
        hesap["parola"] = eski.get("parola", "") or ""
        if eski.get("sunucu"):
            hesap["sunucu"] = eski["sunucu"]
        if eski.get("yontem"):
            hesap["yontem"] = eski["yontem"]
        if eski.get("son_klasor"):
            hesap["son_klasor"] = eski["son_klasor"]
        yeni = {k: eski[k] for k in GLOBAL_ANAHTARLAR if k in eski}
        yeni["hesaplar"] = [hesap]
        yeni["aktif"] = hesap["id"]
        self.veri = yeni

    # ---------------------------------------------------------- global tercihler

    def al(self, anahtar: str, varsayilan=None):
        if anahtar in self.veri:
            deger = self.veri[anahtar]
            # None yazılmışsa (örn. eski sürümden kalan) varsayılana dön
            return varsayilan if deger is None else deger
        if anahtar in ESKI_ANAHTARLAR:
            # Geriye dönük uyum: eski tekli anahtarlar aktif hesaptan okunur
            # (eski test betikleri ve yardımcılar böyle çalışır).
            hesap = self.aktif_hesap() or {}
            return hesap.get(anahtar, varsayilan)
        return varsayilan

    def ayarla(self, anahtar: str, deger) -> None:
        if anahtar in ESKI_ANAHTARLAR:
            hesap = self.aktif_hesap()
            if hesap is not None:
                hesap[anahtar] = deger
                return
        self.veri[anahtar] = deger

    def kaydet(self) -> None:
        dizin = os.path.dirname(self.yol)
        os.makedirs(dizin, exist_ok=True)
        os.chmod(dizin, stat.S_IRWXU)
        gecici = self.yol + ".tmp"
        with open(gecici, "w", encoding="utf-8") as f:
            json.dump(self.veri, f, ensure_ascii=False, indent=2)
        os.replace(gecici, self.yol)
        os.chmod(self.yol, stat.S_IRUSR | stat.S_IWUSR)  # 0600

    # ------------------------------------------------------------------ hesaplar

    def hesaplar(self) -> list:
        """Tüm hesaplar (liste kopyası değil; düzenleme için doğrudan referans)."""
        return self.veri.get("hesaplar", [])

    def hesap(self, hesap_id: str) -> dict | None:
        for h in self.veri.get("hesaplar", []):
            if h.get("id") == hesap_id:
                return h
        return None

    def aktif_hesap_id(self) -> str:
        return self.veri.get("aktif", "")

    def aktif_hesap(self) -> dict | None:
        return self.hesap(self.aktif_hesap_id())

    def aktif_ayarla(self, hesap_id: str) -> None:
        if self.hesap(hesap_id) is not None:
            self.veri["aktif"] = hesap_id

    def hesap_ekle(self, hesap: dict) -> dict:
        """Yeni hesap ekler (id yoksa üretir), kaydeder ve döndürür."""
        hesap = dict(hesap)
        if not hesap.get("id"):
            hesap["id"] = yeni_hesap_id()
        turler = HESAP_VARSAYILAN.get(hesap.get("tur", ""), {})
        for anahtar, deger in turler.items():
            hesap.setdefault(anahtar, deger)
        hesap.setdefault("ad", hesap.get("kullanici", "") or "Hesap")
        hesap.setdefault("parola", "")
        self.veri.setdefault("hesaplar", []).append(hesap)
        if not self.veri.get("aktif"):
            self.veri["aktif"] = hesap["id"]
        self.kaydet()
        return hesap

    def hesap_guncelle(self, hesap_id: str, alanlar: dict) -> None:
        hesap = self.hesap(hesap_id)
        if hesap is None:
            return
        hesap.update(alanlar)
        self.kaydet()

    def hesap_sil(self, hesap_id: str) -> None:
        """Hesabı siler; aktif hesap silinirse diğer hesaba geçilir."""
        hesaplar = self.veri.get("hesaplar", [])
        self.veri["hesaplar"] = [h for h in hesaplar if h.get("id") != hesap_id]
        if self.veri.get("aktif") == hesap_id:
            kalan = self.veri["hesaplar"]
            self.veri["aktif"] = kalan[0]["id"] if kalan else ""
        self.kaydet()

    # -------------------------------------------------------------- takvimler

    def takvimler(self) -> list:
        """Takvim hesapları listesi (CalDAV ya da EWS'ye bağlı)."""
        if not isinstance(self.veri.get("takvimler"), list):
            self.veri["takvimler"] = []
        return self.veri["takvimler"]

    def takvim(self, takvim_id: str) -> dict | None:
        for t in self.takvimler():
            if t.get("id") == takvim_id:
                return t
        return None

    def takvim_ekle(self, takvim: dict) -> dict:
        takvim = dict(takvim)
        if not takvim.get("id"):
            takvim["id"] = yeni_hesap_id()
        takvim.setdefault("ad", takvim.get("kullanici") or "Takvim")
        self.takvimler().append(takvim)
        self.kaydet()
        return takvim

    def takvim_guncelle(self, takvim_id: str, alanlar: dict) -> None:
        t = self.takvim(takvim_id)
        if t is None:
            return
        t.update(alanlar)
        self.kaydet()

    def takvim_sil(self, takvim_id: str) -> None:
        self.veri["takvimler"] = [
            t for t in self.takvimler() if t.get("id") != takvim_id
        ]
        self.kaydet()


class KisiDefteri:
    """Kullanılan kişiler (Outlook otomatik tamamlama önbelleği gibi).

    `kisiler.json` içinde en yeni kullanılan başta durur; yazma
    penceresindeki Kime/Bilgi alanları, kurum dizini kullanılamadığında
    buradan yedek öneri verir.
    """

    SINIR = 200

    def __init__(self, yol: str = VARSAYILAN_KISILER):
        self.yol = yol
        self.kisiler: list = []  # [{"ad": ..., "eposta": ...}] en yeni başta
        self._yukle()

    def _yukle(self) -> None:
        try:
            with open(self.yol, "r", encoding="utf-8") as f:
                veri = json.load(f)
            if isinstance(veri, list):
                self.kisiler = [k for k in veri if isinstance(k, dict) and k.get("eposta")]
        except (OSError, ValueError):
            pass

    def kaydet(self) -> None:
        dizin = os.path.dirname(self.yol)
        os.makedirs(dizin, exist_ok=True)
        os.chmod(dizin, stat.S_IRWXU)
        gecici = self.yol + ".tmp"
        with open(gecici, "w", encoding="utf-8") as f:
            json.dump(self.kisiler, f, ensure_ascii=False, indent=2)
        os.replace(gecici, self.yol)
        os.chmod(self.yol, stat.S_IRUSR | stat.S_IWUSR)  # 0600

    def ekle(self, ad: str, eposta: str) -> None:
        eposta = (eposta or "").strip()
        if not eposta:
            return
        ad = (ad or "").strip() or eposta
        anahtar = eposta.lower()
        self.kisiler = [k for k in self.kisiler if k.get("eposta", "").lower() != anahtar]
        self.kisiler.insert(0, {"ad": ad, "eposta": eposta})
        del self.kisiler[self.SINIR:]
        self.kaydet()

    def ara(self, metin: str, en_fazla: int = 8) -> list:
        """Ad/e-posta içinde arar; [(ad, eposta), ...] — en yeni kullanılan önce."""
        metin = (metin or "").strip().lower()
        if not metin:
            return []
        sonuc = []
        for k in self.kisiler:
            ad = k.get("ad", "")
            eposta = k.get("eposta", "")
            if metin in ad.lower() or metin in eposta.lower():
                sonuc.append((ad, eposta))
            if len(sonuc) >= en_fazla:
                break
        return sonuc
