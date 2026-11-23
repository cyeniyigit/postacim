"""IMAP/SMTP posta istemcisi (Gmail ve diğer IMAP hesapları için).

Kurum Exchange'i EWS ile konuşur; Gmail gibi hesaplar IMAP (okuma) ve
SMTP (gönderme) kullanır. `ImapIstemci`, `EwsIstemci` ile **aynı arayüzü**
sunar — `ui.py` her ikisini de aynı çağrılarla kullanır.

Gmail erişimi için Google hesabında 2 adımlı doğrulama açıkken üretilen
16 haneli **uygulama parolası** gerekir (normal parola IMAP'ta reddedilir).

Hata tipleri arayüzle ortaktır: kimlik hatası `EwsYetkiHatasi` (giriş
penceresi açılır), istemci hatası `EwsHata`, ağ hatası
`requests.RequestException` (yine giriş penceresi) — adlarına rağmen
`ews.py` sınıfları tüm istemcilerin ortak hata tipleridir.
"""

from __future__ import annotations

import base64
import imaplib
import re
import smtplib
import socket
import threading
from datetime import datetime, timezone
from email import policy as mime_policy
from email.message import EmailMessage
from email.parser import BytesParser
from email.utils import formataddr, formatdate, make_msgid, parsedate_to_datetime
from typing import Iterable

import requests

from .ews import (
    Ek,
    EwsHata,
    EwsYetkiHatasi,
    Klasor,
    Mesaj,
    _adres_listesi,
    _mime_den_ek,
    html_metni,
)

# IMAP SPECIAL-USE öznitelikleri → arayüz klasör kimlikleri
OZEL_KIMLIK = {
    "\\Inbox": "inbox",
    "\\Sent": "sentitems",
    "\\Drafts": "drafts",
    "\\Trash": "deleteditems",
    "\\Junk": "junkemail",
    "\\Archive": "archive",
    "\\All": "archive",  # Gmail "Tüm Posta"
}
# Gmail "Tüm Posta" (\All) arşivdir; \Archive varsa önceliklidir.
ALL_ONECILIK = ("\\Archive", "\\All")

# Klasör sırası (arayüzdeki görünüm)
SIRA = ["inbox", "sentitems", "drafts", "deleteditems", "junkemail",
        "archive", "outbox"]

# Tam klasör onbelleği üst sınırı (en yeni N mesajın zarfı çekilir).
# 5000 → 1000: ilk açılış ~15sn → ~3sn. Arama sunucuda çalışır
# (ARAMA_SINIR ayrı), etkilenmez. Sayfalama 1000/50 = 20 sayfa.
ONBELLEK_SINIR = 1000
# Arama sonucu üst sınırı (en yeni N eşleşme)
ARAMA_SINIR = 500
# Zarf çekme grubu (tur başına FETCH zarfı)
GRUP = 300
# MIME onbelleği (mesaj başına, en eski düşer)
MIME_SINIR = 8


def _kilitli(islev):
    """İstemci komutlarını tek iş parçacığına seri bağlar.

    imaplib bağlantısı **eşzamanlı kullanılamaz** (arka plan iş parçacıkları
    aynı anda komut gönderirse yanıt eşleşmesi bozulur → "illegal in state"
    hataları). Her genel işlem bağlantıyı kilitleyerek yürütülür.
    """
    def sarmal(self, *args, **kwargs):
        with self._kilit:
            return islev(self, *args, **kwargs)
    return sarmal


# ------------------------------------------------------------------ UTF-7

def _utf7_kodla(metin: str) -> str:
    """IMAP klasör adları için değiştirilmiş UTF-7 (RFC 3501)."""
    parcalar: list[str] = []
    birikim: list[str] = []

    def bosalt():
        if birikim:
            ham = "".join(birikim).encode("utf-16be")
            kod = base64.b64encode(ham).decode("ascii").rstrip("=").replace("/", ",")
            parcalar.append("&" + kod + "-")
            birikim.clear()

    for ch in metin or "":
        if 0x20 <= ord(ch) <= 0x7E:
            bosalt()
            parcalar.append("&-" if ch == "&" else ch)
        else:
            birikim.append(ch)
    bosalt()
    return "".join(parcalar)


def _utf7_coz(deger) -> str:
    """Değiştirilmiş UTF-7'yi çözer (bytes veya str)."""
    if isinstance(deger, bytes):
        metin = deger.decode("ascii", "replace")
    else:
        metin = str(deger or "")

    def coz(m):
        icerik = m.group(1)
        if icerik == "-":
            return "&"
        try:
            ham = icerik.replace(",", "/")
            ham += "=" * (-len(ham) % 4)
            return base64.b64decode(ham).decode("utf-16be")
        except Exception:
            return m.group(0)

    return re.sub(r"&([^-]*)-", coz, metin)


def _tirnakla(ad: str) -> str:
    """IMAP klasör adını tırnaklar (boşluklu adlar için)."""
    return '"' + ad.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _adres_bicim(adresler: str) -> str:
    """'Ad <a@x>, b@y' → RFC822 To/Cc metni."""
    parcalar = []
    for adres in _adres_listesi(adresler or ""):
        parcalar.append(adres)
    return ", ".join(parcalar)


