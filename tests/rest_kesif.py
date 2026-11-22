#!/usr/bin/env python3
"""Exchange REST API (/api/v2.0) yetenek kesfi.

Kullanim:  .venv/bin/python tests/rest_kesif.py
"""
import json
import os
import sys

import requests
from requests_ntlm import HttpNtlmAuth

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from postacim.config import Ayarlar

SUNUCU = "mail.kurum.gov.tr"
API = f"https://{SUNUCU}/api/v2.0"


def main() -> int:
    ayarlar = Ayarlar()
    kullanici = ayarlar.al("kullanici", "")
    parola = ayarlar.al("parola", "")
    s = requests.Session()
    s.auth = HttpNtlmAuth(kullanici, parola)
    s.headers.update({"Accept": "application/json"})

    def get(yol, **kw):
        return s.get(f"{API}{yol}", timeout=40, **kw)

    print("1) Klasörler")
    r = get("/me/mailFolders")
    print(f"   HTTP {r.status_code}")
    if r.status_code == 200:
        veri = r.json()
        with open("/tmp/opencode/rest_klasorler.json", "w", encoding="utf-8") as f:
            json.dump(veri, f, indent=2, ensure_ascii=False)
        for f in veri.get("value", []):
            print(f"   • id={str(f.get('id')):24} displayName={str(f.get('displayName')):22} "
                  f"total={f.get('totalItemCount')} unread={f.get('unreadItemCount')} "
                  f"child={f.get('childFolderCount')}")

    print("\n2) Gelen kutusu mesajları (sayfalama + sıralama)")
    r = get("/me/mailFolders/inbox/messages?$top=5&$orderby=ReceivedDateTime desc")
    print(f"   HTTP {r.status_code}")
    mesajlar = []
    if r.status_code == 200:
        veri = r.json()
        mesajlar = veri.get("value", [])
        print(f"   {len(mesajlar)} mesaj, anahtarlar: {list(mesajlar[0].keys()) if mesajlar else '-'}")
        for m in mesajlar:
            print(f"   • {m.get('receivedDateTime','')[:19]}  {m.get('from',{}).get('emailAddress',{}).get('address','?'):38}"
                  f"  okundu={m.get('isRead')}  ek={m.get('hasAttachments')}")
            print(f"       konu: {m.get('subject')}")
        print(f"   @odata.nextLink: {veri.get('@odata.nextLink')}")
    else:
        print("   " + r.text[:300])

    if not mesajlar:
        print("\n   (mesaj yok, diğer adımlar atlandı)")
        return 1

    kimlik = mesajlar[0]["id"]

    print("\n3) Tek mesaj (id ile)")
    r = get(f"/me/messages/{kimlik}")
    print(f"   HTTP {r.status_code}")
    if r.status_code == 200:
        m = r.json()
        for k, v in m.items():
            if isinstance(v, (str, int, float, bool)) or v is None:
                print(f"   • {k}: {str(v)[:110]}")

    print("\n4) Gövde")
    for uygulama in ("text", "html"):
        r = get(f"/me/messages/{kimlik}/body?$top=1&contentType={uygulama}")
        if r.status_code == 200:
            try:
                j = r.json()
                icerik = j.get("content", "")
                print(f"   {uygulama}: {len(icerik)} karakter → {repr(icerik[:150])}")
            except Exception:
                print(f"   {uygulama}: {len(r.text)} bayt → {repr(r.text[:150])}")
        else:
            print(f"   {uygulama}: HTTP {r.status_code} {r.text[:120]}")

    print("\n5) Ekler")
    r = get(f"/me/messages/{kimlik}/attachments")
    print(f"   HTTP {r.status_code} → {r.text[:220]}")

    print("\n6) Arama (filter)")
    for f in ("contains(subject,'a')", "from/emailAddress/address eq 'kullanici@ornek.gov.tr'",
              "isRead eq false", "receivedDateTime ge 2020-01-01T00:00:00Z"):
        r = get(f"/me/mailFolders/inbox/messages?$top=3&$filter={requests.utils.quote(f)}")
        sayi = "-"
        if r.status_code == 200:
            sayi = len(r.json().get("value", []))
        print(f"   $filter={f[:60]:60} → {r.status_code} ({sayi} sonuç) {'' if r.status_code==200 else r.text[:100]}")

    print("\n7) Sayfalama ($skip / $top / $orderby)")
    for q in ("?$top=3&$skip=2&$orderby=ReceivedDateTime desc",
              "?$top=3&$orderby=ReceivedDateTime asc",
              "?$top=3&$select=Subject,From,IsRead",
              "?$top=3&$filter=hasAttachments eq true"):
        r = get(f"/me/mailFolders/inbox/messages{q}")
        sayi = "-"
        if r.status_code == 200:
            sayi = len(r.json().get("value", []))
        print(f"   {q[:58]:58} → {r.status_code} ({sayi}) {'' if r.status_code==200 else r.text[:100]}")

    print("\n8) Diğer klasörler")
    for k in ("sentitems", "drafts", "deleteditems", "junkemail", "archive", "outbox"):
        r = get(f"/me/mailFolders/{k}/messages?$top=1")
        sayi = "-"
        ad = "-"
        if r.status_code == 200:
            veri = r.json()
            sayi = len(veri.get("value", []))
            if veri.get("value"):
                ad = veri["value"][0].get("subject", "")[:40]
        print(f"   {k:14} → {r.status_code} ({sayi}) {ad}")

    print("\n9) Kişi / olay / yönetici (kapsam kontrolü)")
    for u in ("/me/contacts", "/me/events", "/me/people", "/me/photo/$value"):
        r = get(u)
        print(f"   {u:22} → {r.status_code} {r.text[:80]}")

    print("\n10) Gönderme (kendine test) — POST /me/sendMail")
    govde = {
        "Message": {
            "Subject": "Postacim REST testi",
            "Body": {"ContentType": "Text", "Content": "Bu bir test ilidir."},
            "ToRecipients": [
                {"EmailAddress": {"Address": "kullanici@ornek.gov.tr",
                                  "Name": "Caglar Yeniyigit"}}
            ],
        },
        "SaveToSentItems": "true",
    }
    r = s.post(f"{API}/me/sendMail", json=govde, timeout=40)
    print(f"   HTTP {r.status_code} → {r.text[:200]}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
