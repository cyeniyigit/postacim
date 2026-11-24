#!/usr/bin/env python3
"""Gövde resimleri testi: [resim: ad] yer tutucuları, çözümleme
(cid / http / data URI) ve arayüzde tıkla-göster + "Resimleri göster" akışı.

Kullanim:
    .venv/bin/python tests/resim_test.py
    xvfb-run -a .venv/bin/python tests/resim_test.py   # arayüz testleri dahil
"""
from __future__ import annotations

import base64
import io
import os
import sys
import threading
import time
import types
from http.server import BaseHTTPRequestHandler, HTTPServer

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from postacim.ews import (  # noqa: E402
    RESIM_SEMASI,
    Ek,
    EwsHata,
    Mesaj,
    Resim,
    govde_html_gosterim,
    html_metni,
    html_taglari_kapat,
    html_tablolar_onar,
    resim_verisi,
)

HATALAR = []


def kontrol(kosul, mesaj):
    if kosul:
        print(f"  ✓ {mesaj}")
    else:
        HATALAR.append(mesaj)
        print(f"  !! {mesaj}")


# ----------------------------------------------------------------- sahte parçalar


class SahteIstemci:
    """Sunucuya gitmeyen istemci (MIME + ek indirme taklidi)."""

    oturum = None

    def __init__(self, mime: bytes = b""):
        self.mime = mime
        self.ek_cagrilari: list[str] = []

    def mesaj_mime(self, mesaj_id: str) -> bytes:
        return self.mime

    def ek_indir(self, ek) -> bytes:
        self.ek_cagrilari.append(ek.ad)
        return b"ek-icerik"


class SahteYanit:
    status_code = 200
    content = b"ntlm-resim"

    def raise_for_status(self):
        pass


class SahteOturum:
    def get(self, url, timeout=None, headers=None):
        return SahteYanit()


class ResimHttpHandler(BaseHTTPRequestHandler):
    """GET /resim.png → PNG baytları; diğer her şeye 401."""

    png = b""
    istek_ua: list = []  # /resim.png isteklerinin User-Agent başlıkları

    def do_GET(self):
        if self.path == "/resim.png":
            self.istek_ua.append(self.headers.get("User-Agent") or "")
            self.send_response(200)
            self.send_header("Content-Type", "image/png")
            self.send_header("Content-Length", str(len(self.png)))
            self.end_headers()
            self.wfile.write(self.png)
        else:
            self.send_response(401)
            self.send_header("WWW-Authenticate", "NTLM")
            self.send_header("Content-Length", "0")
            self.end_headers()

    def log_message(self, *args):
        pass


def png_baytlari(renk=(255, 0, 0), boyut=(4, 4)) -> bytes:
    from PIL import Image

    tampon = io.BytesIO()
    Image.new("RGB", boyut, renk).save(tampon, "PNG")
    return tampon.getvalue()


def jpeg_baytlari(renk=(0, 128, 255), boyut=(4, 4)) -> bytes:
    from PIL import Image

    tampon = io.BytesIO()
    Image.new("RGB", boyut, renk).save(tampon, "JPEG")
    return tampon.getvalue()


def data_uri(mime: str, veri: bytes) -> str:
    return f"data:{mime};base64," + base64.b64encode(veri).decode("ascii")


# ------------------------------------------------------------------ html_metni


def test_yer_tutucular():
    print("\n— html_metni yer tutucuları —")
    resimler: list = []
    ekler = [Ek(ad="grafik.png", content_id="ii_1")]
    metin = html_metni(
        '<p>Önce</p><img src="cid:ii_1"><p>sonra</p>'
        '<img src="https://a.com/klasor/foto.jpg?w=10" alt="">'
        '<img src="data:image/png;base64,QUFB" alt="logo">',
        resimler,
        ekler,
    )
    kontrol(
        metin == "Önce\n[resim: grafik.png]sonra\n[resim: foto.jpg][resim: logo]",
        f"yer tutucular sırayla, satır içinde: {metin!r}",
    )
    kontrol(len(resimler) == 3, f"3 Resim kaydı: {len(resimler)}")
    kontrol(resimler[0].kaynak == "cid:ii_1", "cid kaynağı korunur")
    kontrol(resimler[0].yer_tutucu == "[resim: grafik.png]", "yer tutucu metni")
    kontrol(resimler[2].ad == "logo", "data: URI adı alt'tan")

    bos = html_metni("<p>düz <img src=\"x.png\"> metin</p>")
    kontrol("[resim: x.png]" in bos, "liste verilmezse de yer tutucu yazılır")

    temiz = html_metni('<img src="x.png" alt="a&lt;b&gt;c">', [], ekler)
    kontrol("<" not in temiz and ">" not in temiz, "ad temizliği: < > girmez")