class ImapIstemci:
    """IMAP (okuma) + SMTP (gönderme) posta kutusu."""

    def __init__(self, hesap: dict):
        self.hesap = dict(hesap)
        self.kullanici = hesap.get("kullanici", "") or ""
        self.parola = hesap.get("parola", "") or ""
        self.gelen_sunucu = hesap.get("gelen_sunucu", "imap.gmail.com")
        self.gelen_port = int(hesap.get("gelen_port", 993))
        self.giden_sunucu = hesap.get("giden_sunucu", "smtp.gmail.com")
        self.giden_port = int(hesap.get("giden_port", 465))
        self.guvenli = hesap.get("guvenli", "ssl")  # ssl | starttls
        self.imap: imaplib.IMAP4 | None = None
        self._secili: str | None = None
        self._klasor_adlari: dict = {}   # kimlik → sunucu adı
        self._onbellek: dict = {}        # klasör → kayıt dict'i
        self._mime_onbellek: dict[str, bytes] = {}
        self._kilit = threading.RLock()  # imaplib bağlantısı tek thread'de
        # Gövde indirmeleri ayrı oturumda yürür: klasör senkronizasyonu
        # sürerken seçilen mail beklemesin (mesaj_detay/ek_indir/.eml)
        self._detay_imap: imaplib.IMAP4 | None = None
        self._detay_secili: str | None = None
        self._kilit_detay = threading.RLock()

    # ------------------------------------------------------------ bağlantı

    def _yeni_baglanti(self) -> imaplib.IMAP4:
        """Yeni bir IMAP oturumu açar ve giriş yapar; hazır bağlantı döner."""
        if not self.kullanici or not self.parola:
            raise EwsYetkiHatasi(
                "E-posta veya uygulama parolası girilmemiş."
            )
        try:
            if self.guvenli == "starttls":
                baglanti = imaplib.IMAP4(self.gelen_sunucu, self.gelen_port,
                                         timeout=30)
                baglanti.starttls()
            else:
                baglanti = imaplib.IMAP4_SSL(self.gelen_sunucu, self.gelen_port,
                                             timeout=30)
            baglanti.login(self.kullanici, self.parola)
            return baglanti
        except (imaplib.IMAP4.error, imaplib.IMAP4.abort) as exc:
            metin = str(exc).lower()
            if any(x in metin for x in ("auth", "login", "credential",
                                        "password", "user")):
                raise EwsYetkiHatasi(
                    "IMAP kimlik doğrulama başarısız. Gmail için normal parola "
                    "değil, uygulama parolası kullanılmalı (Google Hesabı → "
                    "Güvenlik → 2 Adımlı Doğrulama → Uygulama parolaları)."
                ) from exc
            raise EwsHata(f"IMAP hatası: {exc}") from exc
        except (OSError, socket.error) as exc:
            raise requests.RequestException(
                f"Bağlantı kurulamadı: {self.gelen_sunucu}:{self.gelen_port} — {exc}"
            ) from exc

    def _baglan(self) -> None:
        with self._kilit:
            if self.imap is not None:
                # Sunucu BYE ile oturumu kapattıysa durum LOGOUT'ta kalır;
                # böyle bağlantı atılır ve yeniden bağlanılır.
                if getattr(self.imap, "state", "") != "LOGOUT":
                    return
                self._kop()
            try:
                self.imap = self._yeni_baglanti()
                self._secili = None
            except Exception:
                self.imap = None
                raise

    def _kop(self) -> None:
        with self._kilit:
            try:
                if self.imap is not None:
                    self.imap.logout()
            except Exception:
                pass
            self.imap = None
            self._secili = None
        self._kop_detay()

    # ------------------------------------------------- gövde bağlantısı (ayrı)

    def _baglan_detay(self) -> None:
        """Gövde indirmeleri için **ayrı** IMAP oturumu açar.

        Neden ayrı? Mesaj gövdesi (BODY.PEEK[]) yavaş bir indirme olabilir;
        aynı oturumda klasör senkronizasyonu sürerken beklemek yerine
        paralel bağlantı kullanılır — klasör yüklenirken de seçilen mail
        hemen açılır. İki oturum IMAP sunucularında sorun olmaz.
        """
        with self._kilit_detay:
            if self._detay_imap is not None:
                if getattr(self._detay_imap, "state", "") != "LOGOUT":
                    return
                self._kop_detay()
            try:
                self._detay_imap = self._yeni_baglanti()
                self._detay_secili = None
            except Exception:
                self._detay_imap = None
                raise

    def detay_hazirla(self) -> None:
        """Gövde bağlantısını önceden açar (arka planda ısınma)."""
        try:
            self._baglan_detay()
        except (EwsHata, requests.RequestException):
            pass  # ilk gerçek gövde çekiminde yeniden denenecek

    def _kop_detay(self) -> None:
        with self._kilit_detay:
            try:
                if self._detay_imap is not None:
                    self._detay_imap.logout()
            except Exception:
                pass
            self._detay_imap = None
            self._detay_secili = None

    def _komut_detay(self, ad: str, *args, **kwargs):
        """`_komut`un gövde oturumu sürümü (`self._detay_imap` üzerinde)."""
        with self._kilit_detay:
            for deneme in range(2):
                self._baglan_detay()
                try:
                    return getattr(self._detay_imap, ad)(*args, **kwargs)
                except (imaplib.IMAP4.abort, OSError) as exc:
                    self._kop_detay()
                    if deneme == 0:
                        continue
                    raise requests.RequestException(
                        f"Bağlantı koptu: {exc}"
                    ) from exc
                except imaplib.IMAP4.error as exc:
                    if (getattr(self._detay_imap, "state", "") == "LOGOUT"
                            and deneme == 0):
                        self._kop_detay()
                        continue
                    raise EwsHata(f"IMAP komutu reddedildi: {exc}") from exc

    def _sec_detay(self, klasor_adi: str) -> None:
        """Gövde oturumunda klasör seçer (yazma erişimi gerekmez)."""
        if self._detay_secili == klasor_adi:
            return
        tip, _ = self._komut_detay(
            "select", _tirnakla(klasor_adi), readonly=True
        )
        if tip != "OK":
            raise EwsHata(f"Klasör seçilemedi: {klasor_adi}")
        self._detay_secili = klasor_adi

    def _komut(self, ad: str, *args, **kwargs):
        """IMAP komutu (`ad`: `self.imap` üzerindeki metod adı).

        Neden bağlı metod değil? Bağlantı koptuğunda `_kop()` eski nesneyi
        bırakır ve yenisi açılır; `getattr(self.imap, ad)` her denemede
        **taze bağlantıyı** çözer — eski (LOGOUT) nesne üzerinde "illegal in
        state" hatası alınmaz.

        Sunucunun NO/BAD ile reddettiği komutlar (`IMAP4.error`, ör.
        "LIST command error: BAD …") bağlantı hatası değildir: `EwsHata`
        olarak, okunur Türkçe mesajla yukarı çıkarılır. Bağlantı LOGOUT'a
        düştüyse (sunucu BYE) bir kez yeniden bağlanıp denenir.
        """
        with self._kilit:
            for deneme in range(2):
                self._baglan()
                try:
                    return getattr(self.imap, ad)(*args, **kwargs)
                except (imaplib.IMAP4.abort, OSError) as exc:
                    # Kopan bağlantı: bir kez yeniden bağlanıp dene
                    self._kop()
                    if deneme == 0:
                        continue
                    raise requests.RequestException(
                        f"Bağlantı koptu: {exc}"
                    ) from exc
                except imaplib.IMAP4.error as exc:
                    if (getattr(self.imap, "state", "") == "LOGOUT"
                            and deneme == 0):
                        # Sunucu oturumu kapattı (BYE) → yeniden bağlan
                        self._kop()
                        continue
                    raise EwsHata(f"IMAP komutu reddedildi: {exc}") from exc

    def _sec(self, klasor_adi: str) -> None:
        """Klasörü seçer (yazma erişimiyle); seçili değilse."""
        if self._secili == klasor_adi:
            return
        ad = _tirnakla(klasor_adi)
        tip, _ = self._komut("select", ad, readonly=False)
        if tip != "OK":
            raise EwsHata(f"Klasör seçilemedi: {klasor_adi}")
        self._secili = klasor_adi

    # -------------------------------------------------------------- klasörler

    @_kilitli
    def klasor_listesi(self) -> list:
        """Kullanılabilir klasörleri döndürür: [Klasor] (özel kullanım sırasıyla)."""
        self._baglan()
        # Dizin argümanı imaplib'in beklediği biçimde tırnaklı boş olmalı:
        # "" (boş) verilirse sunucuya `LIST  *` (tek argüman) gider → BAD.
        tip, satirlar = self._komut("list", '""', "*")
        if tip != "OK":
            raise EwsHata("Klasör listesi alınamadı (LIST).")

        adaylar: list[tuple[str, str, str]] = []  # (kimlik, sunucu_adi, attrs)
        gorulen: set = set()
        for ham in satirlar or []:
            if not ham:
                continue
            ozellikler, ayrac, ad = _list_satiri(ham)
            if not ad:
                continue
            if "\\Noselect" in ozellikler:
                continue
            kimlik = _ozel_kimlik(ozellikler, ad)
            if kimlik in gorulen:
                continue  # \Archive + \All gibi çiftler
            gorulen.add(kimlik)
            adaylar.append((kimlik, ad, ozellikler))

        # Sıra: bilinen kimlikler önce, sonra alfabetik
        def anahtar(k):
            kimlik, ad, _ = k
            return (SIRA.index(kimlik) if kimlik in SIRA else len(SIRA),
                    ad.lower())

        adaylar.sort(key=anahtar)

        liste = []
        self._klasor_adlari = {}
        for kimlik, ad, _ in adaylar:
            # Komutlarda kullanılacak ham ad (değiştirilmiş UTF-7, ascii)
            # saklanır; görünen ad çözülür (Gönderilmiş, Çöp Kutusu…).
            self._klasor_adlari[kimlik] = ad
            toplam, okunmamis = self._sayac(ad)
            liste.append(
                Klasor(
                    kimlik=kimlik,
                    ad=_guzel_ad(_utf7_coz(ad)),
                    toplam=toplam,
                    okunmamis=okunmamis,
                )
            )
        return liste

    def _sayac(self, klasor_adi: str) -> tuple[int, int]:
        """STATUS ile (toplam, okunmamis) sayısını alır."""
        try:
            tip, veri = self._komut(
                "status", _tirnakla(klasor_adi),
                "(MESSAGES UNSEEN)",
            )
            if tip != "OK" or not veri:
                return 0, 0
            metin = veri[0].decode("ascii", "replace") if isinstance(veri[0], bytes) else str(veri[0])
            m_toplam = re.search(r"MESSAGES\s+(\d+)", metin)
            m_okunmamis = re.search(r"UNSEEN\s+(\d+)", metin)
            toplam = int(m_toplam.group(1)) if m_toplam else 0
            okunmamis = int(m_okunmamis.group(1)) if m_okunmamis else 0
            return toplam, okunmamis
        except (EwsHata, requests.RequestException, ValueError):
            return 0, 0

    def _klasor_adi(self, kimlik: str) -> str:
        """Klasör kimliğini sunucu adına çevirir (listelenmemişse kimliğin kendisi)."""
        return self._klasor_adlari.get(kimlik, kimlik)

    # --------------------------------------------------------------- mesajlar

    @_kilitli
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
        """(mesajlar, toplam_sayi) döndürür.

        Listeleme IMAP `UID SEARCH` + `UID FETCH (RFC822.HEADER)` ile yapılır:
        tüm klasörün zarfları onbelleğe alınır (en yeni ONBELLEK_SINIR kadar),
        sayfalama istemci tarafında yapılır.

        `tam=True` onbelleği sıfırlar ve klasörü baştan çeker.
        `tazele=False` yalnızca onbelleği okur (sayfalama için; ağ yok).
        `arama` verilirse sunucu tarafında `SEARCH` yapılır (yoksa tampondan
        istemci tarafında filtrelenir).
        """
        if arama and tazele:
            self._arama_yap(klasor, arama, alan, tam=tam)
        elif tazele:
            self._senkronize(klasor, tam=tam)

        kayit = self._onbellek.get(klasor, {})
        if arama:
            mesajlar = list(kayit.get("sirali_arama", []))
        else:
            mesajlar = list(kayit.get("sirali", []))

        if arama and not tazele:
            # Onbellek okumasında da EWS gibi istemci tarafı filtre uygulanır.
            arama_k = arama.strip().lower()
            if alan == "gonderen":
                mesajlar = [
                    m for m in mesajlar
                    if arama_k in (m.gonderen or "").lower()
                    or arama_k in (m.gonderen_ad or "").lower()
                ]
            else:
                mesajlar = [
                    m for m in mesajlar
                    if arama_k in (m.konu or "").lower()
                    or arama_k in (m.onizleme or "").lower()
                    or arama_k in (m.gonderen_ad or m.gonderen or "").lower()
                ]

        toplam = len(mesajlar)
        sayfa = mesajlar[offset : offset + sayfa_boyutu]
        return sayfa, toplam

    @_kilitli
    def gelen_sayisi(self) -> int:
        """Gelen Kutusu'ndaki toplam mesaj sayısı (tek STATUS isteği)."""
        self._baglan()
        ad = self._klasor_adi("inbox")
        toplam, _okunmamis = self._sayac(ad)
        return toplam

    def guncelle(self, klasorler: Iterable[str] | None = None) -> dict:
        """Onbellekli klasörlerdeki değişiklikleri çeker (Gönder/Al).

        Her klasör için UID farkı alınır; onbelleği olmayan klasörler
        atlanır. {klasor: yeni_mesaj_sayisi} döndürür.
        """
        hedefler = (
            list(klasorler) if klasorler is not None else list(self._onbellek)
        )
        sonuc = {}
        for klasor in hedefler:
            kayit = self._onbellek.get(klasor)
            if not kayit or not kayit.get("tam"):
                continue  # onbelleği olmayan klasör atlanır
            try:
                eklenen = self._senkronize(klasor)
            except (EwsHata, requests.RequestException):
                continue
            sonuc[klasor] = eklenen
            # Varsa arama katmanı da tazelenir
            arama_kayit = kayit.get("arama")
            if arama_kayit:
                try:
                    self._arama_yap(klasor, arama_kayit[0], arama_kayit[1])
                except (EwsHata, requests.RequestException):
                    pass
        return sonuc

    def _senkronize(self, klasor: str, tam: bool = False) -> int:
        """Klasörün zarf onbelleğini günceller; yeni mesaj sayısını döndürür."""
        kayit = self._onbellek.setdefault(
            klasor,
            {"uidler": set(), "mesajlar": {}, "tam": False,
             "sirali": [], "sirali_arama": [], "arama": None},
        )
        if tam:
            kayit["uidler"] = set()
            kayit["mesajlar"] = {}
            kayit["tam"] = False
            kayit["sirali"] = []
        kayit["tam"] = False

        klasor_adi = self._klasor_adi(klasor)
        self._sec(klasor_adi)
        tip, veri = self._komut("uid", "search", None, "ALL")
        if tip != "OK":
            raise EwsHata(f"Klasör aranamadı: {klasor_adi}")
        tum = [int(u) for u in (veri[0] or b"").split() if u.isdigit()]
        # En yeni ONBELLEK_SINIR kadar (UID artan → sondan alınır)
        uidler = list(reversed(tum))[:ONBELLEK_SINIR]

        yeni = [u for u in uidler if u not in kayit["uidler"]]
        silinen = kayit["uidler"] - set(uidler)
        if yeni:
            self._zarf_cek(klasor, yeni)
        for u in silinen:
            kayit["mesajlar"].pop(u, None)
        kayit["uidler"] = set(uidler)
        kayit["sirali"] = self._sirala(
            kayit["mesajlar"][u] for u in uidler if u in kayit["mesajlar"]
        )
        kayit["tam"] = True
        return len(yeni)

    def _arama_yap(self, klasor: str, arama: str, alan: str, tam: bool = False) -> None:
        """Sunucu tarafı arama; eşleşen zarfları onbelleğe alır."""
        arama = (arama or "").strip()
        kayit = self._onbellek.setdefault(
            klasor,
            {"uidler": set(), "mesajlar": {}, "tam": False,
             "sirali": [], "sirali_arama": [], "arama": None},
        )
        kayit["arama"] = (arama, alan) if arama else None
        if not arama:
            kayit["sirali_arama"] = []
            return

        klasor_adi = self._klasor_adi(klasor)
        try:
            self._sec(klasor_adi)
            if alan == "gonderen":
                kriter = [b"FROM", _arama_dizesi(arama)]
            else:
                kriter = [b"TEXT", _arama_dizesi(arama)]
            tip, veri = self._komut(
                "uid", "search", "UTF-8", *kriter
            )
            if tip != "OK":
                raise EwsHata("SEARCH başarısız")
            uidler = [int(u) for u in (veri[0] or b"").split() if u.isdigit()]
        except (EwsHata, requests.RequestException):
            # Sunucu UTF-8 aramayı desteklemiyorsa: tam onbellek + istemci filtresi.
            self._senkronize(klasor, tam=tam)
            kayit["sirali_arama"] = [
                m for m in kayit["sirali"] if _eslesir(m, arama, alan)
            ]
            return

        uidler = list(reversed(uidler))[:ARAMA_SINIR]
        eksik = [u for u in uidler if u not in kayit["mesajlar"]]
        if eksik:
            self._zarf_cek(klasor, eksik)
        kayit["sirali_arama"] = self._sirala(
            kayit["mesajlar"][u] for u in uidler if u in kayit["mesajlar"]
        )

    def _zarf_cek(self, klasor: str, uidler: list) -> None:
        """Zarf + bayrakları topluca çeker (RFC822.HEADER)."""
        kayit = self._onbellek[klasor]
        for bas in range(0, len(uidler), GRUP):
            grup = uidler[bas : bas + GRUP]
            küme = ",".join(str(u) for u in grup)
            tip, veri = self._komut(
                "uid", "fetch", küme,
                "(UID FLAGS RFC822.HEADER)",
            )
            if tip != "OK":
                raise EwsHata(f"Zarf çekilemedi ({len(grup)} mesaj).")
            for parca in veri or []:
                if not isinstance(parca, tuple) or len(parca) < 2:
                    continue
                baslik = parca[0] if isinstance(parca[0], bytes) else b""
                icerik = parca[1] if isinstance(parca[1], bytes) else b""
                if not icerik:
                    continue
                m_uid = re.search(rb"UID\s+(\d+)", baslik)
                if not m_uid:
                    continue
                uid = int(m_uid.group(1))
                m_flag = re.search(rb"FLAGS\s+\(([^)]*)\)", baslik)
                bayraklar = m_flag.group(1).decode("ascii", "replace") if m_flag else ""
                kayit["mesajlar"][uid] = _zarf_mesaji(
                    icerik, uid, klasor, bayraklar
                )

    @staticmethod
    def _sirala(mesajlar) -> list:
        """En yeniden eskiye (tarihi olmayanlar sona)."""
        return sorted(mesajlar, key=lambda m: m.tariham or "", reverse=True)

    # ------------------------------------------------------- detay / ek / .eml

    def mesaj_detay(self, mesaj: Mesaj) -> Mesaj:
        """Mesaj gövdesini ve ek listesini doldurur (MIME üzerinden).

        `_kilitli` değildir: gövde indirmesi ayrı oturumda (`_kilit_detay`)
        yürür, ana oturumun klasör senkronizasyonunu beklemez.
        """
        ham = self._mime_cek(mesaj.item_id)
        msg = BytesParser(policy=mime_policy.default).parsebytes(ham)
        mesaj.alici = ", ".join(
            a for a in (msg.get("To") or "").replace("\n", " ").split(",") if a.strip()
        )
        mesaj.bilgi = ", ".join(
            a for a in (msg.get("Cc") or "").replace("\n", " ").split(",") if a.strip()
        )

        # Ekler once toplanir: <img> yer tutuculari (cid:...) ek adlariyla
        # eslesir.
        mesaj.ekler = []
        for parca in msg.walk():
            if parca.is_multipart():
                continue
            ad = parca.get_filename()
            if not ad:
                continue
            try:
                icerik = parca.get_payload(decode=True) or b""
            except Exception:
                icerik = b""
            ek = Ek()
            ek.ad = ad
            ek.tur = parca.get_content_type() or "application/octet-stream"
            ek.boyut = len(icerik)
            ek.ek_id = ad
            ek.mesaj_id = mesaj.item_id
            ek.content_id = (parca.get("Content-ID") or "").strip().strip("<>")
            mesaj.ekler.append(ek)

        govde_metin, govde_html = _govde_bul(msg)
        if govde_html:
            mesaj.govde_html = govde_html
            mesaj.govde = html_metni(govde_html, mesaj.resimler, mesaj.ekler)
        else:
            mesaj.govde = govde_metin or ""
        return mesaj

    def _mime_cek(self, mesaj_id: str) -> bytes:
        """Mesajın tam MIME içeriğini indirir (onbellekli).

        Gövde indirmesi **ayrı oturumda** (`_detay_imap`) yapılır: klasör
        senkronizasyonu sürerken bile seçilen mail beklemeksizin açılır.
        Sunucu ikinci oturumu reddederse eski yola (ana oturum) dönülür.
        """
        if not mesaj_id:
            raise EwsHata("Mesaj kimliği yok.")
        if mesaj_id in self._mime_onbellek:
            return self._mime_onbellek[mesaj_id]
        try:
            ham = self._mime_detay_cek(mesaj_id)
        except EwsHata:
            ham = self._mime_ana_cek(mesaj_id)
        with self._kilit_detay:  # önbellek yazımı tek yerde
            self._mime_onbellek[mesaj_id] = ham
            while len(self._mime_onbellek) > MIME_SINIR:
                self._mime_onbellek.pop(next(iter(self._mime_onbellek)))
        return ham

    def _mime_detay_cek(self, mesaj_id: str) -> bytes:
        """MIME içeriğini ayrı (gövde) oturumunda çeker."""
        uid = int(mesaj_id)
        klasor = self._mesaj_klasoru(uid)
        with self._kilit_detay:
            self._baglan_detay()
            if klasor:
                self._sec_detay(klasor)
            tip, veri = self._komut_detay(
                "uid", "fetch", str(uid), "(BODY.PEEK[])"
            )
            ham = self._fetch_govdesi(veri)
        if ham is None:
            raise EwsHata("Mesaj içeriği (MIME) alınamadı.")
        return ham

    def _mime_ana_cek(self, mesaj_id: str) -> bytes:
        """MIME içeriğini ana oturumda çeker (eski davranış; yedek yol)."""
        uid = int(mesaj_id)
        with self._kilit:
            klasor = self._mesaj_klasoru(uid)
            if klasor:
                self._sec(klasor)
            tip, veri = self._komut(
                "uid", "fetch", str(uid), "(BODY.PEEK[])"
            )
            ham = self._fetch_govdesi(veri)
        if ham is None:
            raise EwsHata("Mesaj içeriği (MIME) alınamadı.")
        return ham

    @staticmethod
    def _fetch_govdesi(veri) -> bytes | None:
        """FETCH yanıtındaki en büyük ham bayt bloğunu döndürür."""
        ham = None
        for parca in veri or []:
            if isinstance(parca, tuple) and len(parca) >= 2 \
                    and isinstance(parca[1], bytes):
                if ham is None or len(parca[1]) > len(ham):
                    ham = parca[1]
        return ham

    def _mesaj_klasoru(self, uid: int) -> str | None:
        """Mesajın bulunduğu seçili/onbellekli klasörü bulur.

        `_onbellek` ana oturum kilidi altında değişir; kısa bir tarama
        olduğu için o kilide girilir (diğer iş parçacığını az bekletir).
        """
        with self._kilit:
            for klasor, kayit in self._onbellek.items():
                if uid in kayit.get("mesajlar", {}):
                    return self._klasor_adi(klasor)
        return None

    def ek_indir(self, ek: Ek) -> bytes:
        """Eki mesajın MIME içeriğinden indirir (gövde oturumunda)."""
        ham = self._mime_cek(ek.mesaj_id)
        veri = _mime_den_ek(ham, ek.ad)
        if veri is None:
            raise EwsHata(f"Ek indirilemedi: {ek.ad}")
        return veri

    def mesaj_mime(self, mesaj_id: str) -> bytes:
        """Mesajın tam MIME içeriğini (.eml) döndürür (gövde oturumunda)."""
        return self._mime_cek(mesaj_id)

    # ------------------------------------------------------------------ yazma

    @_kilitli
    def gonder(
        self,
        alici: str,
        konu: str,
        govde: str,
        ekler: Iterable[tuple[str, bytes, str]] = (),
        cc: str = "",
        bcc: str = "",
    ) -> str:
        """E-postayı SMTP ile gönderir. ekler: (ad, icerik, mime) üçlüleri."""
        mesaj = EmailMessage()
        mesaj["From"] = formataddr(("", self.kullanici))
        mesaj["To"] = _adres_bicim(alici)
        if cc:
            mesaj["Cc"] = _adres_bicim(cc)
        if bcc:
            mesaj["Bcc"] = _adres_bicim(bcc)
        mesaj["Subject"] = konu or ""
        mesaj["Date"] = formatdate(localtime=True)
        mesaj["Message-ID"] = make_msgid()
        mesaj.set_content(govde or "")
        for ad, icerik, mime in ekler:
            tur = (mime or "application/octet-stream").split("/", 1)
            if len(tur) == 2:
                mesaj.add_attachment(icerik, maintype=tur[0], subtype=tur[1],
                                     filename=ad)
            else:
                mesaj.add_attachment(icerik, filename=ad)
        self._smtp_gonder(mesaj)

        # Gönderilen klasörüne kopya: Gmail SMTP ile gönderileni kendisi
        # kaydeder; diğer sunucularda istemci APPEND eder.
        if "gmail" not in (self.giden_sunucu or "").lower():
            try:
                gonderilen = self._klasor_adi("sentitems")
                if gonderilen and gonderilen != "sentitems":
                    self._ekle(gonderilen, "(\\Seen)", mesaj.as_bytes())
            except (EwsHata, requests.RequestException, OSError):
                pass
        return ""

    def _smtp_gonder(self, mesaj: EmailMessage) -> None:
        try:
            if self.guvenli == "ssl":
                sunucu = smtplib.SMTP_SSL(self.giden_sunucu, self.giden_port,
                                          timeout=30)
            else:
                sunucu = smtplib.SMTP(self.giden_sunucu, self.giden_port,
                                      timeout=30)
                sunucu.starttls()
            with sunucu:
                sunucu.login(self.kullanici, self.parola)
                sunucu.send_message(
                    mesaj,
                    from_addr=self.kullanici,
                    to_addrs=_adres_listesi(
                        (mesaj.get("To") or "") + "," + (mesaj.get("Cc") or "")
                        + "," + (mesaj.get("Bcc") or "")
                    ),
                )
        except smtplib.SMTPAuthenticationError as exc:
            raise EwsYetkiHatasi(
                "SMTP kimlik doğrulama başarısız. Gmail için uygulama "
                "parolası kullanılmalı."
            ) from exc
        except smtplib.SMTPException as exc:
            raise EwsHata(f"SMTP hatası: {exc}") from exc
        except (OSError, socket.error) as exc:
            raise requests.RequestException(
                f"Bağlantı kurulamadı: {self.giden_sunucu}:{self.giden_port} — {exc}"
            ) from exc

    @_kilitli
    def taslağa_kaydet(self, alici: str, konu: str, govde: str) -> str:
        """Taslak oluşturur (Gönder düğmesi değil): Drafts klasörüne APPEND."""
        mesaj = EmailMessage()
        mesaj["From"] = formataddr(("", self.kullanici))
        mesaj["To"] = _adres_bicim(alici)
        mesaj["Subject"] = konu or ""
        mesaj["Date"] = formatdate(localtime=True)
        mesaj["Message-ID"] = make_msgid()
        mesaj.set_content(govde or "")
        hedef = self._klasor_adi("drafts")
        self._ekle(hedef, "(\\Draft)", mesaj.as_bytes())
        return ""

    def _ekle(self, klasor_adi: str, bayraklar: str, ileti: bytes) -> None:
        """Mesajı klasöre ekler (APPEND)."""
        if not klasor_adi:
            raise EwsHata("Hedef klasör bulunamadı.")
        tip, _ = self._komut(
            "append", _tirnakla(klasor_adi), bayraklar, None, ileti
        )
        if tip != "OK":
            raise EwsHata(f"Mesaj klasöre eklenemedi: {klasor_adi}")

    def cozumle(self, metin: str, en_fazla: int = 20) -> list:
        """IMAP hesapta dizin çözümleme yoktur → boş liste.

        `ui.py` aktif hesap IMAP olduğunda `cozum_yok` bayrağını kurar ve
        yalnızca kayıtlı kişiler (KisiDefteri) önerir.
        """
        return []

    @_kilitli
    def okundu_isaretle(self, mesaj: Mesaj, okundu: bool = True) -> None:
        """Okundu/okunmadı bayrağını IMAP ile yazar (STORE FLAGS)."""
        uid = int(mesaj.item_id)
        klasor = mesaj.klasor or "inbox"
        self._sec(self._klasor_adi(klasor))
        bayrak = "+FLAGS" if okundu else "-FLAGS"
        tip, _ = self._komut(
            "uid", "store", str(uid), bayrak, "(\\Seen)"
        )
        if tip != "OK":
            raise EwsHata("Okundu bayrağı yazılamadı.")
        mesaj.okundu = okundu

    @_kilitli
    def tasi(self, mesaj: Mesaj, hedef: str = "deleteditems") -> None:
        """Mesajı hedef klasöre taşır (MOVE; olmazsa COPY + sil)."""
        uid = int(mesaj.item_id)
        kaynak = self._klasor_adi(mesaj.klasor or "inbox")
        hedef_ad = self._klasor_adi(hedef)
        self._sec(kaynak)
        try:
            tip, _ = self._komut(
                "uid", "move", str(uid), _tirnakla(hedef_ad)
            )
            if tip != "OK":
                raise imaplib.IMAP4.error("MOVE başarısız")
        except (imaplib.IMAP4.error, EwsHata):
            # MOVE uzantısı yoksa: COPY + \Deleted + EXPUNGE
            tip, _ = self._komut(
                "uid", "copy", str(uid), _tirnakla(hedef_ad)
            )
            if tip != "OK":
                raise EwsHata(f"Taşınamadı → {hedef_ad}")
            self._komut("uid", "store", str(uid), "+FLAGS", "(\\Deleted)")
            self._komut("expunge")
        # Onbellekten düşür (yenilemede listeden kaybolur)
        self._ondan_sil(uid)

    @_kilitli
    def kalici_sil(self, mesaj: Mesaj) -> None:
        """Mesajı kalıcı olarak siler (\\Deleted + EXPUNGE)."""
        uid = int(mesaj.item_id)
        klasor = self._klasor_adi(mesaj.klasor or "inbox")
        self._sec(klasor)
        self._komut("uid", "store", str(uid), "+FLAGS", "(\\Deleted)")
        self._komut("expunge")
        self._ondan_sil(uid)

    @_kilitli
    def klasor_olustur(self, ad: str) -> str:
        """Yeni klasör (Gmail etiketi) oluşturur: `CREATE <klasör>`.

        Döndürülen değer klasör **kimliğidir** (değiştirilmiş UTF-7 sunucu
        adı); klasör listesi yenilendiğinde aynı kimlikle görünür.
        """
        ad = (ad or "").strip()
        if not ad:
            raise EwsHata("Klasör adı boş olamaz.")
        if any(ord(ch) < 0x20 for ch in ad):
            raise EwsHata("Klasör adı kontrol karakterleri içeremez.")
        kod = _utf7_kodla(ad)
        tip, _ = self._komut("create", _tirnakla(kod))
        if tip != "OK":
            raise EwsHata(f"Klasör oluşturulamadı: {ad} — sunucu reddetti.")
        # Listeleme güncellenene kadar komutlar bu adla çalışsın
        self._klasor_adlari[kod] = kod
        return kod

    @_kilitli
    def klasor_yeniden_adlandir(self, kimlik: str, yeni_ad: str) -> str:
        """Klasörü yeniden adlandırır: `RENAME <eski> <yeni>`.

        IMAP'te klasör adı aynı zamanda kimliğidir; başarılı olunca yeni
        **kimlik** döner ve eski adla kurulan önbellek/harita kayıtları
        taşınır. Özel klasörler (gelen kutusu, gönderilmiş, …) reddedilir.
        """
        if kimlik in SIRA:
            raise EwsHata(
                "Özel klasör yeniden adlandırılamaz (gelen kutusu, "
                "gönderilmiş, taslak, çöp, spam, arşiv, giden kutusu)."
            )
        yeni_ad = (yeni_ad or "").strip()
        if not yeni_ad:
            raise EwsHata("Klasör adı boş olamaz.")
        if any(ord(ch) < 0x20 for ch in yeni_ad):
            raise EwsHata("Klasör adı kontrol karakterleri içeremez.")
        eski_ad = self._klasor_adi(kimlik)
        yeni_kod = _utf7_kodla(yeni_ad)
        if yeni_kod == eski_ad:
            return kimlik  # ad değişmedi — sunucuya gitmeye gerek yok
        tip, _ = self._komut("rename", _tirnakla(eski_ad), _tirnakla(yeni_kod))
        if tip != "OK":
            raise EwsHata(
                f"Klasör yeniden adlandırılamadı: {kimlik} → {yeni_ad} "
                "— sunucu reddetti."
            )
        # Kimlik değişti: haritayı taşı, eski önbelleği bırak (yeni klasör
        # ilk açılışta baştan çekilir)
        self._klasor_adlari.pop(kimlik, None)
        self._klasor_adlari[yeni_kod] = yeni_kod
        self._onbellek.pop(kimlik, None)
        return yeni_kod

    @_kilitli
    def klasoru_bosalt(self, kimlik: str) -> int:
        """Klasördeki tüm mesajları kalıcı siler; silinen sayıyı döndürür.

        Yalnız çöp kutusu ve spam klasörüne izin verilir: UID SEARCH ALL →
        \\Deleted işaretle (300'lük kümeler) → EXPUNGE. Gmail'de bu, çöp
        kutusunu/spam'i gerçekten boşaltır.
        """
        if kimlik not in ("deleteditems", "junkemail"):
            raise EwsHata(
                "Yalnız çöp kutusu ve spam klasörü bu yolla boşaltılabilir."
            )
        ad = self._klasor_adi(kimlik)
        self._sec(ad)
        tip, veri = self._komut("uid", "search", "ALL")
        if tip != "OK":
            raise EwsHata("Klasördeki mesajlar listelenemedi.")
        uidler = [int(u) for u in (veri[0] or b"").split() if u.isdigit()]
        if not uidler:
            self._onbellek.pop(kimlik, None)
            return 0
        for kume in self._uid_kumeleri(uidler):
            tip, _ = self._komut(
                "uid", "store", kume, "+FLAGS.SILENT", "(\\Deleted)"
            )
            if tip != "OK":
                raise EwsHata("Mesajlar silinmek üzere işaretlenemedi.")
        tip, _ = self._komut("expunge")
        if tip != "OK":
            raise EwsHata("Klasör boşaltılamadı.")
        self._onbellek.pop(kimlik, None)
        return len(uidler)

    @staticmethod
    def _uid_kumeleri(uidler: list, boyut: int = 300) -> list:
        """Artan UID listesini aralık kümelerine böler (1:5,9,11:14)."""
        kumeler: list[str] = []
        bas = onceki = None
        sayi = 0
        for u in uidler:
            if bas is None:
                bas = onceki = u
                sayi = 1
            elif u == onceki + 1 and sayi < boyut:
                onceki = u
                sayi += 1
            else:
                kumeler.append(
                    str(bas) if bas == onceki else f"{bas}:{onceki}"
                )
                bas = onceki = u
                sayi = 1
        if bas is not None:
            kumeler.append(str(bas) if bas == onceki else f"{bas}:{onceki}")
        return kumeler

    @_kilitli
    def klasor_sil(self, kimlik: str) -> None:
        """Klasörü (IMAP etiketini) siler: `DELETE <klasör>`.

        Özel klasörler (gelen kutusu, gönderilmiş, taslak, çöp, spam,
        arşiv, giden) sunucu tarafından korunur — silinemez.
        Gmail'de bir etiketin silinmesi o etiketi **tüm mesajlardan kaldırır**;
        mesajlar silinmez (Tüm Postalar'da durur).
        """
        if kimlik in SIRA:
            raise EwsHata(
                "Özel klasör silinemez (gelen kutusu, gönderilmiş, taslak, "
                "çöp, spam, arşiv, giden kutusu)."
            )
        ad = self._klasor_adi(kimlik)
        tip, _ = self._komut("delete", _tirnakla(ad))
        if tip != "OK":
            raise EwsHata(f"Klasör silinemedi: {ad} — sunucu reddetti.")
        # Onbelleklerden düşür (yenilemede listeden kaybolur)
        self._onbellek.pop(kimlik, None)
        self._klasor_adlari.pop(kimlik, None)
        if self._secili == ad:
            self._secili = None

    def _ondan_sil(self, uid: int) -> None:
        for kayit in self._onbellek.values():
            if uid in kayit.get("mesajlar", {}):
                kayit["mesajlar"].pop(uid, None)
                kayit["uidler"].discard(uid)
                kayit["sirali"] = [m for m in kayit["sirali"]
                                   if m.item_id != str(uid)]
                kayit["sirali_arama"] = [m for m in kayit["sirali_arama"]
                                         if m.item_id != str(uid)]


