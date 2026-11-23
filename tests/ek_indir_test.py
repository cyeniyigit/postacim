#!/usr/bin/env python3
"""Toplu ek indirme testleri — dosya adı güvenliği ve çoklu kayıt.

Kapsam:
  * Ek adındaki yol ayırıcıları ve geçersiz karakterler temizlenir.
  * Aynı adlı dosyalar ' (1)', ' (2)' eklenerek çakışmadan yazılır.
  * Birden çok ek tek arka plan işinde indirilip klasöre kaydedilir.
  * Bir ek indirilemezse diğerleri kaydedilir; hata listelenir.
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from postacim.ews import Ek
from postacim.ui import Postacim, _benzersiz_yol, _temiz_dosya_adi

HATALAR = []


def kontrol(kosul, aciklama):
    if kosul:
        print(f"  ✓ {aciklama}")
    else:
        print(f"  ✗ {aciklama}")
        HATALAR.append(aciklama)


class SahteIstemci:
    def ek_indir(self, ek):
        if ek.ad == "bozuk.txt":
            raise OSError("sunucudan indirilemedi")
        return f"veri:{ek.ad}".encode("utf-8")


class SahteAna:
    istemci = SahteIstemci()


def main() -> int:
    print("dosya adı temizliği")
    kontrol(_temiz_dosya_adi("../../etc/passwd") == "passwd",
            "yol bileşenleri atılır")
    kontrol(_temiz_dosya_adi('a<b>c:d"e|f?g*h.txt')
            == "a_b_c_d_e_f_g_h.txt", "geçersiz karakterler '_' olur")
    kontrol(_temiz_dosya_adi("") == "ek", "boş ad 'ek' olur")
    kontrol(_temiz_dosya_adi("...") == "ek", "yalnız nokta 'ek' olur")
    kontrol(_temiz_dosya_adi("alt/yol/b.txt") == "b.txt",
            "alt dizin yolu tek ada indirgenir")

    with tempfile.TemporaryDirectory() as dizin:
        print("çakışan adlar")
        kontrol(_benzersiz_yol(dizin, "rapor.pdf")
                == os.path.join(dizin, "rapor.pdf"),
                "boş klasörde ad korunur")
        with open(os.path.join(dizin, "rapor.pdf"), "wb") as f:
            f.write(b"x")
        kontrol(_benzersiz_yol(dizin, "rapor.pdf")
                == os.path.join(dizin, "rapor (1).pdf"),
                "aynı ad ' (1)' alır")
        with open(os.path.join(dizin, "rapor (1).pdf"), "wb") as f:
            f.write(b"x")
        kontrol(_benzersiz_yol(dizin, "rapor.pdf")
                == os.path.join(dizin, "rapor (2).pdf"),
                "ikinci çakışma ' (2)' alır")

        print("toplu indirme")
        ekler = [
            Ek(ad="a.txt"),
            Ek(ad="../../yol/b.txt"),
            Ek(ad="bozuk.txt"),
            Ek(ad="a.txt"),
        ]
        sonuc = Postacim._ekleri_indir_cek(SahteAna(), ekler, dizin)
        kontrol(sonuc[0] == "ek_toplu", "sonuç türü ek_toplu")
        kaydedilen, hatalar, hedef = sonuc[1], sonuc[2], sonuc[3]
        kontrol(hedef == dizin, "hedef klasör korunur")
        kontrol(kaydedilen == ["a.txt", "b.txt", "a (1).txt"],
                f"kaydedilenler: {kaydedilen}")
        kontrol(len(hatalar) == 1 and "bozuk.txt" in hatalar[0],
                "başarısız ek hata listesinde")
        with open(os.path.join(dizin, "a.txt"), "rb") as f:
            kontrol(f.read() == b"veri:a.txt", "a.txt içeriği doğru")
        with open(os.path.join(dizin, "b.txt"), "rb") as f:
            kontrol(f.read() == b"veri:../../yol/b.txt",
                    "b.txt içeriği doğru")
        with open(os.path.join(dizin, "a (1).txt"), "rb") as f:
            kontrol(f.read() == b"veri:a.txt", "yinelenen ek ayrı dosyaya yazıldı")
        kontrol(not os.path.exists(os.path.join(dizin, "bozuk.txt")),
                "başarısız ek için dosya oluşmaz")

    if HATALAR:
        print(f"\n!! {len(HATALAR)} hata:")
        for h in HATALAR:
            print(f"   - {h}")
        return 1
    print("\n✓ tüm kontroller geçti")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
