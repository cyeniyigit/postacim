#!/usr/bin/env python3
"""EWS klasör işlemleri — çevrimdışı test (istek mock'lanır).

Kapsam:
  * `_klasor_id_xml`: bilinen 7 klasör DistinguishedFolderId, kullanıcı
    klasörleri FolderId ile yazılır
  * `klasor_olustur`: CreateFolder gövdesi + döndürülen FolderId + ad doğrulama
  * `klasor_listesi`: FindFolder ile kullanıcı klasörleri listeye eklenir;
    varsayılan adlar ve posta olmayan klasörler (takvim/kişiler) elenir;
    60 sn önbellek çalışır; FindFolder hatasında liste yine de dönülür
  * `tasi`: kullanıcı klasörüne taşımada FolderId kullanılır
  * FindFolder yetki hatası (401) yukarı fırlatılır

Kullanim:  .venv/bin/python tests/ews_klasor_test.py
"""
from __future__ import annotations

import os
import sys
from xml.etree import ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from postacim import ews as ews_mod  # noqa: E402

HATALAR = []


def kontrol(kosul, mesaj):
    if kosul:
        print(f"  ✓ {mesaj}")
    else:
        HATALAR.append(mesaj)
        print(f"  !! {mesaj}")


NS_XML = (
    'xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"'
    ' xmlns:t="http://schemas.microsoft.com/exchange/services/2006/types"'
    ' xmlns:m="http://schemas.microsoft.com/exchange/services/2006/messages"'
)


def zarf(icerik: str) -> str:
    return f'<soap:Envelope {NS_XML}>{icerik}</soap:Envelope>'


def getfolder_yaniti() -> str:
    klasorler = "".join(
        f'<t:Folder><t:DisplayName>{ad}</t:DisplayName>'
        f'<t:TotalCount>{i}</t:TotalCount><t:UnreadCount>0</t:UnreadCount>'
        "</t:Folder>"
        for i, ad in enumerate([
            "Gelen Kutusu", "Gönderilmiş", "Taslaklar", "Silinmiş Öğeler",
            "Önemsiz", "Arşiv", "Giden Kutusu",
        ])
    )
    return zarf(f"<m:Folders>{klasorler}</m:Folders>")


def findfolder_yaniti() -> str:
    return zarf(
        "<m:Folders>"
        "<t:Folder><t:FolderId Id=\"ID-PROJE\"/>"
        "<t:DisplayName>Proje X</t:DisplayName>"
        "<t:TotalCount>3</t:TotalCount><t:UnreadCount>1</t:UnreadCount>"
        "<t:FolderClass>IPF.Note</t:FolderClass></t:Folder>"
        # varsayılan klasör → elenmeli (GetFolder'da zaten var)
        "<t:Folder><t:FolderId Id=\"ID-INBOX\"/>"
        "<t:DisplayName>Inbox</t:DisplayName>"
        "<t:TotalCount>9</t:TotalCount><t:UnreadCount>0</t:UnreadCount>"
        "</t:Folder>"
        # posta olmayan klasör → elenmeli
        "<t:Folder><t:FolderId Id=\"ID-TAKVIM\"/>"
        "<t:DisplayName>Takvim</t:DisplayName>"
        "<t:FolderClass>IPF.Appointment</t:FolderClass></t:Folder>"
        "</m:Folders>"
    )


def createfolder_yaniti(kimlik: str) -> str:
    return zarf(
        "<m:Folders><t:Folder>"
        f'<t:FolderId Id="{kimlik}" ChangeKey="AQAAAB=="/>'
        "<t:DisplayName>Notlar</t:DisplayName>"
        "</t:Folder></m:Folders>"
    )


def degiskey_yaniti(kimlik: str) -> str:
    """Klasörün güncel ChangeKey'i (yeniden adlandırma öncesi GetFolder)."""
    return zarf(
        "<m:Folders><t:Folder>"
        f'<t:FolderId Id="{kimlik}" ChangeKey="CK-GUNCEL"/>'
        "</t:Folder></m:Folders>"
    )


