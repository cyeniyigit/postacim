#!/usr/bin/env python3
"""Yerel mini IMAP sunucusuyla tel düzeyi test (gerçek imaplib üzerinden).

Amaç: istemcinin sunucuya gönderdiği HAM komut satırlarını doğrulamak.
Özellikle regresyon: `LIST "" *` gitmeli (`LIST  *` değil — ikincisi
sunucudan BAD yiyordu: "LIST command error: BAD …").

Kullanim:  .venv/bin/python tests/imap_yerel_sunucu_test.py
"""
from __future__ import annotations

import imaplib
import os
import socket
import sys
import threading
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from postacim import imap as imap_mod  # noqa: E402

HATALAR = []


def kontrol(kosul, mesaj):
    if kosul:
        print(f"  ✓ {mesaj}")
    else:
        HATALAR.append(mesaj)
        print(f"  !! {mesaj}")


class MiniImapSunucu:
    """Satır tabanlı, tek bağlantılı sahte IMAP sunucusu.

    Gelen komut satırlarını `self.komutlar`da tutar (tel denetimi için).
    """

    def __init__(self):
        self.komutlar: list[str] = []
        self._soket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._soket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._soket.bind(("127.0.0.1", 0))
        self._soket.listen(2)
        self.port = self._soket.getsockname()[1]
        self._dur = threading.Event()
        threading.Thread(target=self._dinle, daemon=True).start()

    def _dinle(self):
        while not self._dur.is_set():
            try:
                baglanti, _ = self._soket.accept()
            except OSError:
                break
            threading.Thread(target=self._isle, args=(baglanti,),
                             daemon=True).start()

    def _isle(self, conn: socket.socket):
        try:
            conn.sendall(b'* OK [CAPABILITY IMAP4rev1] Mini IMAP hazir\r\n')
            tampon = b""
            while True:
                veri = conn.recv(4096)
                if not veri:
                    break
                tampon += veri
                while b"\r\n" in tampon:
                    satir, tampon = tampon.split(b"\r\n", 1)
                    yanit = self._komut(satir)
                    if yanit is None:
                        return
                    conn.sendall(yanit)
        except OSError:
            pass
        finally:
            try:
                conn.close()
            except OSError:
                pass

    def _komut(self, satir: bytes):
        metin = satir.decode("utf-8", "replace")
        self.komutlar.append(metin)
        parcalar = metin.split(None, 1)
        if not parcalar:
            return b""
        etiket = parcalar[0]
        govde = parcalar[1] if len(parcalar) > 1 else ""
        komut = govde.split(None, 1)[0].upper() if govde else ""

        if komut == "CAPABILITY":
            return (b"* CAPABILITY IMAP4rev1\r\n"
                    + etiket.encode() + b" OK Devam\r\n")
        if komut == "LOGIN":
            return etiket.encode() + b" OK [CAPABILITY IMAP4rev1] Giris tamam\r\n"
        if komut == "LIST":
            # Türkish klasör adı modified UTF-7: Gönderilmiş = G&APY-nderilmi&AV8-
            return (
                b'* LIST (\\HasNoChildren \\Inbox) "/" "INBOX"\r\n'
                b'* LIST (\\HasNoChildren \\Sent) "/" "G&APY-nderilmi&AV8-"\r\n'
                b'* LIST (\\HasNoChildren) "/" "Proje X"\r\n'
                + etiket.encode() + b" OK Devam\r\n"
            )
        if komut == "STATUS":
            # İstek metnini geri sayıyla yanıtlama: INBOX 7/2, diğer 0/0
            if '"INBOX"' in govde:
                govde_satir = b'* STATUS "INBOX" (MESSAGES 7 UNSEEN 2)\r\n'
            else:
                # Tırnaklı adı olduğu gibi yansıt (ad utf-7 olabilir)
                ad = govde.split(None, 1)[1].split(None, 1)[0] \
                    if " " in govde else b'"?"'
                if isinstance(ad, str):
                    ad = ad.encode()
                govde_satir = b"* STATUS " + ad + b" (MESSAGES 5 UNSEEN 0)\r\n"
            return govde_satir + etiket.encode() + b" OK Devam\r\n"
        if komut == "SELECT":
            return b"* 3 EXISTS\r\n* 0 RECENT\r\n" + etiket.encode() + b" OK Devam\r\n"
        if komut == "DELETE":
            return etiket.encode() + b" OK Silindi\r\n"
        if komut == "CREATE":
            return etiket.encode() + b" OK Olusturuldu\r\n"
        if komut == "LOGOUT":
            conn_yok = b"* BYE\r\n" + etiket.encode() + b" OK Devam\r\n"
            return conn_yok
        if komut == "UID" or komut in ("SEARCH", "FETCH", "STORE", "EXPUNGE"):
            if komut == "UID":
                alt = govde.split(None, 1)[1].split(None, 1)[0].upper() \
                    if " " in govde else ""
                if alt == "SEARCH":
                    return b"* SEARCH 101\r\n" + etiket.encode() + b" OK Devam\r\n"
                if alt == "FETCH":
                    return etiket.encode() + b" OK Devam\r\n"
            return etiket.encode() + b" OK Devam\r\n"
        return etiket.encode() + b" NO Desteklenmiyor\r\n"

    def kapat(self):
        self._dur.set()
        try:
            self._soket.close()
        except OSError:
            pass