def test_cozumleme():
    print("\n— resim_verisi çözümleme —")
    png = png_baytlari()
    mesaj = Mesaj(item_id="m1")

    veri = resim_verisi(None, mesaj, Resim(kaynak=data_uri("image/png", png)))
    kontrol(veri == png, "data: URI (base64) çözülür")

    ham_veri = b"\x89PNG ham"
    veri = resim_verisi(
        None, mesaj, Resim(kaynak="data:image/png," + "%89PNG%20ham")
    )
    kontrol(veri == ham_veri, "data: URI (yüzde kodlu) çözülür")

    # http: yerel sunucu
    ResimHttpHandler.png = png
    sunucu = HTTPServer(("127.0.0.1", 0), ResimHttpHandler)
    port = sunucu.server_address[1]
    threading.Thread(target=sunucu.serve_forever, daemon=True).start()
    try:
        ResimHttpHandler.istek_ua = []
        veri = resim_verisi(
            None, mesaj, Resim(kaynak=f"http://127.0.0.1:{port}/resim.png")
        )
        kontrol(veri == png, "http resmi indirilir")
        kontrol(bool(ResimHttpHandler.istek_ua) and
                "Mozilla/5.0" in ResimHttpHandler.istek_ua[0],
                f"uzak resim istekleri tarayıcı kimliğiyle gönderilir "
                f"({ResimHttpHandler.istek_ua})")

        # 401 → istemci oturumu (NTLM) ile yeniden dener
        istemci = SahteIstemci()
        istemci.oturum = SahteOturum()
        veri = resim_verisi(
            istemci,
            mesaj,
            Resim(kaynak=f"http://127.0.0.1:{port}/korumali.png"),
        )
        kontrol(veri == b"ntlm-resim", "401'de NTLM oturumuyla yeniden denenir")

        try:
            resim_verisi(
                None, mesaj, Resim(kaynak=f"http://127.0.0.1:{port}/yok.png")
            )
            kontrol(False, "olmayan http resmi hata vermeli")
        except EwsHata:
            kontrol(True, "indirilemeyen http resmi hata verir")
    finally:
        sunucu.shutdown()

    # cid → MIME parçası
    mime = (
        b"From: a@b\r\nTo: c@d\r\nSubject: t\r\nMIME-Version: 1.0\r\n"
        b'Content-Type: multipart/related; boundary="XX"\r\n\r\n'
        b'--XX\r\nContent-Type: text/html; charset="utf-8"\r\n\r\n'
        b'<img src="cid:ii_1">\r\n'
        b'--XX\r\nContent-Type: image/png\r\nContent-ID: <ii_1>\r\n'
        b'Content-Disposition: inline; filename="grafik.png"\r\n\r\n'
        + png
        + b"\r\n--XX--\r\n"
    )
    istemci = SahteIstemci(mime)
    veri = resim_verisi(istemci, mesaj, Resim(ad="grafik.png", kaynak="cid:ii_1"))
    kontrol(veri == png, "cid: MIME içinden Content-Id ile bulunur")

    veri = resim_verisi(istemci, mesaj, Resim(ad="grafik.png", kaynak="grafik.png"))
    kontrol(veri == png, "dosya adı ile MIME içinden bulunur")

    # ek listesi yedeği
    mesaj2 = Mesaj(item_id="m2", ekler=[Ek(ad="x.png", content_id="cid_x", mesaj_id="m2")])
    veri = resim_verisi(SahteIstemci(), mesaj2, Resim(kaynak="cid:cid_x"))
    kontrol(veri == b"ek-icerik", "MIME yoksa ek_indir yedeği çalışır")

    try:
        resim_verisi(SahteIstemci(), mesaj2, Resim(kaynak="cid:hiçbiri"))
        kontrol(False, "bulunamayan resim hata vermeli")
    except EwsHata:
        kontrol(True, "bulunamayan resim hata verir")


