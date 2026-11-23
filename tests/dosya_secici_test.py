#!/usr/bin/env python3
"""Dosya seçici testleri — zenity/kdialog/tk seçimi ve yedekleme.

Kapsam:
  * Süzgeçler zenity ve kdialog biçimine doğru çevrilir.
  * POSTACIM_DOSYA_SECICI ortam değişkeni seçiciyi zorlar.
  * zenity çıktısı tek/çoklu dosya olarak çözülür; iptal boş döner.
  * Zenity çalıştırılamazsa tkinter filedialog yedeğine düşülür.
  * Kaydetmede varsayılan uzantı eklenir ve son dizin hatırlanır.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from postacim import dosya_secici as ds

HATALAR = []


def kontrol(kosul, aciklama):
    if kosul:
        print(f"  ✓ {aciklama}")
    else:
        print(f"  ✗ {aciklama}")
        HATALAR.append(aciklama)


def which_sadece(*araçlar):
    return lambda ad: f"/usr/bin/{ad}" if ad in araçlar else None


def ortam_ayarla(deger=None):
    if deger is None:
        os.environ.pop("POSTACIM_DOSYA_SECICI", None)
    else:
        os.environ["POSTACIM_DOSYA_SECICI"] = deger


def main() -> int:
    eski_which = ds.shutil.which
    eski_calistir = ds._calistir
    eski_zenity_ac = ds._zenity_ac
    eski_tk_ac = ds._tk_ac
    try:
        print("süzgeçler")
        kontrol(ds._desenler("*.*") == ["*"], "*.* → * dönüşür")
        kontrol(
            ds._desenler("*.pdf *.doc") == ["*.pdf", "*.doc"],
            "boşluklu desen listeye ayrılır",
        )
        zf = ds._zenity_filtreleri([("Belgeler", "*.pdf *.doc")])
        kontrol(zf == ["Belgeler | *.pdf *.doc"], "zenity süzgeç biçimi")
        kf = ds._kdialog_filtreleri([("Belgeler", "*.pdf *.doc")])
        kontrol(kf == "Belgeler (*.pdf *.doc)", "kdialog süzgeç biçimi")

        print("seçici belirleme")
        ortam_ayarla("tk")
        secim = ds._komut_sec()
        kontrol(secim == "tk", "ortam değişkeni tk'yı zorlar")
        ortam_ayarla(None)
        ds.shutil.which = which_sadece("zenity")
        kontrol(ds._komut_sec() == "zenity", "zenity varsa o seçilir")
        ds.shutil.which = which_sadece("kdialog")
        kontrol(ds._komut_sec() == "kdialog", "yalnız kdialog varsa o seçilir")
        ds.shutil.which = which_sadece()
        kontrol(ds._komut_sec() == "tk", "ikisi de yoksa tk yedeği")

        print("zenity: tek dosya")
        os.environ["POSTACIM_DOSYA_SECICI"] = "zenity"
        ds.shutil.which = which_sadece("zenity")
        komutlar = []

        def sahte_calistir(komut):
            komutlar.append(komut)
            return True, "/tmp/opencode/rapor.pdf"

        ds._calistir = sahte_calistir
        yol = ds.dosya_ac("Ek seç", turler=ds.EK_TURLERI)
        kontrol(yol == "/tmp/opencode/rapor.pdf", "seçilen yol döner")
        if komutlar:
            komut = komutlar[0]
            kontrol("--file-selection" in komut, "zenity dosya seçme kipi")
            kontrol("--title=Ek seç" in komut, "başlık aktarılır")
            kontrol(any(k.startswith("--file-filter=") for k in komut),
                    "süzgeç aktarılır")
            kontrol("--multiple" not in komut, "tekli seçimde --multiple yok")
        kontrol(ds._son_dizin == "/tmp/opencode", "son dizin hatırlanır")

        print("zenity: çoklu dosya")
        ds._calistir = lambda komut: (
            True, "/tmp/opencode/a.txt\n/tmp/opencode/b.txt"
        )
        yollar = ds.dosya_ac_coklu("Ek seç")
        kontrol(yollar == ["/tmp/opencode/a.txt", "/tmp/opencode/b.txt"],
                "yeni satırla ayrılan yollar listelenir")

        print("iptal")
        ds._calistir = lambda komut: (False, "")
        kontrol(ds.dosya_ac("Ek seç") == "", "iptalde boş dize")
        kontrol(ds.dosya_ac_coklu("Ek seç") == [], "iptalde boş liste")
        kontrol(ds.dosya_kaydet("Kaydet") == "", "iptalde kaydet boş dize")

        print("zenity: kaydet + uzantı")
        komutlar.clear()

        def kaydet_calistir(komut):
            komutlar.append(komut)
            return True, "/tmp/opencode/rapor"

        ds._calistir = kaydet_calistir
        hedef = ds.dosya_kaydet(
            "Mesajı farklı kaydet", baslangic="rapor.eml",
            varsayilan_uzanti=".eml",
            turler=[("E-posta (.eml)", "*.eml")],
        )
        kontrol(hedef == "/tmp/opencode/rapor.eml", "uzantı eklenir")
        if komutlar:
            kontrol("--save" in komutlar[0], "zenity kaydetme kipi")
            kontrol(
                any(k.startswith("--filename=") and k.endswith("rapor.eml")
                    for k in komutlar[0]),
                "önerilen dosya adı aktarılır",
            )

        print("kdialog: çoklu aç")
        os.environ["POSTACIM_DOSYA_SECICI"] = "kdialog"
        ds.shutil.which = which_sadece("kdialog")
        komutlar.clear()
        ds._calistir = lambda komut: (komutlar.append(komut) or True, "/tmp/a.txt")
        ds.dosya_ac_coklu("Ek seç")
        if komutlar:
            komut = komutlar[0]
            kontrol("--getopenfilename" in komut, "kdialog açma kipi")
            kontrol("--multiple" in komut, "kdialog çoklu seçim")

        print("tk yedeği")
        os.environ["POSTACIM_DOSYA_SECICI"] = "zenity"
        ds.shutil.which = which_sadece("zenity")

        def patlayan(*a, **k):
            raise OSError("zenity yok")

        ds._zenity_ac = patlayan
        ds._tk_ac = lambda *a, **k: (True, "/tmp/opencode/yedek.txt")
        kontrol(ds.dosya_ac("Ek seç") == "/tmp/opencode/yedek.txt",
                "zenity başlatılamazsa tk yedeği kullanılır")
    finally:
        ds.shutil.which = eski_which
        ds._calistir = eski_calistir
        ds._zenity_ac = eski_zenity_ac
        ds._tk_ac = eski_tk_ac
        ortam_ayarla(None)

    if HATALAR:
        print(f"\n!! {len(HATALAR)} hata:")
        for h in HATALAR:
            print(f"   - {h}")
        return 1
    print("\n✓ tüm kontroller geçti")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
