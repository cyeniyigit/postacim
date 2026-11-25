#!/usr/bin/env python3
"""OAuth2 canlı test: yetkilendirme + IMAP + SMTP + CalDAV (gerçek hesap).

Akış:
1. Tarayıcıda Google yetkilendirmesi açılır (kullanıcı izin verir).
2. İzin ekranının ekran görüntüsü alınır.
3. IMAP XOAUTH2: klasör listesi (sayaçlar).
4. SMTP XOAUTH2: yalnız kimlik doğrulama (mail gönderilmez).
5. CalDAV Bearer: takvim keşfi (Google yeni ucu).
6. Sonuç penceresi çizilir + ekran görüntüsü alınır.

Sonuçlar: /tmp/opencode/oauth_test_gunluk.txt + PNG görüntüler.
"""
import base64
import json
import os
import re
import smtplib
import sys
import threading
import time
import traceback

KOK = "/home/amca/postacim"
sys.path.insert(0, KOK)

from postacim import google_oturum  # noqa: E402

KULLANICI = os.environ.get(
    "POSTACIM_OAUTH_TEST_KULLANICI", "deneme@gmail.com"
)
CIKIS = "/tmp/opencode"
GUNLUK = f"{CIKIS}/oauth_test_gunluk.txt"
KAPSAMLAR = google_oturum.KAPSAMLAR

sonuc = {}
satirlar = []


def yaz(metin):
    print(metin, flush=True)
    satirlar.append(metin)


def cek(dosya):
    os.system(
        f"ffmpeg -y -loglevel error -f x11grab -video_size 1600x900 "
        f"-i {os.environ.get('DISPLAY', ':0')} -frames:v 1 {dosya}"
    )


# ------------------------------------------------------------------ adım 1
def yetkilendir_is_():
    try:
        sonuc["token"] = google_oturum.yetkilendir(
            KULLANICI, None, kapsamlar=KAPSAMLAR, beklemek=240
        )
    except Exception as exc:  # noqa: BLE001
        sonuc["hata"] = f"{exc}\n{traceback.format_exc()}"


def main():
    os.makedirs(CIKIS, exist_ok=True)
    t = threading.Thread(target=yetkilendir_is_, daemon=True)
    t.start()
    # Tarayıcının açılmasını ve izin ekranının gelmesini bekle
    time.sleep(6)
    cek(f"{CIKIS}/oauth-1-izin-ekrani.png")

    t.join(timeout=240)
    if sonuc.get("hata"):
        yaz(f"YETKILENDIRME HATA: {sonuc['hata']}")
        return 1
    token = sonuc.get("token") or {}
    yaz("1) YETKILENDIRME OK")
    yaz(f"   kapsam: {', '.join(token.get('kapsam', []))}")
    yaz(f"   refresh_token var: {bool(token.get('refresh_token'))}")

    # Token'ı yerel dosyaya koy (hesap.json'a dokunmuyoruz)
    with open(f"{CIKIS}/oauth_test_token.json", "w") as f:
        json.dump(token, f)
    os.chmod(f"{CIKIS}/oauth_test_token.json", 0o600)

    # -------------------------------------------------------------- IMAP
    import imaplib

    imaplib._MAXLINE = 10_000_000
    try:
        im = imaplib.IMAP4_SSL("imap.gmail.com", 993, timeout=30)
        auth_dize = google_oturum._xoauth2_dize(KULLANICI,
                                                token["access_token"])
        im.authenticate("XOAUTH2", lambda _: auth_dize.encode())
        yaz("2) IMAP XOAUTH2 OK")
        tip, veri = im.list('""', "*")
        adlar = []
        for satir in veri or []:
            if not satir:
                continue
            m = re.search(rb'"]?([^""]+)"?\r?$', satir) if isinstance(
                satir, bytes
            ) else None
            if m:
                adlar.append(m.group(1).decode("utf-8", "replace"))
            else:
                try:
                    adlar.append(satir.decode("utf-8", "replace"))
                except Exception:
                    pass
        tip, sayac = im.select("INBOX", readonly=True)
        toplam = int(sayac[0]) if tip == "OK" else 0
        yaz(f"   klasor sayisi: {len(adlar)}")
        for ad in adlar[:8]:
            yaz(f"   • {ad}")
        yaz(f"   INBOX toplam: {toplam}")
        im.logout()
    except Exception as exc:  # noqa: BLE001
        yaz(f"IMAP HATA: {exc}")

    # -------------------------------------------------------------- SMTP
    try:
        s = smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30)
        s.ehlo()
        auth_dize = google_oturum._xoauth2_dize(KULLANICI,
                                                token["access_token"])
        kod, yanit = s.docmd("AUTH", "XOAUTH2 " + auth_dize)
        if kod == 235:
            yaz("3) SMTP XOAUTH2 OK (yalnız kimlik doğrulama — mail yok)")
        else:
            if kod == 334:
                s.docmd("")
            yaz(f"SMTP HATA: kod={kod} {yanit}")
        s.quit()
    except Exception as exc:  # noqa: BLE001
        yaz(f"SMTP HATA: {exc}")

    # ------------------------------------------------------------- CalDAV
    try:
        from postacim.caldav import CalDavIstemci

        c = CalDavIstemci(
            f"https://apidata.googleusercontent.com/caldav/v2/"
            f"{KULLANICI}/events",
            KULLANICI, "",
            oauth=token,
        )
        koleksiyonlar = c.kesfet()
        yaz("4) CALDAV OK (Google yeni uç)")
        yaz(f"   takvim sayisi: {len(koleksiyonlar)}")
        for k in koleksiyonlar[:6]:
            yaz(f"   • {k.ad} — {k.url[:70]}")
        # İlk takvimden küçük bir aralık çek (okuma testi)
        if koleksiyonlar:
            from datetime import date, timedelta

            bugun = date.today()
            randevular = c.randevular(
                bugun, bugun + timedelta(days=30),
                koleksiyon=koleksiyonlar[0].url,
            )
            yaz(f"   30 günlük randevu: {len(randevular)}")
    except Exception as exc:  # noqa: BLE001
        yaz(f"CALDAV HATA: {exc}\n{traceback.format_exc()}")

    # ------------------------------------------------------ sonuç penceresi
    try:
        sonuc_penceresi(satirlar)
    except Exception as exc:  # noqa: BLE001
        yaz(f"pencere hatası: {exc}")
    with open(GUNLUK, "w", encoding="utf-8") as f:
        f.write("\n".join(satirlar))
    return 0


def sonuc_penceresi(satirlar):
    import tkinter as tk

    kok = tk.Tk()
    kok.title("OAuth2 canlı test — sonuç")
    kok.geometry("760x520")
    kok.attributes("-topmost", True)
    tk.Label(
        kok, text="Google OAuth2 canlı test", font=("Ubuntu", 14, "bold")
    ).pack(pady=(10, 4))
    metin = tk.Text(kok, font=("Monospace", 10), wrap="word")
    metin.pack(fill="both", expand=True, padx=12, pady=8)
    metin.insert("1.0", "\n".join(satirlar))
    tk.Button(kok, text="Kapat", command=kok.destroy).pack(pady=6)

    def gecikmeli_cekim():
        kok.update_idletasks()
        kok.update()
        cek(f"{CIKIS}/oauth-2-sonuc.png")
        kok.after(1500, gecikmeli_cekim)

    gecikmeli_cekim()
    kok.mainloop()


if __name__ == "__main__":
    sys.exit(main())
