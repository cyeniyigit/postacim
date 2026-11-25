"""Google OAuth2 oturumu testleri (çevrimdışı).

Kapsam:
- XOAUTH2 dize üretimi (RFC biçimi)
- İstemci kimliği kaydetme/okuma (0600)
- Token yenileme (requests.post sahte yanıtlarla)
- token_al: geçerli token ağa gitmez, bayat token yenilenir
- yetkilendirme: yerel loopback sunucu + PKCE + kod değişimi (sahte tarayıcı)
- IMAP/SMTP XOAUTH2 girişi (sahte imaplib/smtplib nesneleriyle)
- CalDAV Bearer başlığı + 401'de yenileme (sahte oturumla)

Ağ erişimi YOK — tüm Google uçları sahte yanıtlarla karşılanır.
"""

import base64
import json
import os
import sys
import tempfile
import threading
import time
import unittest
import urllib.parse
import urllib.request
from unittest import mock

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, KOK)

from postacim import google_oturum  # noqa: E402
from postacim.caldav import CalDavIstemci  # noqa: E402
from postacim.imap import ImapIstemci  # noqa: E402

ISTEMCI = {"client_id": "cid.apps.googleusercontent.com",
           "client_secret": "gizli"}


def _yanit(veri: dict, durum: int = 200):
    """requests.post için sahte yanıt."""
    class Yanit:
        status_code = durum
        text = json.dumps(veri)

        def json(self):
            return veri
    return Yanit()


class Xoauth2Test(unittest.TestCase):
    def test_dize_bicimi(self):
        dize = google_oturum._xoauth2_dize("a@b.c", "tok")
        ham = base64.b64decode(dize).decode("utf-8")
        # RFC: user=^Aauth=Bearer ^A^A
        self.assertEqual(ham, "user=a@b.c\x01auth=Bearer tok\x01\x01")


class IstemciTest(unittest.TestCase):
    def setUp(self):
        self.dizin = tempfile.mkdtemp()
        self.yol = os.path.join(self.dizin, "google_istemci.json")

    def test_kaydet_ve_oku(self):
        google_oturum.istemci_yukle.cache_clear() if hasattr(
            google_oturum.istemci_yukle, "cache_clear"
        ) else None
        kaynak = os.path.join(self.dizin, "indirilen.json")
        with open(kaynak, "w", encoding="utf-8") as f:
            json.dump({"installed": {
                "client_id": "cid", "client_secret": "gizli",
            }}, f)
        kimlik = google_oturum.istemci_kaydet(kaynak, self.yol)
        self.assertEqual(kimlik, {"client_id": "cid", "client_secret": "gizli"})
        self.assertEqual(os.stat(self.yol).st_mode & 0o777, 0o600)
        okunan = google_oturum.istemci_yukle(self.yol)
        self.assertEqual(okunan["client_id"], "cid")

    def test_oku_duz_bicim(self):
        with open(self.yol, "w", encoding="utf-8") as f:
            json.dump({"client_id": "d", "client_secret": "s"}, f)
        okunan = google_oturum.istemci_yukle(self.yol)
        self.assertEqual(okunan["client_id"], "d")

    def test_oku_yok(self):
        with self.assertRaises(google_oturum.OturumHatasi):
            google_oturum.istemci_yukle(
                os.path.join(self.dizin, "yok.json")
            )