# ---------------------------------------------------------- html gösterim üretimi


def test_html_gosterim():
    print("\n— govde_html_gosterim —")
    mesaj = Mesaj(
        govde_html=(
            "<p>Merhaba</p><img src=\"cid:ii_1\"><img src=\"https://a.com/b.png\">"
            "<script>alert(1)</script><base href=\"http://x/\"><meta"
            " http-equiv=\"refresh\" content=\"1;url=y\">"
        ),
        resimler=[
            Resim(ad="logo.png", yer_tutucu="[resim: logo.png]"),
            Resim(ad="b.png", yer_tutucu="[resim: b.png]"),
        ],
    )
    h = govde_html_gosterim(mesaj)
    kontrol(
        f'<a href="{RESIM_SEMASI}0">[resim: logo.png]</a>' in h,
        "yer tutucu bağlantı + dosya adı",
    )
    kontrol(
        f'<a href="{RESIM_SEMASI}1">[resim: b.png]</a>' in h,
        "ikinci yer tutucu sıra ile",
    )
    kontrol("<img" not in h, "çözülmemiş hiçbir <img> kalmaz (uzak resim yok)")
    kontrol("alert(1)" not in h and "<script" not in h, "script atılır")
    kontrol("<base" not in h and "http-equiv" not in h, "base/meta yönlendirme atılır")

    gecen = {1: '<img src="data:image/png;base64,QQ==">'}
    h2 = govde_html_gosterim(mesaj, gecen)
    kontrol(
        '<img src="data:image/png;base64,QQ==">' in h2
        and f'{RESIM_SEMASI}1' not in h2,
        "çözülen resim data: URI olarak gömülür",
    )

    duz = govde_html_gosterim(Mesaj(govde="a <b> & c"))
    kontrol("a &lt;b&gt; &amp; c" in duz, "düz metin kaçırılır (<pre>)")
    kontrol(
        govde_html_gosterim(Mesaj(govde_html="<p>x</p>", resimler=[])).count("<a ") == 0,
        "resim yoksa bağlantı yok",
    )


def test_html_taglari_kapat():
    """Tkhtml segfault önlemi: kapanmamış table/tbody + yeni tablo."""
    print("\n— html_taglari_kapat —")
    # Tivibu tipi: </body> öncesi açık tbody/table, sonra yeni tablo
    bozuk = (
        "<html><body><table><tr><td>x</td></tr></table>"
        "<tbody></body></html>"
        "<table><tr><td>footer</td></tr></table>"
    )
    duz = html_taglari_kapat(bozuk)
    kontrol(
        duz.count("<tbody>") == duz.count("</tbody>"),
        "açık tbody kapatılır",
    )
    kontrol(
        duz.count("<table") == duz.count("</table>"),
        "açık table kapatılır",
    )
    kontrol(
        "</body></html>" in duz.replace(" ", ""),
        "</body></html> yapısı korunur",
    )
    # Bozulmamış HTML'e dokunulmaz
    saglam = "<html><body><p>ok</p></body></html>"
    kontrol(html_taglari_kapat(saglam) == saglam, "sağlam HTML aynen kalır")
    # Gösterim üretimi de kapatma uygular
    h = govde_html_gosterim(
        Mesaj(govde_html="<table><tr><td>a</td></tr><tbody>", resimler=[])
    )
    kontrol(
        h.count("<tbody>") == h.count("</tbody>"),
        "govde_html_gosterim kapanışı uygular",
    )


