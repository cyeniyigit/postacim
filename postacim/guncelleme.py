"""Otomatik güncelleme — GitHub'dan sürüm denetimi ve kendini kurma.

Akış:
1. `son_surum()` GitHub'daki en yeni sürümü sorgular (API → yedek raw dosya).
2. Kurulu sürümden daha yeniyse `indir()` arşivi akışla indirir
   (ilerleme yüzdesi çağrı geri çağrısına gider).
3. `kur()` arşivi ayıklar, çalışan sanal ortama pip ile kurar ve
   sürümün gerçekten değiştiğini doğrular.
4. Arayüz `yeniden_baslat()` ile uygulamayı yeni sürümle yeniden açar.

Güvenlik: indirme yalnızca GitHub (HTTPS) üzerinden yapılır; kurulum
kullanıcının kendi sanal ortamına (sudo yok, ~/.local) yapılır.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import tarfile
import tempfile

import requests

from . import __version__

REPO = "cyeniyigit/postacim"
API_ADRESI = f"https://api.github.com/repos/{REPO}/releases/latest"
RAW_ADRESI = (
    f"https://raw.githubusercontent.com/{REPO}/main/"
    "postacim/__init__.py"
)
ARSIV_ADRESI = f"https://github.com/{REPO}/archive/refs/heads/main.tar.gz"


class GuncellemeHatasi(Exception):
    """Güncelleme akışında bir adım başarısız oldu."""


def mevcut_surum() -> str:
    """Çalışan uygulamanın sürümü."""
    return __version__


def _surum_parcala(surum: str) -> tuple[int, ...]:
    """'0.1.16' / 'v0.2' → (0, 1, 16) / (0, 2). Sayısal olmayanlar atılır."""
    sayilar = re.findall(r"\d+", surum or "")
    return tuple(int(s) for s in sayilar)


def daha_yeni(yeni: str, eski: str) -> bool:
    """`yeni`, `eski`den daha yeni bir sürüm mü? (sayısal karşılaştırma)"""
    y, e = _surum_parcala(yeni), _surum_parcala(eski)
    uzunluk = max(len(y), len(e))
    y += (0,) * (uzunluk - len(y))
    e += (0,) * (uzunluk - len(e))
    return y > e


def son_surum(zaman_asimi: float = 5.0) -> tuple[str | None, str | None]:
    """GitHub'daki en yeni sürüm (sürüm, arşiv-adresi).

    Önce Releases API, olmazsa main dalındaki `__init__.py` okunur
    (proje GitHub Release kullanmayabilir). Ağ yoksa / yanıt yoksa
    (None, None) — hata fırlatmaz, açılışı engellememeli.
    """
    try:
        yanit = requests.get(
            API_ADRESI,
            timeout=zaman_asimi,
            headers={"Accept": "application/vnd.github+json"},
        )
        if yanit.ok:
            bilgi = yanit.json()
            surum = (bilgi.get("tag_name") or "").lstrip("v")
            if surum:
                return surum, bilgi.get("tarball_url") or ARSIV_ADRESI
    except (requests.RequestException, ValueError):
        pass
    try:
        yanit = requests.get(RAW_ADRESI, timeout=zaman_asimi)
        eslesme = re.search(r'__version__\s*=\s*"([^"]+)"', yanit.text)
        if yanit.ok and eslesme:
            return eslesme.group(1), ARSIV_ADRESI
    except requests.RequestException:
        pass
    return None, None


def indir(
    adres: str,
    hedef_dizin: str,
    ilerleme=None,
    zaman_asimi: float = 30.0,
) -> str:
    """Arşivi akışla indirir; `ilerleme(yuklenen, toplam)` çağrılır.

    Content-Length yoksa ilerleme çağrılmaz (arayüz belirsiz modda bekler).
    """
    hedef = os.path.join(hedef_dizin, "postacim-guncelleme.tar.gz")
    try:
        yanit = requests.get(adres, stream=True, timeout=zaman_asimi)
        yanit.raise_for_status()
        toplam = int(yanit.headers.get("Content-Length") or 0)
        yuklenen = 0
        with open(hedef, "wb") as f:
            for parca in yanit.iter_content(65536):
                f.write(parca)
                yuklenen += len(parca)
                if ilerleme and toplam:
                    ilerleme(yuklenen, toplam)
    except (requests.RequestException, OSError) as exc:
        raise GuncellemeHatasi(f"Güncelleme indirilemedi: {exc}") from exc
    return hedef


def _arsiv_ayikla(arsiv_yolu: str) -> str:
    """tar.gz'yi geçici dizine açar; postacim paketinin kaynak kökünü döner."""
    try:
        dizin = tempfile.mkdtemp(prefix="postacim-guncelleme-")
        with tarfile.open(arsiv_yolu, "r:gz") as arsiv:
            arsiv.extractall(dizin, filter="data")
    except (tarfile.TarError, OSError) as exc:
        raise GuncellemeHatasi(f"Arşiv ayıklanamadı: {exc}") from exc
    for kok, _d, _d2 in os.walk(dizin):
        if os.path.isfile(os.path.join(kok, "postacim", "__init__.py")):
            return kok
    raise GuncellemeHatasi("Arşiv içinde postacim paketi bulunamadı.")


