#!/usr/bin/env python3
"""Arayüz duman testi: gerçek sunucuya bağlanır, listeleri doldurur, bir
mesajı açar ve sayfalamayı dener. Xvfb ile başsız da çalışır.

Kullanim:  xvfb-run -a .venv/bin/python tests/ui_smoke.py
"""
import os
import sys
import time

# Canlı testte dosya seçici penceresi açılmasın; tkinter yedeği kullanılsın
os.environ.setdefault("POSTACIM_DOSYA_SECICI", "tk")

import tkinter.messagebox as messagebox
from tkinter import filedialog, ttk

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from postacim.ui import Postacim

HATALAR = []


def mesaj_kutusu_yok(title="", message="", **kw):
    HATALAR.append(f"[{title}] {message}")
    print(f"  !! {title}: {message}")
    return "ok"


messagebox.showerror = mesaj_kutusu_yok
messagebox.showinfo = mesaj_kutusu_yok
messagebox.showwarning = mesaj_kutusu_yok
messagebox.askyesno = lambda *a, **k: True


def bekle(uygulama, saniye):
    """Tk olay dongusunu islerken bekler."""
    bitis = time.time() + saniye
    while time.time() < bitis:
        uygulama.update()
        time.sleep(0.05)


def main() -> int:
    uygulama = Postacim()
    hata = []

    def izle(exc_type, exc, tb):
        hata.append(f"{exc_type.__name__}: {exc}")

    sys.excepthook = izle

    def tk_hata(exc_type, exc, tb):
        hata.append(f"TK {exc_type.__name__}: {exc}")
        print(f"  !! TK hatası: {exc_type.__name__}: {exc}")

    uygulama.report_callback_exception = tk_hata

    bekle(uygulama, 12)
    print(f"klasör sayısı   : {len(uygulama.klasor_liste)}")
    print(f"klasör listesi  : {[k.ad for k in uygulama.klasor_liste]}")
    print(f"mesaj sayısı    : {len(uygulama.mesajlar)}")
    print(f"sayfa           : {uygulama.sayfa_etiket.cget('text')}")
    print(f"durum           : {uygulama.durum.get()}")
    if uygulama.mesajlar:
        ilk = uygulama.mesajlar[0]
        print(f"ilk mesaj       : {ilk.tarih} | {ilk.gonderen_ad or ilk.gonderen} | {ilk.konu[:50]}")
        # Mesajı seç (okuyucu penceresini doldur)
        uygulama.liste.selection_set("0")
        uygulama._mesaj_secildi(None)
        bekle(uygulama, 5)
        # Okuyucu düz metin (Text) ya da HTML (tkinterweb HtmlFrame) olabilir
        if hasattr(uygulama.ayrinti, "get"):
            govde = uygulama.ayrinti.get("1.0", "end").strip()
        else:  # HTML modu: düz metin gövde mesajdan okunur
            secili = getattr(uygulama, "secili", None)
            govde = (getattr(secili, "govde", "") or "").strip()
        print(f"okuyucu gövdesi : {len(govde)} karakter → {govde[:70]!r}")
        print(f"ek sayısı       : {len(uygulama.ek_listesi.ekler)}")

        # Sağ tuş menüsü (Outlook tarzı)
        menu = uygulama._mesaj_menu_olustur()
        ogeler = [
            menu.entrycget(i, "label")
            for i in range(menu.index("end") + 1)
            if menu.type(i) in ("command", "cascade")
        ]
        print(f"sağ tuş menüsü  : {len(ogeler)} öğe → {', '.join(ogeler)}")
        menu.destroy()
        # Sayfalama
        uygulama._sayfa_degistir(1)
        bekle(uygulama, 5)
        print(f"2. sayfa        : {uygulama.sayfa_etiket.cget('text')}, {len(uygulama.mesajlar)} mesaj")
        # Arama
        uygulama.arama.set("e-posta")
        uygulama._arama_yap()
        bekle(uygulama, 8)
        print(f"arama sonucu    : {len(uygulama.mesajlar)} mesaj, durum={uygulama.durum.get()}")
        uygulama.arama.set("")
        uygulama._arama_yap()
        bekle(uygulama, 8)
        print(f"temizleme sonrası: {len(uygulama.mesajlar)} mesaj")
    else:
        print("!! mesaj listesi boş")

    # Klasör değiştirme (Treeview + ikon) — ağaç iki kademeli: hesap → klasör
    aktif_kok = f"hesap:{uygulama.aktif_id}"
    if uygulama.klasor_listesi.get_children(aktif_kok):
        hedef_iid = f"{uygulama.aktif_id}|sentitems"
        if hedef_iid in uygulama.klasor_listesi.get_children(aktif_kok):
            uygulama.klasor_listesi.selection_set(hedef_iid)
            uygulama.klasor_listesi.event_generate("<<TreeviewSelect>>")
            bekle(uygulama, 8)
            print(f"klasör değişimi    : {uygulama.klasor} → {len(uygulama.mesajlar)} mesaj, "
                  f"durum={uygulama.durum.get()}")
            # gelen kutusuna dön
            inbox_iid = f"{uygulama.aktif_id}|inbox"
            uygulama.klasor_listesi.selection_set(inbox_iid)
            uygulama.klasor_listesi.event_generate("<<TreeviewSelect>>")
            bekle(uygulama, 8)
            print(f"gelen kutusuna dönüş: {uygulama.klasor} → {len(uygulama.mesajlar)} mesaj")

    # Hesaplar menüsü + hesap ağacı varlık kontrolü
    hesap_ogeleri = []
    for i in range(uygulama.ust_menu.index("end") + 1):
        if uygulama.ust_menu.type(i) == "cascade" and \
                uygulama.ust_menu.entrycget(i, "label") == "Hesaplar":
            alt = uygulama.nametowidget(uygulama.ust_menu.entrycget(i, "menu"))
            hesap_ogeleri = [
                alt.entrycget(j, "label")
                for j in range(alt.index("end") + 1)
                if alt.type(j) in ("command", "radiobutton")
            ]
    print(f"hesaplar menüsü   : {hesap_ogeleri}")
    if "Hesap Ekle…" not in hesap_ogeleri:
        hata.append("Hesaplar menüsünde 'Hesap Ekle…' yok")
    koklar = uygulama.klasor_listesi.get_children()
    if not any(str(k).startswith("hesap:") for k in koklar):
        hata.append("Klasör ağacında hesap düğümü yok")
    else:
        print(f"hesap ağacı       : {list(koklar)}")

    # Gönder/Al (F9): klasör sayaçları + artımlı güncelleme + aktif liste
    uygulama.gonder_al()
    bekle(uygulama, 10)
    print(f"gönder/al       : {len(uygulama.mesajlar)} mesaj, durum={uygulama.durum.get()}")

    # Otomatik yenileme: menü seçenekleri + sessiz yenileme + seçim koruması
    etiketler = [
        uygulama.otomatik_menu.entrycget(i, "label")
        for i in range(uygulama.otomatik_menu.index("end") + 1)
        if uygulama.otomatik_menu.type(i) == "radiobutton"
    ]
    print(f"otomatik menü  : {', '.join(etiketler)}")
    if etiketler != ["Kapalı", "30 saniye", "1 dakika", "2 dakika", "5 dakika"]:
        hata.append(f"Otomatik yenileme menüsü beklenmiyor: {etiketler}")
    uygulama.otomatik_yenile = 0  # diğer adımları bölmesin (ayar dosyasına yazılmaz)
    uygulama._otomatik_baslat()
    if uygulama.mesajlar:
        uygulama.liste.selection_set("0")
        uygulama._mesaj_secildi(None)
        bekle(uygulama, 3)
        secili = uygulama._secili_mesajlar()
        secili_id = secili[0].item_id if secili else None
        uygulama._otomatik_yenile_yap()
        bekle(uygulama, 8)
        sonrasi = uygulama._secili_mesajlar()
        korundu = bool(sonrasi) and sonrasi[0].item_id == secili_id
        print(f"otomatik yenileme: {len(uygulama.mesajlar)} mesaj, seçim korundu={korundu}")
        if secili_id and not korundu:
            hata.append("Otomatik yenilemede seçim kayboldu")
    uygulama.otomatik_yenile = 60
    uygulama._otomatik_durdur()

    # Hesaptan Çıkış: Dosya menüsü + üst çubuk butonu (yalnız varlık; çağrılmaz)
    menu_ogeleri = []
    for i in range(uygulama.ust_menu.index("end") + 1):
        if uygulama.ust_menu.type(i) == "cascade":
            alt = uygulama.nametowidget(uygulama.ust_menu.entrycget(i, "menu"))
            for j in range(alt.index("end") + 1):
                if alt.type(j) == "command":
                    menu_ogeleri.append(alt.entrycget(j, "label"))
    print(f"dosya menüsü    : {'Hesaptan Çıkış…' in menu_ogeleri} (öğe sayısı {len(menu_ogeleri)})")
    if "Hesaptan Çıkış…" not in menu_ogeleri:
        hata.append("Dosya menüsünde 'Hesaptan Çıkış…' yok")

    def _butonu_bul(kok):
        for w in kok.winfo_children():
            if isinstance(w, ttk.Button) and w.cget("text") == "Hesaptan Çıkış":
                return w
            b = _butonu_bul(w)
            if b:
                return b
        return None

    cikis_butonu = _butonu_bul(uygulama)
    print(f"üst çubuk       : {'Hesaptan Çıkış' if cikis_butonu else 'BULUNAMADI'} butonu")
    if not cikis_butonu:
        hata.append("Üst çubukta 'Hesaptan Çıkış' butonu yok")

    # Bağlanamama → giriş penceresi (401 ve ağ hatası "giris" turuna düşmeli)
    import requests as _istekler
    from postacim.ews import EwsYetkiHatasi

    tur_sonuclari = []
    eski_sor, eski_yenile = uygulama._kimlik_sor, uygulama.yenile
    uygulama._kimlik_sor = lambda hata=None: tur_sonuclari.append(("sor", hata)) or False

    def _firlat(mazeret):
        def _islev():
            raise mazeret
        uygulama._arka_plan(_islev)

    _firlat(EwsYetkiHatasi("Kimlik doğrulama başarısız (401)."))
    _firlat(_istekler.ConnectionError("sunucuya ulaşılamıyor"))
    bekle(uygulama, 1)
    giris_sayisi = sum(1 for t, _ in tur_sonuclari if t == "sor")
    print(f"bağlantı hatası  : giriş penceresi {giris_sayisi} kez soruldu "
          f"(401 + ağ hatası beklenen 2)")
    if giris_sayisi != 2:
        hata.append(f"Beklenen 2 giriş isteği, gelen {giris_sayisi}")
    hata_metinleri = [m for _, m in tur_sonuclari if m]
    if not any("401" in (m or "") for m in hata_metinleri):
        hata.append("401 hatası giriş isteğine taşınmadı")

    # İptal → istemci sıfırlanır, yenile çağrılmaz
    uygulama._kimlik_sor = lambda hata=None: tur_sonuclari.append(("iptal", hata)) or False
    yenile_sayaci = []
    uygulama.yenile = lambda: yenile_sayaci.append(True)
    uygulama.istemci = None
    uygulama._giris_iste("deneme hatası")
    print(f"giriş iptali     : istemci {uygulama.istemci is None}, "
          f"yenile {len(yenile_sayaci)} kez, durum={uygulama.durum.get()!r}")
    if yenile_sayaci:
        hata.append("İptal durumunda yanlışlıkla yenile çağrıldı")

    # Onay → yenile ile yeniden bağlanma denenir
    uygulama._kimlik_sor = lambda hata=None: tur_sonuclari.append(("tamam", hata)) or True
    uygulama._giris_iste("deneme hatası 2")
    print(f"giriş onayı       : yenile {len(yenile_sayaci)} kez çağrıldı")
    if len(yenile_sayaci) != 1:
        hata.append("Giriş onayında yeniden bağlanma denenmedi")
    # Gerçek yenile'yi geri koyup gerçekten yeniden bağlan
    uygulama._kimlik_sor, uygulama.yenile = eski_sor, eski_yenile
    uygulama.yenile()
    bekle(uygulama, 8)
    print(f"yeniden bağlanma : istemci {uygulama.istemci is not None}, "
          f"mesaj {len(uygulama.mesajlar)}, durum={uygulama.durum.get()!r}")
    if uygulama.istemci is None or not uygulama.mesajlar:
        hata.append("Giriş sonrası yeniden bağlanma başarısız")

    # Çoklu seçim (Ctrl/Shift, Outlook tarzı) + taşıma sonrası yenileme
    if str(uygulama.liste.cget("selectmode")) != "extended":
        hata.append("Mesaj listesi selectmode=extended değil")
    uygulama.liste.selection_set(("0", "1", "2"))
    secili = uygulama._secili_mesajlar()
    print(f"çoklu seçim     : {len(secili)} mesaj seçildi (beklenen 3)")
    if len(secili) != 3:
        hata.append(f"Çoklu seçim bozuk: {len(secili)}/3")
    uygulama._mesaj_secildi(None)
    print(f"seçim durumu    : {uygulama.durum.get()!r}")
    if "3 mesaj seçildi" not in uygulama.durum.get():
        hata.append("Çoklu seçim durum mesajı görünmedi")
    bekle(uygulama, 0.5)
    # Taşıma sonrası "yenile" sonucu → liste tazelenmeli (gerçek silme yok)
    eski_yenile2 = uygulama.yenile
    yenile_sayaci2 = []
    uygulama.yenile = lambda: yenile_sayaci2.append(True)
    uygulama._sonuc_isle(("yenile", "Taşındı → test (3 mesaj)"))
    print(f"taşıma yenileme : yenile {len(yenile_sayaci2)} kez çağrıldı")
    if len(yenile_sayaci2) != 1:
        hata.append("Taşıma sonrası yenileme tetiklenmedi")
    uygulama.yenile = eski_yenile2
    uygulama.liste.selection_remove(*uygulama.liste.get_children())

    # Yazma penceresi: ikonlar ve düzen (gecmis KeyError burada yakalandi)
    uygulama.yeni_posta()
    bekle(uygulama, 2)
    pencere = [w for w in uygulama.winfo_children() if w.winfo_class() == "Toplevel"]
    if pencere:
        p = pencere[0]
        print(f"yazma penceresi   : {p.winfo_width()}x{p.winfo_height()}, "
              f"{len(p.winfo_children())} widget")
        # Kişi tamamlama: kurum dizininde filtreleme (canlı) + kayıtlı kişiler yedeği
        uygulama.kisiler.ekle("Test Kişi", "test.kisi@ornek.gov.tr")
        uygulama.cozum_yok = True  # deterministik: yedek (kayıtlı kişiler) yolu
        p.kime_giris.insert(0, "test")
        p.kime_giris.icursor(4)
        p._kime_tamamla._oneri()
        bekle(uygulama, 1)
        yerel = list(p._kime_tamamla._sonuc)
        print(f"yedek öneri      : {len(yerel)} öneri → {yerel[:3]}")
        if not any(e == "test.kisi@ornek.gov.tr" for _, e in yerel):
            hata.append("Kayıtlı kişiler yedeği görünmedi")
        p._kime_tamamla._enter(None)
        print(f"tamamlanan kime  : {p.kime_var.get()!r}")
        if "test.kisi@ornek.gov.tr" not in p.kime_var.get():
            hata.append("Kişi tamamlama alana yazılmadı")
        # Kurum dizini (canlı; sunucu desteklemiyorsa cozum_yok kurulur)
        uygulama.cozum_yok = False
        parca = (uygulama.ayarlar.al("kullanici", "").split("\\")[-1]
                 .split("@")[0][:2] or "ad")
        p.kime_giris.delete(0, "end")
        p.kime_giris.insert(0, parca)
        p.kime_giris.icursor(len(parca))
        p._kime_tamamla._oneri()
        for _ in range(10):
            bekle(uygulama, 0.5)
            if uygulama.cozum_yok or p._kime_tamamla._sonuc:
                break
        print(f"kurum dizini     : {parca!r} → {len(p._kime_tamamla._sonuc)} öneri, "
              f"cozum_yok={uygulama.cozum_yok}")
        p.destroy()
    else:
        print("!! yazma penceresi açılmadı")

    # Ek indirme: "yemek" aranir, ekli mesaj acilir, ilk ek kaydedilir
    hedef_ek = "/tmp/opencode/ek_test.bin"
    filedialog.asksaveasfilename = lambda **kw: hedef_ek
    uygulama.arama.set("yemek")
    uygulama._arama_yap()
    bekle(uygulama, 8)
    if uygulama.mesajlar:
        uygulama.liste.selection_set("0")
        uygulama._mesaj_secildi(None)
        bekle(uygulama, 8)
        ekler = getattr(uygulama.ek_listesi, "ekler", [])
        print(f"ekli mesaj açıldı : {len(ekler)} ek")
        if ekler:
            uygulama.ek_listesi.selection_set("0")  # Treeview iid = sıra no
            uygulama.ek_indir()
            bekle(uygulama, 25)
            if os.path.exists(hedef_ek):
                boyut = os.path.getsize(hedef_ek)
                with open(hedef_ek, "rb") as f:
                    ilk = f.read(4)
                print(f"ek indirildi      : {boyut} bayt, ilk 4 bayt={ilk!r}")
                os.remove(hedef_ek)
            else:
                print("!! ek dosyası yazılmadı")
        else:
            print("!! mesajda ek listesi boş")
    else:
        print("!! ekli mesaj bulunamadı")

    uygulama.destroy()
    if hata:
        print("\n!! HATALAR:")
        for h in hata:
            print("   ", h)
        return 1
    print("\n✓ arayüz testi tamam, istisna yok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