def updatefolder_yaniti(kimlik: str) -> str:
    return zarf(
        "<m:UpdateFolderResponseMessage ResponseClass=\"Success\">"
        "<m:ResponseCode>NoError</m:ResponseCode>"
        "<m:Folders><t:Folder>"
        f'<t:FolderId Id="{kimlik}" ChangeKey="CK-YENI"/>'
        "<t:DisplayName>Yeni Ad</t:DisplayName>"
        "</t:Folder></m:Folders>"
        "</m:UpdateFolderResponseMessage>"
    )


def main() -> int:
    print("== ews: klasör oluşturma + kullanıcı klasörleri ==")
    istemci = ews_mod.EwsIstemci(
        "mail.ornek.gov.tr", "KURUM\\kisi", "ornek-parola"
    )

    # --- _klasor_id_xml ---
    kontrol(
        ews_mod._klasor_id_xml("inbox")
        == '<t:DistinguishedFolderId Id="inbox"/>',
        "bilinen klasör DistinguishedFolderId ile yazılır",
    )
    kontrol(
        ews_mod._klasor_id_xml("ID-ABC/1==")
        == '<t:FolderId Id="ID-ABC/1=="/>',
        "kullanıcı klasörü FolderId ile yazılır",
    )

    # --- klasor_olustur ---
    istekler: list[str] = []

    def sahte_istek(govde: str, tekrar: int = 3):
        istekler.append(govde)
        if "CreateFolder" in govde:
            return ET.fromstring(createfolder_yaniti("ID-NOTLAR"))
        if "UpdateFolder" in govde:
            return ET.fromstring(updatefolder_yaniti("ID-PROJE"))
        if "FindFolder" in govde:
            return ET.fromstring(findfolder_yaniti())
        if "GetFolder" in govde and '<t:FolderId Id="ID-PROJE"' in govde:
            # Kullanıcı klasörünün güncel ChangeKey'i isteniyor
            return ET.fromstring(degiskey_yaniti("ID-PROJE"))
        return ET.fromstring(getfolder_yaniti())

    istemci.istek = sahte_istek  # noqa: SLF001 — test amaçlı değiştirme
    kimlik = istemci.klasor_olustur("Notlar")
    kontrol(kimlik == "ID-NOTLAR", f"CreateFolder FolderId döndürür ({kimlik})")
    govde = istekler[-1]
    kontrol(
        '<m:ParentFolderId><t:DistinguishedFolderId Id="msgfolderroot"/>'
        "</m:ParentFolderId>" in govde,
        "CreateFolder kökte açılır (msgfolderroot)",
    )
    kontrol("<t:DisplayName>Notlar</t:DisplayName>" in govde,
            "klasör adı gövdede")
    kontrol(
        '<t:DisplayName>&lt;deneme&gt;</t:DisplayName>'
        in (
            (istemci.klasor_olustur("<deneme>"), istekler[-1])[1]
        ),
        "klasör adı XML'e kaçışlı yazılır",
    )
    kontrol(istemci._ozel_klasor_onbellek is None,
            "oluşturma FindFolder önbelleğini düşürür")
    try:
        istemci.klasor_olustur("   ")
        kontrol(False, "boş klasör adı hata fırlatmalı")
    except ews_mod.EwsHata as exc:
        kontrol("boş" in str(exc), f"boş ad reddedildi ({exc})")

    # --- klasor_listesi: kullanıcı klasörleri eklenir, varsayılanlar tek ---
    klasorler = istemci.klasor_listesi()
    adlar = [k.ad for k in klasorler]
    kontrol(len(klasorler) == 8,
            f"7 varsayılan + 1 kullanıcı klasörü ({adlar})")
    kontrol("Proje X" in adlar, "kullanıcı klasörü listede")
    kontrol("Inbox" not in adlar and "Takvim" not in adlar,
            "varsayılan/posta olmayan klasörler elenir")
    proje = next(k for k in klasorler if k.ad == "Proje X")
    kontrol((proje.kimlik, proje.toplam, proje.okunmamis)
            == ("ID-PROJE", 3, 1),
            "kullanıcı klasörü sayaçları okundu")

    # --- 60 sn önbellek: ikinci çağrıda FindFolder istenmez ---
    find_sayisi = sum(1 for g in istekler if "FindFolder" in g)
    istemci.klasor_listesi()
    find_sayisi_2 = sum(1 for g in istekler if "FindFolder" in g)
    kontrol(find_sayisi == find_sayisi_2,
            "önbellek süresi dolmadan FindFolder tekrarlanmaz")

    # --- klasor_yeniden_adlandir: GetFolder (ChangeKey) + UpdateFolder ---
    istemci.istek = sahte_istek
    istemci._ozel_klasor_onbellek = ["eski"]  # düşürülceğini görmek için
    istekler.clear()
    donen = istemci.klasor_yeniden_adlandir("ID-PROJE", "Yeni Ad")
    kontrol(donen == "ID-PROJE", "EWS'te kimlik adlandırmada değişmez")
    istekler_y = [g for g in istekler if "UpdateFolder" in g]
    kontrol(len(istekler_y) == 1, "UpdateFolder bir kez gönderildi")
    govde = istekler_y[0]
    kontrol('FieldURI="folder:DisplayName"' in govde,
            "DisplayName alanı güncelleniyor")
    kontrol("<t:DisplayName>Yeni Ad</t:DisplayName>" in govde,
            "yeni ad gövdede")
    kontrol('<t:FolderId Id="ID-PROJE" ChangeKey="CK-GUNCEL"/>' in govde,
            "güncel ChangeKey GetFolder'dan alınıp kullanıldı")
    kontrol(istemci._ozel_klasor_onbellek is None,
            "adlandırma FindFolder önbelleğini düşürür")
    try:
        istemci.klasor_yeniden_adlandir("inbox", "Gelen 2")
        kontrol(False, "varsayılan klasör adlandırılmamalı")
    except ews_mod.EwsHata as exc:
        kontrol("adlandırılamaz" in str(exc),
                f"varsayılan klasör koruması ({exc})")
    try:
        istemci.klasor_yeniden_adlandir("ID-PROJE", "   ")
        kontrol(False, "boş yeni ad hata fırlatmalı")
    except ews_mod.EwsHata as exc:
        kontrol("boş" in str(exc), f"boş ad reddedildi ({exc})")

    # --- FindFolder hatası: liste yine de dönülür ---
    istemci._ozel_klasor_onbellek = None
    istemci._ozel_klasor_zaman = 0.0
    istek_sayaci = {"n": 0}

    def hatali_istek(govde: str, tekrar: int = 3):
        if "FindFolder" in govde:
            raise ews_mod.EwsHata("FindFolder desteklenmiyor")
        return ET.fromstring(getfolder_yaniti())

    istemci.istek = hatali_istek
    klasorler = istemci.klasor_listesi()
    kontrol(len(klasorler) == 7,
            "FindFolder hatasında 7 varsayılan klasörle devam")
    kontrol(all(k.kimlik in ews_mod.KLASORLER for k in klasorler),
            "hatada yalnız bilinen kimlikler")

    # --- Yetki hatası yukarı fırlatılır ---
    def yetki_istek(govde: str, tekrar: int = 3):
        if "FindFolder" in govde:
            raise ews_mod.EwsYetkiHatasi("401")
        return ET.fromstring(getfolder_yaniti())

    istemci.istek = yetki_istek
    istemci._ozel_klasor_onbellek = None
    istemci._ozel_klasor_zaman = 0.0
    try:
        istemci.klasor_listesi()
        kontrol(False, "yetki hatası yukarı fırlatılmalı")
    except ews_mod.EwsYetkiHatasi:
        kontrol(True, "yetki hatası yukarı fırlatıldı")

    # --- tasi: kullanıcı klasörüne taşıma FolderId ister ---
    mesaj = ews_mod.Mesaj(item_id="AAA=", change_key="CK==", konu="Deneme")
    istemci.istek = sahte_istek
    istekler.clear()
    istemci.tasi(mesaj, hedef="ID-PROJE")
    kontrol('<t:FolderId Id="ID-PROJE"/>' in istekler[-1],
            "kullanıcı klasörüne taşıma FolderId ile")
    istemci.tasi(mesaj, hedef="deleteditems")
    kontrol('<t:DistinguishedFolderId Id="deleteditems"/>' in istekler[-1],
            "Silinmiş Öğeler'e taşıma DistinguishedFolderId ile")

    if HATALAR:
        print(f"\n!! {len(HATALAR)} HATA:")
        for h in HATALAR:
            print("   ", h)
        return 1
    print("\n✓ ews klasör testi geçti")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
