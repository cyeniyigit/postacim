#!/usr/bin/env python3
"""Haberler modülü + Haberler sekmesi testi (çevrimdışı).

Kapsar:
- haberler modülü: RSS 2.0 + Atom ayrıştırma (başlık/bağlantı/özet/tarih,
  media:content + enclosure + açıklama <img> medya bulma), windows-1254,
  metin_temizle, tarih_coz, sirala (tarihsizler sona), medya_indir
  (boyut sınırı), besleme_bul (doğrudan besleme / <link rel=alternate>
  keşfi / yaygın yollar / bulunamadı)
- arayüz: Haberler sekmesi (Takvim'in sağında), kaynak ekleme penceresi
  (hesap.json'a kayıt), tek liste + kaynak sütunu + combobox filtresi,
  okuyucu (başlık+meta+özet+tam metin), yazı tipi/boyut seçimi, resmi
  sorarak indirip gömme, videoyu indirip oynatıcıya verme, kaynak silme,
  sekme değişiminde otomatik tazeleme zamanlayıcısı

Kullanim:  xvfb-run -a .venv/bin/python tests/haber_test.py
"""
from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import time
from datetime import datetime, timedelta
from email.utils import format_datetime

os.environ["POSTACIM_GUNCELLEME"] = "0"  # gerçek ağ denetimi asla başlamasın

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from postacim.config import Ayarlar  # noqa: E402
from postacim.ews import Klasor  # noqa: E402
from postacim import haberler  # noqa: E402
import postacim.ui as ui_mod  # noqa: E402

HATALAR = []


def kontrol(kosul, mesaj):
    if kosul:
        print(f"  ✓ {mesaj}")
    else:
        HATALAR.append(mesaj)
        print(f"  !! {mesaj}")


def bekle(uygulama, saniye):
    bitis = time.time() + saniye
    while time.time() < bitis:
        uygulama.update()
        time.sleep(0.05)


BUGUN = datetime.now()
RFC_TARIH = format_datetime(BUGUN - timedelta(hours=2))
RFC_TARIH_ESKI = format_datetime(BUGUN - timedelta(days=3))

RSS = f"""<?xml version="1.0" encoding="utf-8"?>
<rss version="2.0" xmlns:media="http://search.yahoo.com/mrss/">
<channel><title>Örnek Gazete</title>
<item><title>Fiyatlar &amp; güncellendi</title>
<link>https://ornekgazete.com/haber-1</link>
<pubDate>{RFC_TARIH}</pubDate>
<description><![CDATA[<p>Özet <b>metni</b> &amp; ayrıntı</p>]]></description>
<media:content url="https://ornekgazete.com/r1.jpg" type="image/jpeg" medium="image"/>
</item>
<item><title>Videolu haber</title>
<link>https://ornekgazete.com/haber-2</link>
<pubDate>{RFC_TARIH}</pubDate>
<description>Düz özet</description>
<enclosure url="https://ornekgazete.com/v1.mp4" type="video/mp4"/>
</item>
<item><title>Açıklamada resim olan</title>
<link>https://ornekgazete.com/haber-3</link>
<pubDate>{RFC_TARIH_ESKI}</pubDate>
<description>&lt;img src="https://ornekgazete.com/i2.png"&gt; özet</description>
</item>
<item><title>Tarihsiz haber</title><link>https://ornekgazete.com/haber-4</link>
<description>xyz</description></item>
</channel></rss>"""

ATOM = f"""<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
<title>Atom Kaynak</title>
<entry><title>Atom başlığı</title>
<link rel="alternate" href="https://atomkaynak.com/1"/>
<published>{(BUGUN - timedelta(hours=1)).strftime('%Y-%m-%dT%H:%M:%SZ')}</published>
<summary>Atom özeti</summary></entry>
</feed>"""

HTML_KESEF = """<html><head>
<link rel="alternate" title="RSS" type="application/rss+xml"
      href="/rss/anasayfa.xml"></head><body>sayfa</body></html>"""

HTML_KESEF_YOK = "<html><head><title>x</title></head><body>y</body></html>"

MAKALE = """
<html><body>
<div class="sidebar"><p>Menü kısa satır</p><p>Diğer kısa satır</p></div>
<div class="newsDetailText">
<img src="https://ornekgazete.com/m1.jpg">
<p>ASIL PARAGRAF BİR: Bu haberin gövde metnidir ve otuz karakteri aşıyor.</p>
<p>Devamı için tıklayınız</p>
<p>ASIL PARAGRAF İKİ: İkinci gövde paragrafı, o da otuz karakteri aşıyor.</p>
</div>
<script>document.write("kirli")</script>
</body></html>"""