# ------------------------------------------------------------------ yardımcılar

def _list_satiri(ham: bytes) -> tuple[str, str, str]:
    """LIST yanıt satırını (özellikler, ayraç, ad) ayrıştırır.

    Örnek: b'(\\\\HasNoChildren \\\\Sent) \"/\" \"[Gmail]/Gönderilmiş\"'
    """
    if isinstance(ham, str):
        ham = ham.encode("utf-8", "replace")
    metin = ham.decode("utf-8", "replace").strip()
    ozellikler = ""
    if metin.startswith("("):
        bitis = metin.find(")")
        if bitis > 0:
            ozellikler = metin[1:bitis]
            metin = metin[bitis + 1 :].strip()
    # Ayraç: tırnaklı ya da tek atom
    ayrac = ""
    if metin.startswith('"'):
        son = metin.find('"', 1)
        if son > 0:
            ayrac = metin[1:son]
            metin = metin[son + 1 :].strip()
    else:
        parcalar = metin.split(None, 1)
        if parcalar:
            ayrac = parcalar[0]
            metin = parcalar[1] if len(parcalar) > 1 else ""
    ad = metin.strip()
    if ad.startswith('"') and ad.endswith('"') and len(ad) >= 2:
        ad = ad[1:-1].replace('\\"', '"').replace("\\\\", "\\")
    return ozellikler, ayrac, ad


