#!/usr/bin/env python3
"""ResolveNames (kişi çözümleme) canlı testi — kurum ağındayken çalıştırın.

Kime/Bilgi alanındaki "yazınca kişi bulma" özelliğinin dayandığı EWS
`ResolveNames` işleminin bu sunucuda çalışıp çalışmadığını doğrular.

Kullanım:  .venv/bin/python tests/cozum_dene.py [aranacak_parça]
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from postacim.config import Ayarlar
from postacim.ews import NS, EwsHata, EwsIstemci


def main() -> int:
    parca = sys.argv[1] if len(sys.argv) > 1 else ""
    ayarlar = Ayarlar()
    kullanici = ayarlar.al("kullanici", "")
    parola = ayarlar.al("parola", "")
    if not (kullanici and parola):
        print("Kayıtlı kimlik yok. Önce uygulamadan bir kez giriş yapın.")
        return 1

    istemci = EwsIstemci(
        sunucu=ayarlar.al("sunucu", "mail.kurum.gov.tr"),
        kullanici=kullanici,
        parola=parola,
        yontem=ayarlar.al("yontem", "ntlm"),
    )
    if not parca:
        parca = kullanici.split("\\")[-1].split("@")[0].split(".")[0]
        print(f"Parça verilmedi; kendi adınızın parçasıyla deneniyor: {parca!r}")

    print("\n--- cozumle() — uygulamanın kullandığı yol ---")
    try:
        sonuc = istemci.cozumle(parca)
    except EwsHata as exc:
        print(f"  HATA: {exc}")
        sonuc = None
    if sonuc is not None:
        for ad, eposta in sonuc[:15]:
            print(f"  - {ad} <{eposta}>")
        print(f"  toplam {len(sonuc)} çözüm")

    for kapsam in ("ContactsActiveDirectory", "ActiveDirectory"):
        print(f"\n--- ham ResolveNames SearchScope={kapsam} ---")
        try:
            govde = (
                "<m:ResolveNames ReturnFullContactData=\"false\" "
                f"SearchScope=\"{kapsam}\">"
                f"<m:UnresolvedEntry>{parca}</m:UnresolvedEntry>"
                "</m:ResolveNames>"
            )
            kok = istemci.istek(govde)
        except EwsHata as exc:
            print(f"  HATA: {exc}")
            continue
        cozumler = kok.findall(".//t:Resolution", NS) or kok.findall(".//m:Resolution", NS)
        if not cozumler:
            print("  eşleşme yok")
            continue
        for cozum in cozumler[:15]:
            kutu = cozum.find("t:Mailbox", NS)
            ad = kutu.find("t:Name", NS) if kutu is not None else None
            ep = kutu.find("t:EmailAddress", NS) if kutu is not None else None
            print(f"  - {(ad.text if ad is not None else '?')} <{(ep.text if ep is not None else '?')}>")
        print(f"  toplam {len(cozumler)} çözüm")
    return 0


if __name__ == "__main__":
    sys.exit(main())