class TazelemeTest(unittest.TestCase):
    def test_tazele(self):
        gonderilen = {}

        def sahte_post(adres, data=None, timeout=None):
            gonderilen.update(data or {})
            return _yanit({
                "access_token": "yeni-erisim",
                "expires_in": 3600,
                # refresh_token YOK → eski değer korunmalı
            })

        kayit = {"refresh_token": "rt-eski", "access_token": "eski",
                 "sona_erme": 0}
        with mock.patch.object(google_oturum.requests, "post", sahte_post):
            yeni = google_oturum.tazele(kayit, ISTEMCI)
        self.assertEqual(yeni["access_token"], "yeni-erisim")
        self.assertEqual(gonderilen["grant_type"], "refresh_token")
        self.assertEqual(gonderilen["refresh_token"], "rt-eski")
        self.assertEqual(gonderilen["client_id"], ISTEMCI["client_id"])
        self.assertEqual(yeni["refresh_token"], "rt-eski")  # korundu
        self.assertGreater(yeni["sona_erme"], time.time())

    def test_tazele_yeni_refresh(self):
        def sahte_post(adres, data=None, timeout=None):
            return _yanit({
                "access_token": "yeni", "refresh_token": "rt-yeni",
                "expires_in": 1200,
            })

        with mock.patch.object(google_oturum.requests, "post", sahte_post):
            yeni = google_oturum.tazele({"refresh_token": "eski"}, ISTEMCI)
        self.assertEqual(yeni["refresh_token"], "rt-yeni")

    def test_tazele_hata(self):
        def sahte_post(adres, data=None, timeout=None):
            return _yanit({"error": "invalid_grant"}, durum=400)

        with mock.patch.object(google_oturum.requests, "post", sahte_post):
            with self.assertRaises(google_oturum.YetkiHatasi):
                google_oturum.tazele({"refresh_token": "rt"}, ISTEMCI)


class TokenAlTest(unittest.TestCase):
    def test_gecerli_token_aga_gitmez(self):
        kayit = {"access_token": "taze", "sona_erme": time.time() + 3600,
                 "refresh_token": "rt"}
        with mock.patch.object(google_oturum.requests, "post") as sahte:
            self.assertEqual(google_oturum.token_al(kayit, ISTEMCI), "taze")
            sahte.assert_not_called()

    def test_bayat_token_yenilenir(self):
        kayit = {"access_token": "bayat", "sona_erme": time.time() - 10,
                 "refresh_token": "rt"}
        saklanan = []

        def sahte_post(adres, data=None, timeout=None):
            return _yanit({"access_token": "yeni", "expires_in": 3600})

        with mock.patch.object(google_oturum.requests, "post", sahte_post):
            token = google_oturum.token_al(kayit, ISTEMCI,
                                           tazele_islevi=saklanan.append)
        self.assertEqual(token, "yeni")
        self.assertEqual(saklanan and saklanan[0]["access_token"], "yeni")


