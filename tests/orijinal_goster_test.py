#!/usr/bin/env python3
""""Orijinali göster" arayüz testi (çevrimdışı; sahte istemci).

Kapsar:
- Gövde araç çubuğunda "Orijinali göster" düğmesi var
- Tıklayınca gövde alanı **orijinal (işlenmemiş) HTML** ile çizilir:
  resim yer tutucuları kalkar, cid resmi gövdeye gömülür,
  düğme "İşlenmiş hali göster" olur
- Tekrar tıklanınca işlenmiş gösterime dönülür (sunucuya gitmeden)
- Düz metin mesajda ayrım yapılmaz (durum bilgilendirir)
- Hazırlama hatasında düğme sıfırlanır, durum çubuğu bildirir
- Mesaj seçili değilken tıklama hata vermez, durum çubuğu bilgilendirir

Kullanim:  xvfb-run -a .venv/bin/python tests/orijinal_goster_test.py
"""
from __future__ import annotations

import base64
import io
import json
import os
import sys
import tempfile
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from postacim.config import Ayarlar  # noqa: E402
from postacim.ews import Klasor, Mesaj, Resim  # noqa: E402
import postacim.ui as ui_mod  # noqa: E402

HATALAR = []


def kontrol(kosul, mesaj):
    if kosul:
        print(f"  ✓ {mesaj}")
    else:
        HATALAR.append(mesaj)
        print(f"  !! {mesaj}")


def png_baytlari() -> bytes:
    from PIL import Image

    tampon = io.BytesIO()
    Image.new("RGB", (4, 4), (255, 0, 0)).save(tampon, "PNG")
    return tampon.getvalue()


CID_MIME = (
    b"From: a@b\r\nTo: c@d\r\nSubject: t\r\nMIME-Version: 1.0\r\n"
    b'Content-Type: multipart/related; boundary="XX"\r\n\r\n'
    b'--XX\r\nContent-Type: text/html; charset="utf-8"\r\n\r\n'
    b'<p>orijinal-mime</p><img src="cid:ii_1">\r\n'
    b'--XX\r\nContent-Type: image/png\r\nContent-ID: <ii_1>\r\n'
    b'Content-Disposition: inline; filename="grafik.png"\r\n\r\n'
    + png_baytlari()
    + b"\r\n--XX--\r\n"
)


class SahteIstemci:
    def __init__(self, hesap: dict):
        self.hesap = hesap

    def klasor_listesi(self):
        return [
            Klasor(kimlik="inbox", ad="Gelen Kutusu", toplam=2, okunmamis=0),
            Klasor(kimlik="sentitems", ad="Gönderilmiş", toplam=0, okunmamis=0),
        ]

    def mesajlar(self, klasor="inbox", sayfa_boyutu=50, offset=0, arama="",
                 alan="konu", tam=False, tazele=True):
        ms = [
            Mesaj(item_id="m1", konu="deneme mesajı",
                  gonderen="gonderen@ornek.gov.tr",
                  gonderen_ad="Gönderen Kişi", tarih="24.11.2026 10:00",
                  okundu=True, klasor=klasor, tariham="2026-11-24T10:00:00"),
            Mesaj(item_id="m2", konu="düz mesaj",
                  gonderen="ikinci@ornek.gov.tr", tarih="23.11.2026 09:00",
                  okundu=True, klasor=klasor, tariham="2026-11-23T09:00:00"),
            Mesaj(item_id="m3", konu="zorlu cid",
                  gonderen="ucuncu@ornek.gov.tr", tarih="22.11.2026 08:00",
                  okundu=True, klasor=klasor, tariham="2026-11-22T08:00:00"),
        ]
        return ms[offset:offset + sayfa_boyutu], len(ms)

    def guncelle(self, klasorler=None):
        return {}

    def cozumle(self, metin, en_fazla=20):
        return []

    def mesaj_detay(self, mesaj):
        if mesaj.item_id == "m1":
            mesaj.govde = "Gövde (sahte)"
            mesaj.govde_html = (
                "<html><body><p>ORIJINAL_GOVDE_ICERIK</p>"
                '<img src="cid:ii_1"><script>kotu()</script></body></html>'
            )
            mesaj.resimler = [Resim(ad="grafik.png", kaynak="cid:ii_1")]
        elif mesaj.item_id == "m3":
            # Zorlu durum: tek tırnak + büyük harf CID + resimler listesi boş
            mesaj.govde = "Zorlu gövde"
            mesaj.govde_html = (
                '<html><body><p>ZORLU_CID_ICERIK</p>'
                "<IMG border=0 SRC='CID:II_1'></body></html>"
            )
            mesaj.resimler = []
        else:
            mesaj.govde = "Düz metin gövde"
            mesaj.govde_html = ""
        return mesaj

    def okundu_isaretle(self, mesaj, okundu=True):
        mesaj.okundu = okundu

    def tasi(self, mesaj, hedef="deleteditems"):
        pass

    def mesaj_mime(self, mesaj_id):
        return CID_MIME


def bekle(uygulama, saniye):
    bitis = time.time() + saniye
    while time.time() < bitis:
        uygulama.update()
        time.sleep(0.05)