def test_html_tablolar_onar():
    """Tkhtml segfault önlemi: `<table>` çocuğu doğrudan `<table>`.

    Hepsiburada tipi bozuk e-posta: tablo, arada <tr><td> olmadan iç
    içe gelir; Tkhtml3 (C) bu yapıda segfault üretir. Tarayıcı kuralı
    uygulanır: çıplak çocuk `<tr><td>…</td></tr>` içine sarılır.
    """
    print("\n— html_tablolar_onar —")
    bozuk = (
        '<table style="margin-top: 2em;"><table'
        ' style="background-color:#fce7f5;border-radius:8px;">'
        "<tr><td>icerik</td></tr></table></table>"
    )
    duz = html_tablolar_onar(bozuk)
    kontrol(
        duz.count("<tr>") == duz.count("</tr>")
        and duz.count("<td") == duz.count("</td>"),
        f"çıplak çocuk sarıldı ({duz})",
    )
    kontrol(
        "style=\"margin-top: 2em;\"><tr><td><table" in duz,
        "sarma açılış etiketin hemen ardında",
    )
    kontrol(
        "</table></td></tr></table>" in duz,
        "sarma kapanışı çocuk tablonun kapanışından sonra",
    )
    # Art arda çıplak çocuklar
    coklu = "<table><table><tr><td>a</td></tr></table><table><tr><td>b</td></tr></table></table>"
    duz = html_tablolar_onar(coklu)
    kontrol(
        duz.count("<tr><td><table") == 2
        and duz.count("</table></td></tr>") == 2,
        f"her çıplak çocuk ayrıca sarılır ({duz})",
    )
    # Sağlam yapı değişmez
    saglam = (
        "<table><tr><td>"
        "<table><tr><td>normal iç içe</td></tr></table>"
        "</td></tr></table>"
    )
    kontrol(html_tablolar_onar(saglam) == saglam, "hücre içi tablo dokunulmaz")
    # tbody aracılığıyla açılmış çıplak çocuk da sarılır
    tbody = "<table><tbody><table><tr><td>x</td></tr></table></tbody></table>"
    duz = html_tablolar_onar(tbody)
    kontrol("<tbody><tr><td><table" in duz, "tbody altındaki çıplak çocuk sarılır")
    # Kapanmamış tablo: dosya sonunda sarmalama unutulmaz
    acik = "<table><table><tr><td>x</td></tr>"
    duz = html_tablolar_onar(acik)
    kontrol(
        duz.count("<table") == duz.count("</table")
        and "</td></tr>" in duz,
        f"kapanmamış tablonun sarmalaması kapatılır ({duz})",
    )
    # Gösterim üretimi onarımı uygular
    h = govde_html_gosterim(Mesaj(govde_html=bozuk, resimler=[]))
    kontrol(
        'style="margin-top: 2em;"><tr><td><table' in h,
        "govde_html_gosterim onarımı uygular",
    )


def test_html_onar_yorum_opakligi():
    """Yorum/script/style içindeki etiketler onarımı yanıltamaz.

    AliExpress tipi e-posta `<table>` içeren `<!--[if mso | IE]>…
    <![endif]-->` yorumlarıyla doludur; hayalet etiketler sayılınca
    gerçek tabloya yanlış `<tr><td>`/`</td></tr>` yerleşir ve Tkhtml
    (C) segfault üretir. Yorum içindekiler dokunulmalıdır.
    """
    print("\n— yorum opaklığı —")
    yorumlu = (
        "<div><table><tr><td>"
        "<!--[if mso | IE]><table><tr><td width=\"600\">"
        "<![endif]-->merhaba"
        "<!--[if mso | IE]></td></tr></table><![endif]-->"
        "</td></tr></table></div>"
    )
    kontrol(html_tablolar_onar(yorumlu) == yorumlu,
            "tablolar_onar: yorumdaki tablo sayılmaz")
    kontrol(html_taglari_kapat(yorumlu) == yorumlu,
            "taglari_kapat: yorumdaki kapanışlar sayılmaz")
    stil = "<style>td { color: red; } /* <table> </table> */</style><table><tr><td>x</td></tr></table>"
    kontrol(html_tablolar_onar(stil) == stil,
            "tablolar_onar: style gövdesi opak")
    script = "<script>var x = '<table><tr><td>';</script><table><tr><td>x</td></tr></table>"
    kontrol(html_taglari_kapat(script) == script,
            "taglari_kapat: script gövdesi opak")


# ----------------------------------------------------------------- EWS ayrıştırma


