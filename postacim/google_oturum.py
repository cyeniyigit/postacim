"""Google OAuth2 oturumu (Gmail IMAP/SMTP + CalDAV).

Google hesabını **tek yetkilendirme** ile posta ve takvimde kullanmayı
sağlar:

- IMAP/SMTP: SASL **XOAUTH2** (kapsam `https://mail.google.com/`)
- CalDAV: **Bearer** token (kapsam `https://www.googleapis.com/auth/calendar`)

## Akış

1. **İstemci kimliği** (`client_id`/`client_secret`) kullanıcının Google
   Cloud kurulumundan gelir ve `~/.config/postacim/google_istemci.json`
   içinde 0600 izinle durur (depoloya/girmez).
2. **Yetkilendirme:** yerel bir HTTP sunucusu (loopback) açılır, tarayıcı
   Google'da açılır; kullanıcı izin verince Google `code`'u geri çağırır.
   PKCE (S256) kullanılır, `access_type=offline` ile refresh token alınır.
3. **Token** çağıran tarafça saklanır (`hesap.json`, 0600).
4. **Yenileme:** erişim token'ı ~1 saat ömürlüdür; `token_al()` süresi
   geçince refresh token ile sessizce yeniler.

Referanslar: Google OAuth2 (developers.google.com/identity/protocols/
oauth2), XOAUTH2 (developers.google.com/gmail/imap/xoauth2-protocol).
"""

from __future__ import annotations

import base64
import hashlib
import http.server
import json
import os
import secrets
import stat
import threading
import time
import urllib.parse
import webbrowser

import requests

# Google uç noktaları (doğrulanmış)
AUTH_UC = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_UC = "https://oauth2.googleapis.com/token"

# Kapsamlar: posta (IMAP/SMTP) + takvim (CalDAV) — tek yetkilendirmede ikisi
KAPSAM_POSTA = "https://mail.google.com/"
KAPSAM_TAKVIM = "https://www.googleapis.com/auth/calendar"
KAPSAMLAR = [KAPSAM_POSTA, KAPSAM_TAKVIM]

# İstemci kimliği dosyası (kullanıcının Google Cloud kurulumundan)
ISTEMCI_DOSYA = os.path.join(
    os.path.expanduser("~"), ".config", "postacim", "google_istemci.json"
)


class OturumHatasi(Exception):
    """OAuth2 akışı başarısız."""


class YetkiHatasi(OturumHatasi):
    """Kullanıcı izin vermedi ya da istemci kimliği reddedildi."""


# ------------------------------------------------------------ istemci kimliği

def istemci_yukle(yol: str = ISTEMCI_DOSYA) -> dict:
    """İstemci kimliğini (client_id, client_secret) okur.

    Google'ın indirilen JSON biçimi (`installed` ya da `web` altındaki) ve
    düz `{"client_id": ..., "client_secret": ...}` biçimi kabul edilir.
    """
    try:
        with open(yol, "r", encoding="utf-8") as f:
            veri = json.load(f)
    except (OSError, ValueError) as exc:
        raise OturumHatasi(
            f"İstemci kimliği okunamadı: {yol} — Google Cloud'dan indirilen "
            "client_secret JSON dosyasını bu konuma kopyalayın."
        ) from exc
    kayit = veri.get("installed") or veri.get("web") or veri
    cid = kayit.get("client_id", "")
    gizli = kayit.get("client_secret", "")
    if not cid or not gizli:
        raise OturumHatasi("İstemci kimliği eksik (client_id/client_secret).")
    return {"client_id": cid, "client_secret": gizli}


def istemci_kaydet(kaynak_json: str, yol: str = ISTEMCI_DOSYA) -> dict:
    """Google'dan indirilen client_secret JSON'ını 0600 izinle kopyalar."""
    kimlik = istemci_yukle(kaynak_json)
    dizin = os.path.dirname(yol)
    os.makedirs(dizin, exist_ok=True)
    os.chmod(dizin, stat.S_IRWXU)
    gecici = yol + ".tmp"
    with open(gecici, "w", encoding="utf-8") as f:
        json.dump(kimlik, f, ensure_ascii=False)
    os.replace(gecici, yol)
    os.chmod(yol, stat.S_IRUSR | stat.S_IWUSR)  # 0600
    return kimlik