def main() -> int:
    dizin = tempfile.mkdtemp(prefix="orijinal_test_")
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
    messagebox.showerror = lambda *a, **k: HATALAR.append(f"showerror {a}")
    messagebox.showinfo = lambda *a, **k: HATALAR.append(f"showinfo {a}")

    uygulama = ui_mod.Postacim()
    try:
        bekle(uygulama, 3)

        # --- Düğme var ---
        kontrol(hasattr(uygulama, "orijinal_dugme") and
                uygulama.orijinal_dugme.winfo_exists(),
                "gövde araç çubuğunda düğme var")
        kontrol(uygulama.orijinal_dugme.cget("text") == "Orijinali göster",
                "düğme yazısı 'Orijinali göster'")

        # --- Mesaj seçili değilken: hata vermez, durum bilgilendirir ---
        uygulama.orijinal_goster()
        kontrol("Önce bir mesaj seçin" in uygulama.durum.get(),
                f"mesaj yokken durum uyarısı ({uygulama.durum.get()!r})")

        # --- HTML mesaj seç → işlenmiş gösterimde yer tutucu görünür ---
        uygulama.klasor_listesi.selection_set("kurum001|inbox")
        uygulama.liste.selection_set(uygulama.liste.get_children()[0])
        uygulama.liste.event_generate("<<TreeviewSelect>>")
        bekle(uygulama, 3)
        kontrol(uygulama.secili is not None and
                uygulama.secili.item_id == "m1", "HTML mesaj seçildi")
        kontrol("[resim: grafik.png]" in uygulama.ayrinti.get_page_text(),
                "işlenmiş gösterimde resim yer tutucusu var")

        # --- Orijinal göster: gövde alanı orijinal HTML ile çizilir ---
        uygulama.orijinal_goster()
        kontrol(uygulama.orijinal_dugme.cget("text") == "İşlenmiş hali göster",
                "düğme 'İşlenmiş hali göster' oldu")
        bekle(uygulama, 4)
        sayfa = uygulama.ayrinti.get_page_text()
        kontrol("[resim:" not in sayfa,
                "orijinal gösterimde yer tutucu kalkar")
        kontrol("ORIJINAL_GOVDE_ICERIK" in sayfa,
                "orijinal gövde içeriği aynı alanda görünür")
        kontrol("kotu()" not in sayfa, "script metni gösterime sızmaz")
        # Gömme denetimi doğrudan üretilen HTML üzerinden yapılır
        # (image_names sayımı kırık resimde de arttığı için yanıltıcıydı).
        html = uygulama._orijinal_html(uygulama.secili)
        kontrol("data:image/png;base64," in html,
                "cid resmi orijinal HTML'e gömülür")
        kontrol('src="cid:ii_1"' not in html, "cid adresi HTML'de kalmaz")
        kontrol(uygulama._orijinal_basarisiz == [],
                f"çözülemeyen resim yok ({uygulama._orijinal_basarisiz})")
        kontrol("Orijinal gösterim" in uygulama.durum.get(),
                f"durum çubuğu orijinal modu bildirir ({uygulama.durum.get()!r})")

        # --- Tekrar tıkla → işlenmiş gösterime dönüş (sunucuya gitmeden) ---
        uygulama.orijinal_goster()
        kontrol(uygulama.orijinal_dugme.cget("text") == "Orijinali göster",
                "düğme eski yazısına döndü")
        bekle(uygulama, 2)
        kontrol("[resim: grafik.png]" in uygulama.ayrinti.get_page_text(),
                "işlenmiş gösterime geri dönüldü")

        # --- Düz metin mesaj: orijinal ayrımı yapılmaz ---
        uygulama.liste.selection_set(uygulama.liste.get_children()[1])
        uygulama.liste.event_generate("<<TreeviewSelect>>")
        bekle(uygulama, 2)
        uygulama.orijinal_goster()
        kontrol("düz metin" in uygulama.durum.get(),
                f"düz metin mesajda durum bilgilendirir ({uygulama.durum.get()!r})")
        kontrol(not uygulama._govde_orijinal, "düz metin mesajda mod değişmez")

        # --- Zorlu cid: tek tırnak + büyük harf + resimler listesi boş ---
        uygulama.liste.selection_set(uygulama.liste.get_children()[2])
        uygulama.liste.event_generate("<<TreeviewSelect>>")
        bekle(uygulama, 2)
        html = uygulama._orijinal_html(uygulama.secili)
        kontrol("data:image/png;base64," in html,
                "tek tırnak/büyük harf cid de gömülür")
        kontrol("ZORLU_CID_ICERIK" in html, "zorlu mesajın içeriği görünür")

        # --- Hazırlama hatası: düğme sıfırlanır, durum bildirir ---
        uygulama.liste.selection_set(uygulama.liste.get_children()[0])
        uygulama.liste.event_generate("<<TreeviewSelect>>")
        bekle(uygulama, 2)
        eski_html = uygulama._orijinal_html

        def bozuk(_mesaj):
            raise ValueError("deneme hatası")

        uygulama._orijinal_html = bozuk
        uygulama.orijinal_goster()
        bekle(uygulama, 3)
        uygulama._orijinal_html = eski_html
        kontrol(uygulama.orijinal_dugme.cget("text") == "Orijinali göster",
                "hatada düğme eski yazısına döndü")
        kontrol("Orijinal gösterilemedi" in uygulama.durum.get(),
                f"hatada durum çubuğu bildirir ({uygulama.durum.get()!r})")
        kontrol(not uygulama._govde_orijinal, "hatada orijinal mod kapanır")
    finally:
        uygulama.destroy()
        ui_mod.Ayarlar, ui_mod.Postacim._istemci_kur = eski_ayarlar, eski_kur

    if HATALAR:
        print(f"\n!! {len(HATALAR)} hata:")
        for h in HATALAR:
            print(f"  - {h}")
        return 1
    print("\n✓ tüm kontroller geçti")
    return 0


if __name__ == "__main__":
    sys.exit(main())
