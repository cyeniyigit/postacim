#!/usr/bin/env python3
"""Arama + sayfa silme + seçim akışı — kullanıcı çökmesi yeniden üretimi.

Senaryo (kullanıcı raporu):
  1. Gmail'de "Hepsi" araması yapıldı (sayfalı sonuçlar)
  2. İlk sayfadaki mailler Shift ile toplu seçilip silindi
  3. Yeni sayfa yüklendi, mouse ile seçim yapılırken program çöktü

Bu test aynı akışı sahte istemciyle (gerçek sunucu yok) koşturur ve Tk
geri çağrılarında yükselen her istisnayı yakalar.

Kullanim:  xvfb-run -a .venv/bin/python tests/silme_sayfa_test.py
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import threading
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from postacim.config import Ayarlar  # noqa: E402
from postacim.ews import Klasor, Mesaj  # noqa: E402
import postacim.ui as ui_mod  # noqa: E402

HATALAR = []


def kontrol(kosul, mesaj):
    if kosul:
        print(f"  ✓ {mesaj}")
    else:
        HATALAR.append(mesaj)
        print(f"  !! {mesaj}")


class SahteGmail:
    """Sayfalı arama + silinenlerin toplamdan düşmesi + gövde çekme."""

    def __init__(self, hesap: dict):
        self.hesap = hesap
        self.kilit = threading.Lock()
        self.havuz = [
            Mesaj(item_id=str(i), konu=f"Hepsi — mesaj {i}",
                  gonderen=f"gonderen{i}@ornek.gov.tr",
                  gonderen_ad=f"Gönderen {i}", tarih="19.11.2026",
                  okundu=i % 3 == 0, klasor="inbox",
                  tariham="2026-11-19T10:00:00")
            for i in range(100, 125)  # 25 mesaj → sayfa_boyutu 10 ile 3 sayfa
        ]
        self.tasinanlar: list = []

    def klasor_listesi(self):
        return [
            Klasor(kimlik="inbox", ad="Gelen Kutusu", toplam=25, okunmamis=16),
            Klasor(kimlik="sentitems", ad="Gönderilmiş", toplam=0, okunmamis=0),
            Klasor(kimlik="drafts", ad="Taslaklar", toplam=0, okunmamis=0),
            Klasor(kimlik="deleteditems", ad="Silinmiş Öğeler",
                   toplam=len(self.tasinanlar), okunmamis=0),
            Klasor(kimlik="Proje X", ad="Proje X", toplam=1, okunmamis=0),
        ]

    def mesajlar(self, klasor="inbox", sayfa_boyutu=50, offset=0, arama="",
                 alan="konu", tam=False, tazele=True):
        with self.kilit:
            if arama:
                ms = [m for m in self.havuz if arama.lower() in m.konu.lower()]
            else:
                ms = list(self.havuz)
        return ms[offset:offset + sayfa_boyutu], len(ms)

    def guncelle(self, klasorler=None):
        return {}

    def cozumle(self, metin, en_fazla=20):
        return []

    def mesaj_detay(self, mesaj):
        mesaj.govde = f"Gövde {mesaj.konu}"
        return mesaj

    def okundu_isaretle(self, mesaj, okundu=True):
        mesaj.okundu = okundu

    def tasi(self, mesaj, hedef="deleteditems"):
        with self.kilit:
            if mesaj in self.havuz:
                self.havuz.remove(mesaj)
        self.tasinanlar.append(mesaj.item_id)

    def kalici_sil(self, mesaj):
        with self.kilit:
            if mesaj in self.havuz:
                self.havuz.remove(mesaj)

    def gonder(self, *a, **k):
        return ""

    def taslağa_kaydet(self, *a, **k):
        return ""

    def mesaj_mime(self, mesaj_id):
        return b"From: x\r\n\r\nSubject: y\r\n\r\n"

    def ek_indir(self, ek):
        return b""


def bekle(uygulama, saniye):
    bitis = time.time() + saniye
    while time.time() < bitis:
        uygulama.update()
        time.sleep(0.05)


def main() -> int:
    print("== arama + sayfa silme + seçim (çökme senaryosu) ==")
    d = tempfile.mkdtemp(prefix="postacim-silme-")
    yol = os.path.join(d, "hesap.json")
    gmail_id, kurum_id = "gmail001", "kurum001"
    with open(yol, "w", encoding="utf-8") as f:
        json.dump({
            "hesaplar": [
                {"id": kurum_id, "ad": "Kurum", "tur": "ews",
                 "sunucu": "mail.ornek.gov.tr", "kullanici": "KURUM\\kisi",
                 "parola": "sifre", "yontem": "ntlm", "son_klasor": "inbox"},
                {"id": gmail_id, "ad": "Gmail", "tur": "imap",
                 "kullanici": "deneme@gmail.com", "parola": "uygulama parolası",
                 "gelen_sunucu": "imap.gmail.com", "gelen_port": 993,
                 "giden_sunucu": "smtp.gmail.com", "giden_port": 465,
                 "guvenli": "ssl", "son_klasor": "inbox"},
            ],
            "aktif": gmail_id,
            "tema": "light", "otomatik_yenile": 0,
        }, f, ensure_ascii=False, indent=2)

    eski_ayarlar, eski_kur = ui_mod.Ayarlar, ui_mod.Postacim._istemci_kur
    ui_mod.Ayarlar = lambda: Ayarlar(yol)

    gmail_istemci = SahteGmail({"id": gmail_id, "ad": "Gmail"})
    istemciler = {gmail_id: gmail_istemci}
    ui_mod.Postacim._istemci_kur = lambda self, hesap: istemciler[hesap["id"]]

    import tkinter.messagebox as messagebox
    eski_soru = messagebox.askyesno
    messagebox.askyesno = lambda *a, **k: True

    uygulama = ui_mod.Postacim()
    hata = []

    def izle(exc_type, exc, tb):
        import traceback
        hata.append(f"{exc_type.__name__}: {exc}")
        traceback.print_exception(exc_type, exc, tb)

    uygulama.report_callback_exception = lambda *a: izle(*a[:3])

    try:
        # Sayfa boyutu küçültülür: 25 arama sonucu → 3 sayfa (10+10+5)
        uygulama.sayfa_boyutu = 10
        bekle(uygulama, 3)
        kontrol(uygulama.istemci is gmail_istemci, "Gmail hesabı aktif")

        # 1) "Hepsi" araması
        uygulama.arama.set("Hepsi")
        uygulama._arama_yap()
        bekle(uygulama, 3)
        kontrol(len(uygulama.mesajlar) == 10,
                f"arama 1. sayfa yüklendi ({len(uygulama.mesajlar)})")
        kontrol(uygulama.sayfa_sayisi == 3,
                f"3 sayfa ({uygulama.sayfa_sayisi})")

        # 2) İlk sayfayı Shift-gibi tüm seç + sil
        uygulama.liste.selection_set(*uygulama.liste.get_children())
        uygulama.tasi_klasore("deleteditems")
        bekle(uygulama, 4)
        kontrol(len(gmail_istemci.tasinanlar) == 10,
                f"10 mesaj silindi ({len(gmail_istemci.tasinanlar)})")

        # 3) "İkinci sayfa" yüklendi (kalan sonuçların 1. sayfası)
        kontrol(len(uygulama.mesajlar) == 10,
                f"silme sonrası liste yenilendi ({len(uygulama.mesajlar)})")
        uygulama._sayfa_degistir(1)
        bekle(uygulama, 3)
        kontrol(len(uygulama.mesajlar) == 5,
                f"2. sayfa 5 mesaj ({len(uygulama.mesajlar)})")

        # 4) Mouse/Shift ile seçim — çöken yer burasıydı
        uygulama.liste.selection_set("0")
        uygulama.liste.event_generate("<<TreeviewSelect>>")
        bekle(uygulama, 2)
        uygulama.liste.selection_add("1")
        uygulama.liste.event_generate("<<TreeviewSelect>>")
        bekle(uygulama, 2)
        kontrol(uygulama.secili is not None
                and uygulama.secili.govde.startswith("Gövde"),
                "seçim + gövde yüklendi, çökme yok")

        # 4b) Yenileme koşarken hızlı seçim (yarış durumu taklidi)
        uygulama.yenile()
        bekle(uygulama, 0.3)  # klasörler henüz gelmeden seçim yap
        uygulama.liste.selection_set("2")
        uygulama.liste.event_generate("<<TreeviewSelect>>")
        bekle(uygulama, 3)

        # 4c) Sayfa küçülme yolu: son sayfanın tümünü sil
        uygulama.liste.selection_set(*uygulama.liste.get_children())
        uygulama.tasi_klasore("deleteditems")
        bekle(uygulama, 4)
        # sayfa_no=1 >= sayfa_sayisi=1 → küçülme + tekrar yükleme
        kontrol(uygulama.sayfa_no < uygulama.sayfa_sayisi,
                f"sayfa aralığı düzeldi (no={uygulama.sayfa_no}, "
                f"sayısı={uygulama.sayfa_sayisi})")
        # silme + küçülme sonrası hemen seçim
        if uygulama.liste.get_children():
            uygulama.liste.selection_set(uygulama.liste.get_children()[0])
            uygulama.liste.event_generate("<<TreeviewSelect>>")
            bekle(uygulama, 2)
        kontrol(not uygulama.liste.get_children()
                or uygulama.secili is not None,
                "küçülme + seçim sonrası çökme yok")

        # 5) Fare basılıyken gelen sonuç ertelenir, bırakınca uygulanır
        uygulama.liste.event_generate("<Button-1>")
        kontrol(uygulama._mouse_basili, "fare basılı bayrağı kuruldu")
        uygulama.liste.event_generate("<ButtonRelease-1>")
        kontrol(not uygulama._mouse_basili, "bırakınca bayrak düşer")
        # Basılı tutarak sonuç işle (queue üzerinden)
        uygulama.liste.event_generate("<Button-1>")
        uygulama.is_kuyrugu.put((
            "ok", ("mesajlar", list(gmail_istemci.havuz[:2]), 2)
        ))
        bekle(uygulama, 1)
        kontrol(len(uygulama.liste.get_children()) != 2,
                "fare basılıyken liste yeniden kurulmadı (ertelendi)")
        uygulama.liste.event_generate("<ButtonRelease-1>")
        bekle(uygulama, 1.5)
        kontrol(len(uygulama.liste.get_children()) == 2,
                f"bırakınca bekleyen liste uygulandı "
                f"({len(uygulama.liste.get_children())})")
        # Seçimler geçerli kalmalı: erteleme sonrası seçim + detay
        uygulama.liste.selection_set("0")
        uygulama.liste.event_generate("<<TreeviewSelect>>")
        bekle(uygulama, 2)
        kontrol(uygulama.secili is not None
                and uygulama.secili.govde.startswith("Gövde"),
                "erteleme sonrası seçim çökmüyor")

        # Ertelenen liste temizlendi; şimdi Tk hata kaydı yolu
        gecici_state = os.path.join(d, "state")
        eski_state = os.environ.get("XDG_STATE_HOME")
        os.environ["XDG_STATE_HOME"] = gecici_state
        import tkinter.messagebox as messagebox
        eski_goster = messagebox.showerror
        gosterilen = []
        messagebox.showerror = lambda *a, **k: gosterilen.append(a)
        try:
            try:
                raise ValueError("deneme çökmesi")
            except ValueError:
                uygulama._tk_hata_yakala(*sys.exc_info())
        finally:
            messagebox.showerror = eski_goster
            if eski_state is None:
                os.environ.pop("XDG_STATE_HOME", None)
            else:
                os.environ["XDG_STATE_HOME"] = eski_state
        kontrol(bool(gosterilen), "beklenmeyen hata kullanıcıya gösterilir")
        log_yolu = os.path.join(gecici_state, "postacim", "hata.log")
        kontrol(
            os.path.exists(log_yolu)
            and "deneme çökmesi" in open(log_yolu, encoding="utf-8").read(),
            f"Tk hata izi hata.log'a yazıldı ({log_yolu})",
        )
    finally:
        try:
            uygulama.destroy()
        except Exception:
            pass
        ui_mod.Ayarlar, ui_mod.Postacim._istemci_kur = eski_ayarlar, eski_kur
        messagebox.askyesno = eski_soru

    if hata:
        print("\n!! İstisnalar:")
        for h in hata:
            print("   ", h)
        HATALAR.extend(hata)
    if HATALAR:
        print(f"\n!! {len(HATALAR)} HATA:")
        for h in HATALAR:
            print("   ", h)
        return 1
    print("\n✓ silme/sayfa/ seçim senaryosu hatasız")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
