#!/usr/bin/env python3
"""Çoklu hesap arayüz testi (çevrimdışı; sahte istemciler, gerçek sunucu yok).

Kapsar:
- Hesap → klasör iki kademeli ağaç (Evolution tarzı)
- Başka hesabın klasörüne tıklayınca hesap geçişi (aktif, başlık, mesajlar)
- Hesaplar menüsü varlığı
- Hesap ekleme penceresi + "Gmail'e ayarla" hazır ayarı
- Giriş/silme akışlarının çökmemesi

Kullanim:  xvfb-run -a .venv/bin/python tests/hesap_ui_test.py
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import time

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
    """EwsIstemci/ImapIstemci arayüzünü taklit eder; mesajlar hesaba özgü."""

    def __init__(self, hesap: dict):
        self.hesap = hesap
        self.silinenler: list = []  # klasor_sil çağrıları
        self.olusturulanlar: list = []  # klasor_olustur çağrıları

    def klasor_listesi(self):
        return [
            Klasor(kimlik="inbox", ad="Gelen Kutusu", toplam=2, okunmamis=1),
            Klasor(kimlik="sentitems", ad="Gönderilmiş", toplam=0, okunmamis=0),
            Klasor(kimlik="drafts", ad="Taslaklar", toplam=0, okunmamis=0),
            # İkonsuz klasörler (Gmail etiketleri gibi): image=None Treeview'i
            # çökertmemeli — "value for "-image" missing" regresyonu
            Klasor(kimlik="Proje X", ad="Proje X", toplam=1, okunmamis=0),
            Klasor(kimlik="Faturalarım", ad="Faturalarım", toplam=4, okunmamis=1),
        ]

    def mesajlar(self, klasor="inbox", sayfa_boyutu=50, offset=0, arama="",
                 alan="konu", tam=False, tazele=True):
        ad = self.hesap.get("ad", "?")
        ms = [
            Mesaj(item_id=f"{self.hesap['id']}-{klasor}-1",
                  konu=f"{ad} — birinci mesaj", gonderen="gonderen@ornek.gov.tr",
                  gonderen_ad="Gönderen Kişi", tarih="19.11.2026 10:00",
                  okundu=True, klasor=klasor, tariham="2026-11-19T10:00:00"),
            Mesaj(item_id=f"{self.hesap['id']}-{klasor}-2",
                  konu=f"{ad} — ikinci mesaj", gonderen="ikinci@ornek.gov.tr",
                  tarih="18.11.2026 09:00", okundu=False, klasor=klasor,
                  tariham="2026-11-18T09:00:00"),
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

    def klasor_sil(self, kimlik):
        self.silinenler.append(kimlik)

    def klasor_olustur(self, ad):
        self.olusturulanlar.append(ad)
        return ad

    def kalici_sil(self, mesaj):
        pass

    def gonder(self, *a, **k):
        return ""

    def taslağa_kaydet(self, *a, **k):
        return ""

    def mesaj_mime(self, mesaj_id):
        return b"From: x\r\n\r\n"

    def ek_indir(self, ek):
        return b""


def bekle(uygulama, saniye):
    bitis = time.time() + saniye
    while time.time() < bitis:
        uygulama.update()
        time.sleep(0.05)


def main() -> int:
    # Geçici ayar dosyası (gerçek ~/.config/postacim'ya dokunulmaz)
    dizin = tempfile.mkdtemp(prefix="hesap_ui_test_")
    yol = os.path.join(dizin, "hesap.json")
    kurum_id, gmail_id = "kurum001", "gmail002"
    with open(yol, "w", encoding="utf-8") as f:
        json.dump({
            "hesaplar": [
                {"id": kurum_id, "ad": "Kurum", "tur": "ews",
                 "sunucu": "mail.ornek.gov.tr", "kullanici": "KURUM\\kisi",
                 "parola": "sifre", "yontem": "ntlm", "son_klasor": "inbox"},
                {"id": gmail_id, "ad": "Gmail", "tur": "imap",
                 "kullanici": "deneme@gmail.com", "parola": "uygulama parolası",
                 "gelen_sunucu": "imap.gmail.com", "gelen_port": 993,
                 "giden_sunucu": "smtp.gmail.com", "giden_port": 465,
                 "guvenli": "ssl", "son_klasor": "inbox"},
            ],
            "aktif": kurum_id,
            "tema": "light", "otomatik_yenile": 0,
        }, f, ensure_ascii=False, indent=2)

    # Yamalar: geçici config + sahte istemci
    eski_ayarlar, eski_kur = ui_mod.Ayarlar, ui_mod.Postacim._istemci_kur
    ui_mod.Ayarlar = lambda: Ayarlar(yol)
    ui_mod.Postacim._istemci_kur = lambda self, hesap: SahteIstemci(hesap)

    import tkinter.messagebox as messagebox
    eski_soru = messagebox.askyesno
    messagebox.askyesno = lambda *a, **k: True
    eski_uyari = messagebox.showwarning
    uyari_kutular: list = []
    messagebox.showwarning = lambda *a, **k: uyari_kutular.append(a)

    uygulama = ui_mod.Postacim()
    hata = []

    def izle(exc_type, exc, tb):
        import traceback
        hata.append(f"{exc_type.__name__}: {exc}")
        traceback.print_exception(exc_type, exc, tb)

    sys.excepthook = izle
    uygulama.report_callback_exception = lambda *a: izle(*a[:3])

    try:
        # İlk hesabın klasörleri + mesajları yüklensin
        bekle(uygulama, 3)
        print(f"başlık           : {uygulama.title()!r}")
        kontrol("Kurum" in uygulama.title(), "başlıkta aktif hesap adı")

        # --- Pencere simgesi ve WM_CLASS (görev çubuğu eşleşmesi) ---
        kontrol(uygulama.tk.call("tk", "appname") == "postacim",
                f"WM_CLASS uygulama adı ({uygulama.tk.call('tk', 'appname')!r})")
        kontrol(uygulama.iconname() == "Postacım",
                f"WM_ICONNAME Postacım ({uygulama.iconname()!r})")
        kontrol(getattr(uygulama, "_pencere_simgesi_ref", None) is not None,
                "başlık çubuğu simgesi ayarlandı")
        kontrol("uygulama_64" in uygulama.ikon,
                "64×64 pencere simgesi yüklendi")

        # --- Hesap ağacı (Evolution tarzı) ---
        koklar = uygulama.klasor_listesi.get_children()
        kontrol(len(koklar) == 2, f"2 hesap düğümü ({koklar})")
        kontrol(f"hesap:{kurum_id}" in koklar, "aktif hesap düğümü var")
        kontrol(f"hesap:{gmail_id}" in koklar, "diğer hesap düğümü var")
        aktif_cocuk = uygulama.klasor_listesi.get_children(f"hesap:{kurum_id}")
        kontrol(f"{kurum_id}|inbox" in aktif_cocuk, "klasörler hesap altinda")
        kontrol(f"{kurum_id}|sentitems" in aktif_cocuk, "sentitems alt düğümde")
        kontrol(f"{kurum_id}|Proje X" in aktif_cocuk,
                "ikonsuz özel klasör ağaçta (image=None regresyonu)")
        kontrol(f"{kurum_id}|Faturalarım" in aktif_cocuk,
                "türkçe etiketli klasör ağaçta")

        # --- Aktif hesabın mesajları ---
        kontrol(len(uygulama.mesajlar) == 2, "mesajlar yüklendi")
        kontrol(uygulama.mesajlar and "Kurum" in uygulama.mesajlar[0].konu,
                "mesajlar aktif hesaptan geldi")
        kontrol(uygulama.istemci is not None and
                uygulama.istemci.hesap["id"] == kurum_id,
                "istemci aktif hesabın")

        # --- Diğer hesabın klasörüne tıkla → geçiş ---
        hedef = f"{gmail_id}|inbox"
        uygulama.klasor_listesi.selection_set(hedef)
        uygulama.klasor_listesi.event_generate("<<TreeviewSelect>>")
        bekle(uygulama, 3)
        kontrol(uygulama.aktif_id == gmail_id, "aktif hesap değişti")
        kontrol("Gmail" in uygulama.title(), "başlık Gmail oldu")
        kontrol(uygulama.istemci.hesap["id"] == gmail_id,
                "istemci Gmail hesabına geçti")
        kontrol(len(uygulama.mesajlar) == 2 and
                "Gmail" in uygulama.mesajlar[0].konu,
                "mesajlar Gmail'den geldi")
        kontrol(uygulama.cozum_yok is True,
                "IMAP hesapta cozum_yok (dizin yok, kişilerden öner)")
        kontrol(uygulama.klasor == "inbox", "klasör inbox")
        if hasattr(uygulama, "hesap_degisken"):
            kontrol(uygulama.hesap_degisken.get() == gmail_id,
                    "menü işareti yeni hesapta")

        # --- Klasör menüsü (sağ tuş) — aktif IMAP hesabı ---
        gmail_istemci = uygulama.istemci

        def menu_komutlari(menu):
            if menu is None:
                return []
            return [
                menu.entrycget(i, "label")
                for i in range(menu.index("end") + 1)
                if menu.type(i) == "command"
            ]

        # Aktif IMAP: "Yeni Klasör…" her klasörde; "Klasörü Sil…" yalnız
        # özel olmayan klasörde
        ogeler = menu_komutlari(uygulama._klasor_menu_olustur(f"{gmail_id}|inbox"))
        kontrol("Yeni Klasör…" in ogeler,
                f"IMAP inbox'ta yeni klasör öğesi var ({ogeler})")
        kontrol("Klasörü Sil…" not in ogeler,
                f"özel klasörde (inbox) silme öğesi yok ({ogeler})")
        ogeler = menu_komutlari(uygulama._klasor_menu_olustur(f"{gmail_id}|Proje X"))
        kontrol("Klasörü Sil…" in ogeler,
                f"özel olmayan klasörde silme öğesi var ({ogeler})")
        kontrol("Yeni Klasör…" in ogeler,
                f"özel olmayan klasörde yeni klasör öğesi de var ({ogeler})")
        ogeler = menu_komutlari(uygulama._klasor_menu_olustur(f"hesap:{gmail_id}"))
        kontrol("Yeni Klasör…" in ogeler,
                f"hesap düğümünde yeni klasör öğesi var ({ogeler})")
        kontrol(uygulama._klasor_menu_olustur(f"{kurum_id}|inbox") is None,
                "başka hesabın klasöründe menü yok")
        # Silme akışı: onay (askyesno=True) → istemci.klasor_sil çağrılır
        uygulama.klasor_sil("Proje X", "Proje X")
        bekle(uygulama, 2)
        kontrol(gmail_istemci.silinenler == ["Proje X"],
                f"klasör silme istemciye ulaştı ({gmail_istemci.silinenler})")

        # Oluşturma akışı: ad verilmiş → pencere açılmaz, arka planda
        uygulama.klasor_olustur("Proje Y")
        bekle(uygulama, 2)
        kontrol(gmail_istemci.olusturulanlar == ["Proje Y"],
                f"klasör oluşturma istemciye ulaştı ({gmail_istemci.olusturulanlar})")
        # Boş ad → uyarı kutusu, istemciye gitmez
        uygulama.klasor_olustur("   ")
        bekle(uygulama, 1)
        kontrol(len(uyari_kutular) == 1
                and gmail_istemci.olusturulanlar == ["Proje Y"],
                f"boş klasör adı uyarı verir, oluşturmaz ({uyari_kutular})")

        # Geri dönüş
        uygulama.klasor_listesi.selection_set(f"{kurum_id}|sentitems")
        uygulama.klasor_listesi.event_generate("<<TreeviewSelect>>")
        bekle(uygulama, 2)
        kontrol(uygulama.aktif_id == kurum_id, "eski hesaba dönüldü")
        kontrol(uygulama.klasor == "sentitems", "sentitems seçildi")
        kontrol(uygulama.cozum_yok is False, "EWS hesapta cozum_yok=False")
        ogeler = menu_komutlari(uygulama._klasor_menu_olustur(f"{kurum_id}|inbox"))
        kontrol("Yeni Klasör…" in ogeler,
                f"aktif EWS hesapta yeni klasör öğesi var ({ogeler})")
        kontrol("Klasörü Sil…" not in ogeler,
                f"EWS (kurum) hesapta klasör silme öğesi yok ({ogeler})")
        # EWS hesapta da oluşturma çalışır
        kurum_istemci = uygulama.istemci
        uygulama.klasor_olustur("Kurum Klasörü")
        bekle(uygulama, 2)
        kontrol(kurum_istemci.olusturulanlar == ["Kurum Klasörü"],
                f"EWS hesapta oluşturma istemciye ulaştı "
                f"({kurum_istemci.olusturulanlar})")

        # --- Hesaplar menüsü ---
        ogeler = []
        for i in range(uygulama.ust_menu.index("end") + 1):
            if uygulama.ust_menu.type(i) == "cascade" and \
                    uygulama.ust_menu.entrycget(i, "label") == "Hesaplar":
                alt = uygulama.nametowidget(uygulama.ust_menu.entrycget(i, "menu"))
                ogeler = [
                    alt.entrycget(j, "label")
                    for j in range(alt.index("end") + 1)
                    if alt.type(j) in ("command", "radiobutton")
                ]
        kontrol("Hesap Ekle…" in ogeler and "Hesap Düzenle…" in ogeler
                and "Hesap Sil…" in ogeler, f"Hesaplar menüsü ({ogeler})")
        kontrol("Kurum" in ogeler and "Gmail" in ogeler, "menüde hesap adları")

        # --- Hesap ekleme penceresi + Gmail hazır ayarı ---
        pencere = ui_mod.HesapPenceresi(uygulama)
        pencere._gmail_ayarla()
        kontrol(pencere.tur_degisken.get() == "imap", "Gmail ayarı tür=imap")
        kontrol(pencere.gelen_var.get() == "imap.gmail.com" and
                pencere.gelen_port_var.get() == "993", "gelen sunucu hazır")
        kontrol(pencere.giden_var.get() == "smtp.gmail.com" and
                pencere.giden_port_var.get() == "465", "giden sunucu hazır")
        kontrol(pencere.ad_var.get() == "Gmail", "hesap adı önerildi")
        # Kaydet: yeni hesap eklenir ve ona geçilir
        pencere.eposta_var.set("yeni@gmail.com")
        pencere.parola_var.set("uygulama parolası 123")
        pencere._kaydet()
        bekle(uygulama, 2)
        kontrol(len(uygulama.ayarlar.hesaplar()) == 3, "yeni hesap eklendi")
        kontrol(uygulama.aktif_id != kurum_id, "yeni hesaba geçildi")
        kontrol(uygulama.istemci.hesap["kullanici"] == "yeni@gmail.com",
                "istemci yeni hesabın")

        # --- Hesap silme (aktif) ---
        uygulama._hesap_sil_penceresi()
        bekle(uygulama, 2)
        kontrol(len(uygulama.ayarlar.hesaplar()) == 2, "hesap silindi")
        kontrol(uygulama.aktif_id in (kurum_id, gmail_id),
                f"aktif hesap geçerli kaldı ({uygulama.aktif_id})")
        kontrol(uygulama.istemci is not None, "silme sonrası bağlı")

        # Kuyruk/yutma yardımcıları çökmemeli
        uygulama._kuyrugu_yut()
        uygulama._mesaj_alanini_temizle()
        uygulama._agaci_yenile()
        kontrol(True, "kuyruk/yutma + ağaç yenileme hatasız")

        # --- Hakkında penceresi (logolu) ---
        uygulama.hakkinda()
        bekle(uygulama, 1)
        hakkinda = [w for w in uygulama.winfo_children()
                    if w.winfo_class() == "Toplevel"]
        kontrol(len(hakkinda) == 1, "Hakkında penceresi açıldı")
        if hakkinda:
            p = hakkinda[0]
            kontrol("Hakkında" in p.title() or "hakkında" in p.title(),
                    f"pencere başlığı ({p.title()!r})")
            kontrol(p.tk.call("tk", "appname") == "postacim",
                    "Hakkında penceresi de aynı WM_CLASS")
            p.destroy()

        # --- Yardım menüsünde kaldırma öğesi ---
        yardim_ogeleri = []
        for i in range(uygulama.ust_menu.index("end") + 1):
            if uygulama.ust_menu.type(i) != "cascade":
                continue
            if uygulama.ust_menu.entrycget(i, "label") != "Yardım":
                continue
            alt = uygulama.nametowidget(uygulama.ust_menu.entrycget(i, "menu"))
            yardim_ogeleri = [
                alt.entrycget(j, "label")
                for j in range(alt.index("end") + 1)
                if alt.type(j) == "command"
            ]
        kontrol("Postacım'ı Kaldır…" in yardim_ogeleri,
                f"Yardım menüsünde kaldırma öğesi ({yardim_ogeleri})")
    finally:
        try:
            uygulama.destroy()
        except Exception:
            pass
        ui_mod.Ayarlar, ui_mod.Postacim._istemci_kur = eski_ayarlar, eski_kur
        messagebox.askyesno = eski_soru
        messagebox.showwarning = eski_uyari

    if hata:
        print("\n!! İstisnalar:")
        for h in hata:
            print("   ", h)
        HATALAR.extend(hata)
    if HATALAR:
        print(f"\n!! {len(HATALAR)} HATA:")
        for h in HATALAR:
            print("   ", h)
        return 1
    print("\n✓ hesap arayüz testi tamam")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
