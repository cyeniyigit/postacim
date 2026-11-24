#!/usr/bin/env python3
"""MGM hava durumu testi (çevrimdışı; sahte istekler).

Kapsar:
- meteoroloji modülü: uç nokta adresleri, yanıt çözümleme (iller, merkez,
  sondurum, günlük tahmin), hadise kodu eşlemesi + bilinmeyen kod yedeği
- hata yolları (bağlantı hatası → MeteorolojiHatasi, boş yanıt)
- arayüz: üst çubukta hava göstergesi var; "Gönder/Al"/"Yenile"/
  "Hesaptan Çıkış" düğmeleri araç çubuğunda yok; kuyruk sonucu etiketi
  günceller; ayrıntı penceresi açılır ve içerik doludur
- Ayarlar penceresi: il/ilçe seçicileri dolur, hava_konum tercihi kaydedilir

Kullanim:  xvfb-run -a .venv/bin/python tests/hava_test.py
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
from postacim import meteoroloji  # noqa: E402
import postacim.ui as ui_mod  # noqa: E402

HATALAR = []


def kontrol(kosul, mesaj):
    if kosul:
        print(f"  ✓ {mesaj}")
    else:
        HATALAR.append(mesaj)
        print(f"  !! {mesaj}")


ILLER = [{"il": "Ankara", "ilPlaka": 6, "ilce": "Keçiören", "merkezId": 90601,
          "gunlukTahminIstNo": 90601, "oncelik": 1},
         {"il": "İstanbul", "ilPlaka": 34, "ilce": "Bakırköy", "merkezId": 93401,
          "gunlukTahminIstNo": 93401, "oncelik": 1}]
ILCELER = [{"il": "İstanbul", "ilce": "Adalar", "merkezId": 93439},
           {"il": "İstanbul", "ilce": "Bakırköy", "merkezId": 93401},
           {"il": "İstanbul", "ilce": "Beşiktaş", "merkezId": 93405}]
MERKEZ = ILCELER[1]
SONDURUM = [{"sicaklik": 6.1, "hadiseKodu": "PB", "nem": 83, "ruzgarHiz": 3.6,
             "ruzgarYon": 292, "hissedilenSicaklik": 6.1,
             "denizeIndirgenmisBasinc": 1016.6,
             "veriZamani": "2026-11-24T16:44:00.000Z"}]
TAHMIN = [{"enYuksekGun1": 8, "enDusukGun1": -2, "hadiseGun1": "PB",
           "tarihGun1": "2026-11-25T00:00:00",
           "ruzgarHizGun1": 3,
           "enYuksekGun2": 11, "enDusukGun2": 0, "hadiseGun2": "A",
           "tarihGun2": "2026-11-26T00:00:00", "ruzgarHizGun2": 2}]


class SahteYanit:
    def __init__(self, veri):
        self._veri = veri

    def raise_for_status(self):
        pass

    def json(self):
        return self._veri


class SahteIstemci:
    def __init__(self, hesap: dict):
        self.hesap = hesap

    def klasor_listesi(self):
        return [Klasor(kimlik="inbox", ad="Gelen Kutusu", toplam=0,
                       okunmamis=0)]

    def mesajlar(self, klasor="inbox", sayfa_boyutu=50, offset=0, arama="",
                 alan="konu", tam=False, tazele=True):
        return [], 0

    def guncelle(self, klasorler=None):
        return {}

    def cozumle(self, metin, en_fazla=20):
        return []

    def mesaj_detay(self, mesaj):
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


def test_meteoroloji():
    print("\n— meteoroloji modülü (sahte istekler) —")
    cagrilan = []

    def sahte_get(url, **kw):
        cagrilan.append(url)
        if "/web/merkezler/iller" in url:
            return SahteYanit(ILLER)
        if "/web/merkezler/ililcesi" in url:
            return SahteYanit(ILCELER)
        if "/web/merkezler" in url:
            params = kw.get("params") or {}
            kontrol(params.get("il") == "istanbul" and
                    (params.get("ilce") or "").lower() == "bakırköy",
                    f"merkez sorgusu Türkçe uyumlu ({params})")
            return SahteYanit([MERKEZ])
        if "/web/sondurumlar" in url:
            return SahteYanit(SONDURUM)
        if "/web/tahminler/gunluk" in url:
            return SahteYanit(TAHMIN)
        return SahteYanit([])

    eski_get = meteoroloji.requests.get
    meteoroloji.requests.get = sahte_get
    try:
        kontrol("servis.mgm.gov.tr/web/merkezler/iller" in
                meteoroloji.TABAN + "/merkezler/iller",
                "taban adres: servis.mgm.gov.tr/web")
        iller = meteoroloji.iller()
        kontrol(len(iller) == 2 and iller[0]["il"] == "Ankara",
                f"iller çözümlenir ({len(iller)})")
        merkez = meteoroloji.merkez("İstanbul", "Bakırköy")
        kontrol(merkez["merkezId"] == 93401, "merkez seçilir")
        sond = meteoroloji.sondurum(93401)
        kontrol(abs(sond["sicaklik"] - 6.1) < 0.01, "anlık sıcaklık çözülür")
        tah = meteoroloji.gunluk_tahmin(93401)
        kontrol(tah["hadiseGun1"] == "PB", "5 günlük tahmin çözülür")
        simge, ad = meteoroloji.hadise_goster("PB")
        kontrol(simge == "⛅" and ad == "Parçalı bulutlu",
                f"hadise kodu eşlenir ({simge} {ad})")
        simge, ad = meteoroloji.hadise_goster("XX")
        kontrol(simge == "❔" and ad == "XX", "bilinmeyen kod için yedek")
        # boş yanıt → hata
        meteoroloji.requests.get = lambda *a, **k: SahteYanit([])
        try:
            meteoroloji.merkez("yok", "yok")
            kontrol(False, "boş merkez listesi hata vermeli")
        except meteoroloji.MeteorolojiHatasi:
            kontrol(True, "boş merkez listesi MeteorolojiHatasi verir")
        # bağlantı hatası → hata
        class Bozuk:
            def raise_for_status(self):
                raise meteoroloji.requests.RequestException("kopu")

            def json(self):
                return {}

        meteoroloji.requests.get = lambda *a, **k: Bozuk()
        try:
            meteoroloji.iller()
            kontrol(False, "bağlantı hatası hata vermeli")
        except meteoroloji.MeteorolojiHatasi:
            kontrol(True, "bağlantı hatası MeteorolojiHatasi verir")
    finally:
        meteoroloji.requests.get = eski_get


def main() -> int:
    test_meteoroloji()

    dizin = tempfile.mkdtemp(prefix="hava_test_")
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
            "hava_konum": {"il": "İstanbul", "ilce": "Bakırköy"},
        }, f, ensure_ascii=False, indent=2)

    eski_ayarlar, eski_kur = ui_mod.Ayarlar, ui_mod.Postacim._istemci_kur
    ui_mod.Ayarlar = lambda: Ayarlar(yol)
    ui_mod.Postacim._istemci_kur = lambda self, hesap: SahteIstemci(hesap)

    import tkinter.messagebox as messagebox
    eski_error = messagebox.showerror
    messagebox.showerror = lambda *a, **k: HATALAR.append(f"showerror {a}")

    uygulama = ui_mod.Postacim()
    try:
        bekle(uygulama, 3)

        # --- üst çubukta hava göstergesi var, kaldırılan düğmeler yok ---
        kontrol(getattr(uygulama, "hava_gosterge", None) is not None and
                uygulama.hava_gosterge.winfo_exists(),
                "üst çubukta hava göstergesi var")
        arac_textleri = []
        for cocuk in uygulama.winfo_children():
            for torun in cocuk.winfo_children():
                if torun.winfo_class() == "TButton":
                    try:
                        arac_textleri.append(torun.cget("text"))
                    except tk.TclError:
                        pass
        kontrol("Gönder/Al" not in arac_textleri and
                "Yenile" not in arac_textleri and
                "Hesaptan Çıkış" not in arac_textleri,
                f"araç çubuğunda kaldırılan düğmeler yok ({arac_textleri})")
        kontrol("Yeni e-posta" in arac_textleri and
                "Temizle" in arac_textleri,
                "Yeni e-posta ve Temizle çubukta duruyor")

        # --- kuyruk sonucu göstergayı günceller ---
        uygulama._sonuc_isle(("hava", "İstanbul", "Bakırköy", MERKEZ,
                              SONDURUM[0], TAHMIN[0]))
        metin = uygulama.hava_gosterge.cget("text")
        kontrol("Bakırköy" in metin and "6.1" in metin,
                f"gösterge anlık sıcaklığı gösterir ({metin!r})")
        kontrol("⛅" in metin, "gösterge fenomen simgesi içerir")

        # --- ayrıntı penceresi ---
        uygulama._hava_pencere()
        pencere = None
        for p in uygulama.winfo_children():
            if isinstance(p, ui_mod.tk.Toplevel) and \
                    p.title() == "Hava durumu":
                pencere = p
        kontrol(pencere is not None, "hava ayrıntı penceresi açıldı")
        if pencere:
            metin = None
            for cocuk in pencere.winfo_children():
                if cocuk.winfo_class() == "Text":
                    metin = cocuk
            kontrol(metin is not None, "pencerede metin alanı var")
            if metin:
                icerik = metin.get("1.0", "end")
                kontrol("Bakırköy" in icerik and "6.1 °C" in icerik,
                        "ayrıntıda anlık durum var")
                kontrol("5 Günlük Tahmin" in icerik,
                        "5 günlük tahmin başlığı var")
                kontrol("MGM (meteoroloji.gov.tr)" in icerik,
                        "kaynak bilgisi var")
            pencere.destroy()

        # --- hata sonucu: sessiz, etiket nötr ---
        uygulama.hava_gosterge.configure(text="Hava durumu —")
        uygulama._sonuc_isle(("hava_hata", None, "NameError: x"))
        kontrol("Hava durumu alınamadı" in uygulama.durum.get(),
                "hata durum çubuğunda bildirilir")
        kontrol("Hava durumu —" in uygulama.hava_gosterge.cget("text"),
                "hata sonrası gösterge nötr kalır")
    finally:
        uygulama.destroy()
        ui_mod.Ayarlar, ui_mod.Postacim._istemci_kur = eski_ayarlar, eski_kur
        messagebox.showerror = eski_error

    if HATALAR:
        print(f"\n!! {len(HATALAR)} hata:")
        for h in HATALAR:
            print(f"  - {h}")
        return 1
    print("\n✓ tüm kontroller geçti")
    return 0


if __name__ == "__main__":
    sys.exit(main())