class SahteYanit:
    def __init__(self, icerik: bytes, tur: str = "text/xml",
                 url: str = "https://ornekgazete.com"):
        self.content = icerik
        self.text = icerik.decode("utf-8", errors="replace")
        self.url = url
        self.headers = {"Content-Type": tur}

    def raise_for_status(self):
        pass

    def iter_content(self, chunk_size=65536):
        for i in range(0, len(self.content), chunk_size):
            yield self.content[i:i + chunk_size]


class SahteHata(Exception):
    pass


def test_haberler_modulu():
    print("\n— haberler modülü (çevrimdışı ayrıştırma) —")

    liste = haberler._rss_ayristir(RSS.encode(), "Örnek Gazete", 100)
    kontrol(len(liste) == 4, f"RSS öğeleri okunur ({len(liste)})")
    kontrol(liste[0].baslik == "Fiyatlar & güncellendi",
            f"başlıkta varlık çözülür ({liste[0].baslik!r})")
    kontrol(liste[0].ozet == "Özet metni & ayrıntı",
            f"özet HTML'den temizlenir ({liste[0].ozet!r})")
    kontrol(liste[0].tarih is not None and liste[0].tarih < datetime.now(),
            "pubDate çözülür (yerel saate iner)")
    kontrol(liste[0].resim == "https://ornekgazete.com/r1.jpg",
            "media:content resmi bulunur")
    kontrol(liste[1].video == "https://ornekgazete.com/v1.mp4" and
            liste[1].resim is None,
            "enclosure video bulunur")
    kontrol(liste[2].resim == "https://ornekgazete.com/i2.png",
            "açıklamadaki <img> resmi bulunur")
    kontrol(liste[3].tarih is None and liste[3].video is None,
            "tarihsiz/medyasız öğe sorunsuz")

    sirali = haberler.sirala(liste)
    kontrol(sirali[0].baslik == "Fiyatlar & güncellendi" and
            sirali[-1].baslik == "Tarihsiz haber",
            "sıralama: en yeni önce, tarihsizler sona")

    atom = haberler._atom_ayristir(ATOM.encode(), "Atom Kaynak", 100)
    kontrol(len(atom) == 1 and atom[0].baslik == "Atom başlığı" and
            atom[0].baglanti == "https://atomkaynak.com/1" and
            atom[0].ozet == "Atom özeti" and atom[0].tarih is not None,
            "Atom öğesi ayrıştırılır")

    kontrol(haberler.metin_temizle("<p>A&nbsp;&amp; B</p><script>x</script>")
            == "A & B", f"metin_temizle etiket+varlık ({haberler.metin_temizle('<p>A&nbsp;&amp; B</p><script>x</script>')!r})")
    kontrol(haberler.tarih_coz("bozuk tarih") is None and
            haberler.tarih_coz("") is None, "tarih_coz bozuk girdide None")
    kontrol(haberler.tarih_coz(RFC_TARIH) is not None and
            haberler.tarih_coz("2026-11-27T10:00:00Z") is not None,
            "tarih_coz RFC822 + ISO 8601")

    # windows-1254 besleme
    cp = ('<?xml version="1.0" encoding="windows-1254"?>'
          '<rss version="2.0"><channel><title>Gazete</title>'
          f'<item><title>ŞÜkrü ğÜnler</title><link>https://x.com/1</link>'
          f'<pubDate>{RFC_TARIH}</pubDate></item></channel></rss>'
          ).encode("windows-1254")
    liste = haberler._rss_ayristir(cp, "Gazete", 100)
    kontrol(liste[0].baslik == "ŞÜkrü ğÜnler",
            f"windows-1254 bayt ayrıştırılır ({liste[0].baslik!r})")

    # medya_indir: akış + boyut sınırı
    eski_get = haberler.requests.get
    haberler.requests.get = lambda *a, **k: SahteYanit(b"abc12345")
    try:
        kontrol(haberler.medya_indir("https://x.com/d") == b"abc12345",
                "medya_indir akışı birleştirir")
        buyuk = haberler.medya_indir("https://x.com/d", en_fazla=4)
        kontrol(False, f"boyut sınırı aşılmalıydı ({buyuk!r})")
    except ValueError:
        kontrol(True, "medya_indir boyut sınırında ValueError verir")
    finally:
        haberler.requests.get = eski_get

    # --- besleme_bul: doğrudan besleme adresi ---
    eski_get = haberler.requests.get
    yol_img = {"sayfa": SahteYanit(HTML_KESEF.encode("utf-8"), "text/html"),
               "besleme": SahteYanit(RSS.encode(), "application/rss+xml",
                                     url="https://ornekgazete.com/rss/anasayfa.xml")}
    def sahte_get(adres, *a, **k):
        if adres.endswith("/rss/anasayfa.xml"):
            return yol_img["besleme"]
        if "anasayfa.xml" in adres:
            return yol_img["besleme"]
        return yol_img["sayfa"]
    haberler.requests.get = sahte_get
    try:
        besleme, baslik = haberler.besleme_bul(
            "https://ornekgazete.com/rss/anasayfa.xml")
        kontrol(besleme.endswith("/rss/anasayfa.xml") and baslik == "Örnek Gazete",
                f"besleme_bul: doğrudan besleme adresi ({besleme})")

        besleme, baslik = haberler.besleme_bul("https://ornekgazete.com/")
        kontrol(besleme.endswith("/rss/anasayfa.xml") and baslik == "Örnek Gazete",
                f"besleme_bul: <link rel=alternate> keşfi ({besleme})")

        # keşif bağlantısı yok → yaygın yollar denenir
        haberler.requests.get = lambda adres, *a, **k: (
            SahteYanit(RSS.encode(), "application/rss+xml",
                       url="https://ornekgazete.com/rss.xml")
            if adres == "https://ornekgazete.com/rss.xml" or
            adres == "https://ornekgazete.com/rss/anasayfa.xml"
            else SahteYanit(HTML_KESEF_YOK.encode(), "text/html"))
        besleme, baslik = haberler.besleme_bul("https://ornekgazete.com")
        kontrol("rss" in besleme and baslik == "Örnek Gazete",
                f"besleme_bul: yaygın yollar ({besleme})")

        haberler.requests.get = lambda adres, *a, **k: SahteYanit(
            HTML_KESEF_YOK.encode(), "text/html")
        try:
            haberler.besleme_bul("https://ornekgazete.com")
            kontrol(False, "besleme yoksa ValueError beklenirdi")
        except ValueError:
            kontrol(True, "besleme bulunamazsa ValueError")

        # şemasız adres düzeltilir
        haberler.requests.get = lambda adres, *a, **k: SahteYanit(
            RSS.encode(), "application/rss+xml")
        haberler.besleme_bul("ornekgazete.com/rss.xml")
        kontrol(True, "şemasız adres https:// ile denenir")
    finally:
        haberler.requests.get = eski_get

    # --- makale ayıklama (tam metin) ---
    paragraflar, resimler = haberler.makale_ayristir(MAKALE)
    kontrol(len(paragraflar) == 2 and
            paragraflar[0].startswith("ASIL PARAGRAF BİR") and
            paragraflar[1].startswith("ASIL PARAGRAF İKİ"),
            f"makale: gövde paragrafları seçilir ({len(paragraflar)})")
    kontrol(not any("Menü kısa" in p for p in paragraflar),
            "makale: yan sütun/menü paragrafları düşer")
    kontrol(not any("tıklayınız" in p for p in paragraflar),
            "makale: 'devamı için' paragrafı atılır")
    kontrol(not any("kirli" in p for p in paragraflar),
            "makale: script içeriği karışmaz")
    kontrol(resimler == ["https://ornekgazete.com/m1.jpg"],
            f"makale: gövde resmi toplanır ({resimler})")
    kontrol(haberler.makale_ayristir("<html><body>boş</body></html>") ==
            ([], []), "makale: paragrafsız sayfada boş")