def test_ews_mesaj_detay():
    print("\n— EwsIstemci.mesaj_detay (SOAP) —")
    import xml.etree.ElementTree as ET

    from postacim.ews import EwsIstemci

    govde = (
        '<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" '
        'xmlns:t="http://schemas.microsoft.com/exchange/services/2006/types" '
        'xmlns:m="http://schemas.microsoft.com/exchange/services/2006/messages">'
        "<s:Body><m:GetItemResponse><m:ResponseMessages>"
        '<m:GetItemResponseMessage ResponseClass="Success"><m:Items><t:Message>'
        "<t:Subject>Konu</t:Subject>"
        "<t:Body BodyType=\"HTML\">&lt;p&gt;Merhaba&lt;/p&gt;&lt;img src=&quot;cid:ii_1&quot;&gt;</t:Body>"
        "<t:Attachments><t:FileAttachment>"
        "<t:Name>grafik.png</t:Name><t:ContentType>image/png</t:ContentType>"
        '<t:AttachmentId Id="A1"/><t:Size>5</t:Size>'
        "<t:ContentId>ii_1</t:ContentId>"
        "</t:FileAttachment></t:Attachments>"
        "</t:Message></m:Items></m:GetItemResponseMessage>"
        "</m:ResponseMessages></m:GetItemResponse></s:Body></s:Envelope>"
    )

    istemci = EwsIstemci(sunucu="sunucu", kullanici="u", parola="p")
    istemci.istek = lambda _govde, tekrar=3: ET.fromstring(govde)
    mesaj = Mesaj(item_id="E1")
    istemci.mesaj_detay(mesaj)

    kontrol(len(mesaj.ekler) == 1, f"ek listesi: {len(mesaj.ekler)}")
    kontrol(
        mesaj.ekler and mesaj.ekler[0].content_id == "ii_1",
        "EWS Content-Id okunur",
    )
    kontrol(len(mesaj.resimler) == 1, f"resim kaydı: {len(mesaj.resimler)}")
    kontrol(
        mesaj.resimler and mesaj.resimler[0].ad == "grafik.png",
        "yer tutucu adı ekten gelir",
    )
    kontrol("[resim: grafik.png]" in mesaj.govde, "gövdede yer tutucu görünür")


# ---------------------------------------------------------------- IMAP ayrıştırma


def test_imap_mesaj_detay():
    print("\n— ImapIstemci.mesaj_detay (MIME) —")
    from postacim.imap import ImapIstemci

    png = png_baytlari()
    mime = (
        b"From: a@b\r\nTo: c@d\r\nSubject: t\r\nMIME-Version: 1.0\r\n"
        b'Content-Type: multipart/related; boundary="XX"\r\n\r\n'
        b'--XX\r\nContent-Type: text/html; charset="utf-8"\r\n\r\n'
        b"<p>Merhaba</p><img src=\"cid:ii_1\">\r\n"
        b'--XX\r\nContent-Type: image/png\r\nContent-ID: <ii_1>\r\n'
        b'Content-Disposition: inline; filename="grafik.png"\r\n\r\n'
        + png
        + b"\r\n--XX--\r\n"
    )
    istemci = ImapIstemci({"kullanici": "u", "parola": "p"})
    istemci._mime_cek = lambda uid: mime  # sunucu yok
    mesaj = Mesaj(item_id="7")
    istemci.mesaj_detay(mesaj)

    kontrol(len(mesaj.ekler) == 1, f"ek listesi: {len(mesaj.ekler)}")
    kontrol(
        mesaj.ekler and mesaj.ekler[0].content_id == "ii_1",
        "ek Content-Id'si okunur",
    )
    kontrol(len(mesaj.resimler) == 1, f"resim kaydı: {len(mesaj.resimler)}")
    kontrol(
        mesaj.resimler and mesaj.resimler[0].ad == "grafik.png",
        "yer tutucu adı ekten gelir",
    )
    kontrol(
        "[resim: grafik.png]" in mesaj.govde,
        "gövdede yer tutucu görünür",
    )


# ---------------------------------------------------------------------- arayüz


