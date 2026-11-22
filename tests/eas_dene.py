#!/usr/bin/env python3
"""Exchange ActiveSync (EAS) protokolunu cesitli basliklarla dener.

Kullanim:  .venv/bin/python tests/eas_dene.py
"""
import base64
import os
import re
import sys
import urllib.parse

import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from postacim.config import Ayarlar

SUNUCU = "mail.kurum.gov.tr"


def main() -> int:
    ayarlar = Ayarlar()
    kullanici = ayarlar.al("kullanici", "")
    parola = ayarlar.al("parola", "")
    temel = {
        "X-User-Agent": "Android",
        "Device-Id": "postacim0001",
        "Accept": "*/*",
        "Accept-Encoding": "gzip, deflate",
    }

    print("1) Options — farklı Protocol-Version / User-Agent")
    for sürüm in ("14.1", "14.2", "16.1", "16.2", "12.1", "2.1"):
        for ajan in (f"Microsoft-ActiveSync/{sürüm} (Android)", "Microsoft-ActiveSync/16.0 (Android)"):
            h = dict(temel, **{
                "User-Agent": ajan,
                "Protocol-Version": sürüm,
                "MS-ASProtocolVersion": sürüm,
            })
            s = requests.Session()
            s.headers.update(h)
            s.auth = (kullanici, parola)
            try:
                r = s.get(f"https://{SUNUCU}/Microsoft-Server-ActiveSync/Options", timeout=30)
                govde = re.sub(r"\s+", " ", r.text[:200])
                print(f"   PV={sürüm:5} UA={ajan[24:44]:22} → {r.status_code} "
                      f"{len(r.content):5} bayt  {govde[:120]}")
            except Exception as exc:
                print(f"   PV={sürüm:5} → {type(exc).__name__}: {str(exc)[:70]}")

    print("\n2) NTLM ile Options (401 detayı)")
    from requests_ntlm import HttpNtlmAuth
    s = requests.Session()
    s.headers.update(dict(temel, **{"User-Agent": "Microsoft-ActiveSync/16.0 (Android)",
                                    "Protocol-Version": "16.1"}))
    s.auth = HttpNtlmAuth(kullanici, parola)
    try:
        r = s.get(f"https://{SUNUCU}/Microsoft-Server-ActiveSync/Options", timeout=30)
        print(f"   → {r.status_code}")
        for k, v in r.headers.items():
            if k.lower() in ("www-authenticate", "content-type", "allow", "x-ms-user-"):
                print(f"      {k}: {v}")
        print("   gövde:", r.text[:200])
    except Exception as exc:
        print(f"   → {type(exc).__name__}: {str(exc)[:90]}")

    print("\n3) FolderSync (temel auth, farklı protocol sürümleri)")
    user_q = urllib.parse.quote(kullanici, safe="")
    for sürüm in ("14.1", "16.1"):
        h = dict(temel, **{"User-Agent": f"Microsoft-ActiveSync/{sürüm} (Android)",
                            "Protocol-Version": sürüm})
        s = requests.Session()
        s.headers.update(h)
        s.auth = (kullanici, parola)
        yol = f"/Microsoft-Server-ActiveSync/Folder?Cmd=FolderSync&User={user_q}"
        try:
            r = s.get(f"https://{SUNUCU}{yol}", timeout=30)
            print(f"   PV={sürüm} → {r.status_code} ({len(r.content)} bayt) {re.sub(r'\\s+',' ', r.text[:260])}")
        except Exception as exc:
            print(f"   PV={sürüm} → {type(exc).__name__}: {str(exc)[:70]}")

    print("\n4) Basic auth bayt kontrolü")
    print("   Authorization:", base64.b64encode(f"{kullanici}:{parola}".encode()).decode()[:24], "...")

    print("\n5) OWA tabanlı 'Exchange Web Services' alternatif uçları")
    for yol in ("/Microsoft-Server-ActiveSync/", "/ecp/", "/owa/",
                "/owa/ev.owa2", "/exchange/", "/mapi/nspi/", "/Rpc/"):
        try:
            r = requests.get(f"https://{SUNUCU}{yol}", timeout=20)
            print(f"   {yol:28} → {r.status_code} {r.headers.get('Content-Type','')[:30]}")
        except Exception as exc:
            print(f"   {yol:28} → {type(exc).__name__}: {str(exc)[:60]}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
