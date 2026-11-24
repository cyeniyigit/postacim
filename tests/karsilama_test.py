#!/usr/bin/env python3
"""Karşılama penceresi + otomatik güncelleme arayüz testi (çevrimdışı).

Kapsar:
- Açılışta karşılama penceresi: logo, ad, sürüm, ekran ortası
- Çift monitör: uygulamanın çalıştığı monitöre ortalama (xrandr çözümü)
- Durum metni + ilerleme çubuğu (%)
- "guncelleme_durum" kuyruk sonucu pencereyi günceller
- "guncelleme_bitti" → %100 + Yeniden Başlat/Kapat düğmeleri
- "guncelleme_hata" → hata metni
- İlk klasör listesi gelince pencere kapanır (güncelleme sürerken beklemez)
- Elle denetim akışı (uyarılı sonuç, sahte guncelleme modülü ile)

Kullanim:  xvfb-run -a .venv/bin/python tests/karsilama_test.py
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import time

os.environ["POSTACIM_GUNCELLEME"] = "0"  # gerçek ağ denetimi asla başlamasın

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from postacim.config import Ayarlar  # noqa: E402
from postacim.ews import Klasor, Mesaj  # noqa: E402
import postacim.ui as ui_mod  # noqa: E402

HATALAR = []


def kontrol(kosul, mesaj):
    if kosul:
        print(f"  ✓ {mesaj}")
    else:
        HATALAR.append(mesaj)
        print(f"  !! {mesaj}")


class SahteIstemci:
    def __init__(self, hesap: dict):
        self.hesap = hesap

    def klasor_listesi(self):
        return [
            Klasor(kimlik="inbox", ad="Gelen Kutusu", toplam=2, okunmamis=1),
            Klasor(kimlik="sentitems", ad="Gönderilmiş", toplam=0, okunmamis=0),
            Klasor(kimlik="drafts", ad="Taslaklar", toplam=0, okunmamis=0),
        ]

    def mesajlar(self, klasor="inbox", sayfa_boyutu=50, offset=0, arama="",
                 alan="konu", tam=False, tazele=True):
        ms = [
            Mesaj(item_id="m1", konu="deneme",
                  gonderen="gonderen@ornek.gov.tr", tarih="24.11.2026 10:00",
                  okundu=True, klasor=klasor, tariham="2026-11-24T10:00:00"),
        ]
        return ms[offset:offset + sayfa_boyutu], len(ms)

    def guncelle(self, klasorler=None):
        return {}

    def cozumle(self, metin, en_fazla=20):
        return []

    def mesaj_detay(self, mesaj):
        mesaj.govde = "Gövde (sahte)"
        return mesaj

    def okundu_isaretle(self, mesaj, okundu=True):
        mesaj.okundu = okundu

    def tasi(self, mesaj, hedef="deleteditems"):
        pass

    def mesaj_mime(self, mesaj_id):
        return b"From: x\r\n\r\n"


def bekle(uygulama, saniye):
    bitis = time.time() + saniye
    while time.time() < bitis:
        uygulama.update()
        time.sleep(0.05)


def main() -> int:
    dizin = tempfile.mkdtemp(prefix="karsilama_test_")
    yol = os.path.join(dizin, "hesap.json")
    with open(yol, "w", encoding="utf-8") as f:
        json.dump({
            "hesaplar": [
                {"id": "kurum001", "ad": "Kurum", "tur": "ews",
                 "sunucu": "mail.ornek.gov.tr", "kullanici": "KURUM\\kisi",
                 "parola": "sifre", "yontem": "ntlm", "son_klasor": "inbox"},
            ],
            "aktif": "kurum001",
            "tema": "light", "otomatik_yenile": 0,
        }, f, ensure_ascii=False, indent=2)

    eski_ayarlar, eski_kur = ui_mod.Ayarlar, ui_mod.Postacim._istemci_kur
    ui_mod.Ayarlar = lambda: Ayarlar(yol)
    ui_mod.Postacim._istemci_kur = lambda self, hesap: SahteIstemci(hesap)

    import tkinter.messagebox as messagebox
    eski_info = messagebox.showinfo
    eski_soru = messagebox.askyesno
    bilgiler: list = []
    sorular: list = []
    messagebox.showinfo = lambda *a, **k: bilgiler.append(a)
    messagebox.askyesno = lambda *a, **k: sorular.append(a) or False

    uygulama = ui_mod.Postacim()
    try:
        # --- karşılama penceresi açılışta var ---
        kontrol(getattr(uygulama, "karsilama", None) is not None and
                uygulama.karsilama.winfo_exists(),
                "karşılama penceresi açık")
        if getattr(uygulama, "karsilama", None) and \
                uygulama.karsilama.winfo_exists():
            k = uygulama.karsilama
            kontrol(bool(getattr(k, "_logo", None)), "logo görseli yüklü")
            kontrol("Kurum" not in k.durum_etiket.cget("text") and
                    k.durum_etiket.cget("text") != "",
                    f"durum metni var ({k.durum_etiket.cget('text')!r})")
            beklenen = f"sürüm {ui_mod.SURUM}"
            etiketler = [c for c in k.winfo_children()[0].winfo_children()
                         if c.winfo_class() == "Label"]
            kontrol(any(c.cget("text") == beklenen for c in etiketler),
                    f"sürüm etiketi ({beklenen})")
            geo = k.geometry()
            kontrol("+" in geo, f"ekran ortası konumu ({geo})")

            # --- çift monitör: doğru monitöre ortalama ---
            ornek = ("DP-1 connected primary 1920x1080+0+0 (normal) 527mm x 296mm\n"
                     "HDMI-0 connected 1920x1080+1920+0 (normal) 527mm x 296mm\n"
                     "eDP-1 disconnected (normal)\n")
            kontrol(ui_mod._xrandr_coz(ornek) ==
                    [(0, 0, 1920, 1080), (1920, 0, 1920, 1080)],
                    "xrandr çözümlemesi iki monitörü buldu")
            kontrol(ui_mod._xrandr_coz("") == [], "boş xrandr çıktısı → []")
            kontrol(ui_mod._monit_sec(
                [(0, 0, 1920, 1080), (1920, 0, 1920, 1080)], 2500, 300)
                == (1920, 0, 1920, 1080), "nokta sağ monitörde seçildi")
            kontrol(ui_mod._monit_sec(
                [(0, 0, 1920, 1080)], 2500, 300) is None,
                "monitör dışındaki nokta None")
            eski_hedef = k._hedef_monit_or
            k._hedef_monit_or = lambda: (1920, 0, 1920, 1080)
            k._ortala()
            k._hedef_monit_or = eski_hedef
            geo = k.geometry()
            try:
                konum_x = int(geo.split("+")[1])
            except (IndexError, ValueError):
                konum_x = -1
            kontrol(konum_x >= 1920,
                    f"sağ monitöre ortalandı ({geo})")

        # --- ilk klasör listesi gelince pencere kapanır ---
        bekle(uygulama, 3)
        kontrol(len(uygulama.mesajlar) == 1, "mesajlar yüklendi")
        kontrol(getattr(uygulama, "karsilama", None) is None or
                not uygulama.karsilama.winfo_exists(),
                "uygulama hazır olunca karşılama kapandı")

        # --- durum sonucu pencereyi günceller ---
        uygulama.karsilama = ui_mod.Karsilama(uygulama)
        uygulama._sonuc_isle(
            ("guncelleme_durum", "0.1.17 indiriliyor… %42", 42))
        kontrol("0.1.17 indiriliyor" in
                uygulama.karsilama.durum_etiket.cget("text"),
                "durum metni güncellendi")
        kontrol(abs(uygulama.karsilama.cubuk.cget("value") - 42) < 0.1,
                f"çubuk %42 ({uygulama.karsilama.cubuk.cget('value')})")
        kontrol("0.1.17 indiriliyor" in uygulama.durum.get(),
                "durum çubuğu da güncellendi")

        # --- bitti: %100 + düğmeler ---
        uygulama._sonuc_isle(("guncelleme_bitti", "0.1.17"))
        kontrol(abs(uygulama.karsilama.cubuk.cget("value") - 100) < 0.1,
                "bittiğinde çubuk %100")
        dugmeler = [c.cget("text") for c in
                    uygulama.karsilama.dugme_cubugu.winfo_children()]
        kontrol("Yeniden Başlat" in dugmeler and "Kapat" in dugmeler,
                f"bittiğinde düğmeler ({dugmeler})")
        kontrol(uygulama._guncelleme_kurulu == "0.1.17",
                "kurulan sürüm kaydedildi")
        uygulama.karsilama.kapat()

        # kurulu sürüm varken ilk klasör listesi pencereyi yeniden açmaz
        uygulama.karsilama = ui_mod.Karsilama(uygulama)
        uygulama.karsilama.kapat()
        kontrol(True, "pencere kapatma güvenli")

        # --- hata sonucu ---
        uygulama.karsilama = ui_mod.Karsilama(uygulama)
        uygulama._sonuc_isle(("guncelleme_hata", "bağlantı kesildi"))
        kontrol("bağlantı kesildi" in
                uygulama.karsilama.durum_etiket.cget("text"),
                "hata metni pencerede")
        uygulama.karsilama.kapat()
        uygulama._guncelleme_kurulu = None

        # --- elle denetim akışı (sahte modül) ---
        eski_g = ui_mod.guncelleme
        sahte = type("SahteG", (), {})()

        def sahte_son():
            return ("0.1.17", "https://ornek/x.tar.gz")
        sahte.son_surum = sahte_son
        sahte.mevcut_surum = lambda: "0.1.16"
        sahte.daha_yeni = eski_g.daha_yeni
        sahte.GuncellemeHatasi = eski_g.GuncellemeHatasi
        sahte.indir = lambda adres, dizin, ilerleme=None, **k: \
            os.path.join(dizin, "sahte.tar.gz")
        kurulanlar = []
        sahte.kur = lambda arsiv, surum, ilerleme=None, **k: \
            kurulanlar.append(surum) or surum
        sahte.otomatik_izin = eski_g.otomatik_izin
        ui_mod.guncelleme = sahte

        uygulama._guncelleme_sureci = False
        islem = uygulama._guncelleme_denetle(True)
        kontrol(islem[0] in ("uyari", "guncelleme_bitti"),
                f"denetim sonucu döndü ({islem[0]})")
        # Sonucu kuyruktan işlet (pencere kapalı → askyesno yolu)
        uygulama.is_kuyrugu.put(("ok", islem))
        uygulama.update()
        uygulama._kuyruk_yokla()
        kontrol(kurulanlar == ["0.1.17"], f"sahte kurulum çalıştı ({kurulanlar})")
        kontrol(len(sorular) == 1 and "Yeniden başlatılsın" in sorular[0][1],
                f"pencere kapalıysa yeniden başlatma sorusu ({sorular})")
        ui_mod.guncelleme = eski_g
    finally:
        uygulama.destroy()
        ui_mod.Ayarlar, ui_mod.Postacim._istemci_kur = eski_ayarlar, eski_kur
        messagebox.showinfo = eski_info
        messagebox.askyesno = eski_soru

    if HATALAR:
        print(f"\n!! {len(HATALAR)} hata:")
        for h in HATALAR:
            print(f"  - {h}")
        return 1
    print("\n✓ tüm kontroller geçti")
    return 0


if __name__ == "__main__":
    sys.exit(main())