def _arayuz_denetimi(html_mod: bool):
    etiket = "HTML okuyucu (tkinterweb)" if html_mod else "düz metin okuyucu"
    print(f"\n— arayüz ({etiket}): tıkla-göster + Resimleri göster —")
    try:
        import tkinter as tk
        import tkinter.messagebox as messagebox
    except Exception as exc:
        print(f"  -- tkinter yok, atlandı ({exc})")
        return

    try:
        kok = tk.Tk()
        kok.withdraw()
        kok.destroy()
    except tk.TclError:
        print("  -- DISPLAY yok (xvfb-run ile çalıştırın), atlandı")
        return

    import postacim.ui as ui_mod

    gercek_html = ui_mod.HtmlFrame
    if html_mod:
        if gercek_html is None:
            print("  -- tkinterweb kurulu değil, atlandı")
            return
    else:
        ui_mod.HtmlFrame = None  # düz metin okuyucuya zorla

    messagebox.showerror = lambda *a, **k: HATALAR.append(f"showerror {a}")
    messagebox.showinfo = lambda *a, **k: None
    messagebox.showwarning = lambda *a, **k: HATALAR.append(f"showwarning {a}")

    from postacim.ui import Postacim

    # Ağ/diyalog yan etkileri kapatılır; test gövdeye doğrudan mesaj verir.
    bos = lambda *a, **k: None  # noqa: E731
    Postacim.yenile = bos
    Postacim._ilk_baglanti = bos
    Postacim._diger_hesaplari_yukle = bos
    Postacim._otomatik_baslat = bos
    Postacim._hesap_ekle_penceresi = bos
    Postacim._kimlik_sor = lambda self, *a, **k: False

    uygulama = None
    try:
        uygulama = Postacim()
        # Açılış güncelleme kararı beklemeden ana pencereyi aç (600 ms'lik
        # karşılama denetimini atla) — çubuk haritalanma denetimi için.
        uygulama._acilisi_surdur()

        def bekle(saniye):
            bitis = time.time() + saniye
            while time.time() < bitis:
                uygulama.update()
                time.sleep(0.02)

        png = png_baytlari((255, 0, 0))
        jpg = jpeg_baytlari((0, 128, 255))
        mesaj = Mesaj(
            item_id="ui-1", konu="Resimli", gonderen="a@b.c",
            tarih="01.01.2026 00:00", okundu=True,
        )
        mesaj.govde = (
            "Başlık\n[resim: kirmizi.png] ortada [resim: yesil.jpg]\n"
            "[resim: yok.png]"
        )
        mesaj.govde_html = (
            "<p>Başlık</p><img src=\"cid:1\"> ortada <img src=\"cid:2\">"
            "<p><img src=\"https://uzak.com/yok.png\"></p>"
        )
        mesaj.resimler = [
            Resim(ad="kirmizi.png", kaynak=data_uri("image/png", png),
                  yer_tutucu="[resim: kirmizi.png]"),
            Resim(ad="yesil.jpg", kaynak=data_uri("image/jpeg", jpg),
                  yer_tutucu="[resim: yesil.jpg]"),
            Resim(ad="yok.png", kaynak="http://127.0.0.1:1/yok.png",
                  yer_tutucu="[resim: yok.png]"),
        ]
        uygulama._detay_goster(mesaj)
        bekle(0.4)

        kontrol(
            uygulama.resim_cubugu.winfo_ismapped(),
            "resim çubuğu görünür",
        )
        kontrol(
            "3 resim" in uygulama.resim_etiket.cget("text"),
            f"çubukta sayaç: {uygulama.resim_etiket.cget('text')!r}",
        )

        def govde_metni():
            if html_mod:
                return uygulama.ayrinti.get_page_text()
            return uygulama.ayrinti.get("1.0", "end")

        def gomulu_sayisi():
            return len(
                [a for a in uygulama.ayrinti.image_names()
                 if a.startswith("_tkinterweb") or a.startswith("govde_resim")]
            )

        kontrol(
            "[resim: kirmizi.png]" in govde_metni(),
            "ilk açılışta dosya adı yer tutucu olarak görünür",
        )

        if html_mod:
            kontrol(
                "<img" not in govde_html_gosterim(mesaj),
                "üretilen HTML'de çözülmemiş img yok",
            )
            # Yer tutucu bağlantısı tıklamaya bağlanmış mı?
            # (cget: işleyici iç TkinterWeb parçacığına kurulu olmalı —
            # HtmlFrame özniteliği olarak atamak tıklamaya ulaşmıyordu.)
            kontrol(
                uygulama.ayrinti.cget("on_link_click") ==
                uygulama._html_baglanti_tikla,
                "yer tutucu bağlantısı tıklama işleyicisine bağlı",
            )
            kontrol(
                uygulama.ayrinti.cget("on_link_click") ==
                uygulama._html_baglanti_tikla,
                "dış bağlantı işleyicisi de bağlı (tarayıcıda açılır)",
            )
            # request_func: dış ağ kapalı, data: açık
            url, veri, mime, kod = uygulama._govde_istek(
                data_uri("image/png", png)
            )
            kontrol(kod == 200 and veri == png, "data: URI isteğine izin verilir")
            _, _, _, kod = uygulama._govde_istek("https://uzak.com/a.png")
            kontrol(kod == 404, "dış kaynak istekleri engellenir")
            # Tıklamayı taklit et
            uygulama._html_baglanti_tikla(f"{RESIM_SEMASI}0")
        else:
            bas = uygulama.ayrinti.search(
                "[resim: kirmizi.png]", "1.0", stopindex="end"
            )
            kontrol(
                "resim_0" in uygulama.ayrinti.tag_names(bas),
                "yer tutucu tıklanabilir etiketle işaretli",
            )
            kutu = uygulama.ayrinti.bbox(bas)
            if kutu:
                olay = types.SimpleNamespace(x=kutu[0] + 2, y=kutu[1] + 2)
                uygulama._ayrinti_tikla(olay)
            else:
                uygulama._resim_goster(uygulama.resim_kayitlari[0])
        bekle(0.8)
        kontrol(
            gomulu_sayisi() >= 1,
            "tıklayınca resim gövdede belirir",
        )
        kontrol(
            "[resim: kirmizi.png]" not in govde_metni(),
            "yer tutucunun metni kalkar",
        )

        # Toplu göster → kalanlar (başarısız olan hariç hepsi denenir);
        # "Resimleri göster" düğmesi kaldırıldı, toplu yöntem doğrudan çağrılır
        uygulama.tum_resimleri_goster()
        bekle(1.2)
        kontrol(
            gomulu_sayisi() >= 2,
            "toplu gösterimle JPEG resim de görünür (Pillow)",
        )
        bekle(1.2)
        kontrol(
            "görüntülenemedi" in govde_metni(),
            "indirilemeyen resim gövdede belirtilir",
        )
        kontrol(
            uygulama.resim_kayitlari[1]["durum"] == "gosterildi",
            "kayıt durumları güncellenir",
        )
        kontrol(
            "gizli" not in uygulama.resim_etiket.cget("text"),
            f"tümü gösterilince sayaç gizli bildirmez "
            f"({uygulama.resim_etiket.cget('text')!r})",
        )

        # Mesaj değişince eski sonuçlar gövdeye yazılmaz
        uygulama._mesaj_alanini_temizle()
        bekle(0.2)
        kontrol(
            not uygulama.resim_cubugu.winfo_ismapped(),
            "mesaj değişince/resimsiz mesajda çubuk gizlenir",
        )
    finally:
        ui_mod.HtmlFrame = gercek_html
        if uygulama is not None:
            uygulama.destroy()


def test_arayuz():
    _arayuz_denetimi(html_mod=False)
    _arayuz_denetimi(html_mod=True)


def main() -> int:
    test_yer_tutucular()
    test_cozumleme()
    test_html_gosterim()
    test_html_taglari_kapat()
    test_html_tablolar_onar()
    test_html_onar_yorum_opakligi()
    test_ews_mesaj_detay()
    test_imap_mesaj_detay()
    test_arayuz()
    print()
    if HATALAR:
        print(f"BAŞARISIZ: {len(HATALAR)} kontrol")
        return 1
    print("Tüm kontroller geçti.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