class SahteIstemci:
    def __init__(self, hesap: dict):
        self.hesap = hesap

    def klasor_listesi(self):
        return [Klasor(kimlik="inbox", ad="Gelen Kutusu", toplam=0,
                       okunmamis=0)]

    def mesajlar(self, *a, **k):
        return [], 0

    def guncelle(self, klasorler=None):
        return {}

    def cozumle(self, metin, en_fazla=20):
        return []

    def mesaj_detay(self, mesaj):
        return mesaj

    def okundu_isaretle(self, mesaj, okundu=True):
        pass

    def tasi(self, mesaj, hedef="deleteditems"):
        pass

    def mesaj_mime(self, mesaj_id):
        return b"From: x\r\n\r\n"


def main() -> int:
    test_haberler_modulu()

    dizin = tempfile.mkdtemp(prefix="haber_test_")
    yol = os.path.join(dizin, "hesap.json")
    with open(yol, "w", encoding="utf-8") as f:
        json.dump({
            "hesaplar": [
                {"id": "kurum001", "ad": "Kurum", "tur": "ews",
                 "sunucu": "mail.ornek.gov.tr", "kullanici": "KURUM\\kisi",
                 "parola": "sifre", "yontem": "ntlm", "son_klasor": "inbox"},
            ],
            "aktif": "kurum001",
            "tema": "light", "otomatik_yenile": 0,
        }, f, ensure_ascii=False, indent=2)

    eski_ayarlar, eski_kur = ui_mod.Ayarlar, ui_mod.Postacim._istemci_kur
    ui_mod.Ayarlar = lambda: Ayarlar(yol)
    ui_mod.Postacim._istemci_kur = lambda self, hesap: SahteIstemci(hesap)

    import tkinter.messagebox as messagebox
    eski_sor = messagebox.askyesno
    eski_popen = ui_mod.subprocess.Popen
    acilanlar = []

    def sahte_popen(komut, **k):
        acilanlar.append(komut)
        return None

    # sahte ağ: besleme + küçük bir PNG + makale sayfası
    from PIL import Image
    tampon = io.BytesIO()
    Image.new("RGB", (60, 40), "#2266aa").save(tampon, format="PNG")
    PNG_BAYT = tampon.getvalue()

    makale_cagrilar = []

    def sahte_get(adres, *a, **k):
        if adres == "https://ornekgazete.com/r1.jpg":
            return SahteYanit(PNG_BAYT, "image/jpeg")
        if adres == "https://ornekgazete.com/v1.mp4":
            return SahteYanit(b"sahte-video-bayt", "video/mp4")
        if "/haber-" in adres:
            makale_cagrilar.append(adres)
            return SahteYanit(
                MAKALE.replace("https://ornekgazete.com/m1.jpg",
                               adres + "-m.jpg").encode("utf-8"),
                "text/html")
        return SahteYanit(RSS.encode(), "application/rss+xml",
                          url="https://ornekgazete.com/rss/anasayfa.xml")

    eski_haber_get = haberler.requests.get
    haberler.requests.get = sahte_get

    uygulama = None
    try:
        uygulama = ui_mod.Postacim()
        bekle(uygulama, 2)

        kontrol(uygulama.defter.index("end") == 3,
                "üç sekme var (Posta, Takvim, Haberler)")
        kontrol("Haberler" in uygulama.defter.tab(2, "text"),
                "üçüncü sekme Haberler")

        # --- sekmeye geç: widget'lar ancak seçili sekmede eşlenir ---
        uygulama.defter.select(2)
        bekle(uygulama, 1)
        kontrol(uygulama._haber_zamanlayici is not None,
                "sekme açılışı otomatik tazelemeyi kurar")

        # --- kaynak ekleme penceresi (ad + url) ile akış ---
        uygulama._haber_kaynak_formu()
        form = None
        for p in uygulama.winfo_children():
            if isinstance(p, ui_mod.tk.Toplevel) and \
                    p.title() == "Haber Kaynağı Ekle":
                form = p
        kontrol(form is not None, "Kaynak Ekle penceresi açılır")
        if form:
            def tum_cocuklar(w):
                liste = []
                for c in w.winfo_children():
                    liste.append(c)
                    liste.extend(tum_cocuklar(c))
                return liste

            girdiler = [c for c in tum_cocuklar(form)
                        if isinstance(c, ui_mod.ttk.Entry)]
            dugmeler = [c for c in tum_cocuklar(form)
                        if isinstance(c, ui_mod.ttk.Button)]
            kontrol(len(girdiler) == 2, f"pencerede ad + url alanı var "
                    f"({len(girdiler)})")
            girdiler[0].insert(0, "Örnek Gazete")     # gazete adı
            girdiler[1].insert(0, "ornekgazete.com")  # site adresi
            ekle_dugmesi = [d for d in dugmeler if d.cget("text") == "Ekle"]
            if ekle_dugmesi:
                ekle_dugmesi[0].invoke()
            bekle(uygulama, 3)
        kaynaklar = uygulama.ayarlar.al("haber_kaynaklari", [])
        kontrol(len(kaynaklar) == 1 and
                kaynaklar[0]["besleme"].endswith("/rss/anasayfa.xml") and
                kaynaklar[0]["ad"] == "Örnek Gazete",
                f"pencereden kaynak keşifle kaydedilir ({kaynaklar})")

        # --- combobox: kaynaklar + eklende otomatik seçilir ---
        kontrol(tuple(uygulama.haber_kaynak_secici.cget("values")) ==
                ("Tümü", "Örnek Gazete"),
                f"kaynak combobox'ı doldurulur "
                f"({uygulama.haber_kaynak_secici.cget('values')})")
        kontrol(uygulama.haber_kaynak_secim.get() == "Örnek Gazete",
                "eklenen kaynak combobox'ta seçilir")

        # --- ikinci kaynak (doğrudan) + filtre denemeleri ---
        uygulama._haber_site_ekle_uygula(
            {"ad": "Diğer Gazete", "besleme": "https://diger.com/rss.xml",
             "site": "https://diger.com"})
        bekle(uygulama, 3)
        kontrol(uygulama.haber_kaynak_secim.get() == "Diğer Gazete" and
                len(uygulama.haber_agaci.get_children()) == 4 and
                all(uygulama.haber_agaci.item(s, "values")[1] ==
                    "Diğer Gazete"
                    for s in uygulama.haber_agaci.get_children()),
                "combobox'tan seçilen gazeteye filtre uygulanır")
        uygulama.haber_kaynak_secim.set("Tümü")
        uygulama._haberler_listeyi_doldur()
        kontrol(len(uygulama.haber_agaci.get_children()) == 8,
                "'Tümü' seçiminde filtre kalkar")
        uygulama.haber_kaynak_secim.set("Örnek Gazete")
        uygulama._haberler_listeyi_doldur()
        kontrol(len(uygulama.haber_agaci.get_children()) == 4 and
                all(uygulama.haber_agaci.item(s, "values")[1] ==
                    "Örnek Gazete"
                    for s in uygulama.haber_agaci.get_children()),
                "diğer gazete seçimi yalnız onun haberlerini verir")
        uygulama.haber_kaynak_secim.set("Tümü")
        uygulama._haberler_listeyi_doldur()

        # --- liste: tek liste + kaynak sütunu ---
        bekle(uygulama, 1)
        satirlar = uygulama.haber_agaci.get_children()
        kontrol(len(satirlar) == 8, f"haberler listelenir ({len(satirlar)})")
        ilk = uygulama.haber_agaci.item(satirlar[0], "values")
        kontrol(ilk[1] == "Örnek Gazete" and "Fiyatlar" in ilk[2],
                f"kaynak sütunu + başlık ({ilk})")

        # --- okuyucu: başlık + kaynak + haberin TAMAMI ---
        uygulama.haber_agaci.selection_set(satirlar[0])
        bekle(uygulama, 3)
        icerik = uygulama.haber_metin.get("1.0", "end")
        kontrol("Fiyatlar & güncellendi" in icerik and
                "ASIL PARAGRAF BİR" in icerik and
                "ASIL PARAGRAF İKİ" in icerik,
                "okuyucuda haberin TAMAMI gösterilir")
        kontrol("Örnek Gazete" in icerik, "okuyucuda kaynak bilgisi")
        kontrol("Özet metni & ayrıntı" not in icerik,
                "tanıtım özeti tam metinle değişir")
        kontrol(uygulama._haber_tam.get(
                    "https://ornekgazete.com/haber-1") is not None,
                "tam metin önbelleğe alınır")
        kontrol(uygulama.haber_resim_dugmesi.winfo_ismapped() and
                uygulama.haber_tarayici_dugmesi.winfo_ismapped() and
                not uygulama.haber_video_dugmesi.winfo_ismapped(),
                "resimde: Resmi indir + Tarayıcıda aç görünür, video düğmesi gizli")

        # --- resmi sorarak indirip gömme ---
        uygulama._haber_resim_indir()
        bekle(uygulama, 3)
        kontrol(len(uygulama.haber_metin.image_names()) == 1,
                "onayla indirilen resim okuyucuya gömülür")

        # --- önbellek: geri dönünce makale yeniden çekilmez ---
        once = sum(1 for a in makale_cagrilar if a.endswith("haber-1"))
        uygulama.haber_agaci.selection_set(satirlar[1])
        bekle(uygulama, 3)
        uygulama.haber_agaci.selection_set(satirlar[0])
        bekle(uygulama, 2)
        sonra = sum(1 for a in makale_cagrilar if a.endswith("haber-1"))
        kontrol(once == sonra,
                f"tam metin önbellekten gelir, yeniden çekilmez "
                f"({once}→{sonra})")

        # --- video: indirip oynatıcıya verme ---
        uygulama.haber_agaci.selection_set(satirlar[1])
        uygulama.update()
        kontrol(uygulama.haber_video_dugmesi.winfo_ismapped(),
                "videolu haberde video düğmesi görünür")
        ui_mod.subprocess.Popen = sahte_popen  # yalnız video açma için
        uygulama._haber_video_indir()
        bekle(uygulama, 3)
        kontrol(len(acilanlar) == 1 and acilanlar[0][0] == "xdg-open",
                f"video xdg-open ile açılır ({acilanlar})")
        kontrol(acilanlar and os.path.exists(acilanlar[0][1]),
                "video geçici dosyaya yazılır")
        ui_mod.subprocess.Popen = eski_popen

        # --- kaynak silme (onaylı): combobox güncellenir, filtre sıfırlanır ---
        messagebox.askyesno = lambda *a, **k: True
        uygulama._haber_kaynak_sil()
        bekle(uygulama, 1)
        kontrol([k.get("ad") for k in
                 uygulama.ayarlar.al("haber_kaynaklari", [])] ==
                ["Diğer Gazete"],
                "kaynak silme tercihe yazılır")
        kontrol(tuple(uygulama.haber_kaynak_secici.cget("values")) ==
                ("Tümü", "Diğer Gazete") and
                uygulama.haber_kaynak_secim.get() == "Tümü",
                "silinen kaynak combobox'tan düşer, filtre Tümü'ye döner")

        # --- sekme değişimi: zamanlayıcı başlar/durur ---
        uygulama.defter.select(0)
        bekle(uygulama, 0.3)
        kontrol(uygulama._haber_zamanlayici is None,
                "Haberler sekmesinden çıkınca zamanlayıcı durur")
        uygulama.defter.select(2)
        bekle(uygulama, 0.3)
        kontrol(uygulama._haber_zamanlayici is not None,
                "Haberler sekmesine girince zamanlayıcı kurulur")

        # --- haber_hata türü: durum çubuğu + yüklendi sıfırlanır ---
        uygulama.haber_yuklendi = True
        uygulama._sonuc_isle(("haber_hata", None, "kopu"))
        kontrol("Haberler alınamadı" in uygulama.durum.get() and
                not uygulama.haber_yuklendi,
                "haber_hata durum çubuğunda bildirilir")

        # --- okuyucu yazı tipi seçimi (tercih + uygulama) ---
        from tkinter import font as tkfont_test
        degerler = tuple(uygulama.haber_font_secici.cget("values"))
        kontrol(len(degerler) >= 1 and
                uygulama.haber_yazi_tipi_degisken.get() in degerler,
                f"yazı tipi combobox'ı dolu ({degerler})")
        if len(degerler) > 1:
            yeni_aile = degerler[1]
            uygulama.haber_yazi_tipi_degisken.set(yeni_aile)
            uygulama._haber_font_degisti()
            aile = tkfont_test.Font(
                font=uygulama.haber_metin.cget("font")).actual("family")
            kontrol(uygulama.ayarlar.al("haber_yazi_tipi") == yeni_aile and
                    aile == yeni_aile,
                    f"yazı tipi tercihe kaydedilir ve uygulanır ({yeni_aile})")
        eski_boyut = uygulama.haber_yazi_boyutu
        uygulama._haber_font_boyut_degistir(1)
        beklenen = min(20, eski_boyut + 1)
        boyut = tkfont_test.Font(
            font=uygulama.haber_metin.cget("font")).actual("size")
        kontrol(uygulama.haber_yazi_boyutu == beklenen and
                uygulama.ayarlar.al("haber_yazi_boyutu") == beklenen and
                boyut == beklenen,
                f"A+ boyutu artırır ve kaydeder ({boyut})")
        uygulama.haber_yazi_boyutu = 8
        uygulama._haber_font_boyut_degistir(-1)
        kontrol(uygulama.haber_yazi_boyutu == 8, "boyut 8'in altına inmez")
    finally:
        if uygulama is not None:
            uygulama.destroy()
        ui_mod.Ayarlar, ui_mod.Postacim._istemci_kur = eski_ayarlar, eski_kur
        messagebox.askyesno = eski_sor
        ui_mod.subprocess.Popen = eski_popen
        haberler.requests.get = eski_haber_get

    if HATALAR:
        print(f"\n!! {len(HATALAR)} hata:")
        for h in HATALAR:
            print(f"  - {h}")
        return 1
    print("\n✓ tüm kontroller geçti")
    return 0


if __name__ == "__main__":
    sys.exit(main())
