#!/usr/bin/env python3
"""Bildirim testleri — yeni e-posta uyarısı.

Kapsam:
  * Gelen kutusu sayısı ilk ölçüldüğünde bildirim çıkmaz (taban).
  * Sayı arttığında işletim sistemi bildirimi gönderilir.
  * Sayı artmadığında bildirim gönderilmez.
  * Bildirim kapatıldığında (ayarlar) hiç gönderilmez.
  * Sistem balonları kapalıysa uygulama içi uyarı (toast) gösterilir.
  * Durum çubuğu da yeni e-postayı bildirir.
"""
import os
import sys
import tkinter as tk

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

HATALAR = []
GONDERILEN = []


def kontrol(kosul, aciklama):
    if kosul:
        print(f"  ✓ {aciklama}")
    else:
        print(f"  ✗ {aciklama}")
        HATALAR.append(aciklama)


def main() -> int:
    try:
        kok = tk.Tk()
        kok.withdraw()
    except tk.TclError:
        print("  -- DISPLAY yok (xvfb-run ile çalıştırın), atlandı")
        return 0

    import postacim.ui as ui_mod
    from postacim.ui import Postacim

    # Gerçek gönderim yöntemi (testte kullanılacak)
    GERCEK_GONDER = Postacim._bildirim_gonder

    # Bildirim gönderimini yakala (gerçek bildirim gönderilmez)
    def sahte_gonder(self, baslik, govde):
        GONDERILEN.append((baslik, govde))
        return True

    Postacim._bildirim_gonder = sahte_gonder
    Postacim._bildirim_toast = lambda self, baslik, govde: TOASTLAR.append(
        (baslik, govde)
    )
    Postacim._bildirim_balonlari_kapali = lambda self: True

    TOASTLAR = []

    # Bildirim davranışı tek başına test edilir (Tk arayüzü kurmadan)
    class Sahte(Postacim):
        def __init__(self):
            self._son_gelen_sayi = {}
            self._bildirim_acik = True
            self.durum = tk.StringVar()
            self.durum.set("Hazır")

    uygulama = Sahte()

    # 1) İlk ölçüm: taban, bildirim yok
    uygulama._bildirim_kontrol("h1", 10, "Kurum")
    kontrol(not GONDERILEN, "ilk ölçümde bildirim gönderilmez (taban)")
    kontrol(not TOASTLAR, "ilk ölçümde uygulama içi uyarı gösterilmez")

    # 2) Artış: bildirim + toast + durum çubuğu
    uygulama._bildirim_kontrol("h1", 13, "Kurum")
    kontrol(len(GONDERILEN) == 1, "gelen kutusu artınca bildirim gönderilir")
    if GONDERILEN:
        baslik, govde = GONDERILEN[0]
        kontrol("Kurum" in baslik, "bildirim başlığında hesap adı var")
        kontrol("3" in govde, "bildirim gövdesinde yeni mesaj sayısı var")
    kontrol(len(TOASTLAR) == 1, "uygulama içi uyarı gösterilir")
    kontrol("Yeni e-posta" in uygulama.durum.get(), "durum çubuğu bilgilendirilir")

    # 3) Artış yok: yeni bildirim yok
    uygulama._bildirim_kontrol("h1", 13, "Kurum")
    kontrol(len(GONDERILEN) == 1, "sayı değişmezse yeni bildirim gönderilmez")

    # 4) Azalış (okunan mail): bildirim yok
    uygulama._bildirim_kontrol("h1", 11, "Kurum")
    kontrol(len(GONDERILEN) == 1, "sayı azalınca bildirim gönderilmez")

    # 5) Bildirim kapalıyken gönderilmemeli (gerçek yöntem)
    uygulama._bildirim_acik = False
    sonuc = GERCEK_GONDER(uygulama, "Başlık", "Gövde")
    kontrol(sonuc is False, "bildirim kapalıyken gönderim yapılmaz")
    uygulama._bildirim_acik = True

    # 6) Gerçek gönderim yöntemi: komutu doğru kuruyor mu?
    komutlar = []
    eski_popen = ui_mod.subprocess.Popen

    def sahte_popen(komut, *a, **kw):
        komutlar.append(komut)
        raise OSError("test")  # Popen yok sayılır

    ui_mod.subprocess.Popen = sahte_popen
    try:
        uygulama._bildirim_arac = "/usr/bin/notify-send"
        uygulama._bildirim_gdbus = None
        GERCEK_GONDER(uygulama, "Başlık", "Gövde")
    finally:
        ui_mod.subprocess.Popen = eski_popen
    kontrol(bool(komutlar), "bildirim komutu oluşturulur")
    if komutlar:
        komut = komutlar[0]
        kontrol("notify-send" in komut[0], "notify-send kullanılır")
        kontrol("Başlık" in komut and "Gövde" in komut, "başlık ve gövde komuta geçer")
        kontrol("-i" in komut, "uygulama simgesi bildirime eklenir")

    kok.destroy()

    if HATALAR:
        print(f"\n!! {len(HATALAR)} hata:")
        for h in HATALAR:
            print(f"   - {h}")
        return 1
    print("\n✓ tüm kontroller geçti")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