def _ozel_kimlik(ozellikler: str, ad: str) -> str:
    """SPECIAL-USE özniteliklerinden (ya da INBOX adından) klasör kimliği."""
    yukari = (ozellikler or "").upper()
    # \Archive her zaman \All'dan önceliklidir
    for oz in ALL_ONECILIK:
        if oz.upper() in yukari:
            return OZEL_KIMLIK[oz]
    for oz, kimlik in OZEL_KIMLIK.items():
        if oz.upper() in yukari:
            return kimlik
    if ad.upper() == "INBOX":
        return "inbox"
    # Bilinmeyen klasör: adın kendisi kimlik olur
    return ad


def _guzel_ad(ad: str) -> str:
    """Sunucu klasör adını sadeleştirir ('[Gmail]/Gönderilmiş' → 'Gönderilmiş')."""
    for onek in ("[Gmail]/", "[Google Mail]/", "[Google Mail]"):
        if ad.startswith(onek):
            return ad[len(onek) :] or ad
    return ad


def _arama_dizesi(arama: str) -> bytes:
    """Arama terimini IMAP dizesine çevirir (tırnak + UTF-8 baytlar)."""
    temiz = (arama or "").replace('"', "'").strip()
    return f'"{temiz}"'.encode("utf-8")


def _eslesir(mesaj: Mesaj, arama: str, alan: str) -> bool:
    """İstemci tarafı eşleşme (EWS ile aynı davranış)."""
    arama_k = arama.strip().lower()
    if not arama_k:
        return True
    if alan == "gonderen":
        return (
            arama_k in (mesaj.gonderen or "").lower()
            or arama_k in (mesaj.gonderen_ad or "").lower()
        )
    return (
        arama_k in (mesaj.konu or "").lower()
        or arama_k in (mesaj.onizleme or "").lower()
        or arama_k in (mesaj.gonderen_ad or mesaj.gonderen or "").lower()
    )


