#!/usr/bin/env python3
"""Çoklu hesap + IMAP istemcisi testleri (ağ gerektirmez).

Kapsar:
- config: eski tekli biçimden göç, hesap ekle/düzenle/sil, geriye dönük uyum
- imap: UTF-7, LIST ayrıştırma, klasör eşleme, zarf onbelleği/sayfalama,
  arama, taşı/okundu, SMTP gönderimi (hepsi sahte sunucuyla)

Kullanim:  python3 tests/coklu_hesap_test.py
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from postacim.config import Ayarlar, yeni_hesap_id  # noqa: E402
from postacim import imap as imap_mod  # noqa: E402
from postacim.ews import EwsHata, Klasor, Mesaj  # noqa: E402

HATALAR = []


def kontrol(kosul, mesaj):
    if kosul:
        print(f"  ✓ {mesaj}")
    else:
        HATALAR.append(mesaj)
        print(f"  !! {mesaj}")


# ------------------------------------------------------------------ config

ESKI_BICIM = {
    "sunucu": "mail.kurum.gov.tr",
    "kullanici": "KURUM\\kullanici",
    "parola": "gizli123",
    "yontem": "ntlm",
    "son_klasor": "sentitems",
    "tema": "dark",
    "otomatik_yenile": 120,
}


def config_test():
    print("\n== config: göç + çoklu hesap ==")
    with tempfile.TemporaryDirectory() as d:
        yol = os.path.join(d, "hesap.json")
        with open(yol, "w", encoding="utf-8") as f:
            json.dump(ESKI_BICIM, f)

        a = Ayarlar(yol)
        kontrol(len(a.hesaplar()) == 1, "eski biçim → 1 hesap")
        h = a.hesaplar()[0]
        kontrol(h.get("tur") == "ews", "göç eden hesap türü ews")
        kontrol(h.get("kullanici") == ESKI_BICIM["kullanici"], "kullanıcı taşındı")
        kontrol(h.get("parola") == "gizli123", "parola taşındı")
        kontrol(h.get("son_klasor") == "sentitems", "son_klasor taşındı")
        kontrol(a.al("tema") == "dark", "global tema korundu")
        kontrol(a.aktif_hesap_id() == h["id"], "aktif hesap kuruldu")
        # Geriye dönük uyum: eski anahtarlar aktif hesaptan okunur
        kontrol(a.al("kullanici") == ESKI_BICIM["kullanici"],
                "geriye dönük al('kullanici')")
        kontrol(a.al("yontem") == "ntlm", "geriye dönük al('yontem')")

        # İkinci hesap (Gmail) ekle
        gmail = a.hesap_ekle({
            "ad": "Gmail", "tur": "imap",
            "kullanici": "deneme@gmail.com", "parola": "abcd efgh ijkl mnop",
            "gelen_sunucu": "imap.gmail.com", "gelen_port": 993,
            "giden_sunucu": "smtp.gmail.com", "giden_port": 465,
            "guvenli": "ssl",
        })
        kontrol(len(a.hesaplar()) == 2, "ikinci hesap eklendi")
        kontrol(gmail.get("gelen_port") == 993, "imap portu korundu")
        kontrol(a.hesap(gmail["id"]) is not None, "hesap(id) bulunuyor")

        # Yeni hesaba geç
        a.aktif_ayarla(gmail["id"])
        kontrol(a.aktif_hesap_id() == gmail["id"], "aktif hesap değişti")
        kontrol(a.al("kullanici") == "deneme@gmail.com",
                "geriye dönük al() artık Gmail'den okuyor")

        # Düzenle + sil
        a.hesap_guncelle(gmail["id"], {"ad": "Kişisel Gmail"})
        kontrol(a.hesap(gmail["id"])["ad"] == "Kişisel Gmail", "hesap_guncelle")
        a.hesap_sil(gmail["id"])
        kontrol(len(a.hesaplar()) == 1, "hesap silindi")
        kontrol(a.aktif_hesap_id() == h["id"],
                "aktif hesap silinince diğerine geçildi")

        # Diske yazıldı mi (yeniden yükle)
        b = Ayarlar(yol)
        kontrol(len(b.hesaplar()) == 1, "dosya yeniden yüklendi (kalıcı)")

        # Boş/bozuk dosya
        c = Ayarlar(os.path.join(d, "yok.json"))
        kontrol(c.hesaplar() == [], "dosya yoksa boş liste")


# ------------------------------------------------------------------- imap

class SahteImap:
    """imaplib.IMAP4_SSL yerine geçen sahte sunucu."""

    def __init__(self, *a, **kw):
        self.giris_yapildi = False
        self.secili = None
        self.state = "AUTH"        # imaplib durum makinesi (LOGOUT/BYE testleri)
        self.selecti_boz = False   # bir sonraki select LOGOUT hatası versin
        self.komutlar = []          # (komut, argümanlar)
        self.uidler = [101, 102, 103]  # artan
        self.zarflar = {
            101: _zarf("Ali Veli", "ali@ornek.gov.tr", "Merhaba",
                       "Tue, 18 Nov 2026 09:15:00 +0300"),
            102: _zarf("Ayşe Yılmaz", "ayse@ornek.gov.tr", "Toplantı notları",
                       "Tue, 18 Nov 2026 14:40:00 +0300"),
            103: _zarf("", "duyuru@ornek.gov.tr", "Sistem bakımı",
                       "Wed, 19 Nov 2026 08:00:00 +0300"),
        }
        self.bayraklar = {101: "\\Seen", 102: "", 103: "\\Seen"}

    # bağlantı
    def login(self, kullanici, parola):
        if parola != "uygulama-parolasi":
            raise imap_mod.imaplib.IMAP4.error("LOGIN failed.")
        self.giris_yapildi = True
        return ("OK", [b"Logged in"])

    def logout(self):
        self.state = "LOGOUT"
        return ("OK", [b"Bye"])

    def starttls(self):
        return ("OK", [])

    # klasörler (sunucu adları değiştirilmiş UTF-7 gönderir)
    def list(self, directory='""', pattern="*"):
        # Gerçek sunucular gibi: hatalı/eksik argümana BAD döner
        # (dizin tırnaklı boş "" olmalıdır; "" verilirse LIST tek argümanla
        # gelir → BAD → imaplib "LIST command error" fırlatır).
        if directory != '""' or pattern != "*":
            raise imap_mod.imaplib.IMAP4.error(
                "LIST command error: BAD [b'Invalid arguments']"
            )
        u7 = imap_mod._utf7_kodla
        return ("OK", [
            b'(\\HasNoChildren \\Inbox) "/" "INBOX"',
            f'(\\HasNoChildren \\Sent) "/" "{u7("Gönderilmiş")}"'.encode(),
            f'(\\HasNoChildren \\Drafts) "/" "{u7("Taslaklar")}"'.encode(),
            f'(\\HasNoChildren \\Trash) "/" "{u7("Çöp Kutusu")}"'.encode(),
            f'(\\HasNoChildren \\Junk) "/" "{u7("Spam")}"'.encode(),
            f'(\\HasNoChildren \\Archive) "/" "{u7("Arşiv")}"'.encode(),
            b'(\\HasNoChildren) "/" "Proje X"',          # özel olmayan klasör
            b'(\\HasNoChildren \\Noselect) "/" "[Gmail]"',  # atlanmalı
        ])

    def status(self, mailbox, names):
        u7 = imap_mod._utf7_kodla
        sayac = {
            "INBOX": (12, 3),
            u7("Gönderilmiş"): (5, 0),
        }.get(mailbox.strip('"'), (0, 0))
        return ("OK", [f'{mailbox} (MESSAGES {sayac[0]} UNSEEN {sayac[1]})'.encode()])

    def select(self, mailbox, readonly=False):
        if self.selecti_boz:
            # Sunucu BYE göndermiş gibi: durum LOGOUT'a düşer ve komut reddedilir
            self.selecti_boz = False
            self.state = "LOGOUT"
            raise imap_mod.imaplib.IMAP4.error(
                "command SELECT illegal in state LOGOUT, only allowed in "
                "states AUTH, SELECTED"
            )
        self.state = "SELECTED"
        self.secili = mailbox
        return ("OK", [b"0"])

    # mesajlar
    def uid(self, komut, *args):
        self.komutlar.append((komut, args))
        if komut == "search":
            if args and args[0] == "UTF-8":
                # arama: yalnız "toplantı" terimi 102 ile eşleşsin
                return ("OK", [b"102"])
            return ("OK", [b" ".join(str(u).encode() for u in self.uidler)])
        if komut == "fetch":
            kume = args[0]
            secili = [int(u) for u in str(kume).split(",") if u.isdigit()]
            yanit = []
            for u in secili:
                ham = self.zarflar.get(u, b"")
                bayrak = self.bayraklar.get(u, "")
                flags = f" ({bayrak})" if bayrak else " ()"
                yanit.append((
                    f'{u} (UID {u} FLAGS{flags} RFC822.HEADER {{{len(ham)}}}'.encode(),
                    ham,
                ))
                yanit.append(b")")
            return ("OK", yanit)
        if komut == "store":
            return ("OK", [b""])
        if komut == "move":
            return ("OK", [b""])
        if komut == "copy":
            return ("OK", [b""])
        return ("NO", [b"desteklenmiyor"])

    def expunge(self):
        return ("OK", [b""])

    def append(self, mailbox, flags, date_time, message):
        self.komutlar.append(("append", (mailbox, flags, date_time, message)))
        return ("OK", [b""])

    def delete(self, mailbox):
        self.komutlar.append(("delete", (mailbox,)))
        # Gerçek sunucular gibi bazı klasörleri silmeyi reddet
        if "Korumali" in mailbox:
            raise imap_mod.imaplib.IMAP4.error(
                "DELETE command error: NO [Mailbox deletion not permitted]"
            )
        return ("OK", [b""])


def _zarf(ad, adres, konu, tarih, bayrak=""):
    """RFC822.HEADER baytları üretir."""
    basliklar = [
        f"From: {ad} <{adres}>" if ad else f"From: {adres}",
        f"To: ben@ornek.gov.tr",
        f"Subject: {konu}",
        f"Date: {tarih}",
        "Message-ID: <test@ornek.gov.tr>",
        "Content-Type: text/plain; charset=utf-8",
        "",
        "",
    ]
    return "\r\n".join(basliklar).encode("utf-8")


def imap_test():
    print("\n== imap: UTF-7 / LIST / zarf / arama / yazma ==")

    # UTF-7 (bilinen değer: é = U+00E9 → UTF-16BE 00 E9 → base64 "AOk=")
    kontrol(imap_mod._utf7_kodla("é") == "&AOk-", "utf-7 kodlama (é → &AOk-)")
    kontrol(imap_mod._utf7_coz("&AOk-") == "é", "utf-7 çözme (&AOk- → é)")
    kontrol(imap_mod._utf7_kodla("Gönderilmiş").isascii(),
            "utf-7 çıktısı ascii (komutlarda kullanılabilir)")
    kontrol(imap_mod._utf7_kodla("INBOX") == "INBOX", "ascii olduğu gibi")
    kontrol(imap_mod._utf7_coz("INBOX") == "INBOX", "ascii çözme")
    kontrol(imap_mod._utf7_coz(imap_mod._utf7_kodla("Çöp Kutusu")) == "Çöp Kutusu",
            "utf-7 tur tur round-trip (Çöp Kutusu)")

    # LIST ayrıştırma
    oz, ay, ad = imap_mod._list_satiri(
        b'(\\HasNoChildren \\Sent) "/" "G&AMk-nderilmi&AMc-"'
    )
    kontrol("\\Sent" in oz and ad == "G&AMk-nderilmi&AMc-", "list satırı ayrıştı")

    # Özel kimlik eşlemesi
    kontrol(imap_mod._ozel_kimlik("\\Sent", "X") == "sentitems", "\\Sent → sentitems")
    kontrol(imap_mod._ozel_kimlik("\\Trash", "X") == "deleteditems", "\\Trash → silinmiş")
    kontrol(imap_mod._ozel_kimlik("", "INBOX") == "inbox", "INBOX adı → inbox")
    kontrol(imap_mod._ozel_kimlik("\\Archive \\All", "X") == "archive",
            "\\Archive \\All → archive (çift)")
    kontrol(imap_mod._ozel_kimlik("\\All", "X") == "archive", "\\All → archive")
    kontrol(imap_mod._ozel_kimlik("", "Proje X") == "Proje X",
            "bilinmeyen klasör kendi adıyla")
    kontrol(imap_mod._guzel_ad("[Gmail]/Gönderilmiş") == "Gönderilmiş",
            "[Gmail]/ öneki sadeleşir")

    # Sahte sunucuyla tam istemci
    with mock.patch.object(imap_mod.imaplib, "IMAP4_SSL", SahteImap):
        istemci = imap_mod.ImapIstemci({
            "tur": "imap", "kullanici": "deneme@gmail.com",
            "parola": "uygulama-parolasi",
            "gelen_sunucu": "imap.gmail.com", "gelen_port": 993,
            "giden_sunucu": "smtp.gmail.com", "giden_port": 465,
            "guvenli": "ssl",
        })

        klasorler = istemci.klasor_listesi()
        kimlikler = [k.kimlik for k in klasorler]
        kontrol(kimlikler[0] == "inbox", "ilk klasör inbox")

        # REGRESYON: hatalı LIST argümanı (boş dizin) sunucudan BAD yemesin;
        # hata EwsHata olarak, okunur mesajla çıkmalı (Beklenmeyen hata değil).
        try:
            istemci._komut("list", "", "*")
            kontrol(False, "hatalı LIST argümanı hata fırlatmalı")
        except EwsHata as exc:
            kontrol("reddedildi" in str(exc) and "LIST command error" in str(exc),
                    f"hatalı LIST → EwsHata ({exc})")
        except Exception as exc:
            kontrol(False, f"hatalı LIST → EwsHata olmalı, gelen: {type(exc).__name__}")
        kontrol("sentitems" in kimlikler and "drafts" in kimlikler,
                "özel klasörler eşlendi")
        kontrol("Proje X" in kimlikler, "özel olmayan klasör korundu")
        kontrol("[Gmail]" not in kimlikler, "\\Noselect klasörü atlandı")
        kontrol(all(not k.kimlik.startswith("[Gmail]") for k in klasorler),
                "gmail klasör adları sadeleştirildi")
        inbox = next(k for k in klasorler if k.kimlik == "inbox")
        kontrol((inbox.toplam, inbox.okunmamis) == (12, 3), "STATUS sayaçları okundu")
        gonderilmis = next(k for k in klasorler if k.kimlik == "sentitems")
        kontrol(gonderilmis.ad == "Gönderilmiş",
                "klasör adı görünümü çözülmüş (Gönderilmiş)")
        kontrol(imap_mod._utf7_coz(istemci._klasor_adi("sentitems")) == "Gönderilmiş",
                "kimlik → sunucu adı eşlemesi (utf-7 çözülmüş görünüm)")
        kontrol(istemci._klasor_adi("sentitems").isascii(),
                "komut için ham ad ascii (utf-7)")

        # Mesaj listesi (tam senkron + sayfalama)
        sayfa, toplam = istemci.mesajlar(klasor="inbox", sayfa_boyutu=2, offset=0)
        kontrol(toplam == 3, f"3 mesaj senkronize (toplam={toplam})")
        kontrol(len(sayfa) == 2, "sayfa boyutu 2")
        kontrol(sayfa[0].konu == "Sistem bakımı", "en yeni önce sıralandı")
        kontrol(sayfa[0].item_id == "103", "item_id = UID")
        kontrol(sayfa[1].okundu is False, "okunmamış bayrak okundu=False")
        kontrol(sayfa[0].okundu is True, "\\Seen bayrak okundu=True")
        kontrol(sayfa[1].gonderen == "ayse@ornek.gov.tr", "gönderen adresi")
        kontrol(sayfa[1].gonderen_ad == "Ayşe Yılmaz", "gönderen adı")
        kontrol(sayfa[1].tarih.startswith("18.11.2026"), "tarih biçimi")
        sayfa2, _ = istemci.mesajlar(klasor="inbox", sayfa_boyutu=2, offset=2,
                                     tazele=False)
        kontrol(len(sayfa2) == 1, "ikinci sayfa (onbellek, ağ yok)")

        # Arama (sunucu tarafı TEXT)
        a, at = istemci.mesajlar(klasor="inbox", arama="toplantı", alan="konu")
        kontrol(at == 1 and a and a[0].item_id == "102",
                f"sunucu araması eşleşti (toplam={at})")
        # Arama temizlenince tam liste geri gelir
        _, at2 = istemci.mesajlar(klasor="inbox", arama="", tazele=False)
        kontrol(at2 == 3, "arama temizlendi → tam liste")

        # Taşı / okundu
        m = sayfa[0]
        istemci.tasi(m, "deleteditems")
        komutlar = [k for k, _ in istemci.imap.komutlar]
        kontrol("move" in komutlar, "MOVE komutu gönderildi")
        istemci.okundu_isaretle(sayfa[1], True)
        kontrol(any(k == "store" for k, _ in istemci.imap.komutlar),
                "STORE (okundu) gönderildi")

        # APPEND (taslak) — gmail giden olduğu için gönderilen kopyası atlanır
        istemci.taslağa_kaydet("a@b.c", "Konu", "Gövde")
        appendler = [k for k, _ in istemci.imap.komutlar if k == "append"]
        kontrol(len(appendler) == 1, "taslak APPEND edildi")

        # Kimlik hatası → EwsYetkiHatasi (giriş akışı)
        kotu = imap_mod.ImapIstemci({
            "tur": "imap", "kullanici": "x@gmail.com", "parola": "yanlis",
            "gelen_sunucu": "imap.gmail.com", "gelen_port": 993,
            "giden_sunucu": "smtp.gmail.com", "giden_port": 465, "guvenli": "ssl",
        })
        try:
            kotu.klasor_listesi()
            kontrol(False, "yanlış parola hata fırlatmalı")
        except Exception as exc:
            kontrol(type(exc).__name__ == "EwsYetkiHatasi",
                    f"yanlış parola → EwsYetkiHatasi ({type(exc).__name__})")

        # REGRESYON: komut ortasında sunucu BYE gönderdi (state=LOGOUT) →
        # istemci hata yolunda yeniden bağlanıp komutu başarıyla tamamlamalı
        # ("illegal in state LOGOUT" hatası kullanıcıya yansımamalı).
        istemci.imap.selecti_boz = True
        try:
            _, toplam_yeniden = istemci.mesajlar(klasor="inbox", tazele=True)
            kontrol(toplam_yeniden == 3,
                    "komut ortasındaki LOGOUT → otomatik yeniden bağlanma")
        except Exception as exc:
            kontrol(False, f"LOGOUT kurtarması hatasız olmalı, gelen: {exc}")

        # REGRESYON: bağlantı kalıcı olarak LOGOUT'ta kaldıysa (BYE sonrası)
        # bir sonraki işlemde atılıp yeniden bağlanmalı.
        istemci.imap.state = "LOGOUT"
        istemci._secili = None
        try:
            k2 = istemci.klasor_listesi()
            kontrol(bool(k2) and k2[0].kimlik == "inbox",
                    "LOGOUT'ta kalan bağlantı atıldı → yeniden liste alındı")
        except Exception as exc:
            kontrol(False, f"kalıcı LOGOUT kurtarması hatasız olmalı: {exc}")

        # Klasör silme (IMAP DELETE)
        try:
            istemci.klasor_sil("inbox")
            kontrol(False, "özel klasör (inbox) silinmemeli")
        except EwsHata as exc:
            kontrol("silinemez" in str(exc), f"özel klasör koruması ({exc})")
        istemci.klasor_sil("Proje X")
        kontrol(("delete", ('"Proje X"',)) in istemci.imap.komutlar,
                'DELETE "Proje X" komutu gönderildi')
        kontrol("Proje X" not in istemci._klasor_adlari,
                "silinen klasör haritadan düştü")
        try:
            istemci.klasor_sil("Korumali Klasor")
            kontrol(False, "sunucunun reddettiği klasör hata fırlatmalı")
        except EwsHata as exc:
            # Yol A: imaplib NO'yu döndürür → "sunucu reddetti";
            # yol B: BAD/hata fırlatılır → "IMAP komutu reddedildi".
            kontrol("reddetti" in str(exc) or "reddedildi" in str(exc),
                    f"sunucu reddi → okunur hata ({exc})")


def smtp_test():
    print("\n== imap: SMTP gönderimi ==")
    gonderilen = {}

    class SahteSMTP_SSL:
        def __init__(self, host, port, timeout=None):
            gonderilen["host"] = host
            gonderilen["port"] = port

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def login(self, kullanici, parola):
            gonderilen["login"] = (kullanici, parola)

        def send_message(self, msg, from_addr=None, to_addrs=None):
            gonderilen["msg"] = msg
            gonderilen["to"] = to_addrs

    with mock.patch.object(imap_mod.smtplib, "SMTP_SSL", SahteSMTP_SSL):
        istemci = imap_mod.ImapIstemci({
            "tur": "imap", "kullanici": "deneme@gmail.com",
            "parola": "uygulama-parolasi",
            "gelen_sunucu": "imap.gmail.com", "gelen_port": 993,
            "giden_sunucu": "smtp.gmail.com", "giden_port": 465,
            "guvenli": "ssl",
        })
        istemci.gonder("ali@ornek.gov.tr", "Merhaba", "Gövde metni",
                       ekler=[("not.txt", b"icerik", "text/plain")],
                       cc="ayse@ornek.gov.tr")
        kontrol(gonderilen.get("host") == "smtp.gmail.com", "smtp sunucusu")
        kontrol(gonderilen.get("login", ("", ""))[0] == "deneme@gmail.com",
                "smtp girişi")
        msg = gonderilen.get("msg")
        kontrol(msg is not None and msg["Subject"] == "Merhaba", "konu başlığı")
        kontrol(msg is not None and "ali@ornek.gov.tr" in msg["To"], "alıcı")
        kontrol(msg is not None and len(list(msg.iter_attachments())) == 1,
                "ek eklendi")
        kontrol(gonderilen.get("to") == ["ali@ornek.gov.tr", "ayse@ornek.gov.tr"],
                f"to_addrs ({gonderilen.get('to')})")


def main() -> int:
    config_test()
    imap_test()
    smtp_test()
    if HATALAR:
        print(f"\n!! {len(HATALAR)} HATA:")
        for h in HATALAR:
            print("   ", h)
        return 1
    print("\n✓ tüm testler geçti")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