# ------------------------------------------------------------------ PKCE döngüsü

def _xoauth2_dize(kullanici: str, token: str) -> str:
    """SASL XOAUTH2 başlangıç yanıtını üretir (IMAP/SMTP ortak).

    Biçim: base64("user=<e-posta>^Aauth=Bearer <token>^A^A")
    """
    ham = f"user={kullanici}\x01auth=Bearer {token}\x01\x01"
    return base64.b64encode(ham.encode("utf-8")).decode("ascii")


def _yerel_sunucu() -> tuple[http.server.HTTPServer, list, threading.Event]:
    """Tek istek bekleyen yerel yetkilendirme sunucusu açar.

    Google `http://localhost:<port>?code=...` çağırır; kod yakalanır,
    tarayıcıya "bağlantı tamamlandı" sayfası gösterilir.
    """
    sonuc: list[dict] = []

    class Isleyici(http.server.BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802 (BaseHTTPRequestHandler)
            sorgu = urllib.parse.urlparse(self.path)
            parametreler = urllib.parse.parse_qs(sorgu.query)
            kod = (parametreler.get("code") or [""])[0]
            hata = (parametreler.get("error") or [""])[0]
            if kod or hata:
                sonuc.append({"code": kod, "error": hata})
                sayfa = (
                    "<html><head><meta charset='utf-8'>"
                    "<title>Postacım</title></head>"
                    "<body style='font-family:sans-serif;text-align:center;"
                    "padding-top:3em'>"
                    "<h2>✓ Postacım bağlandı</h2>"
                    "<p>Bu pencereyi kapatabilirsiniz.</p></body></html>"
                ).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(sayfa)))
                self.end_headers()
                self.wfile.write(sayfa)
                olay.set()
            else:
                # Google'ın yönlendirmesi değil: sessizce 404
                self.send_response(404)
                self.end_headers()

        def log_message(self, *args):  # sessizlik
            pass

    sunucu = http.server.HTTPServer(("127.0.0.1", 0), Isleyici)
    olay = threading.Event()
    threading.Thread(target=sunucu.serve_forever, daemon=True).start()
    return sunucu, sonuc, olay


def yetkilendir(
    kullanici: str,
    istemci: dict,
    kapsamlar: list[str] | None = None,
    beklemek: int = 300,
) -> dict:
    """Tarayıcıda yetkilendirme akışını yürütür; token kaydı döndürür.

    Döndürülen kayıt: {"access_token", "refresh_token", "sona_erme",
    "kapsam"}. Kaydı çağıran saklar (hesap.json).
    """
    istemci = istemci or istemci_yukle()

    # PKCE
    dogrulayici = secrets.token_urlsafe(64)[:96]
    meydan_okuma = base64.urlsafe_b64encode(
        hashlib.sha256(dogrulayici.encode("ascii")).digest()
    ).decode("ascii").rstrip("=")

    sunucu, sonuc, olay = _yerel_sunucu()
    port = sunucu.server_address[1]
    yonlendirme = f"http://localhost:{port}"
    try:
        parametreler = {
            "client_id": istemci["client_id"],
            "redirect_uri": yonlendirme,
            "response_type": "code",
            "scope": " ".join(kapsamlar or KAPSAMLAR),
            "access_type": "offline",   # refresh token istenir
            "prompt": "consent",        # refresh token garantisi
            "code_challenge": meydan_okuma,
            "code_challenge_method": "S256",
        }
        if kullanici:
            parametreler["login_hint"] = kullanici
        adres = AUTH_UC + "?" + urllib.parse.urlencode(parametreler)
        if not webbrowser.open_new(adres):
            raise OturumHatasi(
                "Tarayıcı açılamadı; adresi elle açın:\n" + adres
            )
        if not olay.wait(beklemek):
            raise OturumHatasi("Yetkilendirme zaman aşımına uğradı.")
        ilk = sonuc[0] if sonuc else {}
        if ilk.get("error"):
            raise YetkiHatasi(
                "İzin verilmedi: " + str(ilk["error"])
            )
        kod = ilk.get("code")
        if not kod:
            raise YetkiHatasi("Yetkilendirme kodu alınamadı.")
        token = _token_degistir(istemci, {
            "grant_type": "authorization_code",
            "code": kod,
            "redirect_uri": yonlendirme,
            "client_id": istemci["client_id"],
            "client_secret": istemci["client_secret"],
            "code_verifier": dogrulayici,
        })
        token["kullanici"] = kullanici
        return token
    finally:
        sunucu.shutdown()
        sunucu.server_close()


