#!/usr/bin/env python3
"""OAuth2 önizleme: Hesap ekle + Takvim Hesapları pencerelerini çizer.

Xvfb altında çalışır (DISPLAY verilmiş ortamda). Ekran görüntüsü üretir:
  /tmp/opencode/onzizleme-hesap.png
  /tmp/opencode/onzizleme-takvim.png
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from postacim.config import Ayarlar  # noqa: E402
import postacim.ui as ui_mod  # noqa: E402

CIKIS = "/tmp/opencode"


class SahteIstemci:
    def __init__(self, hesap):
        self.hesap = hesap

    def klasor_listesi(self):
        return []

    def mesajlar(self, *a, **k):
        return [], 0


def bekle(uygulama, saniye=1.2):
    bitis = time.time() + saniye
    while time.time() < bitis:
        uygulama.update()
        time.sleep(0.03)


def cek(dosya):
    os.system(
        f"ffmpeg -y -loglevel warning -f x11grab -video_size 800x700 "
        f"-i {os.environ.get('DISPLAY', ':0')} -frames:v 1 {dosya}"
        f" >/dev/null 2>&1 || echo 'çekim hatası: {dosya}'"
    )


def main():
    dizin = tempfile.mkdtemp(prefix="postacim_onizleme_")
    yol = os.path.join(dizin, "hesap.json")
    with open(yol, "w", encoding="utf-8") as f:
        json.dump({
            "hesaplar": [
                {"id": "kurum001", "ad": "Kurum", "tur": "ews",
                 "sunucu": "mail.ornek.gov.tr", "kullanici": "KURUM\\kisi",
                 "parola": "sifre", "yontem": "ntlm", "son_klasor": "inbox"},
            ],
            "aktif": "kurum001",
            "tema": "dark", "otomatik_yenile": 0,
        }, f, ensure_ascii=False, indent=2)

    ui_mod.Ayarlar = lambda: Ayarlar(yol)
    ui_mod.Postacim._istemci_kur = lambda self, hesap: SahteIstemci(hesap)

    uygulama = ui_mod.Postacim()
    uygulama.geometry("1000x650")
    bekle(uygulama, 0.8)

    # --- Hesap ekle penceresi (Gmail/IMAP + OAuth2 seçili) ---
    pencere = ui_mod.HesapPenceresi(uygulama, None)
    pencere.tur_degisken.set("imap")
    pencere._tur_goster()
    pencere.eposta_var.set("kullanici@gmail.com")
    pencere.kimlik_var.set("Google (OAuth2)")
    pencere._kimlik_goster()
    pencere._oauth_durum_guncelle()
    pencere.deiconify()
    pencere.lift()
    pencere.focus_force()
    bekle(uygulama, 1.0)
    cek(f"{CIKIS}/onzizleme-hesap.png")
    pencere.destroy()

    # --- Takvim Hesapları penceresi (Gmail OAuth2 şablonu) ---
    tk = ui_mod.TakvimHesapPenceresi(uygulama)
    tk.kullanici_var.set("kullanici@gmail.com")
    tk._sablon("Gmail (OAuth2)")
    tk._oauth_durum_guncelle()
    tk.lift()
    tk.focus_force()
    bekle(uygulama, 1.0)
    cek(f"{CIKIS}/onzizleme-takvim.png")
    tk.destroy()

    uygulama.destroy()
    print("önizleme tamam:", CIKIS)


if __name__ == "__main__":
    main()
