#!/usr/bin/env python3
"""SyncFolderItems tabanli listelemeyi ve EWS yazma islemlerini dogrular.

Kullanim:  .venv/bin/python tests/sync_dene.py
"""
import os
import sys
import time
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from postacim.config import Ayarlar
from postacim.ews import NS, EwsHata, EwsIstemci


def sync_govdesi(klasor, sync_state="", en_fazla=512, sekil="IdOnly"):
    if sekil == "IdOnly":
        shape = (
            "<m:ItemShape><t:BaseShape>IdOnly</t:BaseShape>"
            "<t:AdditionalProperties>"
            '<t:FieldURI FieldURI="Subject"/>'
            '<t:FieldURI FieldURI="From"/>'
            '<t:FieldURI FieldURI="DateTimeReceived"/>'
            '<t:FieldURI FieldURI="IsRead"/>'
            '<t:FieldURI FieldURI="Preview"/>'
            "</t:AdditionalProperties></m:ItemShape>"
        )
    else:
        shape = "<m:ItemShape><t:BaseShape>AllProperties</t:BaseShape></m:ItemShape>"
    state = f"<m:SyncState>{sync_state}</m:SyncState>" if sync_state else "<m:SyncState/>"
    return (
        "<m:SyncFolderItems>"
        f"{shape}"
        f"<m:SyncFolderId><t:DistinguishedFolderId Id=\"{klasor}\"/></m:SyncFolderId>"
        f"{state}"
        f"<m:Ignore/><m:MaxChangesReturned>{en_fazla}</m:MaxChangesReturned>"
        "</m:SyncFolderItems>"
    )


def main() -> int:
    ayarlar = Ayarlar()
    cl = EwsIstemci(kullanici=ayarlar.al("kullanici"), parola=ayarlar.al("parola"))

    print("=" * 72)
    print("1) SyncFolderItems — inbox tam senkronizasyon")
    print("=" * 72)
    state = ""
    toplam = 0
    sayfa = 0
    ilk_tarih = son_tarih = None
    baslangic = time.time()
    while True:
        try:
            kok = cl.istek(sync_govdesi("inbox", state))
        except EwsHata as exc:
            print(f"  ✗ hata: {str(exc)[:160]}")
            break
        sayfa += 1
        degis = kok.findall(".//m:Changes/*", NS)
        mesajlar = kok.findall(".//m:Changes/t:Create/t:Message", NS)
        st = kok.find(".//m:SyncState", NS)
        son = kok.find(".//m:IncludesLastItemInRange", NS)
        state = st.text if st is not None and st.text else ""
        toplam += len(mesajlar)
        tarihler = []
        for m in mesajlar:
            t = m.findtext("t:DateTimeReceived", "", NS)
            if t:
                tarihler.append(t)
        if tarihler:
            ilk_tarih = ilk_tarih or tarihler[0]
            son_tarih = tarihler[-1]
        print(f"  sayfa {sayfa}: {len(degis)} değişiklik / {len(mesajlar)} mesaj | "
              f"son mu: {son.text if son is not None else '?'} | state {len(state)} krk")
        if son is not None and son.text == "true":
            break
        if sayfa > 20:
            break
    print(f"  → toplam {toplam} mesaj ({time.time() - baslangic:.1f} sn)")
    print(f"  → tarih aralığı: {ilk_tarih} … {son_tarih}")

    print("\n" + "=" * 72)
    print("2) Diğer klasörler")
    print("=" * 72)
    for klasor in ("sentitems", "drafts", "deleteditems", "junkemail", "outbox", "archive"):
        try:
            kok = cl.istek(sync_govdesi(klasor))
            mesajlar = kok.findall(".//m:Changes/t:Create/t:Message", NS)
            st = kok.find(".//m:SyncState", NS)
            print(f"  ✓ {klasor:14} {len(mesajlar):4} mesaj | state {len(st.text) if st is not None and st.text else 0} krk")
        except EwsHata as exc:
            print(f"  ✗ {klasor:14} {str(exc)[:120]}")

    print("\n" + "=" * 72)
    print("3) Yazma işlemleri (kendi taslağı üzerinde)")
    print("=" * 72)
    taslak_id = ""
    try:
        kok = cl.istek(
            '<m:CreateItem SendMeetingInvitationsOrCancellations="SendToNone" MessageDisposition="SaveOnly">'
            '<m:SavedItemFolderId><t:DistinguishedFolderId Id="drafts"/></m:SavedItemFolderId>'
            "<m:Items><t:Message><t:Subject>Sync testi taslağı</t:Subject>"
            "<t:Body BodyType=\"Text\">geçici</t:Body></t:Message></m:Items>"
            "</m:CreateItem>"
        )
        el = kok.find(".//m:Items/t:Message/t:ItemId", NS)
        taslak_id = el.get("Id") if el is not None else ""
        ck = el.get("ChangeKey") if el is not None else ""
        print(f"  ✓ CreateItem(SaveOnly): {taslak_id[:36]}...")
    except EwsHata as exc:
        print(f"  ✗ CreateItem: {str(exc)[:160]}")

    if taslak_id:
        try:
            cl.istek(
                '<m:UpdateItem ConflictResolution="AutoResolve" MessageDisposition="SaveOnly">'
                "<m:ItemChanges><m:ItemChange>"
                f'<t:ItemId Id="{taslak_id}" ChangeKey="{ck}"/>'
                "<t:Updates><t:SetItemField>"
                '<t:FieldURI FieldURI="message:IsRead"/>'
                "<t:Message><t:IsRead>true</t:IsRead></t:Message>"
                "</t:SetItemField></t:Updates>"
                "</m:ItemChange></m:ItemChanges></m:UpdateItem>"
            )
            print("  ✓ UpdateItem (okundu işaretle) OK")
        except EwsHata as exc:
            print(f"  ✗ UpdateItem: {str(exc)[:160]}")

        try:
            cl.tasi(type("M", (), {"item_id": taslak_id})(), "deleteditems")
            print("  ✓ MoveItem → deleteditems OK")
        except EwsHata as exc:
            print(f"  ✗ MoveItem: {str(exc)[:160]}")

        try:
            cl.kalici_sil(type("M", (), {"item_id": taslak_id})())
            print("  ✓ DeleteItem (HardDelete) OK")
        except EwsHata as exc:
            print(f"  ✗ DeleteItem: {str(exc)[:160]}")

    print("\n" + "=" * 72)
    print("4) SyncState devamı (ikinci tur) — yeni değişiklik yoksa boş döner mi?")
    print("=" * 72)
    try:
        kok = cl.istek(sync_govdesi("inbox"))
        st = kok.find(".//m:SyncState", NS)
        state = st.text
        kok2 = cl.istek(sync_govdesi("inbox", state))
        d2 = kok2.findall(".//m:Changes/*", NS)
        son2 = kok2.find(".//m:IncludesLastItemInRange", NS)
        print(f"  ✓ devam: {len(d2)} değişiklik, son mu: {son2.text if son2 is not None else '?'}")
    except EwsHata as exc:
        print(f"  ✗ {str(exc)[:160]}")

    print("\n" + "=" * 72)
    print("5) Geçersiz SyncState davranışı")
    print("=" * 72)
    try:
        cl.istek(sync_govdesi("inbox", "bozukDurum123"))
        print("  ? hata vermedi")
    except EwsHata as exc:
        print(f"  ✓ {str(exc)[:160]}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
