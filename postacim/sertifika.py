"""TLS sertifika zinciri onarımı (eksik ara sertifika çözümleme).

Bazı sunucular (örn. MEB `epostagelen.meb.gov.tr`) sertifika zincirini
eksik gönderir: yalnız yaprak (leaf) sertifika gelir, **ara sertifika
gelmez**; istemci zinciri kök CA'ya tamamlayamaz → "certificate verify
failed". Ayrıca eski sistemlerde kök CA (GlobalSign Root R46) yerel
depoda bulunmayabilir.

Bu modül doğrulamayı ASLA kapatmaz; yalnız eksik zincir halkasını
tamamlar:

1. Sunucudan gelen zinciri `openssl s_client -showcerts` ile alır.
2. Yaprak sertifikadaki **AIA (CA Issuers)** adresinden (RFC 5280
   §4.2.2 — standart yol) ara sertifikayı indirir.
3. CA tabanını güncel `certifi` (kuruluysa) + çözülen ara sertifikalarla
   birleştirip `~/.local/state/postacim/sertifika_ca.pem` (0600) yazar.
4. Bu dosyayı `cafile` olarak kullanan bir SSLContext döndürür.

GÜVENLİK: kök CA imzası mutlaka güvenilen depodan (certifi/sistem)
gelmek zorundadır; indirilen ara sertifika yalnız zinciri tamamlar.
"""

from __future__ import annotations

import base64
import os
import re
import shutil
import ssl
import stat
import subprocess
import tempfile

import requests

STATE_DIZIN = os.path.join(
    os.path.expanduser("~"), ".local", "state", "postacim"
)
CA_DOSYA = os.path.join(STATE_DIZIN, "sertifika_ca.pem")

# Derinlik sınırı: ara sertifikanın kendisi de AIA verebilir
EN_FAZLA_DERINLIK = 2
ISTEK_ZAMAN_ASIMI = 15


class SertifikaHatasi(Exception):
    """Sertifika zinciri çözülemedi (normal bağlantı denenmeye devam eder)."""


def _ca_tabani() -> str:
    """En iyi CA deposunu döndürür: certifi (varsa), yoksa sistem deposu."""
    try:
        import certifi

        return certifi.where()
    except Exception:
        pass
    for aday in (
        "/etc/ssl/certs/ca-certificates.crt",   # Debian/Ubuntu
        "/etc/pki/tls/certs/ca-bundle.crt",     # Fedora
        "/etc/ssl/ca-bundle.pem",               # openSUSE
    ):
        if os.path.exists(aday):
            return aday
    return ""


def _pem_yap(icerik: bytes) -> str:
    """Sertifika içeriğini PEM metnine çevirir (PEM geldiyse olduğu gibi)."""
    if icerik.lstrip().startswith(b"-----BEGIN"):
        return icerik.decode("latin-1", "replace")
    b64 = base64.b64encode(icerik).decode("ascii")
    satirlar = "\n".join(b64[i : i + 64] for i in range(0, len(b64), 64))
    return (
        "-----BEGIN CERTIFICATE-----\n" + satirlar
        + "\n-----END CERTIFICATE-----\n"
    )