def _token_degistir(istemci: dict, veri: dict) -> dict:
    """Token isteğini yürütür; standart token kaydına çevirir."""
    try:
        yanit = requests.post(TOKEN_UC, data=veri, timeout=30)
    except requests.RequestException as exc:
        raise OturumHatasi(f"Token isteği başarısız: {exc}") from exc
    try:
        icerik = yanit.json()
    except ValueError:
        icerik = {}
    if yanit.status_code != 200:
        aciklama = icerik.get("error_description") or icerik.get("error") \
            or yanit.text[:200]
        raise YetkiHatasi(f"Token alınamadı ({yanit.status_code}): {aciklama}")
    erisim = icerik.get("access_token", "")
    tazeleme = icerik.get("refresh_token", "")
    if not erisim:
        raise OturumHatasi("Sunucudan erişim token'ı gelmedi.")
    omur = int(icerik.get("expires_in", 3600) or 3600)
    return {
        "access_token": erisim,
        "refresh_token": tazeleme,
        "sona_erme": int(time.time()) + max(omur - 60, 30),
        "kapsam": (icerik.get("scope") or "").split(" "),
    }


def tazele(token_kaydi: dict, istemci: dict | None = None) -> dict:
    """Erişim token'ını refresh token ile yeniler; kaydı güncel döndürür."""
    istemci = istemci or istemci_yukle()
    tazeleme = (token_kaydi or {}).get("refresh_token", "")
    if not tazeleme:
        raise OturumHatasi(
            "Refresh token yok — hesabı yeniden yetkilendirmek gerek."
        )
    yeni = _token_degistir(istemci, {
        "grant_type": "refresh_token",
        "refresh_token": tazeleme,
        "client_id": istemci["client_id"],
        "client_secret": istemci["client_secret"],
    })
    # Refresh token yenilenmezse (Google genelde aynı değeri döndürmezse
    # bile) eski değer korunur.
    kayit = dict(token_kaydi)
    kayit["access_token"] = yeni["access_token"]
    kayit["sona_erme"] = yeni["sona_erme"]
    if yeni.get("refresh_token"):
        kayit["refresh_token"] = yeni["refresh_token"]
    return kayit


def token_al(
    kayit: dict,
    istemci: dict | None = None,
    tazele_islevi=None,
) -> str:
    """Geçerli erişim token'ını döndürür; süresi geçtiyse yeniler.

    `tazele_islevi(kayit)` verilirse yenilenen kayıt saklamak için ona
    verilir (ör. hesabı hesap.json'a yazan işlev). Geçerli token varsa
    ağa hiç gidilmez ve istemci kimliği bile okunmaz.
    """
    kayit = kayit or {}
    if time.time() < int(kayit.get("sona_erme", 0) or 0) - 30:
        return kayit.get("access_token", "")
    istemci = istemci or istemci_yukle()
    yeni = tazele(kayit, istemci)
    if tazele_islevi is not None:
        try:
            tazele_islevi(yeni)
        except Exception:
            pass
    return yeni["access_token"]