class YetkilendirTest(unittest.TestCase):
    """Loopback akışı: sahte tarayıcı kodu geri çağırır, token değişimi sahte."""

    def test_akis(self):
        acilan = {}

        def sahte_tarayici(adres):
            acilan["adres"] = adres
            return True

        def sahte_post(adres, data=None, timeout=None):
            # Kod değişimi: PKCE doğrulayıcı geri gelmeli
            self.assertEqual(data["code"], "gelen-kod")
            self.assertEqual(data["code_verifier"], dogrulayici["deger"])
            self.assertEqual(data["redirect_uri"], dogrulayici["yonlendirme"])
            return _yanit({
                "access_token": "erisim", "refresh_token": "taze",
                "expires_in": 3599, "scope": "https://mail.google.com/",
            })

        # PKCE doğrulayıcıyı yakalamak için yetkilendiriciyi sararız
        dogrulayici = {"deger": "", "yonlendirme": ""}

        gercek = google_oturum._yerel_sunucu

        def sarili_sunucu():
            sunucu, sonuc, olay = gercek()
            port = sunucu.server_address[1]
            dogrulayici["yonlendirme"] = f"http://localhost:{port}"
            return sunucu, sonuc, olay

        gercek_degistir = google_oturum._token_degistir

        def sarili_token(istemci, veri):
            dogrulayici["deger"] = veri.get("code_verifier", "")
            return gercek_degistir(istemci, veri)

        sonuc_kayit = {}

        def is_():
            try:
                sonuc_kayit["kayit"] = google_oturum.yetkilendir(
                    "a@b.c", ISTEMCI, beklemek=20
                )
                sonuc_kayit["hata"] = ""
            except Exception as exc:  # noqa: BLE001
                sonuc_kayit["hata"] = str(exc)

        with mock.patch.object(google_oturum.webbrowser, "open_new",
                               sahte_tarayici), \
             mock.patch.object(google_oturum, "_yerel_sunucu",
                               sarili_sunucu), \
             mock.patch.object(google_oturum, "_token_degistir",
                               sarili_token), \
             mock.patch.object(google_oturum.requests, "post", sahte_post):
            is_parcacigi = threading.Thread(target=is_, daemon=True)
            is_parcacigi.start()
            # Tarayıcı adresi açılana dek bekle
            for _ in range(100):
                if acilan.get("adres"):
                    break
                time.sleep(0.05)
            self.assertTrue(acilan.get("adres"), "tarayıcı adresi açılmadı")
            # Yetkilendirme URL'ini doğrula
            p = urllib.parse.parse_qs(
                urllib.parse.urlparse(acilan["adres"]).query
            )
            self.assertEqual(p["response_type"], ["code"])
            self.assertEqual(p["access_type"], ["offline"])
            self.assertEqual(p["prompt"], ["consent"])
            self.assertEqual(p["client_id"], [ISTEMCI["client_id"]])
            self.assertIn("mail.google.com", p["scope"][0])
            self.assertIn("calendar", p["scope"][0])
            self.assertEqual(p["login_hint"], ["a@b.c"])
            self.assertIn("code_challenge", p)
            # Sahte tarayıcı: Google kodu loopback'e GET ile geri çağırır
            yanit = urllib.request.urlopen(
                dogrulayici["yonlendirme"] + "?code=gelen-kod", timeout=10
            )
            self.assertEqual(yanit.status, 200)
            is_parcacigi.join(timeout=25)
        self.assertEqual(sonuc_kayit.get("hata"), "")
        kayit = sonuc_kayit.get("kayit") or {}
        self.assertEqual(kayit.get("access_token"), "erisim")
        self.assertEqual(kayit.get("refresh_token"), "taze")
        self.assertEqual(kayit.get("kullanici"), "a@b.c")

    def test_izin_verilmedi(self):
        acilan = {}

        def sahte_tarayici(adres):
            acilan["adres"] = adres
            return True

        gercek = google_oturum._yerel_sunucu
        sunucu_ref = {}

        def sarili_sunucu():
            s, sonuc, olay = gercek()
            sunucu_ref["port"] = s.server_address[1]
            return s, sonuc, olay

        hata_kayit = {}

        def is_():
            try:
                google_oturum.yetkilendir("a@b.c", ISTEMCI, beklemek=20)
                hata_kayit["hata"] = ""
            except Exception as exc:  # noqa: BLE001
                hata_kayit["hata"] = str(exc)

        with mock.patch.object(google_oturum.webbrowser, "open_new",
                               sahte_tarayici), \
             mock.patch.object(google_oturum, "_yerel_sunucu", sarili_sunucu):
            is_parcacigi = threading.Thread(target=is_, daemon=True)
            is_parcacigi.start()
            for _ in range(100):
                if acilan.get("adres"):
                    break
                time.sleep(0.05)
            urllib.request.urlopen(
                f"http://localhost:{sunucu_ref['port']}?error=access_denied",
                timeout=10,
            )
            is_parcacigi.join(timeout=25)
        self.assertIn("access_denied", hata_kayit.get("hata") or "")