def _served_certs(host: str, port: int, sunucu_adi: str) -> list[str]:
    """Sunucunun TLS el sıkışmasında gönderdiği sertifikaları (PEM) alır."""
    openssl = shutil.which("openssl")
    if not openssl:
        return []
    try:
        sonuc = subprocess.run(
            [openssl, "s_client", "-connect", f"{host}:{port}",
             "-servername", sunucu_adi, "-showcerts"],
            input=b"", capture_output=True, timeout=ISTEK_ZAMAN_ASIMI,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    cikti = sonuc.stdout.decode("latin-1", "replace")
    return re.findall(
        r"-----BEGIN CERTIFICATE-----.*?-----END CERTIFICATE-----",
        cikti, re.S,
    )


def _aia_adresleri(pem: str) -> list[str]:
    """Sertifikadaki 'CA Issuers' (AIA) adreslerini döndürür."""
    openssl = shutil.which("openssl")
    if not openssl:
        return []
    try:
        sonuc = subprocess.run(
            [openssl, "x509", "-noout", "-ext", "authorityInfoAccess"],
            input=pem.encode(), capture_output=True, timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    return re.findall(
        r"CA Issuers\s*-\s*URI:(\S+)",
        sonuc.stdout.decode("utf-8", "replace"),
    )


def _sertifika_gecerli_mi(pem: str) -> bool:
    openssl = shutil.which("openssl")
    if not openssl:
        return True  # doğrulayamıyorsak indirileni kabul et (root yine denetler)
    try:
        sonuc = subprocess.run(
            [openssl, "x509", "-noout", "-subject"],
            input=pem.encode(), capture_output=True, timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return sonuc.returncode == 0


def _ara_sertifikalari_coz(pemler: list[str]) -> list[str]:
    """Zincirdeki sertifikaların AIA adreslerinden ara sertifikaları indirir.

    Döndürülen liste: indirilen **ara** sertifikalar (PEM). Yine
    eksikse EN_FAZLA_DERINLIK'e kadar devam eder.
    """
    indirilen: list[str] = []
    sira = list(pemler)
    for derinlik in range(EN_FAZLA_DERINLIK):
        yeni_adresler: list[str] = []
        for pem in sira:
            for adres in _aia_adresleri(pem):
                try:
                    yanit = requests.get(adres, timeout=ISTEK_ZAMAN_ASIMI)
                except requests.RequestException:
                    continue
                if yanit.status_code != 200 or not yanit.content:
                    continue
                yeni = _pem_yap(yanit.content)
                if not _sertifika_gecerli_mi(yeni) or yeni in indirilen:
                    continue
                indirilen.append(yeni)
                yeni_adresler.append(yeni)
        if not yeni_adresler:
            break
        sira = yeni_adresler
    return indirilen


def zinciri_onar(host: str, port: int, sunucu_adi: str | None = None) -> str | None:
    """Eksik zinciri çözüp birleşik CA dosyası yazar; yolunu döndürür.

    Başarısızsa None döner (çağıran varsayılan davranışla devam eder).
    """
    sunucu_adi = sunucu_adi or host
    pemler = _served_certs(host, port, sunucu_adi)
    if not pemler:
        return None
    ara = _ara_sertifikalari_coz(pemler)
    taban = _ca_tabani()
    if not taban:
        return None
    try:
        taban_metin = open(taban, "r", encoding="utf-8", errors="replace").read()
    except OSError:
        return None
    birlesik = taban_metin
    for pem in ara:
        if pem not in birlesik:
            birlesik += "\n" + pem + "\n"
    try:
        os.makedirs(STATE_DIZIN, exist_ok=True)
        os.chmod(STATE_DIZIN, stat.S_IRWXU)
        gecici = CA_DOSYA + ".tmp"
        with open(gecici, "w", encoding="utf-8") as f:
            f.write(birlesik)
        os.replace(gecici, CA_DOSYA)
        os.chmod(CA_DOSYA, stat.S_IRUSR | stat.S_IWUSR)  # 0600
    except OSError:
        return None
    return CA_DOSYA


def baglam(ca_dosya: str) -> ssl.SSLContext:
    """Verilen CA dosyasını kullanan, doğrulaması AÇIK SSLContext döndürür."""
    ctx = ssl.create_default_context(cafile=ca_dosya)
    return ctx


def baglan_dene(host: str, port: int, sunucu_adi: str | None = None) -> ssl.SSLContext | None:
    """Varsayılan bağlamda doğrulama düşerse zinciri onarıp bağlam üretir.

    Döndürülen context IMAP4_SSL/SMTP_SSL `ssl_context=` parametresine
    verilir; None dönerse onarım yapılamadı demektir (hata aynen yükselir).
    """
    try:
        zincir = zinciri_onar(host, port, sunucu_adi or host)
    except Exception:
        zincir = None
    if zincir and os.path.exists(zincir):
        try:
            return baglam(zincir)
        except ssl.SSLError:
            return None
    return None
