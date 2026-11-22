#!/usr/bin/env python3
"""FindItem 500 hatasini teşhis eder.

Gecen bulgu: GetFolder calisiyor, FindItem "An internal server error occurred"
donuyor. Bu script farkli FindItem varyantlarini dener:
  - BaseShape: AllProperties / Default / IdOnly
  - ItemView vs IndexedPageItemView
  - SortOrder var/yok
  - ParentFolderIds: DistinguishedFolderId / GetFolder'dan gelen FolderId
  - ServerVersion farklari
  - GetItem calisiyor mu (bulma yontemi)

Kullanım:  .venv/bin/python tests/finditem_dene.py
"""
import os
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from postacim.config import Ayarlar
from postacim.ews import NS, EwsHata, EwsIstemci

VARYANTLAR = []


def variant(ad):
    def kaydet(fn):
        VARYANTLAR.append((ad, fn))
        return fn
    return kaydet


def govde_olustur(shape="AllProperties", sayfa="Indexed", sort=True,
                  restriction="", parent='<t:DistinguishedFolderId Id="inbox"/>'):
    parcalar = [
        "<m:FindItem Traversal=\"Shallow\">",
        f"<t:ItemShape><t:BaseShape>{shape}</t:BaseShape></t:ItemShape>",
    ]
    if sayfa == "Indexed":
        parcalar.append('<t:IndexedPageItemView MaxEntriesReturned="5" Offset="0" BasePoint="Beginning"/>')
    elif sayfa == "IndexedNoBase":
        parcalar.append('<t:IndexedPageItemView MaxEntriesReturned="5" Offset="0"/>')
    elif sayfa == "ItemView":
        parcalar.append('<t:ItemView MaxEntriesReturned="5" Offset="0" BasePoint="Beginning"/>')
    if restriction:
        parcalar.append(restriction)
    if sort:
        parcalar.append('<m:SortOrder><t:MessageSortOrder Order="Descending"/></m:SortOrder>')
    parcalar.append(f"<m:ParentFolderIds>{parent}</m:ParentFolderIds>")
    parcalar.append("</m:FindItem>")
    return "".join(parcalar)


def dene(istemci, ad, govde, surum=None):
    eski = istemci.surum
    if surum:
        istemci.surum = surum
    try:
        kok = istemci.istek(govde)
        adet = len(kok.findall(".//m:Items/t:Message", NS))
        toplam_el = kok.find(".//m:IndexedPageItemView", NS)
        toplam = toplam_el.get("TotalItemsInView") if toplam_el is not None else "?"
        print(f"  ✓ {ad}: {adet} mesaj (toplam={toplam})")
        return True
    except EwsHata as exc:
        print(f"  ✗ {ad}: {str(exc)[:150]}")
        return False
    except Exception as exc:
        print(f"  ? {ad}: {type(exc).__name__}: {str(exc)[:120]}")
        return False
    finally:
        istemci.surum = eski


