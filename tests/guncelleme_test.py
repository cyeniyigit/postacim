#!/usr/bin/env python3
"""Otomatik güncelleme modülü testi (çevrimdışı; GitHub'a bağlanmaz).

Kapsar:
- Sürüm karşılaştırma (daha_yeni / _surum_parcala)
- son_surum: API yanıtı, API düşer → yedek raw dosya, ikisi de olmaz → (None, None)
- indir: akış + ilerleme yüzdesi + hata
- _arsiv_ayikla: tar.gz içinden kaynak kökü, paket yoksa hata
- kur: aşama ilerlemesi + sahte venv python ile pip çağrıları + doğrulama
- otomatik_izin: tercih / ortam değişkeni / geliştirme ortamı kuralları

Kullanim:  .venv/bin/python tests/guncelleme_test.py
"""
from __future__ import annotations

import io
import json
import os
import sys
import tarfile
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import postacim.guncelleme as g  # noqa: E402

HATALAR = []


def kontrol(kosul, mesaj):
    if kosul:
        print(f"  ✓ {mesaj}")
    else:
        HATALAR.append(mesaj)
        print(f"  !! {mesaj}")


def main() -> int:
    # --- sürüm karşılaştırma ---
    kontrol(g.daha_yeni("0.1.17", "0.1.16"), "0.1.17 > 0.1.16")
    kontrol(g.daha_yeni("0.2", "0.1.9"), "0.2 > 0.1.9")
    kontrol(not g.daha_yeni("0.1.16", "0.1.16"), "aynı sürüm değil")
    kontrol(not g.daha_yeni("0.1.15", "0.1.16"), "geri sürüm değil")
    kontrol(g.daha_yeni("v0.1.17", "0.1.16"), "'v' öneki atılır")
    kontrol(g._surum_parcala("0.1.16") == (0, 1, 16), "parçalama doğru")

    # --- son_surum: API yanıtı ---
    import requests

    class Yanit:
        def __init__(self, durum=200, json_=None, metin=""):
            self.status_code = durum
            self._json = json_ or {}
            self.text = metin

        def json(self):
            return self._json

        @property
        def ok(self):
            return self.status_code == 200

    def yanitla(siralama):
        siralama = list(siralama)

        def get(*a, **k):
            if not siralama:
                raise requests.RequestException("bağlantı yok")
            return siralama.pop(0)
        return get

    eski_get = requests.get
    try:
        requests.get = yanitla([
            Yanit(json_={"tag_name": "v0.1.17",
                         "tarball_url": "https://ornek/x.tar.gz"})
        ])
        surum, adres = g.son_surum()
        kontrol(surum == "0.1.17", f"API sürümü okunur ({surum})")
        kontrol(adres == "https://ornek/x.tar.gz", "API arşiv adresi")

        # API boş tag_name → yedek raw
        requests.get = yanitla([
            Yanit(json_={}),
            Yanit(metin='__version__ = "0.1.18"'),
        ])
        surum, adres = g.son_surum()
        kontrol(surum == "0.1.18", f"yedek raw sürümü ({surum})")
        kontrol(adres == g.ARSIV_ADRESI, "yedekte dal arşivi")

        # Ağ yok → (None, None)
        def hata(*a, **k):
            raise requests.RequestException("yok")
        requests.get = hata
        kontrol(g.son_surum() == (None, None), "ağ yokta (None, None)")
    finally:
        requests.get = eski_get

    # --- indir: ilerleme + hata ---
    def get_arsiv(*a, **k):
        class Akis:
            headers = {"Content-Length": "10"}

            def raise_for_status(self):
                pass

            def iter_content(self, boyut):
                yield b"12345"
                yield b"67890"
        return Akis()

    eski_get = requests.get
    try:
        requests.get = get_arsiv
        gecici = tempfile.mkdtemp(prefix="guncelleme-test-")
        sayac = {"yuzde": None}

        def ilerleme(y, t):
            sayac["yuzde"] = int(y * 100 / t)
        arsiv = g.indir("https://ornek/x.tar.gz", gecici, ilerleme=ilerleme)
        kontrol(os.path.isfile(arsiv) and
                os.path.getsize(arsiv) == 10,
                f"indirilen arşiv boyutu ({os.path.getsize(arsiv)})")
        kontrol(sayac["yuzde"] == 100, f"ilerleme %100 ({sayac['yuzde']})")

        def get_kirik(*a, **k):
            raise requests.RequestException("bağlantı kesildi")
        requests.get = get_kirik
        try:
            g.indir("https://ornek/x.tar.gz", gecici)
            kontrol(False, "bağlantı hatasında GuncellemeHatasi")
        except g.GuncellemeHatasi:
            kontrol(True, "bağlantı hatasında GuncellemeHatasi")
    finally:
        requests.get = eski_get

    # --- _arsiv_ayikla ---
    gecici = tempfile.mkdtemp(prefix="guncelleme-test-")
    kaynak = os.path.join(gecici, "kaynak")
    os.makedirs(os.path.join(kaynak, "postacim"))
    with open(os.path.join(kaynak, "postacim", "__init__.py"), "w") as f:
        f.write('__version__ = "9.9.9"\n')
    with open(os.path.join(kaynak, "requirements.txt"), "w") as f:
        f.write("requests\n")
    arsiv_yolu = os.path.join(gecici, "paket.tar.gz")
    with tarfile.open(arsiv_yolu, "w:gz") as tar:
        tar.add(kaynak, arcname="postacim-main")
    kok = g._arsiv_ayikla(arsiv_yolu)
    kontrol(os.path.isfile(os.path.join(kok, "postacim", "__init__.py")),
            "ayıklanan kaynak kökü bulunur")

    bos_arsiv = os.path.join(gecici, "bos.tar.gz")
    with tarfile.open(bos_arsiv, "w:gz") as tar:
        bilgi = io.BytesIO(b"bos")
        bilgi_tar = tarfile.TarInfo("bos.txt")
        bilgi_tar.size = len(b"bos")
        tar.addfile(bilgi_tar, bilgi)
    try:
        g._arsiv_ayikla(bos_arsiv)
        kontrol(False, "paketsiz arşivde hata")
    except g.GuncellemeHatasi:
        kontrol(True, "paketsiz arşivde GuncellemeHatasi")

    # --- kur: sahte venv python ile ---
    sahte_venv = os.path.join(gecici, "sahte-venv")
    os.makedirs(sahte_venv)
    vpy = os.path.join(sahte_venv, "python")
    with open(vpy, "w") as f:
        f.write("""#!/usr/bin/env bash
if [ "$1" = "-m" ] && [ "$2" = "pip" ]; then
    shift 2
    echo "$@" >> "$PWD/pip-cagrilar.log"
    exit 0
fi
if [ "$1" = "-c" ]; then
    echo 9.9.9
    exit 0
fi
exit 1
""")
    os.chmod(vpy, 0o755)
    asamalar = []

    def ilerleme(ad, yuzde):
        asamalar.append((ad, yuzde))

    kurulan = g.kur(arsiv_yolu, "9.9.9", ilerleme=ilerleme, venv_python=vpy)
    kontrol(kurulan == "9.9.9", f"kurulan sürüm ({kurulan})")
    kontrol(asamalar[0][0] == "Arşiv ayıklanıyor…" and
            asamalar[-1] == ("Güncelleme tamamlandı", 100),
            f"aşama ilerlemesi ({asamalar[0][0]} → {asamalar[-1]})")
    kontrol(all(ad for ad, _ in asamalar), "her aşamanın adı var")
    yuzdeler = [y for _, y in asamalar]
    kontrol(yuzdeler == sorted(yuzdeler), "yüzde artan sırada")
    kayit = os.path.join(os.getcwd(), "pip-cagrilar.log")
    kontrol(os.path.isfile(kayit), f"pip çağrıları yapıldı ({kayit})")
    with open(kayit) as f:
        satirlar = f.read()
    kontrol("--no-deps" in satirlar and "requirements" in satirlar,
            "paket + gereksinim kurulumu")

    # Doğrulama tutmazsa hata
    with open(vpy, "w") as f:
        f.write("""#!/usr/bin/env bash
if [ "$1" = "-m" ]; then exit 0; fi
echo 9.9.8
""")
    os.chmod(vpy, 0o755)
    try:
        g.kur(arsiv_yolu, "9.9.9", venv_python=vpy)
        kontrol(False, "sürüm uyuşmazlığında hata")
    except g.GuncellemeHatasi:
        kontrol(True, "sürüm uyuşmazlığında GuncellemeHatasi")

    # --- otomatik_izin ---
    class SahteAyarlar:
        def __init__(self, deger):
            self.deger = deger

        def al(self, anahtar, varsayilan=None):
            if anahtar == "guncelleme_otomatik":
                return self.deger
            return varsayilan

    os.environ.pop("POSTACIM_GUNCELLEME", None)
    kontrol(g.otomatik_izin(SahteAyarlar(True)) is False,
            "geliştirme (.venv) ortamında otomatik denetim yok")
    kontrol(g.otomatik_izin(SahteAyarlar(False)) is False,
            "tercih kapalıysa denetim yok")
    kontrol(g.mevcut_surum(), f"mevcut sürüm okunur ({g.mevcut_surum()})")

    if HATALAR:
        print(f"\n!! {len(HATALAR)} hata:")
        for h in HATALAR:
            print(f"  - {h}")
        return 1
    print("\n✓ tüm kontroller geçti")
    return 0


if __name__ == "__main__":
    sys.exit(main())
