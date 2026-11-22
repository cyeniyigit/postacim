#!/usr/bin/env python3
"""Kullanıcı adı biçimlerini dener.

Kurumda NTLM kullanıcı adı biçimi farklı olabilir (KURUM\\kullanici,
kullanici@kurum.gov.tr, kullanici@kurum.gov.tr ...). Kayıtlı parolayı
okur ve hangi biçimin kabul edildiğini bildirir. Parola ekrana yazılmaz.

Kullanım:  .venv/bin/python tests/kimlik_dene.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from postacim.config import Ayarlar
from postacim.ews import EwsHata, EwsIstemci


def main() -> int:
    ayarlar = Ayarlar()
    parola = ayarlar.al("parola", "")
    if not parola:
        print("Kayıtlı parola yok. Önce uygulamadan bir kez giriş yapın.")
        return 1

    temel = ayarlar.al("kullanici", "")
    parca = temel.split("@")[0] or temel
    denenen = [
        (temel, "kayıtlı biçim"),
        (f"KURUM\\{parca}", "KURUM\\kullanici"),
        (f"{parca}@kurum.gov.tr", "kullanici@kurum.gov.tr"),
        (f"{parca}@kurum.gov.tr", "kullanici@kurum.gov.tr"),
        (parca, "yalnız kullanıcı adı"),
        (f"KURUM\\{parca}", "KURUM\\kullanici"),
    ]

    for kullanici, aciklama in denenen:
        try:
            istemci = EwsIstemci(kullanici=kullanici, parola=parola)
            klasorler = istemci.klasor_listesi()
            if klasorler:
                print(f"✓ BAŞARILI — kullanıcı adı: {kullanici}   ({aciklama})")
                for kimlik, ad in klasorler:
                    print(f"    • {ad}  ({kimlik})")
                print("\nBu biçimi ~/.config/postacim/hesap.json içine yazıp uygulamayı yeniden başlatabilirsiniz.")
                return 0
            print(f"✗ 401 — {kullanici}   ({aciklama})")
        except EwsHata as exc:
            print(f"✗ {kullanici}   ({aciklama}) → {str(exc)[:80]}")
        except Exception as exc:
            print(f"? {kullanici} → {type(exc).__name__}: {str(exc)[:80]}")
    print("\nHiçbir biçim kabul edilmedi. Parola büyük/küçük harf duyarlıdır;")
    print("kurumda 'KURUM' alan adı doğruysa ve parola doğruysa EWS de kabul etmelidir.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
