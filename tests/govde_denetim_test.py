#!/usr/bin/env python3
"""Gövde çökme denetimi testleri (postacim/govde_denetim.py).

Kapsam:
  * Temiz HTML alt süreç denetiminden geçer (True).
  * Tkhtml'i çökerten HTML (hücresiz iç içe tablo) False döndürür.
  * Denetçi bir süreç hatasında None döndürür (gösterim engellenmez).
  * Çökme kaydı hata.log'a eklenir.
  * govde_metin_gosterim güvenli metin gösterimi üretir: metin
    kaçırılır, resim yer tutucuları tıklanabilir bağlantıdır, çözülen
    resim yer tutucunun yanında belirir.
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

HATALAR = []


def kontrol(kosul, aciklama):
    if kosul:
        print(f"  ✓ {aciklama}")
    else:
        print(f"  ✗ {aciklama}")
        HATALAR.append(aciklama)


# tkinterweb HTML'i çökerten bilinen yapı: çocuğu doğrudan <table> olan
# tablo (onarım katmanı atlanıp ham verildiğinde segfault üretir).
COKERTICI = "<html><body><table><table><tr><td>x</td></tr></table></table></body></html>"
TEMIZ = "<html><body><p>merhaba dünya</p></body></html>"


def test_html_guvenli_mi():
    print("\n— html_guvenli_mi —")
    from postacim.govde_denetim import html_guvenli_mi

    kontrol(
        html_guvenli_mi(TEMIZ) is True,
        "temiz HTML alt süreçte hayatta kalır (True)",
    )
    kontrol(
        html_guvenli_mi(COKERTICI) is False,
        "hücresiz iç içe tablo çökme üretir (False)",
    )
    kontrol(html_guvenli_mi("") is True, "boş HTML denetimsiz geçer")


def test_cokme_logla():
    print("\n— cokme_logla —")
    from postacim.govde_denetim import cokme_logla

    with tempfile.TemporaryDirectory() as dizin:
        os.environ["XDG_STATE_HOME"] = dizin
        try:
            yol = cokme_logla("test çökmesi • ilet: abc")
            kontrol(yol is not None, "kayıt yolu döndürülür")
            if yol:
                icerik = open(yol, encoding="utf-8").read()
                kontrol("test çökmesi" in icerik, "kayıt içeriği yazılır")
        finally:
            os.environ.pop("XDG_STATE_HOME", None)


def test_govde_metin_gosterim():
    print("\n— govde_metin_gosterim —")
    from postacim.ews import RESIM_SEMASI, Mesaj, Resim, govde_metin_gosterim

    mesaj = Mesaj(
        konu="deneme",
        govde="Selam <kral> & dostlar\n[resim: logo.png] sonrası",
        resimler=[Resim(ad="logo.png", yer_tutucu="[resim: logo.png]")],
    )
    cikti = govde_metin_gosterim(mesaj)
    kontrol("&lt;kral&gt; &amp; dostlar" in cikti, "metin kaçırılmış basılır")
    kontrol(
        f'<a href="{RESIM_SEMASI}0">[resim: logo.png]</a>' in cikti,
        "resim yer tutucusu tıklanabilir bağlantıdır",
    )
    kontrol("<pre>" in cikti, "gövde <pre> içinde tek parça metindir")
    # Çözülen resim yer tutucunun yanında <img> olarak belirir
    cikti2 = govde_metin_gosterim(mesaj, gecen={0: '<img src="data:image/png;base64,QUJD">'})
    kontrol(
        "data:image/png;base64,QUJD" in cikti2
        and f'href="{RESIM_SEMASI}0"' not in cikti2,
        "çözülen resim yer tutucunun yerine geçer",
    )
    # Yer tutucu bulunamayan resim zarar vermez
    mesaj2 = Mesaj(govde="yer tutucu yok", resimler=[Resim(ad="x.png", yer_tutucu="[yok]")])
    kontrol("(gövde yok)" not in govde_metin_gosterim(mesaj2), "eksik yer tutucu yok sayılır")


def main() -> int:
    test_html_guvenli_mi()
    test_cokme_logla()
    test_govde_metin_gosterim()
    print()
    if HATALAR:
        print(f"BAŞARISIZ: {len(HATALAR)} kontrol")
        return 1
    print("Tüm kontroller geçti.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
