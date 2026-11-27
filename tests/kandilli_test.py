#!/usr/bin/env python3
"""Kandilli deprem modülü + üst çubuk paneli testi (çevrimdışı).

Kapsar:
- kandilli modülü: satır ayrıştırma (ML→Mw→MD yedeği, tarih süzgeği,
  yer ayırma), konum anahtarı, konum istatistikleri, windows-1254 çözümleme
  + virgül→nokta (sahte istekle)
- arayüz: üst çubukta deprem paneli (hava panelinin solunda); kuyruk
  sonucu paneli günceller (en yeni deprem — eşik yok — / "deprem yok"
  boş hâlleri);
  ayrıntı penceresi içeriği (özet + son deprem + konumlar + ≥4.0 listesi);
  hata sonucu paneli bozmaz; ağ hatası
  giriş penceresi açmaz ("deprem_hata")

Kullanim:  xvfb-run -a .venv/bin/python tests/kandilli_test.py
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from datetime import datetime

os.environ["POSTACIM_GUNCELLEME"] = "0"  # gerçek ağ denetimi asla başlamasın

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from postacim.config import Ayarlar  # noqa: E402
from postacim.ews import Klasor  # noqa: E402
from postacim import kandilli  # noqa: E402
import postacim.ui as ui_mod  # noqa: E402

HATALAR = []


def kontrol(kosul, mesaj):
    if kosul:
        print(f"  ✓ {mesaj}")
    else:
        HATALAR.append(mesaj)
        print(f"  !! {mesaj}")


BUGUN = "2026.11.26"

SAYFA = """
<html><body><pre>
..........TÜRKİYE VE YAKIN ÇEVRESİNDEKİ SON DEPREMLER..........
Tarih      Saat      Enlem(N)  Boylam(E) Derinlik(km)  MD   ML   Mw    Yer
---------- --------  --------  -------   ----------    ------------
2026.11.26 20:38:53  40.2970   34.3327        7.5      -.-  1.8  -.-   IKIZLI-SUNGURLU (CORUM)                           İlksel
2026.11.26 19:19:42  37.1058   27.8715       12.9      -.-  4.3  -.-   KIZILKOY-MILAS (MUGLA)                            İlksel
2026.11.26 18:19:42  37.1058   27.8715       12.9      -.-  2.7  -.-   KIZILKOY-MILAS (MUGLA)                            İlksel
2026.11.26 17:19:42  37.1058   27.8715       12.9      -.-  2.5  -.-   KIZILKOY-MILAS (MUGLA)                            İlksel
2026.11.26 15:19:42  36.1058   27.8715       12.9      -.-  -.-  5.2   MARMARIS (MUGLA)                                  Revize
2026.11.26 09:19:42  39.1058   27.8715        9.1      2.1  -.-  -.-   KIZILKOY-(MUGLA)                                  İlksel
2026.11.26 08:19:42  39.1058   27.8715        9.1      -.-  11.5 -.-   ABARTI-YER (YOK)                                  İlksel
2026.11.25 23:19:42  39.1058   27.8715        9.1      -.-  3.9  -.-   DUNLUK-YER (ANKARA)                               İlksel
</pre></body></html>
"""


class SahteYanit:
    def __init__(self, icerik: bytes):
        self.content = icerik

    def raise_for_status(self):
        pass


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


def panel_simgesi(uygulama):
    """deprem_baslik ikonunun Tk adını döndürür (ttk cget demet verebilir)."""
    deger = uygulama.deprem_baslik.cget("image")
    if isinstance(deger, (tuple, list)):
        deger = deger[0] if deger else ""
    return str(deger)


def ayrinti_icerigi(uygulama):
    """Ayrıntı penceresini açar, metin içeriğini döndürür ve pencereyi kapatır."""
    uygulama._deprem_pencere()
    pencere = None
    for p in uygulama.winfo_children():
        if isinstance(p, ui_mod.tk.Toplevel) and \
                p.title() == "Depremler — Kandilli":
            pencere = p
    if pencere is None:
        return None
    icerik = ""
    for cocuk in pencere.winfo_children():
        if cocuk.winfo_class() == "Text":
            icerik = cocuk.get("1.0", "end")
    pencere.destroy()
    return icerik


def test_kandilli():
    print("\n— kandilli modülü (çevrimdışı ayrıştırma) —")

    liste = kandilli.ayristir(SAYFA.replace(",", "."), bugun=BUGUN)
    kontrol(len(liste) == 6,
            f"bugünkü satırlar okunur, diğer gün ve ml>10 atılır ({len(liste)})")
    kontrol(liste[0].saat == "20:38:53" and liste[0].ml == 1.8,
            "ilk satır en yeni (ML okunur)")
    kontrol(liste[1].yer == "KIZILKOY-MILAS (MUGLA)",
            f"yer iki boşluğa göre kesilir ({liste[1].yer!r})")
    kontrol(any(d.ml == 5.2 and d.yer == "MARMARIS (MUGLA)" for d in liste),
            "ML '-.-' iken Mw okunur (5.2)")
    kontrol(any(d.ml == 2.1 and d.yer == "KIZILKOY-(MUGLA)" for d in liste),
            "ML/Mw '-.-' iken MD okunur (2.1)")
    kontrol(kandilli.ayristir("no pre block", bugun=BUGUN) == [],
            "pre bloğu yoksa boş liste")

    kontrol(kandilli.konum_anahtari("KIZILKOY-MILAS (MUGLA)") ==
            "MILAS (MUGLA)", "konum anahtarı: köy öneki düşer")
    kontrol(kandilli.konum_anahtari("KIZILKOY-(MUGLA)") == "MERKEZ (MUGLA)",
            "konum anahtarı: ad boşsa MERKEZ")
    kontrol(kandilli.konum_anahtari("AKDENIZ") == "AKDENIZ" and
            kandilli.konum_anahtari("ONIKI ADALAR (EGE DENIZI)") ==
            "ONIKI ADALAR (EGE DENIZI)",
            "konum anahtarı: tire yoksa yer olduğu gibi")

    istatistik = kandilli.konum_istatistikleri(liste)
    kontrol(istatistik[0]["ad"] == "MILAS (MUGLA)" and
            istatistik[0]["sayi"] == 3 and
            abs(istatistik[0]["en_buyuk"] - 4.3) < 0.01,
            f"en çok deprem olan konum ilk sırada ({istatistik[0]})")
    kontrol(istatistik[1]["ad"] == "MARMARIS (MUGLA)" and
            istatistik[1]["en_buyuk"] == 5.2,
            "aynı sayıda konum en yüksek ML'ye göre sıralanır")
    kontrol(len(kandilli.konum_istatistikleri(liste, en_cok=2)) == 2,
            "en_cok sınırı uygulanır")

    # windows-1254 + virgül→nokta depremler() içinde yapılır
    bugun_tarih = datetime.now().strftime("%Y.%m.%d")
    satir = (f"{bugun_tarih} 10:00:00  40,2970   34,3327        7,5      "
             f"-.-  4,1  -.-   TEST-YERI (IZMIR)                           İlksel")
    html = f"<html><pre>{satir}</pre></html>".encode("windows-1254")
    eski_get = kandilli.requests.get
    kandilli.requests.get = lambda *a, **k: SahteYanit(html)
    try:
        sonuc = kandilli.depremler()
        kontrol(len(sonuc) == 1 and abs(sonuc[0].ml - 4.1) < 0.01 and
                sonuc[0].yer == "TEST-YERI (IZMIR)",
                "depremler(): windows-1254 çözümü + virgül→nokta")
    finally:
        kandilli.requests.get = eski_get

    # ağ hatası istisna verir (ui _deprem_cek bunu deprem_hata'ya çevirir)
    def bozuk(*a, **k):
        raise kandilli.requests.ConnectionError("kopu")

    kandilli.requests.get = bozuk
    try:
        kandilli.depremler()
        kontrol(False, "bağlantı hatası istisna vermeli")
    except kandilli.requests.RequestException:
        kontrol(True, "bağlantı hatası RequestException verir")
    finally:
        kandilli.requests.get = eski_get


def main() -> int:
    test_kandilli()

    dizin = tempfile.mkdtemp(prefix="kandilli_test_")
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
    eski_error = messagebox.showerror
    messagebox.showerror = lambda *a, **k: HATALAR.append(f"showerror {a}")

    uygulama = None
    try:
        uygulama = ui_mod.Postacim()
        bekle(uygulama, 2)

        # --- panel var ve hava panelinin solunda ---
        kontrol(getattr(uygulama, "deprem_paneli", None) is not None and
                uygulama.deprem_paneli.winfo_exists(),
                "üst çubukta deprem paneli var")
        bekle(uygulama, 0.5)
        kontrol(uygulama.deprem_paneli.winfo_rootx() <
                uygulama.hava_paneli.winfo_rootx(),
                "deprem paneli hava panelinin solunda")

        # --- kuyruk sonucu: en yeni deprem gösterilir (eşik yok) ---
        liste = kandilli.ayristir(SAYFA.replace(",", "."), bugun=BUGUN)
        uygulama._sonuc_isle(("deprem", liste))
        metin = uygulama.deprem_baslik.cget("text")
        kontrol("1.8" in metin and "IKIZLI-SUNGURLU (COR..." in metin and
                "IKIZLI-SUNGURLU (CORUM)" not in metin and
                "🌍" not in metin and "⚠" not in metin,
                f"panel en yeni depremi kısaltılmış yerle gösterir "
                f"({metin!r})")
        kontrol(panel_simgesi(uygulama) ==
                str(uygulama.ikon["deprem_orta"]),
                "günün en büyüğü ML 5.2 → orta (uyarı) ikonu")
        ayrinti = uygulama.deprem_ayrinti.cget("text")
        kontrol("20:38" in ayrinti and "5.2" in ayrinti,
                f"ayrıntı satırı saat + en büyüğü verir ({ayrinti!r})")

        # --- ayrıntı penceresi ---
        uygulama._deprem_pencere()
        pencere = None
        for p in uygulama.winfo_children():
            if isinstance(p, ui_mod.tk.Toplevel) and \
                    p.title() == "Depremler — Kandilli":
                pencere = p
        kontrol(pencere is not None, "deprem ayrıntı penceresi açıldı")
        if pencere:
            metin = None
            for cocuk in pencere.winfo_children():
                if cocuk.winfo_class() == "Text":
                    metin = cocuk
            kontrol(metin is not None, "pencerede metin alanı var")
            if metin:
                icerik = metin.get("1.0", "end")
                kontrol("Kandilli Rasathanesi" in icerik and
                        "bugün 6 deprem" in icerik,
                        "ayrıntıda günlük özet var")
                kontrol("5.2" in icerik and "MARMARIS (MUGLA)" in icerik,
                        "ayrıntıda günün en büyüğü var")
                kontrol("MILAS (MUGLA)" in icerik and "3 deprem" in icerik,
                        "ayrıntıda konum istatistikleri var")
                kontrol("ML 4.0 ve üzeri" in icerik and "19:19" in icerik,
                        "ayrıntıda ≥4.0 listesi var")
                kontrol("Son deprem" in icerik and "20:38" in icerik and
                        "1.8" in icerik and
                        "IKIZLI-SUNGURLU (CORUM)" in icerik,
                        "ayrıntıda günün son (en yeni) depremi var")
                kontrol(icerik.index("Son deprem") < icerik.index("En çok deprem"),
                        "'Son deprem' bölümü konum listesinden önce")
                kontrol("KOERI" in icerik, "kaynak bilgisi var")
                resimler = metin.image_names()
                kontrol(len(resimler) >= 3,
                        f"pencerede süs ikonları gömülü ({len(resimler)})")
            pencere.destroy()

        # --- boş hâl: bugün ≥4.0 yokken de en yeni deprem görünür ---
        kucukler = [d for d in liste if d.ml < 4.0]
        uygulama._sonuc_isle(("deprem", kucukler))
        metin = uygulama.deprem_baslik.cget("text")
        kontrol("1.8" in metin and "IKIZLI-SUNGURLU (COR..." in metin,
                f"≥4.0 yokken panel en yeni küçük depremi gösterir "
                f"({metin!r})")
        kontrol(panel_simgesi(uygulama) ==
                str(uygulama.ikon["deprem_dusuk"]),
                "günün en büyüğü <5 → bilgi ikonu")
        kontrol("20:38" in uygulama.deprem_ayrinti.cget("text") and
                "2.7" in uygulama.deprem_ayrinti.cget("text"),
                "ayrıntıda saat + günün en büyüğü var")

        # --- ayrıntı penceresi: ≥4.0 yokken de son deprem görünür ---
        icerik = ayrinti_icerigi(uygulama)
        kontrol(icerik is not None and
                "Son deprem" in icerik and "20:38" in icerik and
                "1.8" in icerik,
                "≥4.0 yokken pencere yine de son depremi gösterir")

        uygulama._sonuc_isle(("deprem", []))
        kontrol("bugün kayıt yok" in uygulama.deprem_ayrinti.cget("text"),
                "boş listede 'kayıt yok'")
        kontrol("Deprem yok" in uygulama.deprem_baslik.cget("text"),
                "boş listede 'Deprem yok'")

        # --- ikon kuralı (eklenti): ML≥6 önemli, ML≥5 uyarı, aksi bilgi ---
        uygulama._sonuc_isle(("deprem", [kandilli.Deprem(
            tarih=BUGUN, saat="12:00:00", ml=6.1, yer="TEST-YERI (YOK)")]))
        kontrol(panel_simgesi(uygulama) ==
                str(uygulama.ikon["deprem_yuksek"]),
                "günün en büyüğü ML≥6 → önemli ikonu")
        uygulama._sonuc_isle(("deprem", [kandilli.Deprem(
            tarih=BUGUN, saat="12:00:00", ml=4.4, yer="TEST-YERI (YOK)")]))
        kontrol(panel_simgesi(uygulama) ==
                str(uygulama.ikon["deprem_dusuk"]) and
                "4.4" in uygulama.deprem_baslik.cget("text"),
                "günün en büyüğü ML<5 → bilgi ikonu, en yeni deprem metni")

        # --- yer adı kısaltması (DEPREM_YER_UZUNLUK = 20) ---
        uygulama._sonuc_isle(("deprem", [kandilli.Deprem(
            tarih=BUGUN, saat="12:00:00", ml=4.1,
            yer="ABCDEFGHIJ1234567890")]))
        metin = uygulama.deprem_baslik.cget("text")
        kontrol("ABCDEFGHIJ1234567890" in metin and "..." not in metin,
                f"20 karakterlik yer adı kırpılmaz ({metin!r})")
        uygulama._sonuc_isle(("deprem", [kandilli.Deprem(
            tarih=BUGUN, saat="12:00:00", ml=4.1,
            yer="ABCDEFGHIJ12345678901")]))
        metin = uygulama.deprem_baslik.cget("text")
        kontrol(metin.endswith("...") and
                "ABCDEFGHIJ12345678901" not in metin,
                f"21 karakterlik yer adı kırılıp '...' eklenir ({metin!r})")

        # --- veri hiç gelmeden pencere: bilgilendirme ---
        uygulama._deprem_veri = None
        uygulama._deprem_pencere()
        pencere = None
        for p in uygulama.winfo_children():
            if isinstance(p, ui_mod.tk.Toplevel) and \
                    p.title() == "Depremler — Kandilli":
                pencere = p
        kontrol(pencere is not None, "verisiz pencere de açılır")
        if pencere:
            icerik = ""
            for cocuk in pencere.winfo_children():
                if cocuk.winfo_class() == "Text":
                    icerik = cocuk.get("1.0", "end")
            kontrol("henüz alınamadı" in icerik,
                    "verisiz pencere bilgilendirir")
            pencere.destroy()

        # --- hata sonucu: panel korunur, durum çubuğunda bildirilir ---
        eski_panel = uygulama.deprem_baslik.cget("text")
        uygulama._sonuc_isle(("deprem_hata", None, "ValueError: x"))
        kontrol("Deprem verisi alınamadı" in uygulama.durum.get(),
                "hata durum çubuğunda bildirilir")
        kontrol(uygulama.deprem_baslik.cget("text") == eski_panel,
                "hata sonrası panel bozulmaz")

        # --- ağ hatası _deprem_cek'te yakalanır; giriş penceresi açılmaz ---
        def bozuk(*a, **k):
            raise ui_mod.requests.ConnectionError("kopu")

        eski_get = kandilli.requests.get
        kandilli.requests.get = bozuk
        try:
            sonuc = uygulama._deprem_cek()
            kontrol(sonuc[0] == "deprem_hata" and "ConnectionError" in sonuc[2],
                    f"ağ hatası deprem_hata turuna düşer ({sonuc[0]})")
        finally:
            kandilli.requests.get = eski_get
        kontrol(not any(isinstance(p, ui_mod.tk.Toplevel) and
                        p.title() == "Giriş" for p in uygulama.winfo_children()),
                "ağ hatası giriş penceresi açmaz")
    finally:
        if uygulama is not None:
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