def main() -> int:
    ayarlar = Ayarlar()
    parola = ayarlar.al("parola", "")
    if not parola:
        print("Kayitli parola yok.")
        return 1
    kullanici = ayarlar.al("kullanici", "")
    istemci = EwsIstemci(kullanici=kullanici, parola=parola)

    print(f"→ {istemci.adres}")
    try:
        klasorler = istemci.klasor_listesi()
    except EwsHata as exc:
        print(f"BAĞLANTI BAŞARISIZ: {exc}")
        return 1
    print(f"✓ GetFolder çalışıyor. Klasörler: {klasorler}")
    print(f"  sunucu sürümü: {istemci.surum}")

    # --- inbox için gerçek FolderId al ---
    govde = (
        "<m:GetFolder>"
        "<m:FolderShape><t:BaseShape>AllProperties</t:BaseShape></m:FolderShape>"
        "<m:FolderIds><t:DistinguishedFolderId Id=\"inbox\"/></m:FolderIds>"
        "</m:GetFolder>"
    )
    kok = istemci.istek(govde)
    fid_el = kok.find(".//t:FolderId", NS)
    folder_id = ""
    if fid_el is not None:
        folder_id = f'<t:FolderId Id="{fid_el.get("Id")}" ChangeKey="{fid_el.get("ChangeKey","")}"/>'
    print(f"  inbox FolderId: {fid_el.get('Id') if fid_el is not None else 'YOK'}")

    print("\n[1] FindItem varyantları (inbox):")
    dene(istemci, "AllProperties + Indexed + Sort", govde_olustur())
    dene(istemci, "Default shape", govde_olustur(shape="Default"))
    dene(istemci, "IdOnly shape", govde_olustur(shape="IdOnly"))
    dene(istemci, "Indexed (BasePoint yok)", govde_olustur(sayfa="IndexedNoBase"))
    dene(istemci, "ItemView", govde_olustur(sayfa="ItemView"))
    dene(istemci, "SortOrder yok", govde_olustur(sort=False))
    dene(istemci, "FolderId ile parent", govde_olustur(parent=folder_id))
    dene(istemci, "ItemView + FolderId", govde_olustur(sayfa="ItemView", parent=folder_id))
    dene(istemci, "IdOnly + ItemView + FolderId", govde_olustur(shape="IdOnly", sayfa="ItemView", parent=folder_id))

    print("\n[2] ServerVersion varyantları:")
    for s in ("Exchange2013_SP1", "Exchange2013", "Exchange2010_SP2"):
        dene(istemci, f"{s} + IdOnly", govde_olustur(shape="IdOnly"), surum=s)

    print("\n[3] FindItem başka klasörlerde (IdOnly + ItemView):")
    for klasor in ("sentitems", "drafts", "deleteditems", "outbox", "junkemail", "archive"):
        dene(istemci, klasor, govde_olustur(shape="IdOnly", sayfa="ItemView",
                                             parent=f'<t:DistinguishedFolderId Id="{klasor}"/>'))

    print("\n[4] FindItem Traversal/Shallow varyantları:")
    dene(istemci, "Associated + ItemView",
         govde_olustur(shape="IdOnly", sayfa="ItemView").replace('Traversal="Shallow"', 'Traversal="Associated"'))
    dene(istemci, "SoftDeleted",
         govde_olustur(shape="IdOnly", sayfa="ItemView").replace('Traversal="Shallow"', 'Traversal="SoftDeleted"'))

    print("\n[5] ResolveFolder + FindItem (klasör id'sini sunucudan al):")
    try:
        govde2 = (
            "<m:ResolveFolder>"
            "<m:FolderIds><t:DistinguishedFolderId Id=\"inbox\"/></m:FolderIds>"
            "</m:ResolveFolder>"
        )
        kok2 = istemci.istek(govde2)
        rf = kok2.find(".//t:FolderId", NS)
        if rf is not None:
            pid = f'<t:FolderId Id="{rf.get("Id")}" ChangeKey="{rf.get("ChangeKey","")}"/>'
            dene(istemci, "ResolveFolder id ile FindItem", govde_olustur(shape="IdOnly", parent=pid))
    except EwsHata as exc:
        print(f"  ✗ ResolveFolder: {str(exc)[:150]}")

    print("\n[6] GetItem testi (Sunucu tarafı okuma çalışıyor mu?):")
    # FindItem calismiyorsa item id bilmiyoruz; inbox'ta tek oge aramak icin
    # FindItem yerine EWS 'ExistentIds' deneriz; once FolderView deneyelim.
    for govde3, ad in (
        ('<m:GetFolder><m:FolderShape><t:BaseShape>AllProperties</t:BaseShape></m:FolderShape>'
         '<m:FolderIds><t:DistinguishedFolderId Id="inbox"/></m:FolderIds></m:GetFolder>', "GetFolder inbox"),
        ('<m:FindItem Traversal="Shallow"><t:ItemShape><t:BaseShape>AllProperties</t:BaseShape></t:ItemShape>'
         '<t:IndexedPageItemView MaxEntriesReturned="1" Offset="0" BasePoint="Beginning"/>'
         '<m:ParentFolderIds><t:DistinguishedFolderId Id="inbox"/></m:ParentFolderIds></m:FindItem>', "FindItem minimal"),
    ):
        try:
            kok3 = istemci.istek(govde3)
            print(f"  ✓ {ad}: OK")
        except EwsHata as exc:
            print(f"  ✗ {ad}: {str(exc)[:150]}")

    print("\n[7] FindFolder (klasör ağacı) çalışıyor mu:")
    try:
        govde4 = (
            "<m:FindFolder Traversal=\"Shallow\">"
            "<m:FolderShape><t:BaseShape>AllProperties</t:BaseShape></m:FolderShape>"
            "<m:ParentFolderIds><t:DistinguishedFolderId Id=\"msgfolderroot\"/></m:ParentFolderIds>"
            "</m:FindFolder>"
        )
        kok4 = istemci.istek(govde4)
        alt = kok4.findall(".//m:Folders/t:Folder", NS)
        print(f"  ✓ FindFolder: {len(alt)} alt klasör")
        for a in alt:
            ad_el = a.find("t:DisplayName", NS)
            print(f"     • {ad_el.text if ad_el is not None else '?'}")
    except EwsHata as exc:
        print(f"  ✗ FindFolder: {str(exc)[:150]}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