def _zarf_mesaji(icerik: bytes, uid: int, klasor: str, bayraklar: str) -> Mesaj:
    """RFC822.HEADER içeriğinden liste mesajı üretir."""
    try:
        msg = BytesParser(policy=mime_policy.default).parsebytes(icerik)
    except Exception:
        msg = None
    konu = gonderen = gonderen_ad = tarih_metni = tariham = ""
    ek_var = False
    if msg is not None:
        konu = str(msg.get("Subject") or "") or "(konu yok)"
        from_ = str(msg.get("From") or "")
        gonderen_ad, gonderen = _adres_ayir(from_)
        tarih_metni, tariham = _tarih_bicim(msg.get("Date"))
        # Ek sezgisi: multipart ise büyük olasılıkla ek vardır
        icerik_turu = (msg.get_content_type() or "").lower()
        ek_var = icerik_turu.startswith("multipart/")
    else:
        konu = "(konu yok)"
    return Mesaj(
        item_id=str(uid),
        change_key="",
        konu=konu,
        gonderen=gonderen,
        gonderen_ad=gonderen_ad,
        tarih=tarih_metni,
        okundu="\\Seen" in (bayraklar or ""),
        onizleme="",
        klasor=klasor,
        tariham=tariham,
        ek_var=ek_var,
    )