def _pip(venv_python: str, arglar: list[str]) -> None:
    """Sanal ortama pip komutu çalıştırır; hata durumunda hatayı yükseltir.

    Paket kurulumunda yalıtımlı derleme ortamı hazırlanamıyorsa (ağ
    kısıtlı ortamlar) `--no-build-isolation` ile bir kez daha denenir.
    """
    islem = subprocess.run(
        [venv_python, "-m", "pip", *arglar],
        capture_output=True, text=True, timeout=600,
    )
    if islem.returncode != 0 and "install" in arglar and \
            "--no-build-isolation" not in arglar:
        yedek = list(arglar)
        yedek.insert(1, "--no-build-isolation")
        islem = subprocess.run(
            [venv_python, "-m", "pip", *yedek],
            capture_output=True, text=True, timeout=600,
        )
    if islem.returncode != 0:
        cikti = (islem.stderr or islem.stdout or "").strip()
        raise GuncellemeHatasi(
            "Yeni paket kurulamadı: " + (cikti[-400:] if cikti else "?")
        )


def _venv_surum(venv_python: str) -> str:
    """Kurulumdan sonra taze bir süreçte sürümü okur (modül önbelleği yok)."""
    islem = subprocess.run(
        [venv_python, "-c", "import postacim; print(postacim.__version__)"],
        capture_output=True, text=True, timeout=60,
    )
    if islem.returncode != 0:
        raise GuncellemeHatasi(
            "Yeni sürüm doğrulanamadı: " + (islem.stderr.strip()[-300:] or "?")
        )
    return islem.stdout.strip().strip('"')


def kur(
    arsiv_yolu: str,
    hedef_surum: str,
    ilerleme=None,
    venv_python: str | None = None,
) -> str:
    """İndirilen arşivi çalışan sanal ortama kurar; kurulan sürümü döner.

    `ilerleme(ad, yuzde)` aşamaları iletir (yüzde 0–100, tüm güncellemenin
    tamamı). `venv_python` verilmemişse **çalışan yorumlayıcı** kullanılır
    — uygulama `~/.local/share/postacim/venv` içinde çalışıyorsa güncelleme
    de oraya kurularak kendini güncellemiş olur.
    """
    vpy = venv_python or sys.executable

    def asama(ad: str, yuzde: int):
        if ilerleme:
            ilerleme(ad, yuzde)

    asama("Arşiv ayıklanıyor…", 75)
    kaynak = _arsiv_ayikla(arsiv_yolu)
    asama("Yeni paket kuruluyor…", 85)
    _pip(vpy, ["install", "--quiet", "--no-deps", kaynak])
    gereksinim = os.path.join(kaynak, "requirements.txt")
    if os.path.isfile(gereksinim):
        asama("Bağımlılıklar kuruluyor…", 92)
        _pip(vpy, ["install", "--quiet", "-r", gereksinim])
    asama("Doğrulanıyor…", 97)
    kurulan = _venv_surum(vpy)
    if kurulan != hedef_surum:
        raise GuncellemeHatasi(
            f"Doğrulama başarısız: {kurulan} ≠ {hedef_surum}"
        )
    asama("Güncelleme tamamlandı", 100)
    return kurulan


def yeniden_baslat() -> None:
    """Uygulamayı yeniden başlatır (yeni sürüm etkinleşir)."""
    # -m postacim: paket olarak çalıştırılmalı (göreli içe aktarım gerekli)
    os.execv(sys.executable, [sys.executable, "-m", "postacim"])


def otomatik_izin(ayarlar) -> bool:
    """Açılışta otomatik denetim yapılmalı mı?

    - Kullanıcı tercihi (`guncelleme_otomatik`, varsayılan açık)
    - Ortam değişkeni `POSTACIM_GUNCELLEME=0` denetimi kapatır (=1 açar)
    - Kaynaktan (geliştirme) çalışırken otomatik denetim yapılmaz:
      geliştiricinin .venv'sine sessiz kurulum istenmez.
    """
    ortam = os.environ.get("POSTACIM_GUNCELLEME")
    if ortam is not None:
        return ortam not in ("", "0", "no", "false")
    if not bool(ayarlar.al("guncelleme_otomatik", True)):
        return False
    calisma_yolu = os.path.normpath(os.path.dirname(sys.executable))
    return calisma_yolu.endswith(os.path.join("share", "postacim", "venv", "bin"))