class ImapXoauth2Test(unittest.TestCase):
    """Sahte imaplib bağlantısıyla XOAUTH2 giriş denetimi."""

    def test_giris_dizesi(self):
        hesap = {
            "tur": "imap", "kullanici": "a@b.c", "yontem": "oauth2",
            "oauth": {"access_token": "tok", "sona_erme":
                      time.time() + 3600, "refresh_token": "rt"},
        }
        istemci = ImapIstemci(hesap)
        yakalanan = {}

        class SahteImap:
            def authenticate(self, mekanizma, geri_cagri):
                yakalanan["mekanizma"] = mekanizma
                yakalanan["yanit"] = geri_cagri(b"")

        istemci._xoauth2_giris(SahteImap())
        self.assertEqual(yakalanan["mekanizma"], "XOAUTH2")
        # imaplib callback'in döndürdüğü veriyi KENDİSİ base64'ler →
        # geri çağrı HAM baytlar döndürmeli (çift kodlama olmamalı)
        ham = yakalanan["yanit"].decode("utf-8")
        self.assertEqual(ham, "user=a@b.c\x01auth=Bearer tok\x01\x01")

    def test_parola_yontemi_degismedi(self):
        hesap = {"tur": "imap", "kullanici": "a@b.c", "parola": "p",
                 "gelen_sunucu": "127.0.0.1", "gelen_port": 1}
        istemci = ImapIstemci(hesap)
        self.assertEqual(istemci.yontem, "parola")


class CalDavBearerTest(unittest.TestCase):
    """OAuth2 CalDAV istemcisi Bearer başlığı + 401 yenileme denetimi."""

    def test_bearer_basligi(self):
        istemci = CalDavIstemci(
            "https://takvim.ornek/dav/", "a@b.c", "",
            oauth={"access_token": "tok", "sona_erme":
                   time.time() + 3600, "refresh_token": "rt"},
        )
        yakalanan = {}

        class SahteYanit:
            status_code = 200
            text = ""
            headers = {}

            def json(self):
                return {}

        oturum = istemci.oturum
        gercek_request = oturum.request

        def sahte_request(metot, adres, data=None, headers=None,
                          timeout=None):
            yakalanan["basliklar"] = headers or {}
            return SahteYanit()

        oturum.request = sahte_request
        istemci._istek("PROPFIND", "https://takvim.ornek/dav/", veri="<x/>")
        self.assertEqual(
            yakalanan["basliklar"].get("Authorization"), "Bearer tok"
        )

    def test_401_yenileme(self):
        istemci = CalDavIstemci(
            "https://takvim.ornek/dav/", "a@b.c", "",
            oauth={"access_token": "bayat", "sona_erme":
                   time.time() + 3600, "refresh_token": "rt"},
        )
        saklanan = []
        istemci.token_sakla = saklanan.append
        cagri = {"sayi": 0}

        class Yanit:
            def __init__(self, kod):
                self.status_code = kod
                self.text = ""
                self.headers = {}

        def sahte_request(metot, adres, data=None, headers=None,
                          timeout=None):
            cagri["sayi"] += 1
            if cagri["sayi"] == 1:
                return Yanit(401)
            return Yanit(200)

        def sahte_post(adres, data=None, timeout=None):
            return _yanit({"access_token": "yeni", "expires_in": 3600})

        def sahte_tazele(kayit, istemci=None):
            yeni = dict(kayit)
            yeni["access_token"] = "yeni"
            yeni["sona_erme"] = time.time() + 3600
            return yeni

        istemci.oturum.request = sahte_request
        with mock.patch.object(google_oturum.requests, "post", sahte_post), \
             mock.patch.object(google_oturum, "tazele", sahte_tazele):
            istemci._istek("PROPFIND", "https://takvim.ornek/dav/",
                           veri="<x/>")
        self.assertEqual(cagri["sayi"], 2)
        self.assertEqual(istemci.oauth["access_token"], "yeni")
        self.assertTrue(saklanan, "token_sakla çağrılmadı")

    def test_basic_yontemi_degismedi(self):
        istemci = CalDavIstemci("https://t.x/", "u", "p")
        self.assertIsNone(istemci.oauth)
        self.assertEqual(istemci.oturum.auth, ("u", "p"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