def _adres_ayir(deger: str) -> tuple[str, str]:
    """'Ad Soyad <a@x>' → (ad, adres); düz adres için ('', adres)."""
    deger = (deger or "").strip()
    if not deger:
        return "", ""
    if "<" in deger:
        ad = deger.split("<", 1)[0].strip().strip('"')
        adres = deger.split("<", 1)[1].rstrip(">").strip()
        return ad, adres
    return "", deger


def _tarih_bicim(deger) -> tuple[str, str]:
    """Date başlığını ('dd.mm.yyyy hh:mm', sıralama anahtarı) çevirir."""
    if not deger:
        return "", ""
    try:
        dt = parsedate_to_datetime(str(deger))
    except Exception:
        return "", ""
    if dt is None:
        return "", ""
    if dt.tzinfo is not None:
        sira = dt.astimezone(timezone.utc).isoformat()
        yerel = dt.astimezone()
    else:
        sira = dt.isoformat()
        yerel = dt
    return (
        f"{yerel.day:02d}.{yerel.month:02d}.{yerel.year} "
        f"{yerel.hour:02d}:{yerel.minute:02d}",
        sira,
    )


def _govde_bul(msg) -> tuple[str, str]:
    """MIME'dan (düz metin, html) gövdeyi bulur."""
    duz = html = ""
    if not msg.is_multipart():
        tur = (msg.get_content_type() or "").lower()
        try:
            icerik = msg.get_content()
        except Exception:
            icerik = ""
        if tur == "text/html":
            html = icerik if isinstance(icerik, str) else ""
        else:
            duz = icerik if isinstance(icerik, str) else ""
        return duz, html
    for parca in msg.walk():
        if parca.is_multipart():
            continue
        tur = (parca.get_content_type() or "").lower()
        try:
            icerik = parca.get_content()
        except Exception:
            icerik = ""
        if not isinstance(icerik, str):
            continue
        if tur == "text/plain" and not duz:
            duz = icerik
        elif tur == "text/html" and not html:
            html = icerik
        if duz and html:
            break
    return duz, html