def main() -> int:
    print("== yerel IMAP sunucusu: tel denetimi ==")
    sunucu = MiniImapSunucu()

    # Güvenli sarmalayıcı yerine düz TCP (TLS'siz yerel sunucu)
    def duz_baglan(host, port, timeout=None):
        return imaplib.IMAP4(host, port, timeout=timeout)

    with mock.patch.object(imap_mod.imaplib, "IMAP4_SSL", duz_baglan):
        istemci = imap_mod.ImapIstemci({
            "tur": "imap",
            "kullanici": "deneme@gmail.com",
            "parola": "uygulama-parolasi",
            "gelen_sunucu": "127.0.0.1",
            "gelen_port": sunucu.port,
            "giden_sunucu": "smtp.gmail.com",
            "giden_port": 465,
            "guvenli": "ssl",
        })
        try:
            klasorler = istemci.klasor_listesi()
            # Klasör silme de telde doğrulanır: DELETE "Proje X"
            istemci.klasor_sil("Proje X")
            # Klasör oluşturma: CREATE "Yeni Klasör"
            istemci.klasor_olustur("Yeni Klasör")
        finally:
            try:
                istemci.imap.shutdown()
            except Exception:
                pass
            sunucu.kapat()

    komutlar = sunucu.komutlar
    print(f"gelen komutlar  : {komutlar}")

    kontrol(any('DELETE "Proje X"' in k for k in komutlar),
            'ham DELETE komutu: DELETE "Proje X"')

    kontrol(any(f'CREATE "{imap_mod._utf7_kodla("Yeni Klasör")}"' in k
                for k in komutlar),
            'ham CREATE komutu: CREATE "Yeni Klas&APY-r" (utf-7)')

    kontrol(any(k.endswith('LIST "" *') for k in komutlar),
            'ham LIST komutu `LIST "" *` (tırnaklı boş dizin)')
    kontrol(not any("LIST  *" in k for k in komutlar),
            "hatalı `LIST  *` (çift boşluk/eksik argüman) gönderilmedi")
    kontrol(any(k.startswith("LOGIN") or " LOGIN " in f" {k}" for k in komutlar),
            "LOGIN gönderildi")
    kontrol(any(" STATUS " in f" {k}" and "MESSAGES UNSEEN" in k
                for k in komutlar),
            "STATUS (MESSAGES UNSEEN) gönderildi")
    kontrol(any("STATUS" in k and "&APY-" in k for k in komutlar),
            "utf-7 klasör adı telde ascii olarak gitti (Gönderilmiş)")

    kimlikler = [k.kimlik for k in klasorler]
    kontrol(kimlikler == ["inbox", "sentitems", "Proje X"],
            f"klasörler: {kimlikler}")
    inbox = klasorler[0]
    kontrol((inbox.toplam, inbox.okunmamis) == (7, 2),
            "INBOX sayaçları sunucudan okundu (7/2)")
    kontrol(klasorler[1].ad == "Gönderilmiş",
            "utf-7 ad çözüldü (Gönderilmiş)")

    if HATALAR:
        print(f"\n!! {len(HATALAR)} HATA:")
        for h in HATALAR:
            print("   ", h)
        return 1
    print("\n✓ yerel IMAP sunucu testi geçti")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
