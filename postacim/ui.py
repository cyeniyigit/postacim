"""Postacim — EWS tabanlı e-posta istemcisi (Tkinter arayüzü)."""

from __future__ import annotations

import base64
import copy
import html as html_mod
import io
import os
import traceback
import queue
import re
import shutil
import subprocess
import threading
import time
import tkinter as tk
import webbrowser
from calendar import monthrange
from datetime import date, datetime, timedelta, timezone
from tkinter import font as tkfont, messagebox, ttk

import requests

try:
    import sv_ttk  # modern tema (Windows 11 tarzı); yoksa varsayılan ile devam
except ImportError:
    sv_ttk = None

try:
    from tkinterweb import HtmlFrame  # HTML gövde gösterimi (Tkhtml3)
except ImportError:
    HtmlFrame = None  # kurulu değilse düz metin okuyucu kullanılır

from .config import Ayarlar, KisiDefteri
from . import dosya_secici
from . import tekrar
from . import PROJE_ADRESI, __version__ as SURUM
from .ews import (
    KLASORLER,
    RESIM_SEMASI,
    EwsHata,
    EwsIstemci,
    EwsYetkiHatasi,
    Mesaj,
    Randevu,
    data_uri_verisi,
    govde_html_gosterim,
    html_metni,
    iso_yerel,
    resim_verisi,
)
from .imap import ImapIstemci, SIRA

UYGULAMA_ADI = "Postacım"
YAZI_TIPİ = "Ubuntu"  # sistemde yoksa Tk varsaylanına düşer

# Takvim görünümü stilleri (Ay|Hafta|Gün) — Ayarlar penceresinden değiştirilir.
# Değerler hesap.json → "takvim_stil" altında saklanır; eksik anahtar buradan.
TAKVIM_STIL_VARSAYILAN: dict = {
    "ay": {
        "hucre": "#ffffff",
        "hucre_metin": "#202124",
        "diger_ay": "#f0f0f0",
        "diger_ay_metin": "#9aa0a6",
        "bugun": "#fce8e6",
        "bugun_metin": "#c5221f",
        "secili": "#0b57d0",
        "secili_metin": "#ffffff",
        "bos": "#e8e8e8",
        "randevu": "#d2e3fc",
        "randevu_metin": "#174ea6",
        "baslik_font": ["TkDefaultFont", 10, "bold"],
        "gun_font": ["TkDefaultFont", 10],
        "randevu_font": ["TkDefaultFont", 8],
    },
    "hafta": {
        "hucre": "#ffffff",
        "hafta_sonu": "#f5f5f5",
        "bugun": "#fff8f7",
        "bugun_metin": "#c5221f",
        "randevu": "#d2e3fc",
        "randevu_metin": "#174ea6",
        "simdi": "#d93025",
        "baslik_font": ["TkDefaultFont", 9, "bold"],
        "saat_font": ["TkDefaultFont", 8],
        "randevu_font": ["TkDefaultFont", 8],
    },
    "gun": {
        "hucre": "#ffffff",
        "bugun": "#fff8f7",
        "tum_gun": "#fce8e6",
        "tum_gun_metin": "#c5221f",
        "randevu": "#d2e3fc",
        "randevu_metin": "#174ea6",
        "simdi": "#d93025",
        "saat_font": ["TkDefaultFont", 9],
        "randevu_font": ["TkDefaultFont", 9],
    },
}

# Koyu tema için takvim varsayılanları (kullanıcı özel stil kaydetmediyse
# bunlar kullanılır; böylece ızgara koyu zeminde de okunur kalır).
TAKVIM_STIL_KOYU: dict = {
    "ay": {
        "hucre": "#2b2b2b",
        "hucre_metin": "#e8eaed",
        "diger_ay": "#232323",
        "diger_ay_metin": "#8a8a8a",
        "bugun": "#4a2c2c",
        "bugun_metin": "#f28b82",
        "secili": "#174ea6",
        "secili_metin": "#ffffff",
        "bos": "#1c1c1c",
        "randevu": "#2f4f76",
        "randevu_metin": "#d2e3fc",
    },
    "hafta": {
        "hucre": "#2b2b2b",
        "hafta_sonu": "#262626",
        "bugun": "#4a2c2c",
        "bugun_metin": "#f28b82",
        "randevu": "#2f4f76",
        "randevu_metin": "#d2e3fc",
        "simdi": "#f28b82",
    },
    "gun": {
        "hucre": "#2b2b2b",
        "bugun": "#4a2c2c",
        "tum_gun": "#5c3a34",
        "tum_gun_metin": "#f28b82",
        "randevu": "#2f4f76",
        "randevu_metin": "#d2e3fc",
        "simdi": "#f28b82",
    },
}


class Postacim(tk.Tk):
    def __init__(self):
        super().__init__()
        # Uygulama adı (WM_CLASS) pencere oluşturulmadan ÖNCE ayarlanmalı;
        # görev çubuğu bu adı masaüstü girdisiyle (StartupWMClass=postacim)
        # eşleştirip doğru simgeyi gösterir.
        try:
            self.tk.call("tk", "appname", "postacim")
        except tk.TclError:
            pass
        self.geometry("1280x820")
        self.minsize(980, 620)

        self.ayarlar = Ayarlar()
        self.kisiler = KisiDefteri()  # otomatik tamamlama önbelleği
        aktif = self.ayarlar.aktif_hesap() or {}
        # ResolveNames yalnız Exchange (EWS) hesabında var; IMAP'ta kişilerden önerilir
        self.cozum_yok = aktif.get("tur") != "ews"
        self.tema = self.ayarlar.al("tema", "light")
        self.istemci = None
        self._istemciler: dict = {}          # hesap_id → bağlı istemci (önbellek)
        self._hesap_klasorleri: dict = {}    # hesap_id → [Klasor] (ağaç için)
        self.aktif_id = self.ayarlar.aktif_hesap_id()
        self.title(self._baslik_metni(aktif))
        self.mesajlar: list[Mesaj] = []
        self.klasor_liste: list = []
        self.secili: Mesaj | None = None
        self.resim_kayitlari: list = []  # gövdedeki satır içi resimler (yer tutucular)
        # Takvim durumu (EWS)
        self.randevular: list[Randevu] = []
        self._genis_randevular: list = []      # tekrarlar genişletilmiş liste
        self._genis_anahtar: tuple | None = None  # genişletme önbelleği anahtarı
        self.takvim_ay = (date.today().year, date.today().month)
        self.takvim_gun = date.today()
        self.takvim_yuklendi = False
        self._takvim_ciziliyor = False
        self.takvim_gorunum = self.ayarlar.al("takvim_gorunum", "ay")  # ay|hafta|gun
        # Takvim otomatik tazeleme (saniye; 0 = kapalı)
        takvim_aralik = self.ayarlar.al("takvim_otomatik_yenileme", 300)
        try:
            self.takvim_otomatik_aralik = int(takvim_aralik)
        except (TypeError, ValueError):
            self.takvim_otomatik_aralik = 300
        self._takvim_zamanlayici = None
        # Takvim renk/font stilleri (Ayarlar penceresi); eksikler varsayılanla
        kayitli_stil = self.ayarlar.al("takvim_stil", None)
        self._takvim_stil_ozel = bool(kayitli_stil)  # kullanıcı kendi stili seçti mi
        varsayilan = (
            TAKVIM_STIL_KOYU if self.tema == "dark" else TAKVIM_STIL_VARSAYILAN
        )
        self.takvim_stil: dict = {
            g: {**varsayilan[g], **(kayitli_stil or {}).get(g, {})}
            for g in varsayilan
        }
        self.klasor = aktif.get("son_klasor") or "inbox"
        self.is_kuyrugu: queue.Queue = queue.Queue()
        self.tasinan = None
        self.sayfa_no = 0
        self.sayfa_boyutu = 50
        self.sayfa_sayisi = 1
        self.tam_yenile = True
        self.oturum = True  # False: hesaptan çıkış yapıldı (kuyruk sonuçları yutulur)
        self._giris_soruluyor = False  # giriş penceresi açıkken yeniden açma
        otomatik_deger = self.ayarlar.al("otomatik_yenile", 60)
        try:
            self.otomatik_yenile = int(otomatik_deger)  # saniye; 0 = kapalı
        except (TypeError, ValueError):
            self.otomatik_yenile = 60
        self._otomatik_zamanlayici = None
        # Bildirim için: hesap_id → son bilinen gelen kutusu sayısı
        self._son_gelen_sayi: dict[str, int] = {}
        self._bildirim_arac = shutil.which("notify-send")
        self._bildirim_gdbus = shutil.which("gdbus")
        self._bildirim_acik = bool(self.ayarlar.al("bildirim", True))
        self._bildirim_balon_durumu: bool | None = None
        self._toast = None
        # Bildirim denetimi otomatik yenilemeden bağımsız çalışır
        self._bildirim_zamanlayici = None
        self._bildirim_bekliyor = False
        self._bildirim_aralik = 60  # saniye
        self._otomatik_bekliyor = False  # otomatik yenileme sonucu dönmediyse yeni tik atlanır
        self._is_sayaci = 0  # sonuçları henüz işlenmemiş arka plan işi sayısı
        self._secim_olayi_yut = 0  # yenilemeden gelen yapay seçim olayları
        # Kullanıcı mesaj listesinde fare düğmesini basılı tutarken listeyi
        # yeniden kurmayız (delete+insert, Tcl seçim sürüklemesiyle
        # çakışıp çökmeye yol açabilir); sonuç düğme kalkınca uygulanır.
        self._mouse_basili = False
        self._mouse_zamani = 0.0
        self._bekleyen_doldurma = None
        # Tk geri çağrı hataları varsayılan olarak yalnız terminale yazılır;
        # menüden açılan uygulamada iz kalmaz → kayda al ve göster.
        self.report_callback_exception = self._tk_hata_yakala

        # Tema widget'lar kurulmadan uygulanmali
        if sv_ttk is not None:
            sv_ttk.set_theme(self.tema, self)
        self.style = ttk.Style(self)

        self._arayuz_kur()
        self._kuyruk_yokla()
        self.after(120, self._kuyruk_yokla)
        self.protocol("WM_DELETE_WINDOW", self._kapat)
        # Hesap yoksa önce hesap ekleme; varsa kayıtlı kimlikle doğrudan
        # bağlan, yoksa giriş penceresini aç.
        if not self.ayarlar.hesaplar():
            self.after(300, self._hesap_ekle_penceresi)
        elif aktif.get("kullanici") and aktif.get("parola"):
            self.after(400, self.yenile)
        else:
            self.after(300, self._ilk_baglanti)
        # Diğer hesapların klasörleri de ağaçta görünsün (Evolution gibi)
        self.after(1500, self._diger_hesaplari_yukle)
        # Yeni mail bildirimi (otomatik yenilemeden bağımsız)
        self.after(2500, self._bildirim_baslat)
        self._otomatik_baslat()

    def _baslik_metni(self, hesap: dict) -> str:
        ad = (hesap or {}).get("ad") or (hesap or {}).get("kullanici")
        return f"{UYGULAMA_ADI} — {ad}" if ad else UYGULAMA_ADI

    # ------------------------------------------------------------ arayüz kurulumu

    def _arayuz_kur(self):
        self._ikonlari_yukle()
        self._pencere_simgesi()
        self._stil_uygula()
        self._menu_renkleri()
        self._menu_kur()
        self._ust_cubuk_kur()
        self._gövde_kur()
        self._durum_cubugu_kur()
        # Widget'lar kurulduktan sonra tema renkleri uygulanır
        self._stil_uygula()

    def _pencere_simgesi(self, pencere=None):
        """Pencere simgesini uygular (başlık çubuğu).

        Görev çubuğu/launcher eşleşmesi `WM_CLASS` ile yapılır ve Tk'de
        `wm class` komutu yoktur; bunun yerine uygulama adı (`tk appname`)
        **pencere oluşturulmadan önce** ayarlanır (bkz. `__init__`).
        """
        pencere = pencere if pencere is not None else self
        try:
            pencere.wm_iconname(UYGULAMA_ADI)
        except tk.TclError:
            pass
        ikon = self.ikon.get("uygulama_64") or self.ikon.get("uygulama")
        if ikon is None:
            return
        try:
            pencere.iconphoto(True, ikon)
            # Referansı tut (Tk, görsel Python tarafında yaşamazsa siler)
            self._pencere_simgesi_ref = ikon
        except tk.TclError:
            pass

    # ------------------------------------------------------------------ tema

    def _metin_rengi(self, arka: str) -> str:
        """Arka plana göre okunur metin rengi.

        sv_ttk bazı stillerde `foreground`'ı boş bırakır (böylece koyu temada
        siyah metin siyah zeminde kaybolurdu); bu yüzden arka planın
        parlaklığına bakılarak siyah/beyaz seçilir.
        """
        try:
            k, m, s = self.winfo_rgb(arka)
        except tk.TclError:
            return "#1c1c1c"
        parlaklik = (k * 299 + m * 587 + s * 114) / 1000
        return "#1c1c1c" if parlaklik > 32768 else "#ffffff"

    def _tema_renkleri(self) -> tuple[str, str]:
        """(arka plan, ön plan) — geçerli temaya göre."""
        arka = self.style.lookup("Treeview", "background") or "#ffffff"
        return arka, self._metin_rengi(arka)

    def _vurgu_rengi(self) -> str:
        """Temanın seçim/vurgu rengi."""
        try:
            for durum, renk in self.style.map("Treeview", "background"):
                if durum == "selected" and renk:
                    return renk
        except tk.TclError:
            pass
        return "#2b579a"

    def _stil_uygula(self):
        """Tema değişince özel stilleri ve tema-bağımlı renkleri ayarlar."""
        tip = (YAZI_TIPİ, 10)
        for ad in (".", "Treeview", "TButton", "TLabel", "TEntry", "TNotebook"):
            try:
                self.style.configure(ad, font=tip)
            except tk.TclError:
                pass
        # Klasör listesi: 20px ikonlar sığsın
        self.style.configure("Klasor.Treeview", rowheight=26, font=tip)
        # Ek listesi: 18px uzantı ikonları sığsın
        self.style.configure("Ek.Treeview", rowheight=26, font=tip)

        arka, on = self._tema_renkleri()
        vurgu = self._vurgu_rengi()
        # Yalnız düz metin okuyucu (tk.Text) bu seçenekleri alır;
        # HtmlFrame'in böyle seçenekleri yok.
        if hasattr(self, "ayrinti") and not self.html_modu:
            self.ayrinti.configure(
                bg=arka, fg=on, insertbackground=on,
                selectbackground=vurgu, selectforeground="#ffffff",
                font=(YAZI_TIPİ, 10),  # Text varsayılanı monospace'tir
            )
        if hasattr(self, "durum_etiket"):
            self.durum_etiket.configure(
                background=arka, foreground=on
            )

    def _menu_renkleri(self):
        """Tk klasik menüleri tema almaz; renkleri seçenek veritabanından verilir."""
        arka, on = self._tema_renkleri()
        vurgu = self._vurgu_rengi()
        self.option_add("*Menu.background", arka)
        self.option_add("*Menu.foreground", on)
        self.option_add("*Menu.activeBackground", vurgu)
        self.option_add("*Menu.activeForeground", "#ffffff")
        self.option_add("*Menu.disabledForeground", on)

    def _tema_degistir(self, tema: str):
        if sv_ttk is None:
            messagebox.showinfo("Bilgi", "Tema paketi (sv-ttk) kurulu değil.")
            return
        sv_ttk.set_theme(tema, self)
        self.tema = tema
        self.ayarlar.ayarla("tema", tema)
        self.ayarlar.kaydet()
        if hasattr(self, "tema_degisken"):
            self.tema_degisken.set(tema)
        self._stil_uygula()
        self._menu_renkleri()
        self._menu_kur()  # menü renkleri yeni temaya uysun diye yeniden kur
        # Takvim renkleri de temaya uysun (kullanıcı kendi stili seçmediyse)
        if not self._takvim_stil_ozel:
            varsayilan = (
                TAKVIM_STIL_KOYU if tema == "dark" else TAKVIM_STIL_VARSAYILAN
            )
            self.takvim_stil = {g: dict(varsayilan[g]) for g in varsayilan}
            if hasattr(self, "_gun_hucreleri"):
                self._takvim_stil_uygula()

    def _ikonlari_yukle(self):
        """Dugme ve klasor ikonlarini yukler (postacim/ikonlar/*.png)."""
        dizin = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ikonlar")
        self.ikon: dict[str, tk.PhotoImage] = {}
        for dosya in sorted(os.listdir(dizin)):
            if not dosya.endswith(".png"):
                continue
            try:
                self.ikon[dosya[:-4]] = tk.PhotoImage(
                    file=os.path.join(dizin, dosya)
                )
            except tk.TclError:
                continue

    def _menu_kur(self):
        menü = tk.Menu(self)
        dosya = tk.Menu(menü, tearoff=0)
        # İkonlar: sol tarafta, etiketle birlikte (compound)
        dosya.add_command(
            label="Yeni e-posta…", image=self.ikon["yeni"], compound="left",
            command=self.yeni_posta, accelerator="Ctrl+N",
        )
        dosya.add_command(
            label="Gönder/Al", image=self.ikon["gonder_al"], compound="left",
            command=self.gonder_al, accelerator="F9",
        )
        dosya.add_command(
            label="Klasörü yenile", image=self.ikon["yenile"], compound="left",
            command=self.yenile, accelerator="F5",
        )
        otomatik = tk.Menu(dosya, tearoff=0)
        self.otomatik_degisken = tk.IntVar(value=self.otomatik_yenile)
        for saniye, etiket in (
            (0, "Kapalı"), (30, "30 saniye"), (60, "1 dakika"),
            (120, "2 dakika"), (300, "5 dakika"),
        ):
            otomatik.add_radiobutton(
                label=etiket, variable=self.otomatik_degisken, value=saniye,
                command=lambda s=saniye: self._otomatik_degistir(s),
            )
        dosya.add_cascade(
            label="Otomatik yenileme", menu=otomatik,
            image=self.ikon["otomatik"], compound="left",
        )
        self.otomatik_menu = otomatik  # test için
        dosya.add_separator()
        dosya.add_command(
            label="Ayarlar…", image=self.ikon["ayarlar"], compound="left",
            command=self._ayarlar_penceresi, accelerator="Ctrl+,",
        )
        dosya.add_separator()
        dosya.add_command(
            label="Hesaptan Çıkış…", image=self.ikon["cikis"], compound="left",
            command=self.hesaptan_cikis, accelerator="Ctrl+Q",
        )
        dosya.add_command(
            label="Çıkış", image=self.ikon["cikis"], compound="left",
            command=self._kapat,
        )
        menü.add_cascade(label="Dosya", menu=dosya)

        # Hesaplar: hızlı geçiş (Evolution tarzı) + ekle/düzenle/sil
        hesaplar_m = tk.Menu(menü, tearoff=0)
        self.hesap_degisken = tk.StringVar(value=self.ayarlar.aktif_hesap_id())
        for h in self.ayarlar.hesaplar():
            ad = h.get("ad") or h.get("kullanici") or "Hesap"
            hesaplar_m.add_radiobutton(
                label=ad,
                variable=self.hesap_degisken,
                value=h.get("id", ""),
                command=lambda hid=h.get("id"): self._hesap_menu_sec(hid),
            )
        hesaplar_m.add_separator()
        hesaplar_m.add_command(
            label="Hesap Ekle…", image=self.ikon["hesap_ekle"], compound="left",
            command=self._hesap_ekle_penceresi,
        )
        hesaplar_m.add_command(
            label="Hesap Düzenle…", image=self.ikon["hesap_duzenle"], compound="left",
            command=self._hesap_duzenle_penceresi,
        )
        hesaplar_m.add_command(
            label="Hesap Sil…", image=self.ikon["sil"], compound="left",
            command=self._hesap_sil_penceresi,
        )
        menü.add_cascade(label="Hesaplar", menu=hesaplar_m)
        self.hesap_menu = hesaplar_m  # test için

        gorunum = tk.Menu(menü, tearoff=0)
        self.tema_degisken = tk.StringVar(value=self.tema)
        gorunum.add_radiobutton(
            label="Açık tema", image=self.ikon["tema_acik"], compound="left",
            variable=self.tema_degisken, value="light",
            command=lambda: self._tema_degistir("light"),
        )
        gorunum.add_radiobutton(
            label="Koyu tema", image=self.ikon["tema_koyu"], compound="left",
            variable=self.tema_degisken, value="dark",
            command=lambda: self._tema_degistir("dark"),
        )
        menü.add_cascade(label="Görünüm", menu=gorunum)

        eylem = tk.Menu(menü, tearoff=0)
        eylem.add_command(
            label="Oku", image=self.ikon["oku"], compound="left",
            command=self.bir_okundu,
        )
        eylem.add_command(
            label="Okunmadı yap", image=self.ikon["okunmadi"], compound="left",
            command=lambda: self.bir_okundu(False),
        )
        eylem.add_command(
            label="Yanıtla", image=self.ikon["yanitla"], compound="left",
            command=self.yanitla, accelerator="Ctrl+R",
        )
        eylem.add_command(
            label="İlet", image=self.ikon["ilet"], compound="left",
            command=self.ilet, accelerator="Ctrl+I",
        )
        eylem.add_command(
            label="Sil", image=self.ikon["sil"], compound="left",
            command=self.sil,
        )
        menü.add_cascade(label="Düzen", menu=eylem)
        yardim = tk.Menu(menü, tearoff=0)
        yardim.add_command(
            label="Bağlantı bilgisi", image=self.ikon["bilgi"], compound="left",
            command=self.baglanti_bilgisi,
        )
        yardim.add_command(
            label="Hakkında", image=self.ikon["hakkinda"], compound="left",
            command=self.hakkinda,
        )
        yardim.add_separator()
        yardim.add_command(
            label="Postacım'ı Kaldır…", image=self.ikon.get("sil"),
            compound="left", command=self.kaldir,
        )
        menü.add_cascade(label="Yardım", menu=yardim)
        self.config(menu=menü)
        self.ust_menu = menü  # test için
        self.bind_all("<Control-n>", lambda e: self.yeni_posta())
        self.bind_all("<Control-r>", lambda e: self.yanitla())
        self.bind_all("<Control-Shift-R>", lambda e: self.yanitla_herkese())
        self.bind_all("<Control-i>", lambda e: self.ilet())
        self.bind_all("<F5>", lambda e: self.yenile())
        self.bind_all("<F9>", lambda e: self.gonder_al())
        self.bind_all("<Control-q>", lambda e: self.hesaptan_cikis())
        self.bind_all("<Control-comma>", lambda e: self._ayarlar_penceresi())

    def _ust_cubuk_kur(self):
        cubuk = ttk.Frame(self, padding=(8, 6))
        cubuk.pack(fill="x")
        ttk.Label(cubuk, text="Konu/Gönderen:").pack(side="left")
        self.arama = tk.StringVar()
        giriş = ttk.Entry(cubuk, textvariable=self.arama, width=32)
        giriş.pack(side="left", padx=6)
        giriş.bind("<Return>", lambda e: self._arama_yap())
        ttk.Button(
            cubuk, text="Ara", image=self.ikon["ara"], compound="left",
            command=self._arama_yap,
        ).pack(side="left")
        ttk.Button(
            cubuk, text="Temizle", image=self.ikon["temizle"], compound="left",
            command=self._aramayi_temizle,
        ).pack(side="left", padx=4)
        ttk.Button(
            cubuk, text="Hesaptan Çıkış", image=self.ikon["cikis"], compound="left",
            command=self.hesaptan_cikis,
        ).pack(side="right", padx=(12, 0))
        ttk.Button(
            cubuk, text="Yeni e-posta", image=self.ikon["yeni"], compound="left",
            command=self.yeni_posta,
        ).pack(side="right")
        ttk.Button(
            cubuk, text="Yenile", image=self.ikon["yenile"], compound="left",
            command=self.yenile,
        ).pack(side="right", padx=6)
        ttk.Button(
            cubuk, text="Gönder/Al", image=self.ikon["gonder_al"], compound="left",
            command=self.gonder_al,
        ).pack(side="right")

    def _gövde_kur(self):
        # Posta | Takvim sekmeleri (Evolution gibi tek pencere)
        self.defter = ttk.Notebook(self)
        self.defter.pack(fill="both", expand=True, padx=8, pady=(0, 4))

        posta = ttk.Frame(self.defter)
        self.defter.add(posta, text="  📧 Posta  ")

        self.ana = ttk.PanedWindow(posta, orient="horizontal")
        self.ana.pack(fill="both", expand=True)

        # --- sol: klasörler ---
        # Listbox görüntü desteklemez; klasör ikonlari icin Treeview kullanilir.
        sol = ttk.Frame(self.ana, width=190)
        stil = ttk.Style(self)
        stil.configure("Klasor.Treeview", rowheight=26, font=("TkDefaultFont", 10))
        self.klasor_listesi = ttk.Treeview(
            sol, show="tree", selectmode="browse", style="Klasor.Treeview"
        )
        self.klasor_listesi.pack(fill="both", expand=True)
        self.klasor_listesi.bind("<<TreeviewSelect>>", self._klasor_secildi)
        self.klasor_listesi.bind("<Button-3>", self._klasor_menusu)
        self.ana.add(sol, weight=0)

        # --- orta: mesaj listesi ---
        orta = ttk.Frame(self.ana)

        # Sayfalama cubugu ONCE paketlenir: tam genisligini alir, kalan alan
        # listenin olur. (Once liste paketlendiğinde Treeview kendi dogal
        # genisliginde kaliyor, arada ~80px'lik bosluk olusuyordu.)
        sayfalama = ttk.Frame(orta)
        sayfalama.pack(side="bottom", fill="x", padx=4, pady=(3, 4))
        ttk.Button(
            sayfalama, text="Önceki", image=self.ikon["once"], compound="left",
            command=lambda: self._sayfa_degistir(-1),
        ).pack(side="left")
        self.sayfa_etiket = ttk.Label(sayfalama, text="Sayfa 1/1")
        self.sayfa_etiket.pack(side="left", padx=12)
        ttk.Button(
            sayfalama, text="Sonraki", image=self.ikon["sonra"], compound="left",
            command=lambda: self._sayfa_degistir(1),
        ).pack(side="left")

        liste_ala = ttk.Frame(orta)
        liste_ala.pack(fill="both", expand=True)

        self.liste = ttk.Treeview(
            liste_ala,
            columns=("durum", "gonderen", "konu", "tarih"),
            show="headings",
            selectmode="extended",  # Ctrl (tek tek) + Shift (aralık) çoklu seçim
        )
        self.liste.heading("durum", text="")
        self.liste.heading("gonderen", text="Gönderen")
        self.liste.heading("konu", text="Konu")
        self.liste.heading("tarih", text="Tarih")
        # Sutun toplami panonun genisliginden kucuk tutulur; fazlasini
        # gonderen/konu sutunlari esner. (Buyuk tutulursa Treeview kendi
        # dogal genisligine yapisir ve kaydirici 1 piksele sikisir.)
        # Tarih sutunu esnemez, tarih tamm gorunsun diye genis birakilir.
        self.liste.column("durum", width=26, stretch=False)
        self.liste.column("gonderen", width=130)
        self.liste.column("konu", width=170)
        self.liste.column("tarih", width=140, stretch=False)
        kaydirma = ttk.Scrollbar(liste_ala, orient="vertical", command=self.liste.yview)
        self.liste.configure(yscrollcommand=kaydirma.set)
        # Kaydirici once paketlenir ki yerini kesin alsin.
        kaydirma.pack(side="right", fill="y")
        self.liste.pack(side="left", fill="both", expand=True)
        self.liste.bind("<<TreeviewSelect>>", self._mesaj_secildi)
        self.liste.bind("<Delete>", lambda e: self.sil())
        self.liste.bind("<Button-3>", self._mesaj_menusu)
        self.liste.bind("<Control-c>", lambda e: self.kopyala() or "break")
        # Seçim sürüklemesi sürerken liste yeniden kurulmasın (çökme önlemi)
        self.liste.bind("<Button-1>", self._mouse_bastı)
        self.liste.bind("<ButtonRelease-1>", self._mouse_birakti)
        self.ana.add(orta, weight=1)

        # --- sağ: okuyucu ---
        sag = ttk.Frame(self.ana)
        self.baslik = ttk.Label(sag, text="Bir mesaj seçin", font=("TkDefaultFont", 11, "bold"))
        self.baslik.pack(anchor="w", padx=6, pady=(6, 2))
        # Resim cubugu: govdedeki satir ici resimler icin (Evolution tarzi).
        # Resim yokken paketlenmez; var olunca ayrinti'den once yerlestirilir.
        self.resim_cubugu = ttk.Frame(sag)
        self.resim_etiket = ttk.Label(self.resim_cubugu, text="")
        self.resim_etiket.pack(side="left", padx=(6, 10))
        self.resim_dugmesi = ttk.Button(
            self.resim_cubugu, text="Resimleri göster",
            image=self.ikon["ek_resim"], compound="left",
            command=self.tum_resimleri_goster,
        )
        self.resim_dugmesi.pack(side="left")
        self.html_modu = HtmlFrame is not None
        # Gövde görüntüleme durumu (zoom / otomatik sığdırma)
        self._gövde_zoom = 1.0
        self._gövde_oto_sigdir = bool(self.ayarlar.al("gövde_oto_sigdir", False))
        self._gövde_oto_sigdir_degisken = tk.BooleanVar(value=self._gövde_oto_sigdir)
        self._gövde_sigdir_zamanlandi = False
        # Araç çubuğu gövdenin ÜSTÜNDE olmalı: pack sırası = ekrandaki sıra.
        self._gövde_arac_kur(sag)
        if self.html_modu:
            # Gerçek HTML gösterimi (tkinterweb/Tkhtml3). script kapalı;
            # request_func ile dış kaynak istekleri engellenir.
            # horizontal_scrollbar="auto": geniş içerik (geniş tablo, sabit
            # aralıklı metin) görüntü alanından taşmasın, yatay kaydırma
            # çubuğuyla erişilebilsin. (Önceden çubuk yoktu; sağa kaymış
            # içeriğin bir kısmı hiç okunamıyordu.)
            self.ayrinti = HtmlFrame(
                sag,
                messages_enabled=False,
                javascript_enabled=False,
                forms_enabled=False,
                objects_enabled=False,
                horizontal_scrollbar="auto",
                vertical_scrollbar="auto",
                request_func=self._govde_istek,
            )
            self.ayrinti.pack(fill="both", expand=True, padx=8, pady=4)
            self.ayrinti.on_link_click = self._html_baglanti_tikla
            self.ayrinti.bind("<Configure>", self._gövde_boyut_degisti)
        else:
            # width=40: PanedWindow'a talep edilen genislik; pencere acildiginda
            # fill/expand ile pano genisligine yayilir.
            self.ayrinti = tk.Text(
                sag, wrap="word", padx=8, pady=6, bg="#fbfbfb", relief="flat",
                width=40, height=10,
            )
            self.ayrinti.pack(fill="both", expand=True, padx=4)
            self.ayrinti.configure(state="disabled")
            self.ayrinti.tag_configure("resim_hata", foreground="#b3261e")
            self.ayrinti.bind("<Button-1>", self._ayrinti_tikla)
            self.ayrinti.bind("<Motion>", self._ayrinti_hareket)
            self.ayrinti.bind("<Configure>", self._gövde_boyut_degisti)
        # Klavye/tekerlek kısayolları
        self.ayrinti.bind("<Control-MouseWheel>", self._gövde_tekerlek)
        self.ayrinti.bind("<Control-Key-0>", lambda e: self._gövde_zoom_uygula(1.0))
        self.ayrinti.bind("<Control-Key-minus>", lambda e: self._gövde_zoom_ayarla(self._gövde_zoom - 0.1))
        self.ayrinti.bind("<Control-Key-equal>", lambda e: self._gövde_zoom_ayarla(self._gövde_zoom + 0.1))
        self.bind("<Control-MouseWheel>", self._gövde_tekerlek)
        self.ek_cerçeve = ttk.LabelFrame(sag, text="Ekler", padding=4)
        self.ek_cerçeve.pack(fill="x", padx=6, pady=4)
        # Listbox ikon desteklemez; uzantı ikonları için Treeview kullanılır.
        self.ek_listesi = ttk.Treeview(
            self.ek_cerçeve, show="tree", height=3,
            selectmode="extended", style="Ek.Treeview",
        )
        self.ek_listesi.pack(fill="x")
        self.ek_listesi.bind("<Double-Button-1>", lambda e: self.ek_indir())
        self.ek_listesi.bind("<Control-a>", self._ek_tumunu_sec)
        self.ek_listesi.bind("<Button-3>", self._ek_menusu)
        self.ana.add(sag, weight=2)

        # --- Takvim sekmesi ---
        self.takvim_sayfa = ttk.Frame(self.defter)
        self.defter.add(self.takvim_sayfa, text="  📅 Takvim  ")
        self._takvim_kur()
        self.defter.bind("<<NotebookTabChanged>>", self._sekme_degisti)

    # ------------------------------------------------- gövde: zoom / sığdırma

    GOVDE_ZOOM_MIN = 0.3
    GOVDE_ZOOM_MAX = 3.0
    # Otomatik sığdırmada alt sınır: yazı tipi çok küçülünce okunmaz olur.
    # Bu sınırın altındaki içerikler yatay kaydırma çubuğuyla görülür.
    GOVDE_SIGDIR_ZOOM_MIN = 0.5

    def _gövde_arac_kur(self, ust: tk.Misc):
        """Gövde için zoom araç çubuğunu kurar.

        İçerik ekrandan geniş olduğunda mesajın sağa kaymış kısmı
        okunamıyordu; araç çubuğu hem yatay kaydırmayı hem de
        "genişliğe sığdır" işlemini sunar.
        """
        self.govde_arac = ttk.Frame(ust)
        self.govde_arac.pack(fill="x", padx=6, pady=(2, 0))
        ttk.Label(self.govde_arac, text="Gövde:").pack(side="left")
        ttk.Button(
            self.govde_arac, text="−", width=3,
            command=lambda: self._gövde_zoom_ayarla(self._gövde_zoom - 0.1),
        ).pack(side="left", padx=(6, 0))
        self.zoom_etiket = ttk.Label(
            self.govde_arac, text="100%", width=6, anchor="center"
        )
        self.zoom_etiket.pack(side="left", padx=2)
        ttk.Button(
            self.govde_arac, text="+", width=3,
            command=lambda: self._gövde_zoom_ayarla(self._gövde_zoom + 0.1),
        ).pack(side="left")
        ttk.Button(
            self.govde_arac, text="Sığdır",
            command=lambda: self._gövde_sigdir(),
        ).pack(side="left", padx=(8, 0))
        ttk.Checkbutton(
            self.govde_arac, text="Genişliğe sığdır",
            variable=self._gövde_oto_sigdir_degisken,
            command=self._gövde_oto_sigdir_degisti,
        ).pack(side="left", padx=(8, 0))
        ttk.Label(
            self.govde_arac, text="Ctrl+tekerlek: yakınlaştır",
            foreground="#666666",
        ).pack(side="right", padx=(6, 0))

    def _gövde_oto_sigdir_degisti(self):
        """'Genişliğe sığdır' seçeneğini uygular ve kaydeder."""
        self._gövde_oto_sigdir = bool(self._gövde_oto_sigdir_degisken.get())
        self.ayarlar.ayarla("gövde_oto_sigdir", self._gövde_oto_sigdir)
        self.ayarlar.kaydet()
        if self._gövde_oto_sigdir:
            self._gövde_sigdir()

    def _gövde_zoom_ayarla(self, zoom: float):
        """Yeni zoom değerini uygular (sınırlar içinde)."""
        zoom = max(self.GOVDE_ZOOM_MIN, min(self.GOVDE_ZOOM_MAX, float(zoom)))
        self._gövde_zoom_uygula(zoom)

    def _gövde_zoom_uygula(self, zoom: float):
        """Zoom'u gövdeye uygular ve etiketi günceller."""
        self._gövde_zoom = float(zoom)
        if self.html_modu:
            try:
                self.ayrinti.configure(zoom=self._gövde_zoom)
            except tk.TclError:
                pass
        else:
            # Metin modunda yazı tipi boyutu ölçeklenir.
            try:
                self.ayrinti.configure(font=("TkDefaultFont", int(10 * self._gövde_zoom)))
            except tk.TclError:
                pass
        try:
            self.zoom_etiket.configure(text=f"{int(round(self._gövde_zoom * 100))}%")
        except tk.TclError:
            pass

    def _gövde_gorunur_oran(self) -> float | None:
        """Gövdenin yatayda görünen oranı (0..1); taşma yoksa 1.0.

        tkinterweb `xview()` gösterilen aralığı (ilk, son) verir. İçerik
        görüntüden genişse oran 1'in altındadır.
        """
        html = getattr(self.ayrinti, "_html", None)
        if html is None:
            return None
        try:
            xview = html.xview()
        except (tk.TclError, TypeError, ValueError):
            return None
        try:
            if isinstance(xview, str):
                parcalar = xview.split()
                if len(parcalar) < 2:
                    return None
                ilk, son = float(parcalar[0]), float(parcalar[1])
            else:
                ilk, son = float(xview[0]), float(xview[1])
        except (TypeError, ValueError, IndexError):
            return None
        if son <= ilk:
            return None
        return max(0.0, min(1.0, son - ilk))

    def _gövde_sigdir(self, _deneme: int = 0):
        """Gövdeyi görüntü genişliğine sığdırır (zoom küçültülerek).

        Tkhtml'in yerleşimi ölçümden sonra yeniden hesaplanır ve ölçekleme
        tam doğrusal değildir; bu yüzden ölçüm birkaç tur tekrarlanır.
        İçerik okunabilirliğin bozulacağı kadar küçültülemezse yatay
        kaydırma çubuğu devreye girer.
        """
        if not self.html_modu:
            return
        try:
            self.ayrinti.update_idletasks()
            gorunum = self.ayrinti.winfo_width()
        except tk.TclError:
            return
        if gorunum < 20:
            return
        oran = self._gövde_gorunur_oran()
        if oran is None:
            return
        if oran >= 0.995:
            if _deneme == 0:
                self.durum.set("Gövde görüntü genişliğine sığdırıldı.")
            return  # zaten sığıyor
        yeni = max(self.GOVDE_SIGDIR_ZOOM_MIN, self._gövde_zoom * oran)
        yeni = min(1.0, yeni)
        if abs(yeni - self._gövde_zoom) < 0.01:
            self.durum.set(
                "Gövde ekrandan geniş — yatay kaydırma çubuğunu kullanın."
            )
            return
        self._gövde_zoom_uygula(yeni)
        if _deneme < 4:
            self.after(80, lambda: self._gövde_sigdir(_deneme + 1))
        else:
            self.durum.set(
                "Gövde ekrandan geniş — yatay kaydırma çubuğunu kullanın."
            )

    def _gövde_boyut_degisti(self, _olay=None):
        """Gövde alanı yeniden boyutlandırıldığında (otomatik sığdırma açıksa)."""
        if not self._gövde_oto_sigdir or self._gövde_sigdir_zamanlandi:
            return
        self._gövde_sigdir_zamanlandi = True
        self.after(150, self._gövde_sigdir_zamanlandi_ekle)

    def _gövde_sigdir_zamanlandi_ekle(self):
        """Sığdırma zamanlamasını temizler ve sığdırmayı uygular."""
        self._gövde_sigdir_zamanlandi = False
        self._gövde_sigdir()

    def _gövde_tekerlek(self, olay):
        """Ctrl+tekerlek: gövdeyi yakınlaştırır/uzaklaştırır."""
        adim = 0.1 if olay.delta > 0 else -0.1
        self._gövde_zoom_ayarla(self._gövde_zoom + adim)
        return "break"

    # ------------------------------------------------------------ Takvim

    def _sekme_degisti(self, _olay=None):
        """Takvim sekmesi açılınca randevuları arka planda çeker."""
        try:
            if self.defter.index("current") != 1:
                self._takvim_otomatik_durdur()
                return
        except tk.TclError:
            return
        if not self._takvim_kaynaklari():
            if hasattr(self, "ajanda_baslik"):
                self.ajanda_baslik.configure(text="Takvim")
                self.ajanda.delete(*self.ajanda.get_children())
                self.ajanda.insert(
                    "", "end", iid="yok",
                    values=("", "Bağlı takvim hesabı yok"),
                )
                self.ajanda_detay.configure(
                    text="“Takvim Hesapları” ile CalDAV (Gmail, Nextcloud, "
                    "iCloud…) bağlayın ya da Exchange (EWS) hesabına geçin."
                )
            return
        if not (self.takvim_yuklendi and self.randevular):
            self._takvim_cek()
        self._takvim_otomatik_baslat()

    # ---- takvim otomatik yenileme ----------------------------------------

    def _takvim_otomatik_baslat(self):
        """Takvim tazeleme zamanlayıcısını kurar (aralık 0 ise kurmaz)."""
        self._takvim_otomatik_durdur()
        if self.takvim_otomatik_aralik > 0:
            self._takvim_zamanlayici = self.after(
                self.takvim_otomatik_aralik * 1000, self._takvim_otomatik_tik
            )
    def _takvim_otomatik_durdur(self):
        if self._takvim_zamanlayici is not None:
            try:
                self.after_cancel(self._takvim_zamanlayici)
            except tk.TclError:
                pass
            self._takvim_zamanlayici = None

    def _takvim_otomatik_tik(self):
        self._takvim_zamanlayici = None
        try:
            self._takvim_otomatik_yap()
        finally:
            self._takvim_otomatik_baslat()

    def _takvim_otomatik_yap(self):
        """Takvimi sessizce tazeler (yalnız takvim sekmesi etkinken)."""
        if not self.oturum or self._giris_soruluyor:
            return
        if self._takvim_ciziliyor or self._is_sayaci > 0:
            return  # devam eden iş varsa bu tik atlanır
        try:
            if self.defter.index("current") != 1:
                return
        except tk.TclError:
            return
        if not self._takvim_kaynaklari():
            return
        self._takvim_cek()

    def _takvim_otomatik_degistir(self, saniye: int):
        """Takvim otomatik tazeleme aralığını değiştirir."""
        self.takvim_otomatik_aralik = saniye
        self.ayarlar.ayarla("takvim_otomatik_yenileme", saniye)
        self.ayarlar.kaydet()
        self._takvim_otomatik_baslat()
        self.durum.set(
            "Takvim otomatik yenileme kapalı" if saniye == 0
            else f"Takvim otomatik yenileme: {saniye} saniyede bir"
        )

    def _takvim_kaynaklari(self) -> list:
        """Kullanılabilir takvim kaynakları: [(tur, veri), ...].

        - EWS: aktif hesap EWS ise
        - CalDAV: kayıtlı tüm takvim hesapları
        """
        kaynaklar = []
        hesap = self.ayarlar.aktif_hesap() or {}
        if hesap.get("tur") == "ews" and hesap.get("kullanici") and hesap.get("parola"):
            kaynaklar.append(("ews", hesap))
        for t in self.ayarlar.takvimler():
            if t.get("tur") == "caldav" and t.get("url") and t.get("kullanici"):
                kaynaklar.append(("caldav", t))
        return kaynaklar

    def _caldav_istemci(self, takvim: dict):
        """CalDAV istemcisi üretir/önbellekler (takvim id → istemci)."""
        if not hasattr(self, "_caldav_istemciler"):
            self._caldav_istemciler: dict = {}
        tid = takvim.get("id", "")
        istemci = self._caldav_istemciler.get(tid)
        if istemci is None:
            from .caldav import CalDavIstemci

            istemci = CalDavIstemci(
                takvim.get("url", ""),
                takvim.get("kullanici", ""),
                takvim.get("parola", ""),
            )
            self._caldav_istemciler[tid] = istemci
        return istemci

    def _takvim_cek(self):
        """Tüm takvim kaynaklarını (EWS + CalDAV) arka planda çeker."""
        kaynaklar = self._takvim_kaynaklari()
        if not kaynaklar:
            return
        if self._takvim_ciziliyor:
            return
        self._takvim_ciziliyor = True
        self.durum.set("Takvim yükleniyor…")
        tam = not self.takvim_yuklendi

        def is_():
            tum: list = []
            hatalar: list = []
            for tur, veri in kaynaklar:
                try:
                    if tur == "ews":
                        istemci = self._istemciler.get(self.aktif_id)
                        if istemci is None or not hasattr(istemci, "takvim_randevulari"):
                            istemci = self._istemci_kur(veri)
                            self._istemciler[self.aktif_id] = istemci
                        gelen = list(istemci.takvim_randevulari(tam=tam))
                    else:
                        c = self._caldav_istemci(veri)
                        gelen = list(c.randevular())
                    # Kaynak bilgisi: silme/güncelleme doğru hesaba gitmeli
                    for r in gelen:
                        r.kaynak_id = veri.get("id", "")
                        r.kaynak_tur = tur
                    tum.extend(gelen)
                except Exception as exc:  # bir kaynak hataları diğerini bozmasın
                    hatalar.append(f"{veri.get('ad', tur)}: {exc}")
            if not tum and hatalar:
                raise EwsHata("; ".join(hatalar))
            return ("takvim", tum)

        threading.Thread(target=self._arka_plan, args=(is_,), daemon=True).start()

    def _takvim_kur(self):
        """Takvim sayfası: görünüm seçici + (Ay|Hafta|Gün) + ajanda."""
        ust = ttk.Frame(self.takvim_sayfa)
        ust.pack(fill="x", padx=8, pady=(8, 4))

        # Görünüm seçici (Evolution gibi)
        self.takvim_gorunum_degisken = tk.StringVar(value=self.takvim_gorunum)
        for ad, etiket in (("ay", "Ay"), ("hafta", "Hafta"), ("gun", "Gün")):
            ttk.Radiobutton(
                ust, text=etiket, value=ad,
                variable=self.takvim_gorunum_degisken,
                command=self._gorunum_degistir,
            ).pack(side="left", padx=(0, 4))

        ttk.Separator(ust, orient="vertical").pack(side="left", fill="y", padx=8)

        ttk.Button(ust, text="◀", width=3, command=lambda: self._yon_degistir(-1)).pack(
            side="left"
        )
        ttk.Button(ust, text="Bugün", command=self._bugune_git).pack(side="left", padx=4)
        ttk.Button(ust, text="▶", width=3, command=lambda: self._yon_degistir(1)).pack(
            side="left"
        )
        self.takvim_baslik = ttk.Label(
            ust, text="", font=("TkDefaultFont", 12, "bold")
        )
        self.takvim_baslik.pack(side="left", padx=16)

        ttk.Button(
            ust, text="Takvim Hesapları", command=self._takvim_hesaplari_penceresi
        ).pack(side="right", padx=(6, 0))
        ttk.Button(
            ust, text="Yeni Randevu", command=self._randevu_penceresi
        ).pack(side="right", padx=(6, 0))
        ttk.Button(
            ust, text="Yenile",
            command=lambda: (setattr(self, "takvim_yuklendi", False), self._takvim_cek()),
        ).pack(side="right")

        govde = ttk.Frame(self.takvim_sayfa)
        govde.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        # Sol: görünüm alanı (Ay | Hafta | Gün) — yalnız biri görünür
        self.gorunum_alan = ttk.Frame(govde)
        self.gorunum_alan.pack(side="left", fill="both", expand=True)

        self._ay_cerceve = ttk.Frame(self.gorunum_alan)
        self._hafta_cerceve = ttk.Frame(self.gorunum_alan)
        self._gun_cerceve = ttk.Frame(self.gorunum_alan)

        self._ay_izgara_kur()
        self._hafta_izgara_kur()
        self._gun_izgara_kur()

        # Sağ: seçili gün/randevu ajandası
        sag = ttk.Frame(govde, width=300)
        sag.pack(side="right", fill="y", padx=(8, 0))
        self.ajanda_baslik = ttk.Label(
            sag, text="", font=("TkDefaultFont", 11, "bold")
        )
        self.ajanda_baslik.pack(anchor="w", pady=(0, 4))
        self.ajanda = ttk.Treeview(
            sag, columns=("saat", "baslik"), show="headings", height=18
        )
        self.ajanda.heading("saat", text="Saat")
        self.ajanda.heading("baslik", text="Başlık")
        self.ajanda.column("saat", width=70, stretch=False)
        self.ajanda.column("baslik", width=200)
        aj_kay = ttk.Scrollbar(sag, orient="vertical", command=self.ajanda.yview)
        self.ajanda.configure(yscrollcommand=aj_kay.set)
        aj_kay.pack(side="right", fill="y")
        self.ajanda.pack(fill="both", expand=True)
        self.ajanda_detay = ttk.Label(sag, text="", wraplength=280, justify="left")
        self.ajanda_detay.pack(fill="x", pady=(6, 0))
        self.ajanda.bind("<<TreeviewSelect>>", self._ajanda_secildi)
        # Sağ tık: düzenle/sil/tamamlandı
        self.ajanda.bind("<Button-3>", self._ajanda_menusu)
        # Çift tık: Düzenle penceresi
        self.ajanda.bind("<Double-Button-1>", self._ajanda_cift_tikla)
        # Tamamlanan satır üstü çizili (Treeview tag font destekler)
        try:
            aj_font = tkfont.nametofont("TkDefaultFont").copy()
            aj_font.configure(overstrike=True)
            self.ajanda.tag_configure("tamamlandi", font=aj_font)
        except tk.TclError:
            pass

        self._gorunum_goster()
        self._takvim_ciz()

        # Fare tekerleği: hafta/gün görünümünde dikey kaydırma (scrollbar
        # hareket eder), ay görünümünde ay değiştirme (Evolution davranışı).
        # Kök pencereye bağlı: tüm alt widget'ların bindtags'inde '.' var.
        self.bind("<Button-4>", self._takvim_tekerlek)
        self.bind("<Button-5>", self._takvim_tekerlek)
        self.bind("<MouseWheel>", self._takvim_tekerlek)  # Windows/macOS

    # ---- takvim stili yardımcıları ---------------------------------------

    def _stil(self, gorunum: str, anahtar: str):
        """Takvim stili değeri (yoksa varsayılan)."""
        return self.takvim_stil.get(gorunum, {}).get(
            anahtar, TAKVIM_STIL_VARSAYILAN[gorunum][anahtar]
        )

    @staticmethod
    def _stil_font(deger) -> tuple:
        """Stil listesini Tk font bağıntısına çevirir: [aile, boyut, stil]."""
        if isinstance(deger, (list, tuple)) and len(deger) >= 2:
            if len(deger) >= 3 and deger[2]:
                return (deger[0], int(deger[1]), deger[2])
            return (deger[0], int(deger[1]))
        return ("TkDefaultFont", 10)

    def _stil_kaydet(self) -> None:
        """takvim_stil tercihini diske yazar."""
        self._takvim_stil_ozel = True
        self.ayarlar.ayarla("takvim_stil", self.takvim_stil)
        self.ayarlar.kaydet()

    def _takvim_stil_uygula(self) -> None:
        """Stil değişince statik etiketleri yeniler ve görünümü çizer."""
        # Ay gün başlıkları
        for et in getattr(self, "_ay_gun_basliklari", []):
            try:
                et.configure(font=self._stil_font(self._stil("ay", "baslik_font")))
            except tk.TclError:
                pass
        # Hafta gün başlıkları + saat etiketleri
        for et in getattr(self, "_hafta_basliklar", []):
            try:
                et.configure(font=self._stil_font(self._stil("hafta", "baslik_font")))
            except tk.TclError:
                pass
        for et in getattr(self, "_hafta_saat_etiketleri", []):
            try:
                et.configure(font=self._stil_font(self._stil("hafta", "saat_font")))
            except tk.TclError:
                pass
        # Gün saat etiketleri
        for et in getattr(self, "_gun_saat_yazilari", []):
            try:
                et.configure(font=self._stil_font(self._stil("gun", "saat_font")))
            except tk.TclError:
                pass
        # Hücre zeminleri (izgara çerçevesi) — çizim metotları da yeniler
        try:
            self._takvim_ciz()
        except tk.TclError:
            pass

    # ---- izgara kurulumları ---------------------------------------------

    def _ay_izgara_kur(self):
        """Ay ızgarası (6×7 hücre)."""
        ızgara_alan = self._ay_cerceve
        gunler = ["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"]
        self._ay_gun_basliklari: list = []
        for s, ad in enumerate(gunler):
            et = ttk.Label(
                ızgara_alan, text=ad, anchor="center",
                font=self._stil_font(self._stil("ay", "baslik_font")),
            )
            et.grid(row=0, column=s, sticky="ew", padx=1, pady=(0, 2))
            self._ay_gun_basliklari.append(et)
        ızgara_alan.columnconfigure(tuple(range(7)), weight=1, uniform="gun")

        self._gun_hucreleri: dict[tuple[int, int], dict] = {}
        bos = self._stil("ay", "bos")
        for satir in range(6):
            ızgara_alan.rowconfigure(satir + 1, weight=1, uniform="satir")
            for sutun in range(7):
                hucre = tk.Frame(
                    ızgara_alan, relief="solid", bd=1, bg=bos
                )
                hucre.grid(
                    row=satir + 1, column=sutun, sticky="nsew",
                    padx=1, pady=1,
                )
                hucre.grid_rowconfigure(1, weight=1)
                hucre.grid_columnconfigure(0, weight=1)
                # Gün numarası: klasik Label (tema zemini beyaz hücreyle
                # uyuşmuyordu → numaralar siyah kutu görünüyordu)
                no_et = tk.Label(
                    hucre, text="", anchor="ne", bg=bos,
                    padx=3, pady=1,
                )
                no_et.grid(row=0, column=0, sticky="ne")
                liste = tk.Frame(hucre, bg=bos)
                liste.grid(row=1, column=0, sticky="nsew", padx=1, pady=(0, 1))
                # Çift tık: gün görünümüne geç; tek tık: seç
                hucre.bind("<Button-1>", lambda e, h=hucre: self._hucre_tikla(h))
                hucre.bind("<Double-Button-1>", lambda e, h=hucre: self._hucre_cift_tikla(h))
                no_et.bind("<Button-1>", lambda e, h=hucre: self._hucre_tikla(h))
                no_et.bind("<Double-Button-1>", lambda e, h=hucre: self._hucre_cift_tikla(h))
                liste.bind("<Button-1>", lambda e, h=hucre: self._hucre_tikla(h))
                self._gun_hucreleri[(satir, sutun)] = {
                    "hucre": hucre, "no": no_et, "liste": liste, "gun": None
                }

    @staticmethod
    def _icerigi_genislet(canvas: tk.Canvas):
        """Gömülü içerik çerçevesini tuval genişliğine yayar.

        Canvas pencere öğesinin genişliği tuvale eşitlenince ızgara
        sütunları (Evolution'daki gibi) tüm alanı kaplar; yükseklik
        otomatik kalır ve dikey kaydırma sürer.
        """
        def boyutla(_olay):
            og = canvas.find_withtag("all")
            if not og:
                return
            canvas.itemconfigure(og[0], width=canvas.winfo_width())
            canvas.configure(scrollregion=canvas.bbox("all"))

        canvas.bind("<Configure>", boyutla)

    def _hafta_izgara_kur(self):
        """Hafta görünümü: 7 gün × 24 saat ızgarası."""
        kaydir = ttk.Frame(self._hafta_cerceve)
        kaydir.pack(fill="both", expand=True)
        # yscrollincrement=36: tekerlek birimleri saat satırı boyu (36px)
        self._hafta_kaydirici = tk.Canvas(
            kaydir, highlightthickness=0, yscrollincrement=36
        )
        kay_y = ttk.Scrollbar(kaydir, orient="vertical", command=self._hafta_kaydirici.yview)
        self._hafta_kaydirici.configure(yscrollcommand=kay_y.set)
        kay_y.pack(side="right", fill="y")
        self._hafta_kaydirici.pack(side="left", fill="both", expand=True)
        # İçerik canvas'ın ÇOCUĞU olmalı: kardeş olarak yaratılırsa canvas
        # sonra eklendiğinde içerik onun arkasında kalır ve ızgara görünmez.
        icerik = ttk.Frame(self._hafta_kaydirici)
        self._hafta_kaydirici.create_window((0, 0), window=icerik, anchor="nw")
        self._icerigi_genislet(self._hafta_kaydirici)
        icerik.bind(
            "<Configure>",
            lambda e: self._hafta_kaydirici.configure(
                scrollregion=self._hafta_kaydirici.bbox("all")
            ),
        )
        self._hafta_icerik = icerik

        # Saat sütunu + 7 gün
        icerik.columnconfigure(0, weight=0)
        for s in range(1, 8):
            icerik.columnconfigure(s, weight=1, uniform="gun")
        self._hafta_basliklar: list = []
        ttk.Label(icerik, text="", width=6).grid(row=0, column=0, sticky="w")
        for s in range(7):
            et = ttk.Label(icerik, text="", anchor="center",
                           font=self._stil_font(self._stil("hafta", "baslik_font")))
            et.grid(row=0, column=s + 1, sticky="ew", padx=1)
            # Gün başlığına tıkla → o gün seçilsin (sağ panel güncellenir)
            et.bind("<Button-1>", lambda e, gg=s: self._hafta_gun_sec(gg))
            self._hafta_basliklar.append(et)

        self._hafta_hucreler: dict[tuple[int, int], dict] = {}
        self._hafta_saat_etiketleri: list = []
        saat_y = 36  # saat başına piksel
        hucre_renk = self._stil("hafta", "hucre")
        for saat in range(24):
            icerik.rowconfigure(saat + 1, minsize=saat_y)
            et = ttk.Label(
                icerik, text=f"{saat:02d}:00", anchor="ne",
                font=self._stil_font(self._stil("hafta", "saat_font")),
                padding=(0, 0, 4, 0),
            )
            et.grid(row=saat + 1, column=0, sticky="ne")
            self._hafta_saat_etiketleri.append(et)
            for gun_s in range(7):
                hucre = tk.Frame(icerik, bg=hucre_renk, relief="solid", bd=1)
                hucre.grid(
                    row=saat + 1, column=gun_s + 1,
                    sticky="nsew", padx=0, pady=0,
                )
                hucre.bind(
                    "<Button-1>",
                    lambda e, gg=gun_s: self._hafta_gun_sec(gg),
                )
                hucre.bind(
                    "<Double-Button-1>",
                    lambda e, ss=saat, gg=gun_s: self._hafta_hucre_cift(ss, gg),
                )
                self._hafta_hucreler[(saat, gun_s)] = {
                    "hucre": hucre, "gun": None
                }
        # Mevcut saat çizgisi etiketi (yenilemede işaretlenir)
        self._hafta_simdi = None

    def _gun_izgara_kur(self):
        """Gün görünümü: tek gün, 24 saat, olay blokları."""
        kaydir = ttk.Frame(self._gun_cerceve)
        kaydir.pack(fill="both", expand=True)
        # yscrollincrement=40: tekerlek birimleri saat satırı boyu (40px)
        self._gun_kaydirici = tk.Canvas(
            kaydir, highlightthickness=0, yscrollincrement=40
        )
        kay_y = ttk.Scrollbar(kaydir, orient="vertical", command=self._gun_kaydirici.yview)
        self._gun_kaydirici.configure(yscrollcommand=kay_y.set)
        kay_y.pack(side="right", fill="y")
        self._gun_kaydirici.pack(side="left", fill="both", expand=True)
        # İçerik canvas'ın çocuğu olmalı (kardeşse canvas arkada kalır)
        icerik = ttk.Frame(self._gun_kaydirici)
        self._gun_kaydirici.create_window((0, 0), window=icerik, anchor="nw")
        self._icerigi_genislet(self._gun_kaydirici)
        icerik.bind(
            "<Configure>",
            lambda e: self._gun_kaydirici.configure(
                scrollregion=self._gun_kaydirici.bbox("all")
            ),
        )
        self._gun_icerik = icerik

        icerik.columnconfigure(0, weight=0)
        icerik.columnconfigure(1, weight=1)
        self._gun_saat_etiketleri: list = []
        self._gun_saat_yazilari: list = []
        saat_y = 40
        hucre_renk = self._stil("gun", "hucre")
        for saat in range(24):
            icerik.rowconfigure(saat + 1, minsize=saat_y)
            et = ttk.Label(
                icerik, text=f"{saat:02d}:00", anchor="ne",
                font=self._stil_font(self._stil("gun", "saat_font")),
                padding=(0, 0, 6, 0),
            )
            et.grid(row=saat + 1, column=0, sticky="ne")
            self._gun_saat_yazilari.append(et)
            hucre = tk.Frame(icerik, bg=hucre_renk, relief="solid", bd=1)
            hucre.grid(row=saat + 1, column=1, sticky="nsew")
            # Boş saate çift tıkla → yeni randevu o saatte
            hucre.bind(
                "<Double-Button-1>",
                lambda e, ss=saat: self._randevu_penceresi(baslangic_saat=ss),
            )
            self._gun_saat_etiketleri.append(hucre)

    # ---- görünüm yönetimi ----------------------------------------------

    def _gorunum_goster(self):
        """Aktif görünüm çerçevesini gösterir, diğerlerini gizler."""
        for c in (self._ay_cerceve, self._hafta_cerceve, self._gun_cerceve):
            c.pack_forget()
        hedef = {
            "ay": self._ay_cerceve,
            "hafta": self._hafta_cerceve,
            "gun": self._gun_cerceve,
        }.get(self.takvim_gorunum, self._ay_cerceve)
        hedef.pack(fill="both", expand=True)

    def _gorunum_degistir(self):
        yeni = self.takvim_gorunum_degisken.get() or "ay"
        if yeni == self.takvim_gorunum:
            return
        self.takvim_gorunum = yeni
        self.ayarlar.ayarla("takvim_gorunum", yeni)
        self.ayarlar.kaydet()
        self._gorunum_goster()
        self._takvim_ciz()

    def _yon_degistir(self, delta: int):
        """◀/▶ düğmeleri: görünüme göre gün/hafta/ay ilerletir."""
        if self.takvim_gorunum == "gun":
            self.takvim_gun += timedelta(days=delta)
            self.takvim_ay = (self.takvim_gun.year, self.takvim_gun.month)
        elif self.takvim_gorunum == "hafta":
            self.takvim_gun += timedelta(days=7 * delta)
            self.takvim_ay = (self.takvim_gun.year, self.takvim_gun.month)
        else:
            self._ay_degistir(delta)
            return
        self._takvim_ciz()

    def _ay_degistir(self, delta: int):
        y, a = self.takvim_ay
        a += delta
        if a < 1:
            a, y = 12, y - 1
        elif a > 12:
            a, y = 1, y + 1
        self.takvim_ay = (y, a)
        self._takvim_ciz()

    def _bugune_git(self):
        bugun = date.today()
        self.takvim_ay = (bugun.year, bugun.month)
        self.takvim_gun = bugun
        self._takvim_ciz()

    def _takvim_tekerlek(self, olay):
        """Fare tekerleği: hafta/gün görünümünde dikey kaydırır, ay görünümünde ay değiştirir."""
        # Yön: X11 Button-4/5, Windows/macOS MouseWheel (delta)
        num = getattr(olay, "num", 0)
        delta = getattr(olay, "delta", 0)
        if num == 4 or delta > 0:
            yon = -1  # yukarı
        elif num == 5 or delta < 0:
            yon = 1   # aşağı
        else:
            return
        # Olay takvim alanından mı? (yalnızca aktif çerçevenin altındaki widget'lar)
        widget = olay.widget
        if isinstance(widget, str):
            try:
                widget = self.nametowidget(widget)
            except tk.TclError:
                return
        if self._altinda_mi(widget, self._hafta_cerceve):
            # 1 birim = 1 saat satırı (yscrollincrement=36); 2 satır kaydır
            self._hafta_kaydirici.yview_scroll(yon * 2, "units")
            return "break"
        if self._altinda_mi(widget, self._gun_cerceve):
            self._gun_kaydirici.yview_scroll(yon * 2, "units")
            return "break"
        if self._altinda_mi(widget, self._ay_cerceve):
            # Ay ızgarası hep sığar; tekerlek aylar arasında geçiş yapar
            self._yon_degistir(yon)
            return "break"
        # Takvim dışı (mesaj listesi, okuyucu, ajanda…): dokunulmaz

    @staticmethod
    def _altinda_mi(widget, kok) -> bool:
        """widget, kok widget'ının altında (çocuğu) mı? master zincirinden tarar."""
        while widget is not None:
            if widget is kok:
                return True
            widget = getattr(widget, "master", None)
        return False

    def _hucre_tikla(self, hucre):
        for kayit in self._gun_hucreleri.values():
            if kayit["hucre"] is hucre and kayit["gun"] is not None:
                self.takvim_gun = kayit["gun"]
                self._takvim_ciz()
                return

    def _hucre_cift_tikla(self, hucre):
        """Ay ızgarasında güne çift tık → Gün (saatli) görünümü."""
        for kayit in self._gun_hucreleri.values():
            if kayit["hucre"] is hucre and kayit["gun"] is not None:
                self.takvim_gun = kayit["gun"]
                self.takvim_gorunum = "gun"
                self.takvim_gorunum_degisken.set("gun")
                self.ayarlar.ayarla("takvim_gorunum", "gun")
                self.ayarlar.kaydet()
                self._gorunum_goster()
                self._takvim_ciz()
                return

    def _hafta_hucre_cift(self, saat: int, gun_index: int):
        """Hafta ızgarasında saate çift tık → yeni randevu."""
        gun = self._hafta_gunleri[gun_index] if hasattr(self, "_hafta_gunleri") else None
        if gun is None:
            return
        self.takvim_gun = gun
        self._randevu_penceresi(baslangic_saat=saat, gun=gun)

    def _hafta_gun_sec(self, gun_index: int):
        """Hafta görünümünde güne tıkla → o gün seçilir, sağ panel güncellenir."""
        if not hasattr(self, "_hafta_gunleri") or not 0 <= gun_index < len(self._hafta_gunleri):
            return
        gun = self._hafta_gunleri[gun_index]
        if gun == self.takvim_gun:
            return
        self.takvim_gun = gun
        self.takvim_ay = (gun.year, gun.month)
        # Yalnızca ajanda + hafta başlıkları yenilensin (ızgara yeniden kurulmasın)
        self._ajanda_ciz()
        self._hafta_basliklari_guncelle()

    def _hafta_basliklari_guncelle(self):
        """Hafta gün başlıklarını (seçili gün dâhil) yeniden yazar."""
        if not hasattr(self, "_hafta_gunleri"):
            return
        bugun = date.today()
        arka = self.style.lookup("TLabel", "background") or "#ffffff"
        for s, gun in enumerate(self._hafta_gunleri):
            etiket = self._hafta_basliklar[s]
            parcalar = [f"{['Pzt', 'Sal', 'Çar', 'Per', 'Cum', 'Cmt', 'Paz'][s]} {gun.day}.{gun.month}"]
            if gun == bugun:
                parcalar.append("←bugün")
            if gun == self.takvim_gun and gun != bugun:
                parcalar.append("•seçili")
            etiket.configure(
                text=" ".join(parcalar),
                foreground=(
                    self._stil("hafta", "bugun_metin") if gun == bugun
                    else (self._stil("ay", "secili") if gun == self.takvim_gun
                          else self._metin_rengi(arka))
                ),
            )

    def _ajanda_secildi(self, _olay=None):
        secim = self.ajanda.selection()
        if not secim:
            return
        iid = secim[0]
        # iid = index into gunun listesi
        try:
            idx = int(iid)
        except ValueError:
            return
        gun_listesi = self._gun_randevulari(self.takvim_gun)
        if 0 <= idx < len(gun_listesi):
            r = gun_listesi[idx]
            parcalar = []
            if r.konum:
                parcalar.append(f"Konum: {r.konum}")
            if r.organizator:
                parcalar.append(f"Düzenleyen: {r.organizator}")
            if r.aciklama:
                metin = re.sub(r"<[^>]+>", " ", r.aciklama)
                metin = re.sub(r"\s+", " ", metin).strip()
                parcalar.append(metin[:300])
            self.ajanda_detay.configure(text="\n".join(parcalar) or "—")

    def _gun_randevulari(self, gun: date) -> list:
        anahtar = gun.strftime("%Y-%m-%d")
        return [r for r in self._genis_randevular if r.gun == anahtar]

    # ---- tekrarlayan olaylar --------------------------------------------

    def _gorunum_penceresi(self) -> tuple[date, date]:
        """Görünür tarih aralığı (başlangıç, bitiş) — ikisi de dâhil."""
        if self.takvim_gorunum == "hafta":
            paz = self._hafta_baslangic()
            return paz, paz + timedelta(days=6)
        if self.takvim_gorunum == "gun":
            return self.takvim_gun, self.takvim_gun
        y, a = self.takvim_ay
        ilk_gun, _ = monthrange(y, a)
        kaydir = (ilk_gun + 6) % 7  # Pazartesi başlangıç
        bas = date(y, a, 1) - timedelta(days=kaydir)
        return bas, bas + timedelta(days=41)

    def _tekrar_genislet(self, zorla: bool = False) -> None:
        """Tekrarlayan randevuları görünür pencereye göre genişletir.

        Tekrarsız randevular olduğu gibi bırakılır; RRULE taşıyan kayıtların
        her tekrarı için ayrı bir kopya üretilir (occurrence_id benzersiz).
        """
        pencere = self._gorunum_penceresi()
        if not zorla and getattr(self, "_genis_anahtar", None) == pencere:
            return
        self._genis_anahtar = pencere
        genis: list = []
        for r in self.randevular:
            ornekler = self._tekrar_ornekleri(r, pencere[0], pencere[1])
            if ornekler:
                genis.extend(ornekler)
            else:
                genis.append(r)
        self._genis_randevular = genis

    def _tekrar_ornekleri(self, r, pencere_bas: date, pencere_bit: date) -> list:
        """Tekrarlayan bir kaydın pencereye düşen tekrar kopyalarını üretir."""
        kural_metni = getattr(r, "rrule", "") or ""
        if not kural_metni:
            return []
        kural = tekrar.kural_ayikla(kural_metni)
        if not kural:
            return []
        bas_dt = iso_yerel(r.baslangic)
        if bas_dt is None:
            return []
        ex = tekrar.exdate_ayikla(getattr(r, "exdate", "") or "")
        rd = tekrar.rdate_ayikla(getattr(r, "rdate", "") or "")
        baslamalar = tekrar.tekrar_baslangiclar(
            bas_dt, kural, pencere_bas, pencere_bit, ex, rd
        )
        if not baslamalar:
            return []
        bit_dt = iso_yerel(r.bitis)
        sure = timedelta(hours=1)
        if bit_dt is not None:
            fark = bit_dt - bas_dt
            if fark.total_seconds() > 0:
                sure = fark
        sonuc = []
        for bas in baslamalar:
            kopya = copy.copy(r)
            kopya.baslangic = bas.strftime("%Y-%m-%dT%H:%M:%S")
            kopya.bitis = (bas + sure).strftime("%Y-%m-%dT%H:%M:%S")
            kopya.occurrence_id = (
                f"{r.item_id or getattr(r, 'uid', '')}"
                f"#{bas.strftime('%Y%m%dT%H%M%S')}"
            )
            kopya.tamamlandi = False
            sonuc.append(kopya)
        return sonuc

    @staticmethod
    def _randevu_etiketi(r: Randevu, aciklama_sinir: int = 48) -> str:
        """Gün görünümü etiketi: başlık — açıklama (sınırlı, HTML arındırılmış).

        Açıklama `aciklama_sinir` karakteri aşıyorsa kesilir ve sonuna
        "..." (üç nokta) eklenir; açıklama yoksa yalnız başlık döner.
        """
        baslik = r.baslik or "(başlıksız)"
        aciklama = re.sub(r"<[^>]+>", " ", r.aciklama or "")
        aciklama = re.sub(r"\s+", " ", aciklama).strip()
        if not aciklama:
            return baslik
        if len(aciklama) > aciklama_sinir:
            aciklama = aciklama[:aciklama_sinir].rstrip() + "..."
        return f"{baslik} — {aciklama}"

    def _takvim_ciz(self):
        """Aktif görünümü (Ay|Hafta|Gün) ve ajandayı çizer."""
        if not hasattr(self, "_gun_hucreleri"):
            return
        self._tekrar_genislet()
        if self.takvim_gorunum == "hafta":
            self._hafta_ciz()
        elif self.takvim_gorunum == "gun":
            self._gun_ciz()
        else:
            self._ay_ciz()
        self._ajanda_ciz()

    def _basligi_guncelle(self):
        y, a = self.takvim_ay
        ay_adlari = [
            "", "Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
            "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık",
        ]
        if self.takvim_gorunum == "gun":
            self.takvim_baslik.configure(
                text=self.takvim_gun.strftime("%d.%m.%Y %A")
            )
        elif self.takvim_gorunum == "hafta":
            paz = self._hafta_baslangic()
            bitis = paz + timedelta(days=6)
            self.takvim_baslik.configure(
                text=f"{paz.strftime('%d.%m')} – {bitis.strftime('%d.%m.%Y')}"
            )
        else:
            self.takvim_baslik.configure(text=f"{ay_adlari[a]} {y}")

    def _ay_ciz(self):
        """Ay ızgarasını çizer."""
        self._basligi_guncelle()
        y, a = self.takvim_ay
        ilk_gun, _gun_sayisi = monthrange(y, a)
        kaydir = (ilk_gun + 6) % 7  # Pazartesi başlangıç
        bugun = date.today()
        stil = "ay"
        no_font = self._stil_font(self._stil(stil, "gun_font"))
        r_font = self._stil_font(self._stil(stil, "randevu_font"))
        r_arka, r_on = self._stil(stil, "randevu"), self._stil(stil, "randevu_metin")

        for i in range(42):
            satir, sutun = divmod(i, 7)
            kayit = self._gun_hucreleri[(satir, sutun)]
            try:
                gun = date(y, a, 1) + timedelta(days=i - kaydir)
            except ValueError:
                gun = None
            kayit["gun"] = gun
            hucre, no_et, liste = kayit["hucre"], kayit["no"], kayit["liste"]
            for cocuk in liste.winfo_children():
                cocuk.destroy()

            if gun is None:
                bos = self._stil(stil, "bos")
                no_et.configure(text="", bg=bos)
                hucre.configure(bg=bos)
                liste.configure(bg=bos)
                continue

            bu_ay = gun.month == a
            bu_gun = gun == bugun
            secili = gun == self.takvim_gun
            if secili:
                arka = self._stil(stil, "secili")
                on = self._stil(stil, "secili_metin")
            elif bu_gun:
                arka = self._stil(stil, "bugun")
                on = self._stil(stil, "bugun_metin")
            elif bu_ay:
                arka = self._stil(stil, "hucre")
                on = self._stil(stil, "hucre_metin")
            else:
                arka = self._stil(stil, "diger_ay")
                on = self._stil(stil, "diger_ay_metin")
            hucre.configure(bg=arka)
            liste.configure(bg=arka)
            no_et.configure(
                text=str(gun.day),
                foreground=on,
                bg=arka,
                font=(no_font[0], no_font[1],
                      "bold" if (bu_gun or secili) else "normal"),
            )

            randevular = self._gun_randevulari(gun)
            for r in randevular[:3]:
                et = tk.Label(
                    liste,
                    text=self._randevu_etiketi(r),
                    anchor="w",
                    bg=r_arka,
                    fg=r_on if bu_ay else self._stil(stil, "diger_ay_metin"),
                    font=self._cizili_font(r_font) if r.tamamlandi else r_font,
                    padx=2,
                )
                et.pack(fill="x", pady=0)
                et.bind(
                    "<Button-1>",
                    lambda e, rr=r: self._randevu_goster(rr),
                )
                et.bind(
                    "<Double-Button-1>",
                    lambda e, rr=r: self._randevu_penceresi(randevu=rr),
                )
            if len(randevular) > 3:
                et = tk.Label(
                    liste, text=f"+{len(randevular) - 3} daha",
                    anchor="w", bg=arka, fg=on,
                    font=(r_font[0], r_font[1], "italic"),
                )
                et.pack(fill="x")

    def _hafta_baslangic(self) -> date:
        """Seçili günün haftasının Pazartesi'si."""
        return self.takvim_gun - timedelta(days=self.takvim_gun.weekday())

    def _hafta_ciz(self):
        """Hafta görünümünü çizer: 7 gün × 24 saat."""
        self._basligi_guncelle()
        bugun = date.today()
        paz = self._hafta_baslangic()
        self._hafta_gunleri = [paz + timedelta(days=i) for i in range(7)]
        stil = "hafta"
        self._hafta_basliklari_guncelle()

        # Hücreleri temizle ve renklendir
        for (saat, g), kayit in self._hafta_hucreler.items():
            gun = self._hafta_gunleri[g]
            hucre = kayit["hucre"]
            kayit["gun"] = gun
            for cocuk in hucre.winfo_children():
                cocuk.destroy()
            if gun == bugun:
                hucre.configure(bg=self._stil(stil, "bugun"))
            elif gun.weekday() >= 5:
                hucre.configure(bg=self._stil(stil, "hafta_sonu"))
            else:
                hucre.configure(bg=self._stil(stil, "hucre"))

        # Randevuları yerleştir
        r_font = self._stil_font(self._stil(stil, "randevu_font"))
        r_arka = self._stil(stil, "randevu")
        r_on = self._stil(stil, "randevu_metin")
        for r in self._genis_randevular:
            dt = iso_yerel(r.baslangic)
            if dt is None:
                continue
            gun = dt.date()
            if gun not in self._hafta_gunleri:
                continue
            g = self._hafta_gunleri.index(gun)
            saat = dt.hour
            hucre = self._hafta_hucreler[(saat, g)]["hucre"]
            et = tk.Label(
                hucre, text=r.baslik[:22], anchor="w", justify="left",
                bg=r_arka, fg=r_on,
                font=self._cizili_font(r_font) if r.tamamlandi else r_font,
                padx=2, wraplength=90,
            )
            et.pack(fill="both", expand=True, padx=1, pady=1)
            et.bind("<Button-1>", lambda e, rr=r: self._randevu_goster(rr))
            et.bind("<Double-Button-1>", lambda e, rr=r: self._randevu_penceresi(randevu=rr))
            et.bind("<Button-3>", lambda e, rr=r: self._randevu_menusu(e, rr))

        # Şu anki saat çizgisi
        if self._hafta_simdi is not None:
            self._hafta_simdi.destroy()
            self._hafta_simdi = None
        if bugun in self._hafta_gunleri:
            simdi = datetime.now()
            g = self._hafta_gunleri.index(bugun)
            hucre = self._hafta_hucreler[(simdi.hour, g)]["hucre"]
            cizgi = tk.Frame(hucre, height=2, bg=self._stil(stil, "simdi"))
            oran = (simdi.minute / 60.0)
            cizgi.place(relx=0, rely=oran, relwidth=1)
            self._hafta_simdi = cizgi

    def _gun_ciz(self):
        """Gün görünümünü çizer: tek gün, 24 saat, olay blokları."""
        self._basligi_guncelle()
        bugun = date.today()
        gun = self.takvim_gun
        stil = "gun"

        # Hücreleri temizle
        bugun_renk = self._stil(stil, "bugun")
        hucre_renk = self._stil(stil, "hucre")
        for hucre in self._gun_saat_etiketleri:
            for cocuk in hucre.winfo_children():
                cocuk.destroy()
            hucre.configure(bg=bugun_renk if gun == bugun else hucre_renk)

        # Tüm gün randevuları en üste
        tum_gunler = [r for r in self._gun_randevulari(gun) if r.tum_gun]
        saatlik = [r for r in self._gun_randevulari(gun) if not r.tum_gun]
        r_font = self._stil_font(self._stil(stil, "randevu_font"))
        r_arka = self._stil(stil, "randevu")
        r_on = self._stil(stil, "randevu_metin")

        if tum_gunler:
            hucre0 = self._gun_saat_etiketleri[0]
            tg_arka = self._stil(stil, "tum_gun")
            tg_on = self._stil(stil, "tum_gun_metin")
            for r in tum_gunler:
                et = tk.Label(
                    hucre0, text=f"📅 {self._randevu_etiketi(r)}", anchor="w",
                    bg=tg_arka, fg=tg_on,
                    font=self._cizili_font((r_font[0], r_font[1], "bold"))
                    if r.tamamlandi else (r_font[0], r_font[1], "bold"),
                    padx=4,
                )
                et.pack(fill="x", pady=1)
                et.bind("<Double-Button-1>", lambda e, rr=r: self._randevu_penceresi(randevu=rr))
                et.bind("<Button-3>", lambda e, rr=r: self._randevu_menusu(e, rr))

        for r in saatlik:
            dt = iso_yerel(r.baslangic)
            if dt is None or dt.date() != gun:
                continue
            saat = min(23, max(0, dt.hour))
            hucre = self._gun_saat_etiketleri[saat]
            bit = iso_yerel(r.bitis)
            sure = "1 sa" if bit is None else f"{max(1, int((bit - dt).total_seconds() // 3600))} sa"
            et = tk.Label(
                hucre,
                text=f"{dt.strftime('%H:%M')}  {self._randevu_etiketi(r)}  ({sure})",
                anchor="w", bg=r_arka, fg=r_on,
                font=self._cizili_font(r_font) if r.tamamlandi else r_font,
                padx=6, pady=4,
            )
            et.pack(fill="x", padx=2, pady=2)
            et.bind("<Button-1>", lambda e, rr=r: self._randevu_goster(rr))
            et.bind("<Double-Button-1>", lambda e, rr=r: self._randevu_penceresi(randevu=rr))
            et.bind("<Button-3>", lambda e, rr=r: self._randevu_menusu(e, rr))

        # Şu anki saat çizgisi
        if gun == bugun:
            simdi = datetime.now()
            hucre = self._gun_saat_etiketleri[simdi.hour]
            cizgi = tk.Frame(hucre, height=2, bg=self._stil(stil, "simdi"))
            cizgi.place(relx=0, rely=(simdi.minute / 60.0), relwidth=1)

        # Gün görünümünde ilk saatlere kaydır
        self.after(50, lambda: self._gun_kaydirici.yview_moveto(0))

    def _ajanda_ciz(self):
        """Sağ panelde seçili günün ajandasını çizer."""
        secili_gun = self.takvim_gun
        bugun = date.today()
        gun_adi = [
            "Pazartesi", "Salı", "Çarşamba", "Perşembe",
            "Cuma", "Cumartesi", "Pazar",
        ][secili_gun.weekday()]
        self.ajanda_baslik.configure(
            text=f"{gun_adi} {secili_gun.strftime('%d.%m.%Y')}"
            + ("  (bugün)" if secili_gun == bugun else "")
        )
        self.ajanda.delete(*self.ajanda.get_children())
        self.ajanda_detay.configure(text="")
        gun_listesi = self._gun_randevulari(secili_gun)
        for i, r in enumerate(gun_listesi):
            saat = self._randevu_saat(r)
            etiketler = ("tamamlandi",) if r.tamamlandi else ()
            self.ajanda.insert(
                "", "end", iid=str(i),
                values=(saat, r.baslik[:60]),
                tags=etiketler,
            )
        if not gun_listesi:
            self.ajanda.insert("", "end", iid="bos", values=("", "Bu gün randevu yok"))

    @staticmethod
    def _randevu_saat(r: Randevu) -> str:
        dt = iso_yerel(r.baslangic)
        if dt is None:
            return ""
        if r.tum_gun:
            return "Tüm gün"
        return dt.strftime("%H:%M")

    @staticmethod
    def _randevu_kisa(r: Randevu) -> str:
        saat = Postacim._randevu_saat(r)
        baslik = r.baslik if len(r.baslik) <= 28 else r.baslik[:27] + "…"
        if saat and saat != "Tüm gün":
            return f"{saat} {baslik}"
        return baslik

    def _randevu_goster(self, r: Randevu):
        """Ajanda listesinde randevuyu seçip detayını gösterir."""
        gun_listesi = self._gun_randevulari(self.takvim_gun)
        for i, x in enumerate(gun_listesi):
            if x.kimlik == r.kimlik:
                self.ajanda.selection_set(str(i))
                self.ajanda.see(str(i))
                break

    def _randevu_menusu(self, olay, r: Randevu):
        """Randevu üzerinde sağ tık menüsü: Düzenle / Tamamlandı / Sil."""
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(
            label="Düzenle…", image=self.ikon["hesap_duzenle"], compound="left",
            command=lambda: self._randevu_penceresi(randevu=r),
        )
        menu.add_command(
            label="Randevu tamamlandı" if not r.tamamlandi else "İşareti kaldır",
            image=self.ikon["tamamlandi"], compound="left",
            command=lambda: self._randevu_tamamla(r),
        )
        menu.add_command(
            label="Sil", image=self.ikon["sil"], compound="left",
            command=lambda: self._randevu_sil(r),
        )
        menu.tk_popup(olay.x_root, olay.y_root)

    def _randevu_tamamla(self, r: Randevu):
        """Randevunun tamamlandı işaretini değiştirir, kaydeder ve çizer."""
        r.tamamlandi = not r.tamamlandi
        kimlik = r.kimlik
        liste = list(self.ayarlar.al("tamamlanan_randevular", []) or [])
        if r.tamamlandi:
            if kimlik not in liste:
                liste.append(kimlik)
        else:
            liste = [x for x in liste if x != kimlik]
        self.ayarlar.ayarla("tamamlanan_randevular", liste)
        self.ayarlar.kaydet()
        self._takvim_ciz()
        self.durum.set(
            "Randevu tamamlandı olarak işaretlendi." if r.tamamlandi
            else "Tamamlandı işareti kaldırıldı."
        )

    def _tamamlanmalari_uygula(self):
        """Kayıtlı tamamlandı işaretlerini yüklenen randevulara uygular."""
        liste = set(self.ayarlar.al("tamamlanan_randevular", []) or [])
        for r in list(self.randevular) + list(self._genis_randevular):
            r.tamamlandi = r.kimlik in liste

    def _cizili_font(self, deger) -> tkfont.Font:
        """(aile, boyut[, stil]) bağıntısını üstü çizili Font'a çevirir (önbellekli)."""
        if isinstance(deger, (list, tuple)) and len(deger) >= 2:
            aile, boyut = deger[0], int(deger[1])
            stil = str(deger[2]) if len(deger) > 2 else ""
        else:
            aile, boyut, stil = "TkDefaultFont", 10, ""
        anahtar = (aile, boyut, stil)
        onbel = getattr(self, "_cizili_onbel", None)
        if onbel is None:
            onbel = self._cizili_onbel = {}
        f = onbel.get(anahtar)
        if f is None:
            try:
                f = tkfont.nametofont(aile).copy()
                f.configure(size=boyut)
            except tk.TclError:
                f = tkfont.Font(family=aile, size=boyut)
            if "bold" in stil:
                f.configure(weight="bold")
            if "italic" in stil:
                f.configure(slant="italic")
            f.configure(overstrike=True)
            onbel[anahtar] = f
        return f

    def _ajanda_cift_tikla(self, olay):
        """Ajanda satırına çift tık → Düzenle penceresi."""
        satir = self.ajanda.identify_row(olay.y)
        if not satir or satir == "bos":
            return
        if satir not in self.ajanda.selection():
            self.ajanda.selection_set(satir)
        try:
            idx = int(satir)
        except ValueError:
            return
        gun_listesi = self._gun_randevulari(self.takvim_gun)
        if 0 <= idx < len(gun_listesi):
            self._randevu_penceresi(randevu=gun_listesi[idx])

    def _ajanda_menusu(self, olay):
        """Ajanda satırında sağ tık."""
        secim = self.ajanda.selection()
        if not secim or secim[0] == "bos":
            menu = tk.Menu(self, tearoff=0)
            menu.add_command(
                label="Yeni Randevu…", image=self.ikon["randevu_ekle"],
                compound="left", command=self._randevu_penceresi,
            )
            menu.tk_popup(olay.x_root, olay.y_root)
            return
        try:
            idx = int(secim[0])
        except ValueError:
            return
        gun_listesi = self._gun_randevulari(self.takvim_gun)
        if 0 <= idx < len(gun_listesi):
            self._randevu_menusu(olay, gun_listesi[idx])

    def _randevu_sil(self, r):
        if not messagebox.askyesno("Randevu Sil", self._sil_sorusu(r)):
            return
        caldav_mi = bool(getattr(r, "url", ""))
        kaynak_id = getattr(r, "kaynak_id", "")

        def is_():
            if caldav_mi:
                cal = self._kaynak_caldav(kaynak_id)
                if cal is None:
                    raise EwsHata("CalDAV takvim hesabı yok.")
                self._caldav_istemci(cal).randevu_sil(r)
            else:
                hesap = self.ayarlar.aktif_hesap() or {}
                istemci = self._istemciler.get(kaynak_id or self.aktif_id)
                if istemci is None:
                    istemci = self._istemci_kur(hesap)
                    self._istemciler[self.aktif_id] = istemci
                istemci.randevu_sil(r)
            return ("takvim_yenile",)

        threading.Thread(target=self._arka_plan, args=(is_,), daemon=True).start()

    def _kaynak_caldav(self, kaynak_id: str = "") -> dict | None:
        """Verilen kimliğe sahip CalDAV hesabını bulur (yoksa ilk CalDAV hesabı)."""
        kaynaklar = self._takvim_kaynaklari()
        if kaynak_id:
            for tur, veri in kaynaklar:
                if tur == "caldav" and veri.get("id") == kaynak_id:
                    return veri
        for tur, veri in kaynaklar:
            if tur == "caldav":
                return veri
        return None

    @staticmethod
    def _sil_sorusu(r) -> str:
        """Silme onay metni (tekrarlı randevularda uyarı ekler)."""
        soru = f"“{r.baslik}” silinsin mi?"
        if getattr(r, "rrule", ""):
            soru += "\n\nBu randevu tekrarlı — tüm tekrarlar silinecek."
        return soru

    def _randevu_penceresi(self, randevu: Randevu | None = None, baslangic_saat: int | None = None, gun: date | None = None):
        """Yeni randevu penceresi ya da mevcut randevuyu düzenleme."""
        kaynaklar = self._takvim_kaynaklari()
        if not kaynaklar:
            messagebox.showwarning(
                "Takvim",
                "Önce bir takvim hesabı bağlayın:\n"
                "• “Takvim Hesapları” → CalDAV (Gmail, Nextcloud…)\n"
                "• Ya da Exchange (EWS) hesabına geçin",
            )
            return
        RandevuPenceresi(self, randevu=randevu, baslangic_saat=baslangic_saat, gun=gun or self.takvim_gun)

    def _takvim_hesaplari_penceresi(self):
        """CalDAV takvim hesabı yönetimi penceresini açar."""
        TakvimHesapPenceresi(self)

    def _ayarlar_penceresi(self):
        """Genel + Takvim ayarları penceresini açar."""
        AyarlarPenceresi(self)

    def _takvim_sonuc(self, randevular: list):
        self.randevular = list(randevular)
        self._tamamlanmalari_uygula()
        self.takvim_yuklendi = True
        self._takvim_ciziliyor = False
        self.durum.set(f"Takvim: {len(self.randevular)} randevu")
        # Veri geldikten sonra görünüm yeniden çizilmeli (Ay/Gün/Hafta +
        # ajanda); aksi halde ızgara ilk çizildiği (boş) haliyle kalır.
        self._tekrar_genislet(zorla=True)
        self._tamamlanmalari_uygula()  # tekrar kopyalarına da işaret uygula
        self._takvim_ciz()

    def _durum_cubugu_kur(self):
        self.durum = tk.StringVar(value="Hazır")
        self.durum_etiket = ttk.Label(
            self, textvariable=self.durum, anchor="w", padding=(10, 4)
        )
        self.durum_etiket.pack(fill="x", side="bottom")

    # ------------------------------------------------------------------ oturum

    def _istemci_kur(self, hesap: dict):
        """Hesap türüne göre istemci üretir (Exchange EWS veya Gmail/IMAP)."""
        if hesap.get("tur") == "imap":
            return ImapIstemci(hesap)
        return EwsIstemci(
            sunucu=hesap.get("sunucu", ""),
            kullanici=hesap.get("kullanici", ""),
            parola=hesap.get("parola", ""),
            yontem=hesap.get("yontem", "ntlm"),
            gonderen=_hesap_adresi(hesap),
        )

    def _istemci_for_adres(self, gonderen: str):
        """Gönderen adresinin hesabına karşılık gelen istemciyi döndürür.

        Adres boşsa ya da hiçbir hesapla eşleşmezse aktif hesabın istemcisi
        kullanılır. Sonuç arka plan iş parçacığından çağrılır (Tk'ye dokunmaz).
        """
        adres = (gonderen or "").strip().lower()
        hedef = None
        if adres:
            for h in self.ayarlar.hesaplar():
                if _hesap_adresi(h).lower() == adres:
                    hedef = h
                    break
        if hedef is None:
            # Eşleşme yoksa aktif hesap
            if self.istemci is not None:
                return self.istemci
            hedef = self.ayarlar.aktif_hesap()
            if hedef is None:
                raise EwsHata("Gönderilecek hesap bulunamadı.")
        # Aktif hesapsa bağlı istemciyi kullan
        if hedef.get("id") == self.aktif_id and self.istemci is not None:
            return self.istemci
        istemci = self._istemciler.get(hedef.get("id"))
        if istemci is None:
            if not hedef.get("parola"):
                if hedef.get("id") == self.aktif_id:
                    raise EwsYetkiHatasi("Oturum kapalı — göndermek için giriş yapın.")
                ad = hedef.get("ad") or "hesap"
                raise EwsHata(
                    f"'{ad}' hesabının parolası kayıtlı değil. Göndermek için "
                    "Hesaplar → Hesap Düzenle…'den parolayı girin."
                )
            istemci = self._istemci_kur(hedef)
            self._istemciler[hedef["id"]] = istemci
        return istemci

    def _baglan(self) -> bool:
        if self.istemci is not None:
            return True
        hesap = self.ayarlar.aktif_hesap()
        if hesap is None:
            self._hesap_ekle_penceresi()
            return False
        if not hesap.get("kullanici") or not hesap.get("parola"):
            if not self._kimlik_sor():
                return False
            hesap = self.ayarlar.aktif_hesap()
            if not hesap or not hesap.get("kullanici"):
                return False
        istemci = self._istemciler.get(hesap["id"])
        if istemci is None:
            try:
                istemci = self._istemci_kur(hesap)
            except EwsHata as exc:
                messagebox.showerror("Bağlantı hatası", str(exc))
                return False
            self._istemciler[hesap["id"]] = istemci
        self.istemci = istemci
        return True

    def _ilk_baglanti(self):
        """Ilk acilista: giris penceresi -> baglan -> klasorleri yukle."""
        if self._kimlik_sor():
            self.yenile()

    def _kimlik_sor(self, hata: str | None = None):
        """Aktif hesabın giriş penceresi (kullanıcı + parola).

        `hata` verilirse pencerenin başında kırmızı olarak gösterilir
        (ör. 401 ya da "bağlanamadı"), kullanıcı neden yeniden sorulduğunu görür.
        """
        if self._giris_soruluyor:
            return False
        hesap = self.ayarlar.aktif_hesap()
        if hesap is None:
            self._hesap_ekle_penceresi()
            return False
        self._giris_soruluyor = True
        try:
            return self._kimlik_penceresi(hesap, hata)
        finally:
            self._giris_soruluyor = False

    def _kimlik_penceresi(self, hesap: dict, hata: str | None) -> bool:
        imap_mi = hesap.get("tur") == "imap"
        pencere = tk.Toplevel(self)
        pencere.title(
            f"Postacım — {hesap.get('ad') or 'Bağlantı bilgileri'}"
        )
        pencere.transient(self)
        self._pencere_simgesi(pencere)
        pencere.grab_set()
        satir = 0
        if hata:
            ttk.Label(
                pencere, text=hata, foreground="#c0392b", justify="left",
                wraplength=360,
            ).grid(row=0, column=0, columnspan=2, padx=14, pady=(12, 6), sticky="w")
            satir = 1
        if imap_mi:
            yardim = (
                "Gmail için: Google Hesabı → Güvenlik → 2 Adımlı Doğrulama\n"
                "açıkken 16 haneli uygulama parolası oluşturun (normal parola\n"
                "çalışmaz). Gmail'de IMAP etkinleştirilmiş olmalıdır."
            )
            kullanici_etiket, parola_etiket = "E-posta:", "Uygulama parolası:"
        else:
            yardim = (
                "Kurumunuzda IMAP/SMTP portları dışarıdan kapalı; e-posta\n"
                "EWS üzerinden okunacak. NTLM kullanıcı adı 'TARIM\\kullanici' olmalı."
            )
            kullanici_etiket, parola_etiket = "Kullanıcı:", "Parola:"
        ttk.Label(
            pencere, text=yardim, justify="left",
        ).grid(row=satir, column=0, columnspan=2, padx=14, pady=(12, 8), sticky="w")
        kullanici_var = tk.StringVar(value=hesap.get("kullanici", ""))
        parola_var = tk.StringVar(value="")
        ttk.Label(pencere, text=kullanici_etiket).grid(
            row=satir + 1, column=0, padx=14, sticky="w"
        )
        ttk.Entry(pencere, textvariable=kullanici_var, width=34).grid(
            row=satir + 1, column=1, padx=8, pady=4
        )
        ttk.Label(pencere, text=parola_etiket).grid(
            row=satir + 2, column=0, padx=14, sticky="w"
        )
        ttk.Entry(pencere, textvariable=parola_var, show="•", width=34).grid(
            row=satir + 2, column=1, padx=8, pady=4
        )
        hatirla_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            pencere, text="Parolayı hatırla (0600 dosya)", variable=hatirla_var
        ).grid(row=satir + 3, column=0, columnspan=2, padx=14, sticky="w", pady=6)

        sonuc = {"tamam": False}

        def kapat(tamam: bool):
            sonuc["tamam"] = tamam
            if tamam:
                hesap["kullanici"] = kullanici_var.get().strip()
                girilen = parola_var.get()
                if hatirla_var.get():
                    # Alan boş bırakıldıysa daha önce kayıtlı parola korunur
                    hesap["parola"] = girilen or hesap.get("parola", "")
                else:
                    hesap["parola"] = ""
                self.ayarlar.kaydet()
            pencere.destroy()

        ttk.Button(pencere, text="Bağlan", command=lambda: kapat(True)).grid(
            row=satir + 4, column=0, padx=14, pady=10, sticky="e"
        )
        ttk.Button(pencere, text="İptal", command=lambda: kapat(False)).grid(
            row=satir + 4, column=1, padx=8, pady=10, sticky="w"
        )
        pencere.wait_window()
        return sonuc["tamam"]

    def hesaptan_cikis(self):
        """Aktif hesabın oturumunu kapatır: istemciyi bırakır, onbellekleri
        siler, kayıtlı parolayı unutur ve giriş penceresini yeniden açar
        (Ctrl+Q). Diğer hesaplar etkilenmez."""
        if not self.oturum:
            self._yeniden_giris()
            return
        hesap = self.ayarlar.aktif_hesap()
        ad = (hesap or {}).get("ad") or (hesap or {}).get("kullanici") or "hesap"
        if not messagebox.askyesno(
            "Hesaptan Çıkış",
            f"'{ad}' oturumu kapatılacak; kayıtlı parola silinip yeniden giriş "
            "istenecek. Diğer hesaplar etkilenmez. Devam edilsin mi?",
        ):
            return
        self.oturum = False
        self.istemci = None
        if hesap:
            self._istemciler.pop(hesap["id"], None)
            self._hesap_klasorleri.pop(hesap["id"], None)
            self.ayarlar.hesap_guncelle(hesap["id"], {"parola": ""})
        self.klasor_liste = []
        self._kuyrugu_yut()
        self._mesaj_alanini_temizle()
        self._agaci_yenile()
        self.durum.set("Oturum kapalı")
        self.after(200, self._yeniden_giris)

    def _kuyrugu_yut(self):
        """Kuyrukta bekleyen sonuçları yutar (hesap geçişinde/çıkışta)."""
        while not self.is_kuyrugu.empty():  # bekleyen sonuçları yut
            try:
                self.is_kuyrugu.get_nowait()
            except queue.Empty:
                break
        self._is_sayaci = 0
        self._otomatik_bekliyor = False

    def _mesaj_alanini_temizle(self):
        """Mesaj listesi + okuyucu alanlarını temizler (hesap geçişinde)."""
        self.mesajlar = []
        self.secili = None
        self.sayfa_no = 0
        self.sayfa_sayisi = 1
        self.tam_yenile = True
        self.liste.delete(*self.liste.get_children())
        self.baslik.configure(text="Bir mesaj seçin")
        if self.html_modu:
            self.ayrinti.load_html("")
        else:
            self.ayrinti.configure(state="normal")
            self.ayrinti.delete("1.0", "end")
            self.ayrinti.configure(state="disabled")
        self.resim_kayitlari = []
        self.resim_cubugu.pack_forget()
        self.ek_listesi.delete(*self.ek_listesi.get_children())
        self.sayfa_etiket.configure(text="Sayfa 1/1")

    def _yeniden_giris(self):
        """Çıkış sonrası giriş penceresi; bağlanılırsa oturum yeniden açılır."""
        if self._kimlik_sor():
            self.oturum = True
            self.yenile()
        else:
            self.durum.set("Oturum kapalı — giriş için herhangi bir işleme basın")

    # --------------------------------------------------------------- arka plan

    def _arka_plan(self, islev, *args):
        """Arka plan is parcaciginda calisacak islev; sonucu kuyruga koyar."""
        self._is_sayaci += 1
        try:
            sonuc = islev(*args)
            self.is_kuyrugu.put(("ok", sonuc))
        except EwsYetkiHatasi as exc:
            # Kimlik gecersiz / parola degismis → giriş penceresi sor.
            self.is_kuyrugu.put(("giris", str(exc)))
        except requests.RequestException as exc:
            # Sunucuya ulasilamadi → yine giriş penceresi (bilgiler tazelenir).
            self.is_kuyrugu.put(("giris", f"Bağlantı kurulamadı: {exc}"))
        except EwsHata as exc:
            self.is_kuyrugu.put(("hata", str(exc)))
        except Exception as exc:  # beklenmeyen
            self.is_kuyrugu.put(("hata", f"Beklenmeyen hata: {exc}"))

    def _tk_hata_yakala(self, exc_type, exc, tb):
        """Tk geri çağrılarındaki beklenmeyen hataları kayda alıp gösterir.

        Tk varsayılanında bu hatalar yalnız terminale yazılır; menüden
        açılan uygulamada hiçbir iz kalmaz ve hatanın kaynağı bilinemez.
        İz `~/.local/state/postacim/hata.log`a eklenir (dosya 400 KB'yi
        aşarsa eskisi silinir) ve kullanıcıya kısa bir açıklama gösterilir;
        uygulama kapanmaz.
        """
        metin = "".join(traceback.format_exception(exc_type, exc, tb))
        try:
            gunluk_dizin = os.path.join(
                os.environ.get("XDG_STATE_HOME", "")
                or os.path.join(os.path.expanduser("~"), ".local", "state"),
                "postacim",
            )
            os.makedirs(gunluk_dizin, exist_ok=True)
            gunluk = os.path.join(gunluk_dizin, "hata.log")
            if os.path.exists(gunluk) and \
                    os.path.getsize(gunluk) > 400_000:
                os.remove(gunluk)
            with open(gunluk, "a", encoding="utf-8") as f:
                f.write(f"\n===== {time.strftime('%Y-%m-%d %H:%M:%S')} =====\n")
                f.write(metin)
        except OSError:
            gunluk = None  # kayıt yazılamıyorsa en azından uygulama yaşasın
        try:
            self.durum.set("Beklenmeyen hata (ayrıntılar hata.log'da)")
            kisalt = metin if len(metin) <= 1500 else "…" + metin[-1500:]
            messagebox.showerror(
                "Beklenmeyen hata",
                "Bir işlem hatayla sonuçlandı; uygulama kapanmadı.\n\n"
                + (f"Ayrıntılar şuraya yazıldı: {gunluk}\n\n" if gunluk else "")
                + kisalt,
            )
        except Exception:
            pass  # diyalog gösterilemediyse sessizce sürdür

    def _kuyruk_yokla(self):
        try:
            while True:
                try:
                    tur, veri = self.is_kuyrugu.get_nowait()
                except queue.Empty:
                    break
                self._is_sayaci = max(0, self._is_sayaci - 1)
                if self._is_sayaci == 0:
                    self._otomatik_bekliyor = False
                if not self.oturum:
                    continue  # hesaptan çıkış sonrası bekleyen sonuçları yut
                try:
                    if tur == "giris":
                        self._giris_iste(str(veri))
                    elif tur == "hata":
                        self._takvim_ciziliyor = False
                        self.durum.set("Hata")
                        messagebox.showerror("Hata", veri)
                    else:
                        self._sonuc_isle(veri)
                except Exception as exc:
                    # Tek bir sonuç işlenemezse kuyruk yoklama DURMASIN
                    # (aksi halde arayüz "Bağlanıyor"da kalır).
                    self.durum.set("Sonuç işlenemedi")
                    messagebox.showerror("Hata", f"Sonuç işlenemedi: {exc}")
        finally:
            try:
                self.after(120, self._kuyruk_yokla)
            except tk.TclError:  # pencere kapandıysa zamanlayıcı kurulmaz
                pass

    def _giris_iste(self, hata: str):
        """Bağlantı kurulamadıysa kullanıcı adı–parola sor; girilirse yeniden dene."""
        if self._giris_soruluyor or not self.oturum:
            return
        self.istemci = None  # yeni bilgilerle yeniden kurulsun
        self._istemciler.pop(self.aktif_id, None)
        if self._kimlik_sor(hata=hata):
            self.durum.set("Yeniden bağlanılıyor…")
            self.yenile()
        else:
            self.durum.set("Bağlantı kurulamadı — giriş iptal edildi")

    def _sonuc_isle(self, veri):
        tur = veri[0]
        if tur == "klasorler":
            self._klasorleri_doldur(veri[1])
        elif tur == "hesap_klasorler":
            # Diğer bir hesabın klasör listesi (arka planda çekildi)
            self._hesap_klasorlerine_yaz(veri[1], veri[2])
        elif tur == "mesajlar":
            self._mesajlari_doldur(veri[1], veri[2])
        elif tur == "gonder_al":
            klasorler, yeni, mesajlar, toplam = veri[1], veri[2], veri[3], veri[4]
            diger = veri[5] if len(veri) > 5 else {}
            self._klasorleri_doldur(klasorler, mesajlari_yukle=False)
            self._mesajlari_doldur(mesajlar, toplam)
            net = sum(yeni.values())
            not_ = f"{net} yeni mesaj" if net > 0 else "yeni mesaj yok"
            self.durum.set(f"Gönder/Al tamamlandı — {not_} • " + self.durum.get())
            self._bildirimleri_denle(diger)

        elif tur == "bildirim":
            diger = veri[1]
            aktif_sayi = veri[2] if len(veri) > 2 else None
            self._bildirimleri_denle(diger, aktif_sayi)
        elif tur == "otomatik":
            self._otomatik_isle(veri[1], veri[2], veri[3],
                               veri[4] if len(veri) > 4 else {})
        elif tur == "detay":
            self._detay_goster(veri[1])
        elif tur == "takvim":
            self._takvim_sonuc(veri[1])
        elif tur == "takvim_yenile":
            self.takvim_yuklendi = False
            self._takvim_ciziliyor = False
            self._takvim_cek()
        elif tur == "resim":
            self._resim_yerlestir(veri[1], veri[2])
        elif tur == "resim_hata":
            self._resim_gosterilemedi(veri[1], veri[2])
        elif tur == "ek":
            self._ek_kaydet(veri[1], veri[2])
        elif tur == "ek_toplu":
            self._ekleri_indir_goster(veri[1], veri[2], veri[3])
        elif tur == "basarili":
            self.durum.set(veri[1])
        elif tur == "yenile":
            # Taşıma/silme sonrası: durumu yaz, listeyi ve klasör sayısını tazele
            self.durum.set(veri[1])
            self.yenile()
        elif tur == "okundu":
            self._okundu_goster(veri[1])
        elif tur == "okundu_hata":
            self.durum.set("Okundu bilgisi sunucuya yazılamadı (EWS UpdateItem hatası)")
        elif tur == "uyari":
            messagebox.showinfo("Bilgi", veri[1])

    def _okundu_goster(self, deger: bool):
        if self.secili:
            self.secili.okundu = deger
        if self.liste.selection():
            i = self.liste.index(self.liste.selection()[0])
            self.liste.set(i, "durum", "" if deger else "●")

    # ------------------------------------------------------------------ eylemler

    def yenile(self):
        if not self._baglan():
            return
        self.durum.set("Bağlanıyor…")
        self.tam_yenile = True
        threading.Thread(
            target=self._arka_plan, args=(self._klasorleri_cek,), daemon=True
        ).start()

    def _klasorleri_cek(self):
        return ("klasorler", self.istemci.klasor_listesi())

    def gonder_al(self):
        """Kutuyu tazeler (Outlook'taki Gonder/Al gibi): klasor sayaclari,
        onbellekli klasorlerdeki degisiklikler ve aktif klasorun listesi."""
        if not self._baglan():
            return
        arama = self.arama.get().strip()
        alan = "gonderen" if arama.lower().startswith("from:") else "konu"
        if alan == "gonderen":
            arama = arama[5:].strip()
        self.durum.set("Gönder/Al yapılıyor…")
        threading.Thread(
            target=self._arka_plan,
            args=(
                self._gonder_al_cek,
                self.klasor,
                self.sayfa_boyutu,
                self.sayfa_no * self.sayfa_boyutu,
                arama,
                alan,
            ),
            daemon=True,
        ).start()

    def _gonder_al_cek(self, klasor, sayfa_boyutu, offset, arama, alan):
        klasorler = self.istemci.klasor_listesi()
        yeni = self.istemci.guncelle()
        mesajlar, toplam = self.istemci.mesajlar(
            klasor=klasor,
            sayfa_boyutu=sayfa_boyutu,
            offset=offset,
            arama=arama,
            alan=alan,
            tazele=False,
        )
        diger = self._diger_hesap_gelen_sayilari()
        return ("gonder_al", klasorler, yeni, mesajlar, toplam)

    # ------------------------------------------------------- otomatik yenileme

    def _otomatik_degistir(self, saniye: int):
        self.otomatik_yenile = saniye
        self.ayarlar.ayarla("otomatik_yenile", saniye)
        self.ayarlar.kaydet()
        self._otomatik_baslat()
        self.durum.set(
            "Otomatik yenileme kapalı" if saniye == 0
            else f"Otomatik yenileme: {saniye} saniyede bir"
        )

    def _otomatik_baslat(self):
        """Zamanlayıcıyı (yeniden) kurar; süre 0 ise durdurur."""
        self._otomatik_durdur()
        if self.otomatik_yenile > 0:
            self._otomatik_zamanlayici = self.after(
                self.otomatik_yenile * 1000, self._otomatik_tik
            )

    def _otomatik_durdur(self):
        if self._otomatik_zamanlayici is not None:
            try:
                self.after_cancel(self._otomatik_zamanlayici)
            except tk.TclError:
                pass
            self._otomatik_zamanlayici = None

    def _otomatik_tik(self):
        self._otomatik_zamanlayici = None
        self._otomatik_yenile_yap()
        self._otomatik_baslat()  # sıradaki tik

    # ------------------------------------------------- yeni mail bildirimi

    def _bildirim_baslat(self):
        """Bildirim denetimini (her 60 sn) başlatır."""
        self._bildirim_durdur()
        # Sistem balonları kapalıysa kullanıcıyı bilgilendir: bildirim
        # gönderilse bile ekranda görünmeyecek.
        if self._bildirim_acik and self._bildirim_balonlari_kapali():
            self.durum.set(
                "Sistem bildirim balonları kapalı — Ayarlar ▸ Genel'den açın"
            )
        self._bildirim_zamanlayici = self.after(
            self._bildirim_aralik * 1000, self._bildirim_tik
        )

    def _bildirim_durdur(self):
        if self._bildirim_zamanlayici is not None:
            try:
                self.after_cancel(self._bildirim_zamanlayici)
            except tk.TclError:
                pass
            self._bildirim_zamanlayici = None

    def _bildirim_tik(self):
        self._bildirim_zamanlayici = None
        self._bildirim_denle()
        self._bildirim_baslat()  # sıradaki tik

    def _bildirim_denle(self):
        """Tüm hesapların gelen kutusunu denetler; yeni varsa bildirir.

        Otomatik yenilemeden bağımsızdır (yenileme kapalı olsa da çalışır).
        """
        if not self.oturum or self._giris_soruluyor:
            return
        if self._bildirim_bekliyor or self._is_sayaci > 0:
            return  # devam eden iş varsa atlanır
        self._bildirim_bekliyor = True

        def is_():
            try:
                diger = self._diger_hesap_gelen_sayilari()
                aktif_sayi = None
                if self.istemci is not None:
                    aktif_sayi = int(self.istemci.gelen_sayisi() or 0)
                self.is_kuyrugu.put(("ok", ("bildirim", diger, aktif_sayi)))
            except Exception:
                self.is_kuyrugu.put(("ok", ("bildirim", {}, None)))
            finally:
                self._bildirim_bekliyor = False

        threading.Thread(target=is_, daemon=True).start()

    def _aktif_gelen_sayisi(self) -> int | None:
        """Aktif hesabın Gelen Kutusu toplam mesaj sayısı (bilinmiyorsa None)."""
        for k in self.klasor_liste:
            if k.kimlik == "inbox":
                return k.toplam
        return None

    def _otomatik_yenile_yap(self):
        """Seçili klasörü sessizce tazeler (periyodik yenileme).

        Yalnızca bağlıyken ve devam eden bir iş varken yenilemez; durum
        çubuğu yalnızca yeni mesaj gelirse yazılır. Giriş penceresi açılmaz.
        """
        if not self.oturum or self._giris_soruluyor or self.istemci is None:
            return
        if self._otomatik_bekliyor or self._is_sayaci > 0:
            return  # devam eden iş varsa bu tik atlanır
        arama = self.arama.get().strip()
        alan = "gonderen" if arama.lower().startswith("from:") else "konu"
        if alan == "gonderen":
            arama = arama[5:].strip()
        self._otomatik_bekliyor = True
        threading.Thread(
            target=self._arka_plan,
            args=(
                self._otomatik_cek,
                self.klasor,
                self.sayfa_boyutu,
                self.sayfa_no * self.sayfa_boyutu,
                arama,
                alan,
            ),
            daemon=True,
        ).start()

    def _otomatik_cek(self, klasor, sayfa_boyutu, offset, arama, alan):
        klasorler = self.istemci.klasor_listesi()
        mesajlar, toplam = self.istemci.mesajlar(
            klasor=klasor,
            sayfa_boyutu=sayfa_boyutu,
            offset=offset,
            arama=arama,
            alan=alan,
            tam=False,
            tazele=True,
        )
        # Diğer hesapların gelen kutuları da denetlenir (bildirim için)
        diger = self._diger_hesap_gelen_sayilari()
        return ("otomatik", klasorler, mesajlar, toplam, diger)

    def _diger_hesap_gelen_sayilari(self) -> dict:
        """Diğer hesapların gelen kutusu toplam sayısı: {hesap_id: sayı}."""
        sonuc: dict[str, int] = {}
        for h in self.ayarlar.hesaplar():
            hid = h.get("id")
            if not hid or hid == self.aktif_id:
                continue
            if not h.get("kullanici") or not h.get("parola"):
                continue
            try:
                istemci = self._istemciler.get(hid)
                if istemci is None:
                    istemci = self._istemci_kur(h)
                    self._istemciler[hid] = istemci
                sonuc[hid] = int(istemci.gelen_sayisi() or 0)
            except Exception:
                continue  # erişilemeyen hesap: bildirim üretilmez
        return sonuc

    def _bildirim_kontrol(self, hesap_id: str, sayi: int, ad: str):
        """Gelen kutusu sayısı arttıysa işletim sistemi bildirimi gönderir.

        İlk ölçüm yalnızca taban kaydedilir (bildirim çıkmaz); sonrakiler
        artışı bildirir.
        """
        onceki = self._son_gelen_sayi.get(hesap_id)
        self._son_gelen_sayi[hesap_id] = sayi
        if onceki is None:
            return  # ilk ölçüm: taban
        if sayi <= onceki:
            return  # artış yok
        fark = sayi - onceki
        baslik = f"Yeni e-posta — {ad}"
        govde = f"{fark} yeni mesaj"
        self._bildirim_gonder(baslik, govde)
        # Durum çubuğu her zaman bildirir (sistem balonları kapalıysa bile).
        self.durum.set(f"Yeni e-posta: {ad} — {fark} yeni mesaj")
        # Uygulama içi uyarı: sistem bildirimleri kapalı olsa da görünür.
        self._bildirim_toast(baslik, govde)

    def _bildirim_simge_yolu(self) -> str:
        """Bildirimde kullanılacak uygulama simgesinin yolu."""
        import os

        adaylar = [
            os.path.join(os.path.dirname(__file__), "ikonlar", "uygulama.png"),
            os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                "data", "icons", "hicolor", "scalable", "apps", "postacim.svg",
            ),
        ]
        for yol in adaylar:
            if os.path.isfile(yol):
                return yol
        return ""

    def _bildirim_gonder(self, baslik: str, govde: str) -> bool:
        """İşletim sistemi masaüstü bildirimi gönderir.

        Önce `notify-send`; yoksa doğrudan D-Bus (`org.freedesktop.Notifications`).
        Gönderilemezse uygulama içi uyarı devreye girer.
        """
        if not self._bildirim_acik:
            return False
        simge = self._bildirim_simge_yolu()
        if self._bildirim_arac:
            komut = [self._bildirim_arac, "-a", UYGULAMA_ADI, "-u", "normal"]
            if simge:
                komut += ["-i", simge]
            komut += [baslik, govde]
            try:
                subprocess.Popen(
                    komut,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                return True
            except OSError:
                self._bildirim_arac = None
        if self._bildirim_gdbus:
            komut = [
                self._bildirim_gdbus, "call", "--session",
                "--dest", "org.freedesktop.Notifications",
                "--object-path", "/org/freedesktop/Notifications",
                "--method", "org.freedesktop.Notifications.Notify",
                UYGULAMA_ADI, "0", simge, baslik, govde, "[]", "{}", "5000",
            ]
            try:
                subprocess.Popen(
                    komut,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                return True
            except OSError:
                self._bildirim_gdbus = None
        return False

    def _bildirim_balonlari_kapali(self) -> bool:
        """GNOME'da bildirim balonları kapalı mı?

        `show-banners=false` iken bildirim gönderilse bile ekranda
        görünmez; bu durumda kullanıcı "bildirim gelmiyor" sanar.
        """
        if self._bildirim_balon_durumu is None:
            durum = False
            arac = shutil.which("gsettings")
            if arac:
                try:
                    cikti = subprocess.run(
                        [
                            arac, "get",
                            "org.gnome.desktop.notifications", "show-banners",
                        ],
                        capture_output=True,
                        text=True,
                        timeout=5,
                    )
                    durum = cikti.stdout.strip().lower() == "false"
                except (OSError, subprocess.SubprocessError):
                    durum = False
            self._bildirim_balon_durumu = durum
        return self._bildirim_balon_durumu

    def _bildirim_toast(self, baslik: str, govde: str):
        """Uygulama içi geçici uyarı penceresi.

        Sistem bildirim balonları kapalıyken de kullanıcıyı uyarmak için
        pencerenin sağ altında kısa süreli bir uyarı gösterir.
        """
        try:
            if self._toast is not None and self._toast.winfo_exists():
                self._toast.destroy()
        except tk.TclError:
            pass
        try:
            toast = tk.Toplevel(self)
            self._toast = toast
            toast.overrideredirect(True)
            toast.attributes("-topmost", True)
            cerceve = ttk.Frame(toast, padding=(14, 10), borderwidth=1, relief="solid")
            cerceve.pack(fill="both", expand=True)
            ttk.Label(
                cerceve, text=baslik, font=("TkDefaultFont", 10, "bold")
            ).pack(anchor="w")
            ttk.Label(cerceve, text=govde).pack(anchor="w")
            toast.bind("<Button-1>", lambda e: self._toast_kapat())
            self.update_idletasks()
            x = self.winfo_rootx() + self.winfo_width() - toast.winfo_reqwidth() - 30
            y = self.winfo_rooty() + self.winfo_height() - toast.winfo_reqheight() - 50
            toast.geometry(f"+{max(0, x)}+{max(0, y)}")
            toast.after(6000, self._toast_kapat)
        except tk.TclError:
            self._toast = None

    def _toast_kapat(self):
        """Uygulama içi uyarı penceresini kapatır."""
        try:
            if self._toast is not None and self._toast.winfo_exists():
                self._toast.destroy()
        except tk.TclError:
            pass
        self._toast = None

    def _bildirim_balonlarini_ac(self) -> bool:
        """Sistem bildirim balonlarını açar (GNOME)."""
        arac = shutil.which("gsettings")
        if not arac:
            return False
        try:
            subprocess.run(
                [
                    arac, "set",
                    "org.gnome.desktop.notifications", "show-banners", "true",
                ],
                capture_output=True,
                timeout=5,
            )
        except (OSError, subprocess.SubprocessError):
            return False
        self._bildirim_balon_durumu = False
        return True

    def _otomatik_isle(self, klasorler, mesajlar, toplam, diger=None):
        """Otomatik yenileme sonucu: listeler sessizce tazelenir."""
        eski = {m.item_id for m in self.mesajlar}
        self._klasorleri_doldur(klasorler, mesajlari_yukle=False, durum_yaz=False)
        self._mesajlari_doldur(mesajlar, toplam, durum_yaz=False)
        net = sum(1 for m in mesajlar if m.item_id not in eski)
        if net:
            self.durum.set(f"Otomatik yenileme — {net} yeni mesaj")
        self._bildirimleri_denle(diger or {})

    def _bildirimleri_denle(self, diger: dict, aktif_sayi: int | None = None):
        """Tüm hesapların gelen kutusu artışını denetler, bildirim üretir."""
        for h in self.ayarlar.hesaplar():
            hid = h.get("id")
            if not hid:
                continue
            ad = h.get("ad") or h.get("kullanici") or "Hesap"
            if hid == self.aktif_id:
                sayi = aktif_sayi
            else:
                sayi = diger.get(hid)
            if sayi is None:
                continue
            self._bildirim_kontrol(hid, sayi, ad)

    def _agaci_yenile(self):
        """Hesap → klasör iki kademeli ağaç kurar (Evolution tarzı).

        Üst düğüm = hesap adı, alt düğümler = o hesabın klasörleri.
        iid: hesap `hesap:<id>`, klasör `<hesap_id>|<klasor_kimlik>`.
        """
        agac = self.klasor_listesi
        # Hesap düğümlerinin açık/kapalı durumunu koru
        acik_durum = {}
        for cocuk in agac.get_children(""):
            try:
                acik_durum[cocuk] = bool(agac.item(cocuk, "open"))
            except tk.TclError:
                pass
        agac.delete(*agac.get_children())
        for hesap in self.ayarlar.hesaplar():
            hid = hesap.get("id")
            if not hid:
                continue
            etiket = hesap.get("ad") or hesap.get("kullanici") or "Hesap"
            if hid != self.aktif_id and hid not in self._hesap_klasorleri:
                if not (hesap.get("kullanici") and hesap.get("parola")):
                    etiket += "  (bağlanmak için tıklayın)"
            kok = f"hesap:{hid}"
            agac.insert(
                "", "end", iid=kok, text=etiket,
                open=acik_durum.get(kok, True),
            )
            for klasor in self._hesap_klasorleri.get(hid, []):
                ozellikler = dict(
                    iid=f"{hid}|{klasor.kimlik}",
                    text=klasor.etiket,
                )
                # İkon her klasörde yok (Gmail etiketleri vb.); image=None
                # Treeview.insert'i çökertir ("value for -image missing").
                ikon = self.ikon.get(f"klasor_{klasor.kimlik}")
                if ikon is not None:
                    ozellikler["image"] = ikon
                agac.insert(kok, "end", **ozellikler)

    def _hesap_klasorlerine_yaz(self, hesap_id: str, klasorler) -> None:
        """Arka planda çekilen başka bir hesabın klasörlerini yazar."""
        self._hesap_klasorleri[hesap_id] = list(klasorler or [])
        self._agaci_yenile()

    def _diger_hesaplari_yukle(self):
        """Diğer hesapların klasör listelerini arka planda çeker (Evolution
        gibi tüm hesaplar ağaçta görünsün diye). Parolası olmayanlar atlanır."""
        hedefler = [
            h for h in self.ayarlar.hesaplar()
            if h.get("id") and h["id"] != self.aktif_id
            and h.get("kullanici") and h.get("parola")
        ]
        if not hedefler:
            return
        threading.Thread(
            target=self._diger_hesap_cek, args=(hedefler,), daemon=True
        ).start()

    def _diger_hesap_cek(self, hedefler):
        """Her hesap için klasör listesini çeker (Tk'ye dokunmaz)."""
        for hesap in hedefler:
            klasorler = []
            try:
                istemci = self._istemciler.get(hesap["id"])
                if istemci is None:
                    istemci = self._istemci_kur(hesap)
                klasorler = istemci.klasor_listesi()
                self._istemciler[hesap["id"]] = istemci
            except Exception:
                klasorler = []
            # Kuyruk biçimi: ("ok", sonuç-tüpü) — _arka_plan ile aynı
            self.is_kuyrugu.put(("ok", ("hesap_klasorler", hesap["id"], klasorler)))

    def _hesap_degistir(self, hesap_id: str, klasor_kimlik: str | None = None) -> bool:
        """Aktif hesabı değiştirir.

        Mesaj alanı temizlenir, yeni hesabın klasörleri ağaçta zaten varsa
        doğrudan o klasörün mesajları yüklenir; yoksa önce bağlanılır.
        Giriş penceresi gerekirse açılır (iptal edilirse False döner).
        """
        if hesap_id == self.aktif_id:
            return True
        hesap = self.ayarlar.hesap(hesap_id)
        if hesap is None:
            return False
        # Devam eden işleri yut (hesaptan çıkıştaki gibi)
        self.oturum = False
        self._kuyrugu_yut()
        self.istemci = None
        self._mesaj_alanini_temizle()
        self.aktif_id = hesap_id
        self.ayarlar.aktif_ayarla(hesap_id)
        self.ayarlar.kaydet()
        self.cozum_yok = hesap.get("tur") != "ews"  # dizin yalnız EWS'te
        # Takvim önbelleği hesaba bağlıdır
        self.randevular = []
        self.takvim_yuklendi = False
        self._takvim_ciziliyor = False
        if hasattr(self, "_takvim_ciz"):
            self._takvim_ciz()
            # Takvim sekmesi açıksa yeni hesabı hemen çek
            try:
                if self.defter.index("current") == 1:
                    self.after(200, self._takvim_cek)
            except tk.TclError:
                pass
        self.title(self._baslik_metni(hesap))
        if hasattr(self, "hesap_degisken"):
            self.hesap_degisken.set(hesap_id)
        klasorler = self._hesap_klasorleri.get(hesap_id) or []
        self.klasor_liste = list(klasorler)  # Taşı menüsü yeni hesabın klasörleri
        self.klasor = (
            klasor_kimlik
            or hesap.get("son_klasor")
            or (klasorler[0].kimlik if klasorler else "inbox")
        )
        self.sayfa_no = 0
        self.sayfa_sayisi = 1
        self.tam_yenile = True
        if not self._baglan():
            # Giriş iptal edildi ya da hesap ekleniyor
            self._agaci_yenile()
            return False
        self.oturum = True
        self._son_gelen_sayi.pop(hesap_id, None)
        self._agaci_yenile()
        hedef_iid = f"{hesap_id}|{self.klasor}"
        if self.klasor_listesi.exists(hedef_iid):
            self.klasor_listesi.selection_set(hedef_iid)
            self.klasor_listesi.see(hedef_iid)
            self._mesajlari_cek_ile()
        else:
            # Klasörler henüz bilinmiyor: bağlanıp ağaçları doldur
            self.yenile()
        return True

    def _hesap_menu_sec(self, hesap_id: str):
        """Hesaplar menüsünden hızlı geçiş."""
        if not hesap_id or hesap_id == self.aktif_id:
            return
        if not self._hesap_degistir(hesap_id):
            # Giriş iptal edildi → menü işaretini geri al
            self.hesap_degisken.set(self.aktif_id)

    def _hesap_ekle_penceresi(self):
        HesapPenceresi(self).ac()

    def _hesap_duzenle_penceresi(self):
        hesap = self.ayarlar.aktif_hesap()
        if not hesap:
            messagebox.showinfo("Hesap", "Düzenlenecek hesap yok.")
            return
        HesapPenceresi(self, hesap=hesap).ac()

    def _hesap_sil_penceresi(self):
        hesap = self.ayarlar.aktif_hesap()
        if not hesap:
            messagebox.showinfo("Hesap", "Silinecek hesap yok.")
            return
        ad = hesap.get("ad") or hesap.get("kullanici") or "hesap"
        if not messagebox.askyesno(
            "Hesap Sil",
            f"'{ad}' hesabı silinsin mi?\n\nKayıtlı parolası da silinir.",
        ):
            return
        silinen_id = hesap["id"]
        silinen_aktif_mi = silinen_id == self.aktif_id
        self.ayarlar.hesap_sil(silinen_id)
        self._istemciler.pop(silinen_id, None)
        self._hesap_klasorleri.pop(silinen_id, None)
        if not self.ayarlar.hesaplar():
            # Hesap kalmadı: hesap ekleme penceresi açılır
            self.oturum = False
            self.istemci = None
            self.aktif_id = ""
            self._mesaj_alanini_temizle()
            self._agaci_yenile()
            self._menu_kur()
            self.after(300, self._hesap_ekle_penceresi)
            return
        self._menu_kur()
        if silinen_aktif_mi:
            # Aktif hesap silindi → kalan ilk hesaba geç
            self.istemci = None
            self.aktif_id = ""
            self._mesaj_alanini_temizle()
            self._hesap_degistir(self.ayarlar.aktif_hesap_id())
        else:
            self._agaci_yenile()

    def _klasorleri_doldur(self, klasorler, mesajlari_yukle: bool = True, durum_yaz: bool = True):
        """Aktif hesabın klasörlerini yazar ve tüm ağacı yeniden kurar."""
        self.klasor_liste = list(klasorler)
        self._hesap_klasorleri[self.aktif_id] = list(klasorler)
        self._agaci_yenile()
        agac = self.klasor_listesi
        cocuklar = agac.get_children(f"hesap:{self.aktif_id}")
        if not cocuklar:
            if durum_yaz:
                self.durum.set("Klasör bulunamadı")
            return
        # Kayitli klasor listede yoksa ilkine dus
        hedef_iid = f"{self.aktif_id}|{self.klasor}"
        if hedef_iid not in cocuklar:
            self.klasor = cocuklar[0].split("|", 1)[1]
            hedef_iid = f"{self.aktif_id}|{self.klasor}"
        agac.selection_set(hedef_iid)
        agac.see(hedef_iid)
        if durum_yaz:
            self.durum.set("Hazır")
        # Klasorler geldi; simdi mesajlari cek
        if mesajlari_yukle:
            self._mesajlari_cek_ile()

    def _klasor_secildi(self, _olay):
        secim = self.klasor_listesi.selection()
        if not secim:
            return
        iid = secim[0]
        if iid.startswith("hesap:"):
            # Hesap düğümü seçildi: ilk klasörü seç (olay yeniden tetiklenir)
            cocuklar = self.klasor_listesi.get_children(iid)
            if cocuklar:
                self.klasor_listesi.selection_set(cocuklar[0])
            return
        hesap_id, ayraclı, klasor_kimlik = iid.partition("|")
        if not ayraclı or not klasor_kimlik:
            return
        if hesap_id != self.aktif_id:
            # Başka hesabın klasörü seçildi → o hesaba geç
            self._hesap_degistir(hesap_id, klasor_kimlik)
            return
        # Yenileme sonrasi ayni klasor tekrar seciliyorsa islem yapma
        # (aksi halde mesaj listesi iki kez yuklenir).
        if klasor_kimlik == self.klasor:
            if self.istemci is not None:
                return
        else:
            self.klasor = klasor_kimlik
            self.ayarlar.hesap_guncelle(hesap_id, {"son_klasor": klasor_kimlik})
            self.sayfa_no = 0
            # Artımlı senkron yeterli: ilk ziyarette önbellek yoksa istemci
            # zaten tam çeker; sonraki ziyaretlerde SyncState/UID önbelleği
            # korunur (tam senkron ~15 sn → ~0.1 sn).
            self.tam_yenile = False
        if self.istemci is None:
            # Oturum kapalıysa (çıkış/silme/iptal) giriş penceresi açılır
            if not self._baglan():
                return
            self.oturum = True
        self._mesajlari_cek_ile()

    def _aramayi_temizle(self):
        self.arama.set("")
        self.sayfa_no = 0
        # Arama önbellek üstünde filtrelenir; tam senkron gereksiz.
        self._mesajlari_cek_ile()

    def _arama_yap(self):
        """Aramayi calistirir; sayfayi basa dondurur."""
        self.sayfa_no = 0
        self._mesajlari_cek_ile()

    def _mesajlari_cek_ile(self, tazele: bool = True):
        """Mesaj listesini arka planda yeniler.

        Tk degiskenleri (arama metni, klasor, sayfa) ana is parcaciginda
        okunur; arka plan is parcacigi sadece ag islemi yapar.
        `tazele=False` onbellekten okur (sayfalama).
        """
        if self.istemci is None:
            return
        arama = self.arama.get().strip()
        alan = "gonderen" if arama.lower().startswith("from:") else "konu"
        if alan == "gonderen":
            arama = arama[5:].strip()
        klasor = self.klasor
        offset = self.sayfa_no * self.sayfa_boyutu
        sayfa_boyutu = self.sayfa_boyutu
        tam = self.tam_yenile
        self.tam_yenile = False
        self.durum.set("Mesajlar yükleniyor…")
        threading.Thread(
            target=self._arka_plan,
            args=(self._mesajlari_cek, klasor, sayfa_boyutu, offset, arama, alan, tam, tazele),
            daemon=True,
        ).start()

    def _mesajlari_cek(self, klasor, sayfa_boyutu, offset, arama, alan, tam, tazele=True):
        mesajlar, toplam = self.istemci.mesajlar(
            klasor=klasor,
            sayfa_boyutu=sayfa_boyutu,
            offset=offset,
            arama=arama,
            alan=alan,
            tam=tam,
            tazele=tazele,
        )
        if hasattr(self.istemci, "detay_hazirla"):
            # IMAP gövde oturumunu şimdiden aç: ilk mesaj seçiminde
            # bağlantı bekleme olmasın (klasör yüklenirken paralel).
            threading.Thread(target=self.istemci.detay_hazirla, daemon=True).start()
        return ("mesajlar", mesajlar, toplam)

    def _mesajlari_doldur(self, mesajlar, toplam, durum_yaz: bool = True):
        if self._mouse_basili:
            # Fare seçim sürüklemesi sürerken listeyi yeniden kurmak
            # Tcl çökmesine yol açabilir → düğme kalkınca uygula.
            self._bekleyen_doldurma = (mesajlar, toplam, durum_yaz)
            self.after(120, self._bekleyen_doldurma_uygula)
            return
        # Yenileme öncesi seçim ve kaydırma konumu korunur; otomatik
        # yenilemede liste zıplamaz (polling'li arayüzde scroll sıfırlanmasın).
        secili_kimlikler = set()
        for s in self.liste.selection():
            try:
                i = int(s)
            except ValueError:
                continue
            if 0 <= i < len(self.mesajlar):
                secili_kimlikler.add(self.mesajlar[i].item_id)
        kaydirma = self.liste.yview()[0] if self.liste.get_children() else 0.0

        # Yapay seçim olayları yutulur: delete (seçim düşerse) + selection_set.
        # Böylece yenileme detay yeniden çekmez, durum çubuğu bozulmaz.
        self._secim_olayi_yut += 1 if secili_kimlikler else 0
        self.mesajlar = mesajlar
        self.liste.delete(*self.liste.get_children())
        geri_yukle = []
        for i, m in enumerate(mesajlar):
            konu = ("📎 " if m.ek_var else "") + m.konu
            self.liste.insert(
                "",
                "end",
                iid=str(i),
                values=("●" if not m.okundu else "", m.gonderen_ad or m.gonderen, konu, m.tarih),
            )
            if m.item_id in secili_kimlikler:
                geri_yukle.append(str(i))
        self.sayfa_sayisi = max(1, (toplam + self.sayfa_boyutu - 1) // self.sayfa_boyutu)
        if self.sayfa_no >= self.sayfa_sayisi:
            # Arama sonucu kuculdu: son sayfaya don ve tekrar yukle.
            self.sayfa_no = self.sayfa_sayisi - 1
            self.sayfa_etiket.configure(text=f"Sayfa {self.sayfa_no + 1}/{self.sayfa_sayisi}")
            self._mesajlari_cek_ile(tazele=False)
            return
        if geri_yukle:
            self._secim_olayi_yut += 1
            self.liste.selection_set(geri_yukle)
        if self.liste.get_children():
            self.liste.yview_moveto(kaydirma)
        self.sayfa_etiket.configure(text=f"Sayfa {self.sayfa_no + 1}/{self.sayfa_sayisi}")
        if durum_yaz:
            self.durum.set(f"{len(mesajlar)} mesaj" + (f" / {toplam} toplam" if toplam else ""))

    def _sayfa_degistir(self, delta: int):
        yeni = self.sayfa_no + delta
        if yeni < 0 or yeni >= self.sayfa_sayisi:
            return
        self.sayfa_no = yeni
        self._mesajlari_cek_ile(tazele=False)

    def _bekleyen_doldurma_uygula(self):
        """Fare bırakıldıysa bekleyen mesaj listesini kurar; basılıysa bekler."""
        if self._mouse_basili and time.time() - self._mouse_zamani < 3:
            self.after(120, self._bekleyen_doldurma_uygula)
            return
        self._mouse_basili = False  # bayrak takılı kaldıysa bırak
        bekleyen = self._bekleyen_doldurma
        self._bekleyen_doldurma = None
        if bekleyen is not None:
            self._mesajlari_doldur(*bekleyen)

    def _mouse_bastı(self, _olay=None):
        self._mouse_basili = True
        self._mouse_zamani = time.time()

    def _mouse_birakti(self, _olay=None):
        self._mouse_basili = False

    def _secili_mesajlar(self) -> list[Mesaj]:
        """Seçili satırlardaki mesajları sırayla döndürür (çoklu seçim)."""
        sonuc = []
        for s in self.liste.selection():
            try:
                i = int(s)
            except ValueError:
                continue  # beklenmedik satır kimliği — çökmesin
            if 0 <= i < len(self.mesajlar):
                sonuc.append(self.mesajlar[i])
        return sonuc

    def _mesaj_secildi(self, _olay):
        if self._secim_olayi_yut > 0:
            self._secim_olayi_yut -= 1  # yenilemeden gelen yapay seçim olayı
            return
        secili = self._secili_mesajlar()
        if not secili:
            return
        self.secili = secili[0]
        if len(secili) > 1:
            self.durum.set(f"{len(secili)} mesaj seçildi — Sil/İçin Delete veya sağ tuş")
        else:
            self.durum.set("Mesaj okunuyor…")
        if self.secili.govde or self.secili.govde_html:
            # Gövde daha önce çekilmiş (onbellekte): anında göster
            self._detay_goster(self.secili)
            return
        threading.Thread(target=self._arka_plan, args=(self._detay_cek,), daemon=True).start()

    def _detay_cek(self):
        return ("detay", self.istemci.mesaj_detay(self.secili))

    def _detay_goster(self, mesaj: Mesaj):
        self.secili = mesaj
        self.baslik.configure(text=f"{mesaj.gonderen_ad or mesaj.gonderen} — {mesaj.konu}")
        if self.html_modu:
            self._resim_yer_tutucularini_kur(mesaj)
            self._html_yukle()
        else:
            self.ayrinti.configure(state="normal")
            self.ayrinti.delete("1.0", "end")
            self.ayrinti.insert("1.0", mesaj.govde or mesaj.onizleme or "(gövde yok)")
            self._resim_yer_tutucularini_kur(mesaj)
            self.ayrinti.configure(state="disabled")
        self.ek_listesi.delete(*self.ek_listesi.get_children())
        for i, ek in enumerate(mesaj.ekler):
            self.ek_listesi.insert(
                "", "end", iid=str(i),
                text=f"{ek.ad}  ({ek.boyut} bayt)",
                image=self._ek_ikonu(ek.ad),
            )
        self.ek_listesi.ekler = mesaj.ekler
        self.durum.set(f"{mesaj.tarih} • {mesaj.gonderen}")
        if not mesaj.okundu:
            threading.Thread(
                target=self._arka_plan, args=(self._okundu_isaretle_kuyruk,), daemon=True
            ).start()

    # ------------------------------------------------- gövdedeki satır içi resimler

    def _resim_yer_tutucularini_kur(self, mesaj: Mesaj):
        """[resim: ad] yer tutucularını tıklanabilir kayıtlara bağlar.

        Evolution gibi ilk anda dosya adı görünür; tıklanınca (ya da
        "Resimleri göster" ile) resim gövdede belirir. HTML modunda yer
        tutucular `govde_html_gosterim` içinde bağlantıdır; düz metin
        modunda gövde metni içindeki yer tutucular aynı sırayla aranıp
        etiketlenir.
        """
        self.resim_kayitlari = []
        resimler = getattr(mesaj, "resimler", None) or []
        konum = "1.0"
        for no, resim in enumerate(resimler):
            kayit = {
                "no": no,
                "resim": resim,
                "mesaj": mesaj,
                "mesaj_id": mesaj.item_id,
                "etiket": f"resim_{no}",
                "durum": "bekliyor",  # bekliyor | yukleniyor | gosterildi | hata
                "foto": None,
                "html": "",  # HTML modunda çözülen resim/hata parçası
            }
            if self.html_modu:
                self.resim_kayitlari.append(kayit)
                continue
            bas = self.ayrinti.search(resim.yer_tutucu, konum, stopindex="end")
            if not bas:
                continue
            son = f"{bas}+{len(resim.yer_tutucu)}c"
            self.ayrinti.tag_add(kayit["etiket"], bas, son)
            self.ayrinti.tag_configure(
                kayit["etiket"], foreground="#0b57d0", underline=True
            )
            self.resim_kayitlari.append(kayit)
            konum = son
        self._resim_cubugunu_guncelle()

    # ------------------------------------------------------- HTML gövde gösterimi

    def _html_yukle(self):
        """HTML gövdeyi (çözülmüş resimlerle) yeniden çizdirir."""
        gecen = {k["no"]: k["html"] for k in self.resim_kayitlari if k["html"]}
        self.ayrinti.load_html(govde_html_gosterim(self.secili, gecen))

    def _html_baglanti_tikla(self, url: str):
        """Yer tutucu bağlantısı resmi açar; dış bağlantı tarayıcıda açılır."""
        if url.startswith(RESIM_SEMASI):
            try:
                no = int(url[len(RESIM_SEMASI):])
            except ValueError:
                return
            for kayit in self.resim_kayitlari:
                if kayit["no"] == no:
                    self._resim_goster(kayit)
                    return
        elif url.startswith(("http://", "https://", "mailto:")):
            webbrowser.open(url)

    def _govde_istek(self, url, *args, **kw):
        """tkinterweb kaynak isteği: yalnız gömülü `data:` resimlerine izin.

        Görsel gizliliği için dış ağ istekleri (uzak resimler, arka plan
        görselleri) engellenir; resimler tıklandığında bizim indirdiğimiz
        baytlar `data:` URI olarak gömülür. tkinterweb `url, data, method,
        decode` gibi değişken sayıda argüman gönderir.
        """
        try:
            if url.lower().startswith("data:"):
                veri = data_uri_verisi(url) or b""
                eslesme = re.match(r"data:([^;,]+)", url)
                mime = eslesme.group(1) if eslesme else "image/png"
                return url, veri, mime, 200
        except Exception:
            pass
        return url, b"", "text/html", 404

    def _resim_data_uri(self, veri: bytes) -> str:
        """Resim baytlarını gövdeye gömülecek `data:` URI'ye çevirir.

        Pillow varsa büyük resimler küçültülür ve PNG'ye çevrilir; yoksa
        ham veri gömülür (Tk'ın kendi PNG/GIF desteğiyle açılır).
        """
        try:
            from PIL import Image
        except ImportError:
            return "data:image/png;base64," + base64.b64encode(veri).decode("ascii")
        resim = Image.open(io.BytesIO(veri))
        resim.load()
        if resim.mode not in ("RGB", "RGBA", "P", "L"):
            resim = resim.convert("RGB")
        genislik = self.ayrinti.winfo_width() - 28
        genislik = max(240, min(genislik, 900))
        if resim.width > genislik:
            oran = genislik / resim.width
            resim = resim.resize(
                (genislik, max(1, int(resim.height * oran))), Image.LANCZOS
            )
        tampon = io.BytesIO()
        resim.save(tampon, "PNG")
        return "data:image/png;base64," + base64.b64encode(
            tampon.getvalue()
        ).decode("ascii")

    def _resim_cubugunu_guncelle(self):
        toplam = len(self.resim_kayitlari)
        if not toplam:
            self.resim_cubugu.pack_forget()
            return
        gosterilen = sum(1 for k in self.resim_kayitlari if k["durum"] == "gosterildi")
        kalan = sum(1 for k in self.resim_kayitlari if k["durum"] == "bekliyor")
        self.resim_etiket.configure(text=f"Bu ileti {toplam} resim içeriyor")
        self.resim_dugmesi.configure(
            text=f"Resimleri göster ({kalan})" if kalan else "Resimler gösterildi"
        )
        if kalan:
            self.resim_dugmesi.state(["!disabled"])
        else:
            self.resim_dugmesi.state(["disabled"])
        if not self.resim_cubugu.winfo_ismapped():
            self.resim_cubugu.pack(fill="x", padx=6, pady=(0, 2), before=self.ayrinti)

    def _ayrinti_tikla(self, olay):
        """Yer tutucuya tıklayınca resmi gövdede gösterir."""
        if not self.resim_kayitlari:
            return
        index = self.ayrinti.index(f"@{olay.x},{olay.y}")
        for kayit in self.resim_kayitlari:
            if kayit["etiket"] in self.ayrinti.tag_names(index):
                self._resim_goster(kayit)
                return

    def _ayrinti_hareket(self, olay):
        """Yer tutucu üzerindeyken imleç el şeklini alır."""
        if not self.resim_kayitlari:
            return
        index = self.ayrinti.index(f"@{olay.x},{olay.y}")
        etiketler = self.ayrinti.tag_names(index)
        elde = any(k["etiket"] in etiketler for k in self.resim_kayitlari)
        imlec = "hand2" if elde else "xterm"
        if str(self.ayrinti.cget("cursor")) != imlec:
            self.ayrinti.configure(cursor=imlec)

    def _resim_goster(self, kayit: dict):
        if kayit["durum"] != "bekliyor":
            return
        kayit["durum"] = "yukleniyor"
        self._resim_cubugunu_guncelle()
        threading.Thread(
            target=self._arka_plan, args=(self._resim_cek, kayit), daemon=True
        ).start()

    def _resim_cek(self, kayit: dict):
        try:
            veri = resim_verisi(self.istemci, kayit["mesaj"], kayit["resim"])
        except EwsYetkiHatasi:
            raise  # _arka_plan giriş penceresi açsın
        except Exception as exc:
            return ("resim_hata", kayit, str(exc))
        return ("resim", kayit, veri)

    def tum_resimleri_goster(self):
        """Tüm yer tutucuların resimlerini sırayla gövdede gösterir."""
        bekleyen = [k for k in self.resim_kayitlari if k["durum"] == "bekliyor"]
        if not bekleyen:
            return
        for kayit in bekleyen:
            kayit["durum"] = "yukleniyor"
        self._resim_cubugunu_guncelle()
        threading.Thread(
            target=self._tum_resimleri_cek, args=(bekleyen,), daemon=True
        ).start()

    def _tum_resimleri_cek(self, bekleyen: list):
        """Resimleri sırayla getirir (sunucuyu yormamak için tek iş parçacığı)."""
        for kayit in bekleyen:
            self._arka_plan(self._resim_cek, kayit)

    def _resim_yerlestir(self, kayit: dict, veri: bytes):
        if not self._resim_kaydi_gecerli(kayit):
            return
        if self.html_modu:
            try:
                uri = self._resim_data_uri(veri)
            except Exception as exc:
                self._resim_gosterilemedi(kayit, f"biçim okunamadı ({exc})")
                return
            ad = html_mod.escape(kayit["resim"].ad)
            kayit["html"] = f'<img src="{uri}" alt="{ad}">'
            kayit["durum"] = "gosterildi"
            self._html_yukle()
            self._resim_cubugunu_guncelle()
            return
        try:
            foto = self._foto_olustur(veri)
        except Exception as exc:
            self._resim_gosterilemedi(kayit, f"biçim okunamadı ({exc})")
            return
        aralik = self.ayrinti.tag_ranges(kayit["etiket"])
        if not aralik:
            return
        bas, son = str(aralik[0]), str(aralik[1])
        self.ayrinti.configure(state="normal")
        self.ayrinti.delete(bas, son)
        self.ayrinti.image_create(
            bas, image=foto, padx=4, pady=4, name=f"govde_resim_{kayit['no']}"
        )
        self.ayrinti.configure(state="disabled")
        kayit["foto"] = foto  # PhotoImage çöp toplayıcıya gitmesin
        kayit["durum"] = "gosterildi"
        self._resim_cubugunu_guncelle()

    def _resim_gosterilemedi(self, kayit: dict, aciklama: str):
        if not self._resim_kaydi_gecerli(kayit):
            return
        if self.html_modu:
            ad = html_mod.escape(kayit["resim"].ad)
            aciklama = html_mod.escape(aciklama)
            kayit["html"] = (
                f'<span style="color:#b3261e">[resim: {ad} — '
                f"görüntülenemedi: {aciklama}]</span>"
            )
            kayit["durum"] = "hata"
            self._html_yukle()
            self._resim_cubugunu_guncelle()
            return
        aralik = self.ayrinti.tag_ranges(kayit["etiket"])
        if aralik:
            bas, son = str(aralik[0]), str(aralik[1])
            self.ayrinti.configure(state="normal")
            self.ayrinti.delete(bas, son)
            self.ayrinti.insert(
                bas,
                f"[resim: {kayit['resim'].ad} — görüntülenemedi: {aciklama}]",
                ("resim_hata",),
            )
            self.ayrinti.configure(state="disabled")
        kayit["durum"] = "hata"
        self._resim_cubugunu_guncelle()

    def _resim_kaydi_gecerli(self, kayit: dict) -> bool:
        """Mesaj değiştiyse eski yüklemelerin sonuçları gövdeye yazılmaz."""
        return bool(
            self.secili
            and kayit["mesaj_id"] == self.secili.item_id
            and any(k is kayit for k in self.resim_kayitlari)
        )

    def _foto_olustur(self, veri: bytes):
        """Resim baytlarını Tk nesnesine çevirir; büyük resimler küçültülür."""
        genislik = self.ayrinti.winfo_width() - 28
        genislik = max(240, min(genislik, 900))
        try:
            from PIL import Image, ImageTk

            resim = Image.open(io.BytesIO(veri))
            resim.load()
            if resim.mode not in ("RGB", "RGBA", "P", "L"):
                resim = resim.convert("RGB")
            if resim.width > genislik:
                oran = genislik / resim.width
                resim = resim.resize(
                    (genislik, max(1, int(resim.height * oran))), Image.LANCZOS
                )
            return ImageTk.PhotoImage(resim)
        except Exception:
            # Pillow yoksa Tk 8.6'nın kendi PNG/GIF desteği
            foto = tk.PhotoImage(data=veri)
            if foto.width() > genislik:
                adim = max(1, -(-foto.width() // genislik))
                foto = foto.subsample(adim)
            return foto

    def _okundu_isaretle_kuyruk(self, deger: bool = True):
        try:
            self.istemci.okundu_isaretle(self.secili, deger)
            self.secili.okundu = deger
            return ("okundu", deger)
        except EwsHata:
            # Kurumda EWS UpdateItem calismiyor; sessizce gec.
            return ("okundu_hata", None)

    def bir_okundu(self, deger: bool = True):
        if not self.secili:
            return
        threading.Thread(
            target=self._arka_plan, args=(self._okundu_isaretle_kuyruk, deger), daemon=True
        ).start()

    def sil(self):
        """Delete tusu veya menu → Silinmiş Öğeler'e taşı."""
        self.tasi_klasore("deleteditems")

    def tasi_klasore(self, hedef: str):
        """Seçili mesaj(lar)ı verilen klasöre taşır; bittiğinde liste yenilenir."""
        secili = self._secili_mesajlar()
        if not secili:
            return
        ad = next((k.ad for k in self.klasor_liste if k.kimlik == hedef), hedef)
        if len(secili) == 1:
            if hedef == "deleteditems":
                soru = f"\"{secili[0].konu}\" mesajı Silinmiş Öğeler'e taşınacak."
            else:
                soru = f"\"{secili[0].konu}\"\n\n\"{ad}\" klasörüne taşınacak."
        else:
            if hedef == "deleteditems":
                soru = f"Seçili {len(secili)} mesaj Silinmiş Öğeler'e taşınacak."
            else:
                soru = f"Seçili {len(secili)} mesaj\n\"{ad}\" klasörüne taşınacak."
        if not messagebox.askyesno("Taşınsın mı?", soru):
            return
        self.durum.set(f"Taşınıyor → {ad} ({len(secili)} mesaj)…")
        threading.Thread(
            target=self._arka_plan,
            args=(self._tasi_cek, secili, hedef, ad),
            daemon=True,
        ).start()

    def _tasi_cek(self, mesajlar: list, hedef: str, ad: str):
        for m in mesajlar:
            self.istemci.tasi(m, hedef)
        self.tam_yenile = True
        return ("yenile", f"Taşındı → {ad} ({len(mesajlar)} mesaj)")

    def _ek_ikonu(self, dosya_adi: str) -> tk.PhotoImage:
        """Dosya uzantısına göre ek ikonu seçer (yoksa genel sayfa)."""
        nokta = dosya_adi.rfind(".")
        uzanti = dosya_adi[nokta + 1:].lower() if nokta > 0 else ""
        harita = {
            "pdf": "ek_pdf",
            "doc": "ek_doc", "docx": "ek_doc", "rtf": "ek_doc", "odt": "ek_doc",
            "xls": "ek_xls", "xlsx": "ek_xls", "csv": "ek_xls", "ods": "ek_xls",
            "ppt": "ek_ppt", "pptx": "ek_ppt", "odp": "ek_ppt",
            "zip": "ek_zip", "rar": "ek_zip", "7z": "ek_zip",
            "tar": "ek_zip", "gz": "ek_zip",
            "jpg": "ek_resim", "jpeg": "ek_resim", "png": "ek_resim",
            "gif": "ek_resim", "bmp": "ek_resim", "webp": "ek_resim",
            "svg": "ek_resim", "tif": "ek_resim", "tiff": "ek_resim",
            "txt": "ek_metin", "log": "ek_metin", "md": "ek_metin",
            "json": "ek_metin", "xml": "ek_metin", "ini": "ek_metin",
            "eml": "ek_eposta", "msg": "ek_eposta",
            "mp4": "ek_video", "avi": "ek_video", "mkv": "ek_video",
            "mov": "ek_video",
            "mp3": "ek_ses", "wav": "ek_ses", "ogg": "ek_ses",
            "m4a": "ek_ses", "flac": "ek_ses",
        }
        return self.ikon.get(harita.get(uzanti, "ek_dosya")) or self.ikon["ek"]

    def _ek_tumunu_sec(self, olay=None):
        """Ek listesindeki tüm dosyaları seçer (Ctrl+A)."""
        self.ek_listesi.selection_set(self.ek_listesi.get_children())
        return "break"

    def _ek_menusu(self, olay):
        """Ek listesinde sağ tuş: seçilenleri / tümünü indir."""
        satir = self.ek_listesi.identify_row(olay.y)
        if satir and satir not in self.ek_listesi.selection():
            self.ek_listesi.selection_set(satir)
        secim = self.ek_listesi.selection()
        if not secim:
            return
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(
            label=f"Seçilenleri indir ({len(secim)})", command=self.ek_indir
        )
        menu.add_command(label="Tümünü indir…", command=self._ek_tumunu_indir)
        menu.tk_popup(olay.x_root, olay.y_root)

    def _ek_tumunu_indir(self):
        self.ek_listesi.selection_set(self.ek_listesi.get_children())
        self.ek_indir()

    def ek_indir(self):
        """Seçili ekleri indirir; birden çok seçiliyse klasöre topluca yazar."""
        secim = self.ek_listesi.selection()
        if not secim:
            return
        ekler = [self.ek_listesi.ekler[int(i)] for i in secim]
        if len(ekler) == 1:
            ek = ekler[0]
            self.durum.set(f"{ek.ad} indiriliyor…")
            threading.Thread(
                target=self._arka_plan, args=(self._ek_indir_cek, ek), daemon=True
            ).start()
            return
        dizin = dosya_secici.dizin_sec("Eklerin kaydedileceği klasör")
        if not dizin:
            return
        self.durum.set(f"{len(ekler)} ek indiriliyor…")
        threading.Thread(
            target=self._arka_plan,
            args=(self._ekleri_indir_cek, ekler, dizin), daemon=True,
        ).start()

    def _ek_indir_cek(self, ek):
        return ("ek", ek, self.istemci.ek_indir(ek))

    def _ekleri_indir_cek(self, ekler, dizin):
        """Ekleri tek tek indirip hedef klasöre yazar (arka plan)."""
        kaydedilen, hatalar = [], []
        for ek in ekler:
            try:
                veri = self.istemci.ek_indir(ek)
                yol = _benzersiz_yol(dizin, ek.ad)
                with open(yol, "wb") as f:
                    f.write(veri)
                kaydedilen.append(os.path.basename(yol))
            except Exception as hata:  # tek ek hatası diğerlerini durdurmasın
                hatalar.append(f"{ek.ad}: {hata}")
        return ("ek_toplu", kaydedilen, hatalar, dizin)

    def _ekleri_indir_goster(self, kaydedilen, hatalar, dizin):
        if kaydedilen:
            self.durum.set(f"{len(kaydedilen)} ek kaydedildi → {dizin}")
        elif hatalar:
            self.durum.set("Ekler indirilemedi")
        if hatalar:
            messagebox.showwarning(
                "Bazı ekler indirilemedi", "\n".join(hatalar)
            )

    def _ek_kaydet(self, ek, veri):
        hedef = dosya_secici.dosya_kaydet(
            "Eki kaydet", baslangic=ek.ad, varsayilan_uzanti=".bin"
        )
        if not hedef:
            return
        with open(hedef, "wb") as f:
            f.write(veri)
        self.durum.set(f"Kaydedildi: {hedef}")

    # --------------------------------------------------------------- yeni e-posta

    def yeni_posta(self):
        YeniPostaPenceresi(self).ac()

    def yanitla(self):
        if not self.secili:
            return
        YeniPostaPenceresi(self).ac(yanit=self.secili)

    def ilet(self):
        if not self.secili:
            return
        YeniPostaPenceresi(self).ac(ilet=self.secili)

    def yanitla_herkese(self):
        if not self.secili:
            return
        YeniPostaPenceresi(self).ac(yanit=self.secili, herkese=True)

    # ------------------------------------------------------- sağ tuş menüsü

    def _mesaj_menusu(self, olay):
        """Mesaj listesinde sağ tuş → Outlook tarzı bağlam menüsü."""
        satir = self.liste.identify_row(olay.y)
        if not satir:
            return
        if satir not in self.liste.selection():
            self.liste.selection_set(satir)
        if not self.secili:
            return
        self._mesaj_menu_olustur().tk_popup(olay.x_root, olay.y_root)

    def _mesaj_menu_olustur(self) -> tk.Menu:
        """Bağlam menüsünü kurar (test için ayrıldı)."""
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(
            label="Yanıtla", image=self.ikon["yanitla"], compound="left",
            accelerator="Ctrl+R", command=self.yanitla,
        )
        menu.add_command(
            label="Yanıtla Herkese", image=self.ikon["yanitla_herkese"],
            compound="left", accelerator="Ctrl+Shift+R",
            command=self.yanitla_herkese,
        )
        menu.add_command(
            label="İlet", image=self.ikon["ilet"], compound="left",
            accelerator="Ctrl+I", command=self.ilet,
        )
        menu.add_separator()
        menu.add_command(
            label="Okundu olarak işaretle", image=self.ikon["oku"],
            compound="left", command=lambda: self.bir_okundu(True),
        )
        menu.add_command(
            label="Okunmadı yap", image=self.ikon["okunmadi"],
            compound="left", command=lambda: self.bir_okundu(False),
        )
        menu.add_separator()
        tasi = tk.Menu(menu, tearoff=0)
        for klasor in self.klasor_liste:
            if klasor.kimlik == self.klasor:
                continue
            # Klasör ikonu varsa kullan (klasor_<kimlik>.png), yoksa ikonsuz
            k_ikon = self.ikon.get(f"klasor_{klasor.kimlik}")
            if k_ikon is not None:
                tasi.add_command(
                    label=klasor.ad, image=k_ikon, compound="left",
                    command=lambda h=klasor.kimlik: self.tasi_klasore(h),
                )
            else:
                tasi.add_command(
                    label=klasor.ad,
                    command=lambda h=klasor.kimlik: self.tasi_klasore(h),
                )
        menu.add_cascade(
            label="Taşı", image=self.ikon["tasi"], compound="left", menu=tasi,
        )
        menu.add_command(
            label="Sil", image=self.ikon["sil"], compound="left",
            accelerator="Delete", command=self.sil,
        )
        menu.add_separator()
        menu.add_command(
            label="Kopyala", image=self.ikon["kopyala"], compound="left",
            accelerator="Ctrl+C", command=self.kopyala,
        )
        menu.add_command(
            label="Farklı Kaydet (.eml)…", image=self.ikon["kaydet"],
            compound="left", command=self.farkli_kaydet,
        )
        menu.add_command(
            label="Bilgiler…", image=self.ikon["bilgi"], compound="left",
            command=self.bilgiler,
        )
        menu.add_separator()
        menu.add_command(
            label="Yenile", image=self.ikon["yenile"], compound="left",
            accelerator="F5", command=self.yenile,
        )
        return menu

    # ------------------------------------------- klasör bağlam menüsü (sağ tuş)

    def _klasor_menusu(self, olay):
        """Klasör ağacında sağ tuş → klasör bağlam menüsü."""
        iid = self.klasor_listesi.identify_row(olay.y)
        if not iid:
            return
        if iid not in self.klasor_listesi.selection():
            self.klasor_listesi.selection_set(iid)
        menu = self._klasor_menu_olustur(iid)
        if menu is not None:
            menu.tk_popup(olay.x_root, olay.y_root)

    def _klasor_menu_olustur(self, iid: str):
        """Klasör için bağlam menüsü (test için ayrıldı).

        **"Yeni Klasör…"** yalnız **aktif hesapta** görünür (IMAP ve EWS);
        kökte (hesap düğümünde) ya da herhangi bir klasörde açılabilir.
        **"Yeniden Adlandır…"** aktif hesapta, özel olmayan klasörlerde
        (IMAP etiketleri ve EWS kullanıcı klasörleri) görünür.
        "Klasörü Sil…" ise yalnız aktif IMAP hesabında ve özel olmayan
        klasörlerde görünür (Exchange hesaplarında klasör silme yok).
        Menüde öğe yoksa None döner.
        """
        if iid.startswith("hesap:"):
            _, _, hesap_id = iid.partition(":")
            kimlik = None
        else:
            hesap_id, ayracılı, kimlik = iid.partition("|")
            if not ayracılı or not kimlik:
                return None
        hesap = self.ayarlar.hesap(hesap_id)
        menu = tk.Menu(self, tearoff=0)
        if hesap_id == self.aktif_id and hesap is not None \
                and self.istemci is not None:
            menu.add_command(
                label="Yeni Klasör…", image=self.ikon.get("klasor_ekle"),
                compound="left", command=self.klasor_olustur,
            )
            if kimlik and kimlik not in SIRA and kimlik not in KLASORLER:
                menu.add_separator()
                ad = next(
                    (k.ad for k in self.klasor_liste if k.kimlik == kimlik),
                    kimlik,
                )
                menu.add_command(
                    label="Yeniden Adlandır…", image=self.ikon["hesap_duzenle"],
                    compound="left",
                    command=lambda: self.klasor_yeniden_adlandir(kimlik, ad),
                )
                if hesap.get("tur") == "imap":
                    menu.add_command(
                        label="Klasörü Sil…", image=self.ikon["sil"],
                        compound="left",
                        command=lambda: self.klasor_sil(kimlik, ad),
                    )
        # Boş menüde `index("end)"` sürüme göre None ya da TclError verir;
        # her iki durumda da "öğe yok" demektir.
        try:
            bos = menu.index("end") is None
        except tk.TclError:
            bos = True
        return None if bos else menu

    def klasor_sil(self, kimlik: str, ad: str):
        """Klasörü (Gmail etiketini) silmek için onay ister ve arka planda siler."""
        if not messagebox.askyesno(
            "Klasör Sil",
            f"«{ad}» klasörü silinecek?\n\n"
            "Gmail'de bu etiket tüm mesajlardan kaldırılır; mesajlar silinmez "
            "(Tüm Postalar'da durur).",
        ):
            return
        self.durum.set(f"Klasör siliniyor: {ad}…")
        threading.Thread(
            target=self._arka_plan, args=(self._klasor_sil_cek, kimlik),
            daemon=True,
        ).start()

    def _klasor_sil_cek(self, kimlik: str):
        self.istemci.klasor_sil(kimlik)
        # Klasör listesi + sayaçlar yenilenir ("yenile" sonucu)
        return ("yenile", "Klasör silindi")

    def klasor_olustur(self, ad: str | None = None):
        """Yeni klasör oluşturur (sağ tuş → Yeni Klasör…).

        `ad` verilmezse küçük bir ad penceresi açılır; oluşturma arka
        planda yapılır, bitince klasör listesi yenilenir.
        """
        if self.istemci is None:
            return
        if ad is None:
            ad = self._klasor_adi_penceresi()
            if not ad:
                return
        ad = ad.strip()
        if not ad:
            messagebox.showwarning("Yeni Klasör", "Klasör adı boş olamaz.")
            return
        self.durum.set(f"Klasör oluşturuluyor: {ad}…")
        threading.Thread(
            target=self._arka_plan, args=(self._klasor_olustur_cek, ad),
            daemon=True,
        ).start()

    def _klasor_olustur_cek(self, ad: str):
        self.istemci.klasor_olustur(ad)
        # Klasör listesi + sayaçlar yenilenir ("yenile" sonucu)
        return ("yenile", f"Klasör oluşturuldu: {ad}")

    def klasor_yeniden_adlandir(self, kimlik: str, ad: str, yeni: str | None = None):
        """Klasörü yeniden adlandırmak için ad penceresi açar (sağ tuş).

        `yeni` verilirse pencere açılmaz (testler için). IMAP'te klasör
        kimliği adla birlikte değişir; EWS'te kimlik aynı kalır.
        """
        if self.istemci is None:
            return
        if yeni is None:
            yeni = self._klasor_adi_penceresi(
                ilk=ad, baslik="Klasörü Yeniden Adlandır"
            )
            if not yeni:
                return
        yeni = yeni.strip()
        if not yeni:
            messagebox.showwarning(
                "Yeniden Adlandır", "Klasör adı boş olamaz."
            )
            return
        if yeni == ad:
            return  # değişiklik yok
        self.durum.set(f"Klasör adı değiştiriliyor: {ad} → {yeni}…")
        threading.Thread(
            target=self._arka_plan,
            args=(self._klasor_yeniden_adlandir_cek, kimlik, yeni),
            daemon=True,
        ).start()

    def _klasor_yeniden_adlandir_cek(self, kimlik: str, yeni: str):
        self.istemci.klasor_yeniden_adlandir(kimlik, yeni)
        # Klasör listesi + sayaçlar yenilenir ("yenile" sonucu)
        return ("yenile", f"Klasör adı değişti: {yeni}")

    def _klasor_adi_penceresi(
        self, ilk: str | None = None, baslik: str = "Yeni Klasör",
    ) -> str | None:
        """Klasör adı soran küçük pencere; İptal/boşsa None döner.

        `ilk` verilirse ad alanı öndoldurulur ve tamamı seçilidir
        (yeniden adlandırmada mevcut ad üzerine yazmak tek hareket).
        """
        pencere = tk.Toplevel(self)
        pencere.title(baslik)
        pencere.transient(self)
        self._pencere_simgesi(pencere)
        pencere.resizable(False, False)
        ttk.Label(
            pencere, text="Klasör adı:",
        ).grid(row=0, column=0, columnspan=2, padx=14, pady=(12, 4), sticky="w")
        ad_degisken = tk.StringVar(value=ilk or "")
        giris = ttk.Entry(pencere, textvariable=ad_degisken, width=34)
        giris.grid(row=1, column=0, columnspan=2, padx=14, pady=4)

        sonuc = {"ad": None}

        def kapat(tamam: bool):
            sonuc["ad"] = ad_degisken.get().strip() if tamam else None
            pencere.destroy()

        dugme_metni = "Değiştir" if ilk else "Oluştur"
        ttk.Button(pencere, text=dugme_metni, command=lambda: kapat(True)).grid(
            row=2, column=0, padx=14, pady=10, sticky="e"
        )
        ttk.Button(pencere, text="İptal", command=lambda: kapat(False)).grid(
            row=2, column=1, padx=8, pady=10, sticky="w"
        )
        giris.focus_set()
        if ilk:
            giris.selection_range(0, "end")
        giris.bind("<Return>", lambda olay: kapat(True))
        giris.bind("<Escape>", lambda olay: kapat(False))
        pencere.grab_set()
        pencere.wait_window()
        return sonuc["ad"]

    # ------------------------------------------------------- menü eylemleri

    def kopyala(self):
        """Mesaj bilgisini + gövdesini panoya kopyalar (Ctrl+C)."""
        if not self.secili:
            return
        m = self.secili
        metin = (
            f"Gönderen: {m.gonderen_ad or m.gonderen}\n"
            + (f"Kime: {m.alici}\n" if m.alici else "")
            + (f"Bilgi: {m.bilgi}\n" if m.bilgi else "")
            + f"Konu: {m.konu}\n"
            f"Tarih: {m.tarih}\n\n"
            f"{m.govde or m.onizleme}"
        )
        self.clipboard_clear()
        self.clipboard_append(metin)
        self.update()
        self.durum.set("Kopyalandı (mesaj bilgileri + gövde)")

    def farkli_kaydet(self):
        """Mesaji .eml (MIME) olarak diske kaydeder."""
        if not self.secili:
            return
        mesaj = self.secili
        temiz = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", mesaj.konu or "mesaj")
        hedef = dosya_secici.dosya_kaydet(
            "Mesajı farklı kaydet",
            baslangic=f"{temiz[:70]}.eml",
            varsayilan_uzanti=".eml",
            turler=[("E-posta (.eml)", "*.eml"), ("Tüm dosyalar", "*.*")],
        )
        if not hedef:
            return
        self.durum.set("MIME içeriği alınıyor…")
        threading.Thread(
            target=self._arka_plan, args=(self._eml_cek, mesaj, hedef), daemon=True
        ).start()

    def _eml_cek(self, mesaj, hedef):
        veri = self.istemci.mesaj_mime(mesaj.item_id)
        with open(hedef, "wb") as f:
            f.write(veri)
        return ("basarili", f"Kaydedildi: {hedef} ({len(veri)} bayt)")

    def bilgiler(self):
        """Mesaj özellik penceresi (Outlook 'Özellikler')."""
        if not self.secili:
            return
        m = self.secili
        arka, on = self._tema_renkleri()
        pencere = tk.Toplevel(self)
        pencere.title("Mesaj bilgileri")
        pencere.transient(self)
        self._pencere_simgesi(pencere)
        pencere.geometry("500x400")
        metin = tk.Text(
            pencere, wrap="word", padx=12, pady=12, relief="flat",
            bg=arka, fg=on, insertbackground=on, font=(YAZI_TIPİ, 10),
        )
        metin.pack(fill="both", expand=True)
        metin.tag_configure("baslik", font=(YAZI_TIPİ, 10, "bold"))
        satirlar = [
            ("Gönderen", m.gonderen_ad or m.gonderen),
            ("Gönderen adresi", m.gonderen),
            ("Kime", m.alici),
            ("Bilgi (Cc)", m.bilgi),
            ("Konu", m.konu),
            ("Tarih", m.tarih),
            ("Klasör", m.klasor),
            ("Okundu", "Evet" if m.okundu else "Hayır"),
            ("Ek sayısı", str(len(m.ekler))),
            ("Ek var mı", "Evet" if m.ek_var else "Hayır"),
            ("Mesaj kimliği", m.item_id),
        ]
        for etiket, deger in satirlar:
            metin.insert("end", f"{etiket}\n", "baslik")
            metin.insert("end", f"{deger or '—'}\n\n")
        metin.configure(state="disabled")
        ttk.Button(pencere, text="Kapat", command=pencere.destroy).pack(pady=10)

    def _yerel_kullanici(self) -> str:
        """Kendi kullanıcı adının yerel kısmını (yanıtla herkese'de elenir)."""
        hesap = self.ayarlar.aktif_hesap() or {}
        k = hesap.get("kullanici", "")
        return k.split("\\")[-1].split("@")[0].lower()

    def baglanti_bilgisi(self):
        hesap = self.ayarlar.aktif_hesap() or {}
        if hesap.get("tur") == "imap":
            self.durum.set(
                f"Hesap: {hesap.get('ad')} • E-posta: {hesap.get('kullanici')} • "
                f"IMAP: {hesap.get('gelen_sunucu')}:{hesap.get('gelen_port')} • "
                f"SMTP: {hesap.get('giden_sunucu')}:{hesap.get('giden_port')}"
            )
        else:
            self.durum.set(
                f"Sunucu: {hesap.get('sunucu')} • Kullanıcı: {hesap.get('kullanici')} "
                f"• Yöntem: {hesap.get('yontem')} • EWS: /EWS/Exchange.asmx"
            )

    def hakkinda(self):
        """Hakkında penceresini açar (logolu, sürüm bilgili)."""
        HakkindaPenceresi(self)

    def kaldir(self):
        """Uygulamayı kaldırır (kurulmuş kaldırıcı betiği çalıştırılır)."""
        betik = os.path.expanduser("~/.local/bin/postacim-kaldir")
        if not os.path.exists(betik):
            messagebox.showinfo(
                "Kaldırma",
                "Postacım kurulum betiğiyle kurulmamış görünüyor.\n\n"
                "Elle kaldırmak için:\n"
                "  rm -rf ~/.local/share/postacim "
                "~/.local/share/applications/postacim.desktop\n"
                "  rm -f ~/.local/bin/postacim\n"
                "  rm -rf ~/.config/postacim   # ayarlar (parola içerir)",
            )
            return
        if not messagebox.askyesno(
            "Postacım'ı Kaldır",
            "Postacım kaldırılsın mı?\n\n"
            "• Uygulama, menü girdisi ve simgeler silinir.\n"
            "• Hesaplarınız ve ayarlarınız SİLİNMEZ "
            "(silmek için: postacim-kaldir --ayarlar)\n\n"
            "Kaldırma, uygulamayı kapatmadan etkin olmaz; "
            "işlem bitince pencereyi kapatıp yeniden açabilirsiniz.",
        ):
            return
        try:
            subprocess.run([betik], check=False)
        except Exception as exc:
            messagebox.showerror("Kaldırma hatası", str(exc))
            return
        self.durum.set("Postacım kaldırıldı — pencereyi kapatabilirsiniz.")
        messagebox.showinfo(
            "Kaldırıldı",
            "Postacım kaldırıldı.\n\n"
            "Bu pencereyi kapatıp yeniden açarsanız uygulama yeniden "
            "kurulmuş gibi davranır; kaldırma tamamlanmış sayılır.",
        )

    def _kapat(self):
        self.ayarlar.kaydet()
        self.destroy()


class HakkindaPenceresi(tk.Toplevel):
    """Hakkında penceresi: logo, sürüm ve kısa bilgi."""

    def __init__(self, ana: "Postacim"):
        super().__init__(ana)
        self.ana = ana
        self.title(f"{UYGULAMA_ADI} hakkında")
        self.transient(ana)
        ana._pencere_simgesi(self)
        self.geometry("420x430")
        self.resizable(False, False)

        arka, on = ana._tema_renkleri()
        govde = tk.Frame(self, bg=arka)
        govde.pack(fill="both", expand=True)

        # Logo
        logo = ana.ikon.get("uygulama_128") or ana.ikon.get("uygulama")
        if logo is not None:
            resim = tk.Label(govde, image=logo, bg=arka, bd=0)
            resim.pack(pady=(22, 8))

        tk.Label(
            govde, text=UYGULAMA_ADI, bg=arka, fg=on,
            font=(YAZI_TIPİ, 16, "bold"),
        ).pack()
        tk.Label(
            govde, text=f"Sürüm {SURUM}", bg=arka, fg=on,
            font=(YAZI_TIPİ, 10),
        ).pack(pady=(2, 14))

        tk.Label(
            govde,
            text=(
                "E-posta ve takvim istemcisi\n"
                "Exchange (EWS) • IMAP/SMTP • CalDAV"
            ),
            bg=arka, fg=on, justify="center", font=(YAZI_TIPİ, 10),
        ).pack()

        ayrac = tk.Frame(govde, bg=arka, height=12)
        ayrac.pack()

        tk.Label(
            govde,
            text=(
                "Kurum Exchange hesapları EWS (NTLM) üzerinden;\n"
                "Gmail ve diğer IMAP hesapları IMAP/SMTP üzerinden\n"
                "okunur ve yazılır. Birden fazla hesap eklenebilir."
            ),
            bg=arka, fg=on, justify="center", font=(YAZI_TIPİ, 10),
        ).pack()

        ayrac2 = tk.Frame(govde, bg=arka, height=12)
        ayrac2.pack()

        tk.Label(
            govde, text="GPL-3.0 lisanslı • açık kaynak",
            bg=arka, fg=on, font=(YAZI_TIPİ, 9),
        ).pack()
        tk.Label(
            govde, text=PROJE_ADRESI, bg=arka, fg=on,
            font=(YAZI_TIPİ, 9),
        ).pack(pady=(2, 16))

        ttk.Button(govde, text="Kapat", command=self.destroy).pack(pady=(0, 16))

        self.after_idle(self._grab_al)

    def _grab_al(self, deneme=0):
        try:
            self.grab_set()
        except tk.TclError:
            if deneme < 20 and self.winfo_exists():
                self.after(50, lambda: self._grab_al(deneme + 1))


class HesapPenceresi(tk.Toplevel):
    """Hesap ekleme/düzenleme penceresi (Kurum EWS veya Gmail/IMAP).

    Gmail için hazır ayar vardır: IMAP `imap.gmail.com:993`,
    SMTP `smtp.gmail.com:465`; erişim uygulama parolası ile yapılır.
    """

    def __init__(self, ana: "Postacim", hesap: dict | None = None):
        super().__init__(ana)
        self.ana = ana
        self.hesap = dict(hesap) if hesap else None
        self.title("Hesap ekle" if hesap is None else "Hesap düzenle")
        self.transient(ana)
        ana._pencere_simgesi(self)
        self.geometry("470x560")
        self.resizable(False, False)

        self.tur_degisken = tk.StringVar(
            value=(self.hesap.get("tur") if self.hesap else "ews")
        )
        self.ad_var = tk.StringVar(
            value=(self.hesap.get("ad", "") if self.hesap else "")
        )
        # EWS alanları
        self.sunucu_var = tk.StringVar(
            value=(self.hesap.get("sunucu", "") if self.hesap else "")
        )
        # IMAP alanları — eposta_var aynı zamanda EWS'te "gönderen" adresi
        if self.hesap and self.hesap.get("tur") == "imap":
            eposta_baslangic = self.hesap.get("kullanici", "")
        elif self.hesap:
            eposta_baslangic = self.hesap.get("eposta", "")
        else:
            eposta_baslangic = ""
        self.eposta_var = tk.StringVar(value=eposta_baslangic)
        self.gelen_var = tk.StringVar(
            value=(self.hesap.get("gelen_sunucu", "imap.gmail.com")
                   if self.hesap else "imap.gmail.com")
        )
        self.gelen_port_var = tk.StringVar(
            value=str(self.hesap.get("gelen_port", 993)) if self.hesap else "993"
        )
        self.giden_var = tk.StringVar(
            value=(self.hesap.get("giden_sunucu", "smtp.gmail.com")
                   if self.hesap else "smtp.gmail.com")
        )
        self.giden_port_var = tk.StringVar(
            value=str(self.hesap.get("giden_port", 465)) if self.hesap else "465"
        )
        # Ortak: kullanıcı/e-posta + parola
        self.kullanici_var = tk.StringVar(
            value=(self.hesap.get("kullanici", "") if self.hesap else "")
        )
        self.parola_var = tk.StringVar(
            value=(self.hesap.get("parola", "") if self.hesap else "")
        )

        satir = 0
        ttk.Label(
            self, text="Hesap türü:", font=(YAZI_TIPİ, 10, "bold")
        ).grid(row=satir, column=0, padx=14, pady=(14, 2), sticky="w")
        tur_cerceve = ttk.Frame(self)
        tur_cerceve.grid(row=satir, column=1, columnspan=2, padx=8,
                         pady=(14, 2), sticky="w")
        durum = "disabled" if self.hesap else "normal"
        ttk.Radiobutton(
            tur_cerceve, text="Exchange (EWS)", value="ews",
            variable=self.tur_degisken, command=self._tur_goster,
            state=durum,
        ).pack(side="left")
        ttk.Radiobutton(
            tur_cerceve, text="Gmail veya IMAP", value="imap",
            variable=self.tur_degisken, command=self._tur_goster,
            state=durum,
        ).pack(side="left", padx=(12, 0))
        satir += 1

        ttk.Label(self, text="Hesap adı:").grid(
            row=satir, column=0, padx=14, sticky="w"
        )
        ttk.Entry(self, textvariable=self.ad_var, width=34).grid(
            row=satir, column=1, columnspan=2, padx=8, pady=4, sticky="we"
        )
        satir += 1

        # --- EWS alanları ---
        self.ews_cerceve = ttk.LabelFrame(self, text="Exchange sunucusu (EWS)", padding=8)
        self.ews_cerceve.grid(row=satir, column=0, columnspan=3,
                              padx=12, pady=6, sticky="we")
        ttk.Label(self.ews_cerceve, text="Sunucu:").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Entry(self.ews_cerceve, textvariable=self.sunucu_var, width=32).grid(
            row=0, column=1, padx=6, pady=3, sticky="we"
        )
        ttk.Label(self.ews_cerceve, text="Kullanıcı:").grid(
            row=1, column=0, sticky="w"
        )
        ttk.Entry(self.ews_cerceve, textvariable=self.kullanici_var,
                  width=32).grid(row=1, column=1, padx=6, pady=3, sticky="we")
        ttk.Label(self.ews_cerceve, text="Parola:").grid(
            row=2, column=0, sticky="w"
        )
        ttk.Entry(self.ews_cerceve, textvariable=self.parola_var, show="•",
                  width=32).grid(row=2, column=1, padx=6, pady=3, sticky="we")
        # Gönderen adresi (zorunlu): ilk kayıttan JSON'a yazılır, gönderme
        # penceresinde dropdown'dan seçilir
        ttk.Label(self.ews_cerceve, text="E-posta (gönderen):").grid(
            row=3, column=0, sticky="w"
        )
        ttk.Entry(self.ews_cerceve, textvariable=self.eposta_var,
                  width=32).grid(row=3, column=1, padx=6, pady=3, sticky="we")
        ttk.Label(
            self.ews_cerceve,
            text="Sunucu: örn. mail.kurum.gov.tr  •  Kullanıcı: KURUM\\kullanici"
                 "  •  Kimlik doğrulama: NTLM",
            foreground="#666666",
        ).grid(row=4, column=0, columnspan=2, sticky="w", pady=(4, 0))
        satir += 1

        # --- IMAP alanları ---
        self.imap_cerceve = ttk.LabelFrame(self, text="IMAP / SMTP", padding=8)
        self.imap_cerceve.grid(row=satir, column=0, columnspan=3,
                               padx=12, pady=6, sticky="we")
        ttk.Label(self.imap_cerceve, text="E-posta:").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Entry(self.imap_cerceve, textvariable=self.eposta_var,
                  width=32).grid(row=0, column=1, padx=6, pady=3, sticky="we")
        ttk.Label(self.imap_cerceve, text="Uygulama parolası:").grid(
            row=1, column=0, sticky="w"
        )
        ttk.Entry(self.imap_cerceve, textvariable=self.parola_var, show="•",
                  width=32).grid(row=1, column=1, padx=6, pady=3, sticky="we")
        ttk.Label(self.imap_cerceve, text="Gelen sunucu:").grid(
            row=2, column=0, sticky="w"
       )
        gel = ttk.Frame(self.imap_cerceve)
        gel.grid(row=2, column=1, padx=6, pady=3, sticky="we")
        ttk.Entry(gel, textvariable=self.gelen_var, width=24).pack(side="left")
        ttk.Label(gel, text=" Port:").pack(side="left")
        ttk.Entry(gel, textvariable=self.gelen_port_var, width=6).pack(
            side="left", padx=(4, 0)
        )
        ttk.Label(self.imap_cerceve, text="Giden sunucu:").grid(
            row=3, column=0, sticky="w"
        )
        gid = ttk.Frame(self.imap_cerceve)
        gid.grid(row=3, column=1, padx=6, pady=3, sticky="we")
        ttk.Entry(gid, textvariable=self.giden_var, width=24).pack(side="left")
        ttk.Label(gid, text=" Port:").pack(side="left")
        ttk.Entry(gid, textvariable=self.giden_port_var, width=6).pack(
            side="left", padx=(4, 0)
        )
        ttk.Button(
            self.imap_cerceve, text="Gmail'e ayarla", command=self._gmail_ayarla
        ).grid(row=4, column=0, columnspan=2, sticky="w", pady=(6, 0))
        satir += 1

        # Yardım metni (türe göre değişir)
        self.yardim_etiket = ttk.Label(self, text="", justify="left",
                                       foreground="#666666", wraplength=430)
        self.yardim_etiket.grid(row=satir, column=0, columnspan=3,
                                padx=14, pady=(2, 4), sticky="w")
        satir += 1

        dugmeler = ttk.Frame(self)
        dugmeler.grid(row=satir, column=0, columnspan=3, padx=12,
                      pady=12, sticky="we")
        ttk.Button(dugmeler, text="Kaydet", command=self._kaydet).pack(
            side="right"
        )
        ttk.Button(dugmeler, text="İptal", command=self.destroy).pack(
            side="right", padx=(0, 8)
        )

        self.columnconfigure(1, weight=1)
        self._tur_goster()

    # ------------------------------------------------------------------ yardım

    def _tur_goster(self):
        """Seçili türe göre alan çerçevelerini ve yardım metnini gösterir."""
        tur = self.tur_degisken.get()
        if tur == "ews":
            self.ews_cerceve.grid()
            self.imap_cerceve.grid_remove()
            self.yardim_etiket.configure(
                text=(
                    "Kurum Exchange: IMAP/SMTP dışarıdan kapalı olduğu için\n"
                    "EWS (Exchange Web Services) kullanılır."
                )
            )
        else:
            self.ews_cerceve.grid_remove()
            self.imap_cerceve.grid()
            self.yardim_etiket.configure(
                text=(
                    "Gmail: Google Hesabı → Güvenlik → 2 Adımlı Doğrulama\n"
                    "açıkken 16 haneli uygulama parolası oluşturun ve buraya\n"
                    "yazın. Gmail'de IMAP etkinleştirilmiş olmalıdır\n"
                    "(Ayarlar → Tüm Ayarlar → Yönlendirme ve POP/IMAP)."
                )
            )

    def _gmail_ayarla(self):
        """Gmail için hazır sunucu ayarlarını doldurur."""
        self.tur_degisken.set("imap")
        if not self.ad_var.get().strip():
            self.ad_var.set("Gmail")
        self.gelen_var.set("imap.gmail.com")
        self.gelen_port_var.set("993")
        self.giden_var.set("smtp.gmail.com")
        self.giden_port_var.set("465")
        self._tur_goster()

    # ------------------------------------------------------------------ kaydet

    def _kaydet(self):
        tur = self.tur_degisken.get()
        ad = self.ad_var.get().strip()
        parola = self.parola_var.get()
        if tur == "ews":
            kullanici = self.kullanici_var.get().strip()
            if not kullanici:
                messagebox.showwarning(
                    "Eksik alan",
                    "Kullanıcı adı girin (örn. KURUM\\kullanici).",
                    parent=self,
                )
                return
            sunucu = self.sunucu_var.get().strip()
            if not sunucu:
                messagebox.showwarning(
                    "Eksik alan",
                    "Exchange sunucu adresini girin (örn. mail.kurum.gov.tr).",
                    parent=self,
                )
                return
            eposta = self.eposta_var.get().strip()
            if not eposta or "@" not in eposta:
                messagebox.showwarning(
                    "Eksik alan",
                    "E-posta adresinizi girin (örn. ad.soyad@kurum.gov.tr). "
                    "Bu adres gönderme penceresinde gönderen olarak görünür.",
                    parent=self,
                )
                return
            if not ad:
                ad = "Exchange"
            alanlar = {
                "ad": ad,
                "tur": "ews",
                "sunucu": sunucu,
                "kullanici": kullanici,
                "parola": parola,
                "yontem": "ntlm",
                "eposta": eposta,
            }
        else:
            eposta = self.eposta_var.get().strip()
            if not eposta or "@" not in eposta:
                messagebox.showwarning(
                    "Eksik alan", "Geçerli bir e-posta adresi girin.", parent=self
                )
                return
            try:
                gelen_port = int(self.gelen_port_var.get().strip() or "993")
                giden_port = int(self.giden_port_var.get().strip() or "465")
            except ValueError:
                messagebox.showwarning(
                    "Hatalı port", "Port numaraları sayı olmalı.", parent=self
                )
                return
            if not ad:
                ad = "Gmail" if "gmail.com" in eposta.lower() else eposta
            alanlar = {
                "ad": ad,
                "tur": "imap",
                "kullanici": eposta,
                "parola": parola,
                "gelen_sunucu": self.gelen_var.get().strip() or "imap.gmail.com",
                "gelen_port": gelen_port,
                "giden_sunucu": self.giden_var.get().strip() or "smtp.gmail.com",
                "giden_port": giden_port,
                "guvenli": "ssl",
            }

        if self.hesap is None:
            # Yeni hesap ekle ve ona geç
            yeni = self.ana.ayarlar.hesap_ekle(alanlar)
            self.destroy()
            self.ana._menu_kur()
            self.ana._hesap_degistir(yeni["id"])
            return

        # Düzenleme
        hesap_id = self.hesap["id"]
        aktif_mi = hesap_id == self.ana.aktif_id
        self.ana.ayarlar.hesap_guncelle(hesap_id, alanlar)
        self.destroy()
        self.ana._menu_kur()
        if aktif_mi:
            # Kimlik değiştiyse yeniden bağlan
            self.ana._istemciler.pop(hesap_id, None)
            self.ana.istemci = None
            self.ana._agaci_yenile()
            self.ana.yenile()
        else:
            self.ana._agaci_yenile()

    def ac(self):
        """Pencereyi gösterir ve kapanmasını bekler."""
        self.wait_window()


def _temiz_dosya_adi(ad: str) -> str:
    """Ek adını güvenli tek dosya adına çevirir (yol ayırıcıları atılır)."""
    ad = os.path.basename((ad or "").replace("\\", "/"))
    ad = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", ad).strip(" .")
    return ad or "ek"


def _benzersiz_yol(dizin: str, ad: str) -> str:
    """Klasörde aynı ad varsa ' (1)', ' (2)' … ekleyerek çakışmayı önler."""
    ad = _temiz_dosya_adi(ad)
    kok, uzanti = os.path.splitext(ad)
    yol = os.path.join(dizin, ad)
    sayac = 1
    while os.path.exists(yol):
        yol = os.path.join(dizin, f"{kok} ({sayac}){uzanti}")
        sayac += 1
    return yol


def _kisi_kayitlari(metin: str) -> list:
    """'Ad <a@x>, b@y' → [('Ad', 'a@x'), ('', 'b@y')]"""
    sonuc = []
    for parca in re.split(r"[;,]", metin or ""):
        parca = parca.strip()
        if not parca:
            continue
        eslesme = re.match(r"^(.*?)\s*<([^<>]+)>\s*$", parca)
        if eslesme:
            sonuc.append((eslesme.group(1).strip(), eslesme.group(2).strip()))
        else:
            sonuc.append(("", parca))
    return sonuc


def _hesap_adresi(hesap: dict) -> str:
    """Hesabın e-posta adresi (IMAP: kullanici; EWS: eposta alanı)."""
    if hesap.get("tur") == "imap":
        return (hesap.get("kullanici") or "").strip()
    return (hesap.get("eposta") or "").strip()


class _AdTamamlama:
    """Kime/Bilgi alanında yazarken kişi önerir (Outlook tarzı otomatik tamamlama).

    Son yazılan parça (';' veya ','dan sonraki) **kurum dizininde** (GAL,
    EWS `ResolveNames`) filtrelenir — kurum e-postası olan tüm kişiler
    arasından eşleşmeler gösterilir. Kayıtlı kişiler yalnızca kurum dizini
    kullanılamadığında yedek olarak önerilir. Seçilen kişi
    "Ad Soyad <adres>; " biçiminde eklenir.
    """

    MIN_PARCA = 2
    BEKLEME = 200  # ms — yazma durunca kurum dizinine sorulur

    def __init__(self, ana: "Postacim", ust: tk.Toplevel, giris: ttk.Entry):
        self.ana = ana
        self.ust = ust
        self.giris = giris
        self._zamanlayici = None
        self._istek_no = 0
        self._cevap = None  # (istek_no, [(ad, eposta)])
        self._sonuc = []  # ekrandaki öneriler
        self._sonuc_parca = ""  # önerilerin ait olduğu parça (bayat kabulü önler)
        self._kutu = None
        self._liste = None
        giris.bind("<KeyRelease>", self._yazildi)
        giris.bind("<Down>", self._asagi)
        giris.bind("<Up>", self._yukari)
        giris.bind("<Return>", self._enter)
        giris.bind("<Tab>", self._tab)
        giris.bind("<Escape>", self._escape)
        giris.bind("<FocusOut>", self._focus_out)

    # ----------------------------------------------------------- parça çözümü

    def _parca_aralik(self) -> tuple:
        """İmleçteki parçanın sınırları → (metin, baş, son)."""
        metin = self.giris.get()
        imlec = int(self.giris.index(tk.INSERT))
        bas = max(metin.rfind(";", 0, imlec), metin.rfind(",", 0, imlec)) + 1
        son = len(metin)
        for ayirici in (";", ","):
            i = metin.find(ayirici, imlec)
            if i != -1:
                son = min(son, i)
        return metin, bas, son

    def _parca(self) -> str:
        metin, bas, son = self._parca_aralik()
        return metin[bas:son].strip()

    # --------------------------------------------------------------- öneriler

    def _yazildi(self, olay):
        if olay.keysym in (
            "Up", "Down", "Return", "Escape", "Tab",
            "Shift_L", "Shift_R", "Control_L", "Control_R",
            "Alt_L", "Alt_R", "Caps_Lock", "Multi_key", "Hyper_L", "Hyper_R",
        ):
            return
        self._oneri()

    def _oneri(self):
        parca = self._parca()
        if len(parca) < self.MIN_PARCA:
            self._sonuc = []
            self._sonuc_parca = ""
            self.kapat()
            return
        if self.ana.istemci is None or self.ana.cozum_yok:
            # Kurum dizini kullanılamıyorsa yedek: kayıtlı kişiler
            self._sonuc = self.ana.kisiler.ara(parca)
            self._sonuc_parca = parca
            self._goster()
            return
        # Kurum e-postası olan tüm kişiler arasından filtreleme: yazma
        # durunca dizine sorulur; mevcut liste sonuç gelene kadar kalır.
        if self._zamanlayici is not None:
            self.ust.after_cancel(self._zamanlayici)
        self._zamanlayici = self.ust.after(self.BEKLEME, self._uzak_ara, parca)

    def _uzak_ara(self, parca: str):
        self._zamanlayici = None
        try:
            if self.ana.istemci is None or self.ana.cozum_yok:
                return
            if self._parca() != parca:
                return  # yazı değişti
        except tk.TclError:
            return  # pencere kapanmış
        self._istek_no += 1
        no = self._istek_no
        threading.Thread(target=self._arka, args=(parca, no), daemon=True).start()
        self.ust.after(150, self._sonuc_yokla, no, 0)

    def _arka(self, parca: str, no: int):
        """Arka planda kurum dizininde arar; Tk'ye dokunmaz."""
        try:
            sonuc = self.ana.istemci.cozumle(parca)
            self._cevap = (no, sonuc, False)
        except Exception:
            self._cevap = (no, [], True)

    def _sonuc_yokla(self, no: int, deneme: int):
        if self._istek_no != no:
            return  # daha yeni bir arama başladı
        if self._cevap is None or self._cevap[0] != no:
            if deneme < 40:  # ≈6 sn
                self.ust.after(150, self._sonuc_yokla, no, deneme + 1)
            return
        _, uzak, hata = self._cevap
        self._cevap = None
        if hata and not self.ana.cozum_yok:
            self.ana.cozum_yok = True
            self.ana.durum.set(
                "Kişi çözümleme kullanılamıyor (sunucu desteklemiyor) — "
                "yalnızca kayıtlı kişiler öneriliyor"
            )
        try:
            parca = self._parca()
        except tk.TclError:
            return  # pencere kapanmış
        if len(parca) < self.MIN_PARCA:
            return
        self._sonuc = list(uzak)  # yalnız kurum dizini eşleşmeleri
        self._sonuc_parca = parca
        self._goster()

    # ------------------------------------------------------------- açılır liste

    def _goster(self):
        if not self._sonuc:
            self.kapat()
            return
        try:
            if self._kutu is None:
                self._kutu = tk.Toplevel(self.ust)
                self._kutu.wm_overrideredirect(True)
                arka, on = self.ana._tema_renkleri()
                vurgu = self.ana._vurgu_rengi()
                self._liste = tk.Listbox(
                    self._kutu, height=min(8, len(self._sonuc)),
                    bg=arka, fg=on, selectbackground=vurgu,
                    selectforeground="#ffffff", activestyle="none",
                    relief="solid", highlightthickness=1,
                    highlightbackground="#a0a0a0", exportselection=False,
                    font=(YAZI_TIPİ, 9),
                )
                self._liste.pack(fill="both", expand=True)
                self._liste.bind("<Button-1>", self._tikla)
            else:
                self._liste.configure(height=min(8, len(self._sonuc)))
            self._liste.delete(0, "end")
            for ad, eposta in self._sonuc:
                self._liste.insert("end", f"{ad}  <{eposta}>")
            self._liste.selection_clear(0, "end")
            self._liste.selection_set(0)
            self._liste.activate(0)
            self._kutu.update_idletasks()
            x = self.giris.winfo_rootx()
            y = self.giris.winfo_rooty() + self.giris.winfo_height() + 2
            self._kutu.geometry(
                f"{self.giris.winfo_width()}x{self._kutu.winfo_reqheight()}+{x}+{y}"
            )
            self._kutu.deiconify()
            self._kutu.lift()
        except tk.TclError:
            self._kutu = None
            self._liste = None

    def kapat(self):
        if self._kutu is not None:
            try:
                self._kutu.destroy()
            except tk.TclError:
                pass
            self._kutu = None
            self._liste = None

    def _tamamla(self, indeks: int):
        if not (0 <= indeks < len(self._sonuc)):
            return
        if self._sonuc_parca != self._parca():
            return  # öneriler başka bir parçaya ait (bayat)
        ad, eposta = self._sonuc[indeks]
        metin, bas, son = self._parca_aralik()
        yeni = (" " if bas > 0 else "") + f"{ad} <{eposta}>; "
        tam = metin[:bas] + yeni + metin[son:]
        self.giris.delete(0, "end")
        self.giris.insert(0, tam)
        self.giris.icursor(bas + len(yeni))
        self.ana.kisiler.ekle(ad, eposta)
        self.kapat()

    # -------------------------------------------------------------- tuş/tuşlar

    def _secili(self) -> int:
        secim = self._liste.curselection() if self._liste is not None else ()
        return secim[0] if secim else 0

    def _adim(self, delta: int):
        yeni = self._secili() + delta
        if 0 <= yeni < self._liste.size():
            self._liste.selection_clear(0, "end")
            self._liste.selection_set(yeni)
            self._liste.activate(yeni)
            self._liste.see(yeni)

    def _asagi(self, _olay):
        if self._kutu is not None and self._sonuc:
            self._adim(1)
            return "break"

    def _yukari(self, _olay):
        if self._kutu is not None and self._sonuc:
            self._adim(-1)
            return "break"

    def _enter(self, _olay):
        if self._kutu is not None and self._sonuc:
            self._tamamla(self._secili())
            return "break"

    def _tab(self, _olay):
        if self._kutu is not None and self._sonuc:
            self._tamamla(self._secili())
            return "break"

    def _escape(self, _olay):
        if self._kutu is not None:
            self.kapat()
            return "break"

    def _tikla(self, olay):
        try:
            self._tamamla(self._liste.nearest(olay.y))
        except tk.TclError:
            pass
        return "break"

    def _focus_out(self, _olay):
        self.ust.after(200, self._focus_kontrol)

    def _focus_kontrol(self):
        try:
            odak = self.ust.focus_get()
        except (tk.TclError, KeyError):
            # messagebox açıkken focus_get() "__tk__messagebox" döndürür ve
            # nametowidget KeyError fırlatır; pencere/kutu kapanmışsa TclError.
            return
        if odak is not self.giris and odak is not self._liste:
            self.kapat()


class YeniPostaPenceresi(tk.Toplevel):
    """Yeni e-posta / yanıtla / ilet penceresi."""

    def __init__(self, ana: Postacim):
        super().__init__(ana)
        self.ana = ana
        hesap = ana.ayarlar.aktif_hesap() or {}
        self.title(
            "Yeni e-posta — "
            + (hesap.get("ad") or hesap.get("kullanici") or "")
        )
        self.geometry("720x600")
        self.transient(ana)
        ana._pencere_simgesi(self)
        self.ekler: list[tuple[str, bytes, str]] = []

        self.kime_var = tk.StringVar()
        self.konu_var = tk.StringVar()
        self.cc_var = tk.StringVar()
        # Klasik Tk widget'ları temadan renk alır (koyu temada beyaz kutu kalmasın)
        arka, on = self.ana._tema_renkleri()
        vurgu = self.ana._vurgu_rengi()
        self.govde = tk.Text(
            self, wrap="word", padx=8, pady=8,
            bg=arka, fg=on, insertbackground=on,
            selectbackground=vurgu, selectforeground="#ffffff", relief="flat",
            font=(YAZI_TIPİ, 10),
        )
        self.ek_listesi = tk.Listbox(
            self, height=4,
            bg=arka, fg=on, selectbackground=vurgu, selectforeground="#ffffff",
            relief="flat", highlightthickness=1, highlightbackground=arka,
        )

        # Gönderen adresi: kayıtlı hesapların e-postaları dropdown'dan seçilebilir
        adresler = []
        for h in ana.ayarlar.hesaplar():
            a = _hesap_adresi(h)
            if "@" in a and a not in adresler:
                adresler.append(a)
        gonderen = _hesap_adresi(hesap)
        if gonderen and gonderen not in adresler:
            adresler.insert(0, gonderen)
        ttk.Label(self, text="Gönderen:").grid(
            row=0, column=0, padx=10, pady=(10, 4), sticky="w"
        )
        # readonly: yalnız listeden seçim yapılabilir (serbest yazılamaz)
        self.gonderen_combo = ttk.Combobox(
            self, values=adresler, state="readonly", width=42
        )
        self.gonderen_combo.grid(
            row=0, column=1, columnspan=2, padx=6, pady=(10, 4), sticky="we"
        )
        self.gonderen_combo.set(gonderen)

        ttk.Label(self, text="Kime:").grid(row=1, column=0, padx=10, pady=(0, 4), sticky="w")
        self.kime_giris = ttk.Entry(self, textvariable=self.kime_var)
        self.kime_giris.grid(row=1, column=1, columnspan=2, padx=6, pady=(0, 4), sticky="we")
        ttk.Label(self, text="Konu:").grid(row=2, column=0, padx=10, sticky="w")
        ttk.Entry(self, textvariable=self.konu_var).grid(
            row=2, column=1, columnspan=2, padx=6, sticky="we"
        )
        ttk.Label(self, text="Bilgi:").grid(row=3, column=0, padx=10, sticky="w")
        self.cc_giris = ttk.Entry(self, textvariable=self.cc_var)
        self.cc_giris.grid(row=3, column=1, columnspan=2, padx=6, sticky="we")
        # Outlook tarzı kişi tamamlama: yazarken kurum dizininde arar
        self._kime_tamamla = _AdTamamlama(ana, self, self.kime_giris)
        self._cc_tamamla = _AdTamamlama(ana, self, self.cc_giris)
        self.govde.grid(row=4, column=0, columnspan=3, padx=10, pady=6, sticky="nsew")
        self.ek_listesi.grid(row=5, column=0, columnspan=3, padx=10, sticky="we")

        # Dugmeler ayri cubukta: boylece 0. sutun etiketlerin genisliginde kalir.
        dugmeler = ttk.Frame(self)
        dugmeler.grid(row=6, column=0, columnspan=3, padx=8, pady=(2, 10), sticky="we")
        ttk.Button(
            dugmeler, text="Ek ekle…", image=self.ana.ikon["ek"], compound="left",
            command=self.ek_ekle,
        ).pack(side="left")
        ttk.Button(
            dugmeler, text="Gönder", image=self.ana.ikon["gonder"], compound="left",
            command=self.gonder,
        ).pack(side="right")
        ttk.Button(
            dugmeler, text="Taslak kaydet", image=self.ana.ikon["taslak"], compound="left",
            command=self.taslak,
        ).pack(side="right", padx=(0, 6))

        self.columnconfigure(1, weight=1)
        self.rowconfigure(4, weight=1)

    def ac(self, yanit: Mesaj | None = None, ilet: Mesaj | None = None,
           herkese: bool = False):
        if yanit is not None:
            self.konu_var.set("RE: " + (yanit.konu or ""))
            kime = yanit.gonderen
            if herkese:
                # Kime: orijinal gönderen + tüm alıcılar (kendim hariç)
                # Bilgi: orijinal Cc (kendim hariç)
                yerel = self.ana._yerel_kullanici()

                def ben_mi(adres: str) -> bool:
                    return adres.split("@")[0].strip().lower() == yerel

                kisiler = [yanit.gonderen] + [
                    a.strip() for a in (yanit.alici or "").split(",")
                    if a.strip() and not ben_mi(a.strip())
                ]
                kime = ", ".join(dict.fromkeys(a for a in kisiler if a))
                self.cc_var.set(
                    ", ".join(
                        a.strip() for a in (yanit.bilgi or "").split(",")
                        if a.strip() and not ben_mi(a.strip())
                    )
                )
            self.kime_var.set(kime)
            self.govde.insert(
                "1.0",
                f"\n\n----- Orijinal mesaj -----\nGönderen: {yanit.gonderen_ad or yanit.gonderen}\n"
                f"Tarih: {yanit.tarih}\nKonu: {yanit.konu}\n\n{yanit.govde or yanit.onizleme}\n",
            )
        elif ilet is not None:
            self.konu_var.set("FW: " + (ilet.konu or ""))
            self.govde.insert(
                "1.0",
                f"\n\n----- İletilen mesaj -----\nGönderen: {ilet.gonderen_ad or ilet.gonderen}\n"
                f"Tarih: {ilet.tarih}\nKonu: {ilet.konu}\n\n{ilet.govde or ilet.onizleme}\n",
            )
        self.deiconify()
        self.focus_set()

    def ek_ekle(self):
        yollar = dosya_secici.dosya_ac_coklu(
            "Ek seç", turler=dosya_secici.EK_TURLERI
        )
        eklenen = 0
        for yol in yollar:
            try:
                with open(yol, "rb") as f:
                    veri = f.read()
            except OSError as hata:
                messagebox.showerror("Ek eklenemedi", f"{yol}\n{hata}")
                continue
            self.ekler.append(
                (os.path.basename(yol), veri, "application/octet-stream")
            )
            self.ek_listesi.insert("end", os.path.basename(yol))
            eklenen += 1
        if eklenen:
            self.ana.durum.set(f"{eklenen} ek eklendi")

    def gonder(self):
        kime = self.kime_var.get().strip()
        if not kime:
            messagebox.showwarning("Eksik alan", "Kime alanı boş.")
            return
        cc = self.cc_var.get().strip()
        gonderen = self.gonderen_combo.get().strip()
        # Gönderilen kişiler deftere yazılır (sonraki yazmalarda anında öneri)
        for ad, eposta in _kisi_kayitlari(kime) + _kisi_kayitlari(cc):
            self.ana.kisiler.ekle(ad, eposta)
        self.ana.durum.set("Gönderiliyor…")
        govde = self.govde.get("1.0", "end")
        konu = self.konu_var.get()
        threading.Thread(
            target=self.ana._arka_plan,
            args=(self._gonder_cek, kime, cc, konu, govde, list(self.ekler), gonderen),
            daemon=True,
        ).start()
        self.destroy()

    def _gonder_cek(self, kime, cc, konu, govde, ekler, gonderen=""):
        # Seçilen gönderen adresi hangi hesabın ise gönderim o hesapla yapılır
        istemci = self.ana._istemci_for_adres(gonderen)
        istemci.gonder(kime, konu, govde, ekler, cc=cc)
        return ("basarili", "E-posta gönderildi.")

    def taslak(self):
        kime = self.kime_var.get().strip()
        if not kime:
            messagebox.showwarning("Eksik alan", "Kime alanı boş.")
            return
        self.ana.durum.set("Taslak kaydediliyor…")
        threading.Thread(
            target=self.ana._arka_plan,
            args=(self._taslak_cek, kime, self.konu_var.get(), self.govde.get("1.0", "end")),
            daemon=True,
        ).start()

    def _taslak_cek(self, kime, konu, govde):
        self.ana.istemci.taslağa_kaydet(kime, konu, govde)
        return ("basarili", "Taslak kaydedildi.")


class RandevuPenceresi(tk.Toplevel):
    """Yeni randevu oluşturma / mevcut randevuyu düzenleme penceresi."""

    def __init__(
        self,
        ana: Postacim,
        randevu: Randevu | None = None,
        baslangic_saat: int | None = None,
        gun: date | None = None,
    ):
        super().__init__(ana)
        self.ana = ana
        self.randevu = randevu
        self.title("Randevu Düzenle" if randevu else "Yeni Randevu")
        self.geometry("460x600")
        self.resizable(False, False)
        self.transient(ana)
        ana._pencere_simgesi(self)
        # grab_set burada yapılmaz: pencere henüz haritalanmadan grab
        # "window not viewable" hatası verir ve __init__ yarıda kesilip
        # boş pencere kalır. Gövde kurulduktan sonra _grab_al denenir.

        gun = gun or date.today()

        # Mevcut randevudan doldur, değilse verilen saatten
        if randevu is not None:
            bas = iso_yerel(randevu.baslangic) or datetime.combine(gun, datetime.min.time())
            bit = iso_yerel(randevu.bitis) or (bas + timedelta(hours=1))
            bas_baslik = randevu.baslik if randevu.baslik != "(başlıksız)" else ""
            konum = randevu.konum
            aciklama = randevu.aciklama
            tum_gun = randevu.tum_gun
        else:
            saat = baslangic_saat if baslangic_saat is not None else 9
            bas = datetime.combine(gun, datetime.min.time()) + timedelta(hours=saat)
            bit = bas + timedelta(hours=1)
            bas_baslik = ""
            konum = ""
            aciklama = ""
            tum_gun = False

        govde = ttk.Frame(self, padding=12)
        govde.pack(fill="both", expand=True)

        # Başlık
        ttk.Label(govde, text="Başlık:").grid(row=0, column=0, sticky="w", pady=4)
        self.baslik_var = tk.StringVar(value=bas_baslik)
        ttk.Entry(govde, textvariable=self.baslik_var, width=42).grid(
            row=0, column=1, columnspan=3, sticky="ew", pady=4
        )

        # Takvim hesabı (kaynak) — birden çok CalDAV hesabı olabilir
        self._kaynaklar = ana._takvim_kaynaklari()
        etiketler = []
        for tur, veri in self._kaynaklar:
            ad = veri.get("ad") or veri.get("url") or tur
            etiketler.append(f"{ad} ({'CalDAV' if tur == 'caldav' else 'EWS'})")
        ttk.Label(govde, text="Takvim:").grid(row=1, column=0, sticky="w", pady=4)
        self.kaynak_var = tk.StringVar()
        self.kaynak_combo = ttk.Combobox(
            govde, textvariable=self.kaynak_var, width=38,
            state="readonly", values=etiketler,
        )
        self.kaynak_combo.grid(row=1, column=1, columnspan=3, sticky="ew", pady=4)
        if etiketler:
            varsayilan = 0
            if randevu is not None:
                kaynak_id = getattr(randevu, "kaynak_id", "")
                for i, (tur, veri) in enumerate(self._kaynaklar):
                    if kaynak_id and veri.get("id") == kaynak_id:
                        varsayilan = i
                        break
            self.kaynak_var.set(etiketler[varsayilan])

        # Tüm gün
        self.tum_gun_var = tk.BooleanVar(value=tum_gun)
        ttk.Checkbutton(
            govde, text="Tüm gün", variable=self.tum_gun_var,
            command=self._tum_gun_degisti,
        ).grid(row=2, column=1, sticky="w", pady=4)

        # Tarih
        ttk.Label(govde, text="Başlangıç:").grid(row=3, column=0, sticky="w", pady=4)
        self.bas_tarih = tk.StringVar(value=bas.strftime("%d.%m.%Y"))
        self.bas_saat = tk.StringVar(value=bas.strftime("%H:%M"))
        ttk.Entry(govde, textvariable=self.bas_tarih, width=11).grid(
            row=3, column=1, sticky="w", pady=4, padx=(0, 4)
        )
        self.saat_1 = ttk.Combobox(
            govde, textvariable=self.bas_saat, width=5, state="readonly",
            values=[f"{h:02d}:{m:02d}" for h in range(24) for m in (0, 15, 30, 45)],
        )
        self.saat_1.grid(row=3, column=2, sticky="w", pady=4)

        ttk.Label(govde, text="Bitiş:").grid(row=4, column=0, sticky="w", pady=4)
        self.bit_tarih = tk.StringVar(value=bit.strftime("%d.%m.%Y"))
        self.bit_saat = tk.StringVar(value=bit.strftime("%H:%M"))
        ttk.Entry(govde, textvariable=self.bit_tarih, width=11).grid(
            row=4, column=1, sticky="w", pady=4, padx=(0, 4)
        )
        self.saat_2 = ttk.Combobox(
            govde, textvariable=self.bit_saat, width=5, state="readonly",
            values=[f"{h:02d}:{m:02d}" for h in range(24) for m in (0, 15, 30, 45)],
        )
        self.saat_2.grid(row=4, column=2, sticky="w", pady=4)

        # Konum
        ttk.Label(govde, text="Konum:").grid(row=5, column=0, sticky="w", pady=4)
        self.konum_var = tk.StringVar(value=konum)
        ttk.Entry(govde, textvariable=self.konum_var, width=42).grid(
            row=5, column=1, columnspan=3, sticky="ew", pady=4
        )

        # Açıklama
        ttk.Label(govde, text="Açıklama:").grid(row=6, column=0, sticky="nw", pady=4)
        self.aciklama = tk.Text(govde, width=40, height=8, wrap="word")
        self.aciklama.grid(row=6, column=1, columnspan=3, sticky="ew", pady=4)
        self.aciklama.insert("1.0", aciklama)

        # Tekrarlama
        self.TEKRAR_SECENEKLERI = (
            "Tek seferlik", "Her gün", "Her hafta", "Her ay", "Her yıl",
        )
        mevcut_kural = getattr(randevu, "rrule", "") if randevu is not None else ""
        ttk.Label(govde, text="Tekrar:").grid(row=7, column=0, sticky="w", pady=4)
        self.tekrar_var = tk.StringVar(value=self._tekrar_seceneği(mevcut_kural))
        self.tekrar_combo = ttk.Combobox(
            govde, textvariable=self.tekrar_var, width=14, state="readonly",
            values=list(self.TEKRAR_SECENEKLERI),
        )
        self.tekrar_combo.grid(row=7, column=1, sticky="w", pady=4, padx=(0, 4))
        self.tekrar_combo.bind("<<ComboboxSelected>>", lambda e: self._tekrar_degisti())
        ttk.Label(govde, text="kaç kez:").grid(row=7, column=2, sticky="e", pady=4)
        self.tekrar_adet = tk.StringVar(value=self._tekrar_adeti(mevcut_kural))
        ttk.Entry(govde, textvariable=self.tekrar_adet, width=6).grid(
            row=7, column=3, sticky="w", pady=4
        )
        # Kullanıcı seçimi değiştirmezse eski kural aynen korunur
        self._ilk_tekrar_sec = self.tekrar_var.get()
        self._ilk_tekrar_adet = self.tekrar_adet.get().strip()
        self._ilk_kural = mevcut_kural
        self.tekrar_ozet = ttk.Label(govde, text="", foreground="#666666")
        self.tekrar_ozet.grid(row=8, column=0, columnspan=4, sticky="w")
        if mevcut_kural:
            ttk.Label(
                govde,
                text="Not: Bu randevu tekrarlı — değişiklikler tüm tekrarlara uygulanır.",
                foreground="#a06000",
            ).grid(row=9, column=0, columnspan=4, sticky="w")

        govde.columnconfigure(1, weight=1)

        # Düğmeler
        dugmeler = ttk.Frame(govde)
        dugmeler.grid(row=10, column=0, columnspan=4, sticky="ew", pady=(12, 0))
        ttk.Button(dugmeler, text="Kaydet", command=self._kaydet).pack(
            side="right", padx=(6, 0)
        )
        ttk.Button(dugmeler, text="İptal", command=self.destroy).pack(side="right")
        if randevu is not None:
            ttk.Button(
                dugmeler, text="Sil", command=self._sil
            ).pack(side="left")
            # Randevu tamamlandı: işaretle/kaldır (arka planda çizim yenilenir)
            self.tamamlandi_dugme = ttk.Button(
                dugmeler,
                text="İşareti kaldır" if randevu.tamamlandi else "Randevu tamamlandı",
                image=self.ana.ikon["tamamlandi"], compound="left",
                command=self._tamamlandi_degistir,
            )
            self.tamamlandi_dugme.pack(side="left", padx=(6, 0))

        self._tum_gun_degisti()
        self._tekrar_degisti()
        # Pencere haritalanana dek grab alınamaz ("window not viewable");
        # idle'da dene, olmazsa kısa aralıklarla tekrar dene.
        self.after_idle(self._grab_al)

    def _grab_al(self, deneme=0):
        try:
            self.grab_set()
        except tk.TclError:
            if deneme < 20 and self.winfo_exists():
                self.after(50, lambda: self._grab_al(deneme + 1))

    def _tamamlandi_degistir(self):
        """Düzenle penceresinde tamamlandı işaretini değiştirir."""
        if self.randevu is None:
            return
        self.ana._randevu_tamamla(self.randevu)
        self.tamamlandi_dugme.configure(
            text="İşareti kaldır" if self.randevu.tamamlandi
            else "Randevu tamamlandı"
        )

    def _tum_gun_degisti(self):
        durum = "disabled" if self.tum_gun_var.get() else "readonly"
        self.saat_1.configure(state=durum)
        self.saat_2.configure(state=durum)

    # ---- tekrarlama ------------------------------------------------------

    @staticmethod
    def _tekrar_seceneği(rrule: str) -> str:
        """RRULE dizesinden seçenek adı ('Her hafta'…)."""
        if not rrule:
            return "Tek seferlik"
        kural = tekrar.kural_ayikla(rrule)
        frekans = str(kural.get("FREQ", "")).upper()
        return {
            "DAILY": "Her gün", "WEEKLY": "Her hafta",
            "MONTHLY": "Her ay", "YEARLY": "Her yıl",
        }.get(frekans, "Tek seferlik")

    @staticmethod
    def _tekrar_adeti(rrule: str) -> str:
        """RRULE dizesinden tekrar sayısı (yoksa boş)."""
        if not rrule:
            return ""
        kural = tekrar.kural_ayikla(rrule)
        adet = kural.get("COUNT", "")
        return str(adet) if adet else ""

    def _tekrar_kural(self, bas: datetime | None = None) -> str:
        """Seçime göre RRULE dizesi üretir (boşsa tekrarsız)."""
        secim = self.tekrar_var.get()
        adet = 0
        try:
            adet = int(self.tekrar_adet.get().strip() or 0)
        except ValueError:
            adet = 0
        gun = bas.weekday() if bas is not None else 0
        if secim == "Her gün":
            return tekrar.kural_olustur("DAILY", adet=adet)
        if secim == "Her hafta":
            return tekrar.kural_olustur("WEEKLY", adet=adet, gunler=[gun])
        if secim == "Her ay":
            return tekrar.kural_olustur("MONTHLY", adet=adet)
        if secim == "Her yıl":
            return tekrar.kural_olustur("YEARLY", adet=adet)
        return ""

    def _tekrar_degisti(self):
        """Tekrar seçimi değişince özet metni tazeler."""
        if self.tekrar_var.get() == "Tek seferlik":
            self.tekrar_ozet.configure(text="")
            return
        bas = self._tarih_saati_coz(
            self.bas_tarih.get(),
            "00:00" if self.tum_gun_var.get() else self.bas_saat.get(),
        )
        kural = self._tekrar_kural(bas)
        ozet = tekrar.kural_ozeti(tekrar.kural_ayikla(kural))
        self.tekrar_ozet.configure(text=ozet)

    def _tarih_saati_coz(self, tarih_metni: str, saat_metni: str) -> datetime | None:
        for biçim in ("%d.%m.%Y", "%Y-%m-%d", "%d/%m/%Y"):
            try:
                gun = datetime.strptime(tarih_metni.strip(), biçim).date()
                break
            except ValueError:
                gun = None
        if gun is None:
            return None
        try:
            sa, dk = (int(x) for x in saat_metni.strip().split(":"))
        except ValueError:
            sa, dk = 9, 0
        return datetime.combine(gun, datetime.min.time()) + timedelta(hours=sa, minutes=dk)

    def _kaydet(self):
        baslik = self.baslik_var.get().strip()
        if not baslik:
            messagebox.showwarning("Eksik alan", "Başlık boş olamaz.", parent=self)
            return
        tum_gun = self.tum_gun_var.get()
        bas = self._tarih_saati_coz(
            self.bas_tarih.get(),
            "00:00" if tum_gun else self.bas_saat.get(),
        )
        bit = self._tarih_saati_coz(
            self.bit_tarih.get(),
            "23:59" if tum_gun else self.bit_saat.get(),
        )
        if bas is None or bit is None:
            messagebox.showwarning("Geçersiz tarih", "Tarih biçimini gg.aa.yyyy yazın.", parent=self)
            return
        if bit <= bas:
            bit = bas + (timedelta(days=1) if tum_gun else timedelta(hours=1))
        konum = self.konum_var.get().strip()
        aciklama = self.aciklama.get("1.0", "end").strip()

        # Hedef kaynak (Tk değişkeni arka plan iş parçacığında okunamaz)
        kaynak = None
        if self._kaynaklar:
            secim = self.kaynak_combo.current()
            if 0 <= secim < len(self._kaynaklar):
                kaynak = self._kaynaklar[secim]

        # Tekrarlama kuralı (kullanıcı değiştirmediyse eskisi korunur)
        if (
            self.tekrar_var.get() == self._ilk_tekrar_sec
            and self.tekrar_adet.get().strip() == self._ilk_tekrar_adet
        ):
            kural = self._ilk_kural
        else:
            kural = self._tekrar_kural(bas)

        if self.randevu is not None:
            r = self.randevu
            # Tekrar kopyası düzenleniyorsa: ana kaydın TARİHİ korunur
            # (aksi halde seri kayar/kayıplar), yalnız saat değişir.
            if getattr(r, "occurrence_id", ""):
                ana_kayit = next(
                    (
                        x for x in self.ana.randevular
                        if x.item_id == r.item_id and not getattr(x, "occurrence_id", "")
                    ),
                    None,
                )
                ana_bas = iso_yerel(ana_kayit.baslangic) if ana_kayit else None
                if ana_bas is not None:
                    sure = bit - bas
                    bas = datetime.combine(ana_bas.date(), bas.time())
                    bit = bas + sure
            r.baslik = baslik
            r.baslangic = _iso_utc_yerel(bas)
            r.bitis = _iso_utc_yerel(bit)
            r.konum = konum
            r.aciklama = aciklama
            r.tum_gun = tum_gun
            r.rrule = kural
            islev = ("guncelle", r, kaynak)
        else:
            islev = ("ekle", baslik, bas, bit, konum, aciklama, tum_gun, kaynak, kural)

        self.ana.durum.set("Randevu kaydediliyor…")
        threading.Thread(
            target=self.ana._arka_plan,
            args=(self._kaydet_cek, islev),
            daemon=True,
        ).start()
        self.destroy()

    def _kaydet_cek(self, islev):
        # CalDAV kayıtları RandevuKaydi (url/etag); EWS Randevu (item_id)
        kaynaklar = self.ana._takvim_kaynaklari()
        if not kaynaklar:
            raise EwsHata("Bağlı takvim hesabı yok.")
        islem = islev[0]
        # "ekle"  : (ekle, baslik, bas, bit, konum, aciklama, tum_gun, kaynak, kural)
        # "guncelle": (guncelle, randevu, kaynak)
        # NOT: seçilen kaynak "ekle"de 7., "guncelle"de 2. sırada;
        # yanlış sıra okunursa datetime nesnesi kaynak sanılır.
        if islem == "ekle":
            _, baslik, bas, bit, konum, aciklama, tum_gun, secilen, kural = islev
        else:
            secilen = islev[2] if len(islev) > 2 else None
        # Düzenlenen kaynak: url varsa CalDAV, item_id varsa EWS
        hedef_tur = None
        if islem == "guncelle":
            r = islev[1]
            hedef_tur = "caldav" if getattr(r, "url", "") else "ews"
        # Varsayılan: seçilen kaynak (yoksa ilk kaynak)
        if hedef_tur is None:
            hedef_tur = secilen[0] if secilen else kaynaklar[0][0]

        if hedef_tur == "caldav":
            cal = None
            if islem == "ekle" and secilen and secilen[0] == "caldav":
                cal = secilen[1]
            else:
                # Düzenlemede kayıt kendi hesabına (kaynak_id) gider
                kaynak_id = getattr(islev[1], "kaynak_id", "") if islem == "guncelle" else ""
                cal = self.ana._kaynak_caldav(kaynak_id)
            if cal is None:
                raise EwsHata("CalDAV takvim hesabı yok.")
            istemci = self.ana._caldav_istemci(cal)
            if islem == "ekle":
                _, baslik, bas, bit, konum, aciklama, tum_gun, _, kural = islev
                istemci.randevu_ekle(
                    baslik, bas, bit, konum, aciklama, tum_gun, rrule=kural
                )
            else:
                istemci.randevu_guncelle(islev[1])
        else:
            # EWS hedefi: seçilen EWS hesabı (yoksa aktif hesap)
            hesap = {}
            if secilen and secilen[0] == "ews":
                hesap = secilen[1]
            if not hesap:
                hesap = self.ana.ayarlar.aktif_hesap() or {}
            hesap_id = hesap.get("id") or self.ana.aktif_id
            istemci = self.ana._istemciler.get(hesap_id)
            if istemci is None:
                istemci = self.ana._istemci_kur(hesap)
                self.ana._istemciler[hesap_id] = istemci
            if islem == "ekle":
                _, baslik, bas, bit, konum, aciklama, tum_gun, _, kural = islev
                istemci.randevu_ekle(
                    baslik, bas, bit, konum, aciklama, tum_gun, rrule=kural
                )
            else:
                istemci.randevu_guncelle(islev[1])
        return ("takvim_yenile",)

    def _sil(self):
        r = self.randevu
        if r is None:
            return
        if not messagebox.askyesno(
            "Randevu Sil", Postacim._sil_sorusu(r), parent=self
        ):
            return
        self.ana._randevu_sil(r)
        self.destroy()


def _iso_utc_yerel(dt: datetime) -> str:
    """Naive datetime → yerel saat varsayılır → UTC ISO (Z)."""
    if dt.tzinfo is None:
        dt = dt.astimezone()
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class TakvimHesapPenceresi(tk.Toplevel):
    """CalDAV takvim hesabı ekleme / düzenleme / silme penceresi."""

    SABLONLAR = {
        "Gmail": {
            # Google'ın CalDAV'ı: yeni uç (apidata.googleusercontent.com)
            # yalnız OAuth2 kabul ediyor; Basic + uygulama parolası yalnız
            # eski uçta çalışır. E-posta alandan doldurulur.
            "url": "https://www.google.com/calendar/dav/{eposta}/events",
            "ipucu": "Gmail → Google Hesabı → Güvenlik → Uygulama şifreleri "
                     "ile 16 haneli şifre oluşturun (2FA şart); IMAP de "
                     "etkin olmalı. E-posta alanını doldurmayı unutmayın.",
        },
        "iCloud": {
            "url": "https://caldav.icloud.com/",
            "ipucu": "Apple kimliği + uygulama şifresi (applespecifc.com).",
        },
        "Yahoo": {
            "url": "https://caldav.calendar.yahoo.com/",
            "ipucu": "Yahoo hesap ayarlarından uygulama şifresi.",
        },
        "Nextcloud / kendi sunucum": {
            "url": "https://ornek-sunucu.com/remote.php/dav/",
            "ipucu": "Nextcloud ana sayfası + /remote.php/dav/ yolu.",
        },
        "Özel URL": {"url": "", "ipucu": "CalDAV sunucu adresini yazın."},
    }

    def __init__(self, ana: Postacim):
        super().__init__(ana)
        self.ana = ana
        self.title("Takvim Hesapları")
        self.geometry("560x480")
        self.transient(ana)
        ana._pencere_simgesi(self)
        self.grab_set()

        govde = ttk.Frame(self, padding=12)
        govde.pack(fill="both", expand=True)

        # Liste
        ttk.Label(govde, text="Bağlı takvimler:", font=("TkDefaultFont", 10, "bold")).pack(
            anchor="w"
        )
        liste_alan = ttk.Frame(govde)
        liste_alan.pack(fill="both", expand=True, pady=(4, 8))
        self.liste = ttk.Treeview(
            liste_alan, columns=("ad", "url"), show="headings", height=7
        )
        self.liste.heading("ad", text="Ad")
        self.liste.heading("url", text="Sunucu")
        self.liste.column("ad", width=140)
        self.liste.column("url", width=340)
        kay = ttk.Scrollbar(liste_alan, orient="vertical", command=self.liste.yview)
        self.liste.configure(yscrollcommand=kay.set)
        kay.pack(side="right", fill="y")
        self.liste.pack(fill="both", expand=True)
        self.liste.bind("<<TreeviewSelect>>", self._secim_degisti)

        # Form
        form = ttk.LabelFrame(govde, text="Hesap", padding=8)
        form.pack(fill="x")
        form.columnconfigure(1, weight=1)

        ttk.Label(form, text="Ad:").grid(row=0, column=0, sticky="w", pady=2)
        self.ad_var = tk.StringVar()
        ttk.Entry(form, textvariable=self.ad_var, width=36).grid(
            row=0, column=1, sticky="ew", pady=2, padx=(6, 0)
        )

        ttk.Label(form, text="Sunucu (URL):").grid(row=1, column=0, sticky="w", pady=2)
        self.url_var = tk.StringVar()
        ttk.Entry(form, textvariable=self.url_var, width=36).grid(
            row=1, column=1, sticky="ew", pady=2, padx=(6, 0)
        )

        ttk.Label(form, text="E-posta:").grid(row=2, column=0, sticky="w", pady=2)
        self.kullanici_var = tk.StringVar()
        ttk.Entry(form, textvariable=self.kullanici_var, width=36).grid(
            row=2, column=1, sticky="ew", pady=2, padx=(6, 0)
        )

        ttk.Label(form, text="Şifre:").grid(row=3, column=0, sticky="w", pady=2)
        self.parola_var = tk.StringVar()
        ttk.Entry(form, textvariable=self.parola_var, width=36, show="•").grid(
            row=3, column=1, sticky="ew", pady=2, padx=(6, 0)
        )

        # Hazır şablonlar
        sablon_alan = ttk.Frame(form)
        sablon_alan.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        ttk.Label(sablon_alan, text="Hazır:").pack(side="left")
        for ad in self.SABLONLAR:
            ttk.Button(
                sablon_alan, text=ad, width=18,
                command=lambda a=ad: self._sablon(a),
            ).pack(side="left", padx=2)

        self.ipucu = ttk.Label(form, text="", wraplength=500, justify="left",
                               foreground="#5f6368")
        self.ipucu.grid(row=5, column=0, columnspan=2, sticky="ew", pady=(6, 0))

        # Düğmeler
        dugmeler = ttk.Frame(govde)
        dugmeler.pack(fill="x", pady=(10, 0))
        ttk.Button(dugmeler, text="Ekle", command=self._ekle).pack(side="left")
        ttk.Button(dugmeler, text="Güncelle", command=self._guncelle).pack(side="left", padx=6)
        ttk.Button(dugmeler, text="Sil", command=self._sil).pack(side="left")
        ttk.Button(dugmeler, text="Bağlantıyı dene", command=self._dene).pack(side="left", padx=6)
        ttk.Button(dugmeler, text="Kapat", command=self.destroy).pack(side="right")

        self._secili_id = ""
        self._listeyi_doldur()

    def _listeyi_doldur(self):
        self.liste.delete(*self.liste.get_children())
        for t in self.ana.ayarlar.takvimler():
            self.liste.insert(
                "", "end", iid=t["id"],
                values=(t.get("ad", ""), t.get("url", "")),
            )

    def _secim_degisti(self, _olay=None):
        secim = self.liste.selection()
        if not secim:
            return
        self._secili_id = secim[0]
        t = self.ana.ayarlar.takvim(self._secili_id)
        if t:
            self.ad_var.set(t.get("ad", ""))
            self.url_var.set(t.get("url", ""))
            self.kullanici_var.set(t.get("kullanici", ""))
            self.parola_var.set(t.get("parola", ""))

    def _sablon(self, ad: str):
        s = self.SABLONLAR[ad]
        url = s["url"]
        if "{eposta}" in url:
            eposta = self.kullanici_var.get().strip()
            if eposta:
                url = url.replace("{eposta}", eposta)
        self.url_var.set(url)
        if not self.ad_var.get():
            self.ad_var.set(ad)
        self.ipucu.configure(text=s["ipucu"])

    def _veri_al(self) -> dict | None:
        ad = self.ad_var.get().strip()
        url = self.url_var.get().strip()
        kullanici = self.kullanici_var.get().strip()
        parola = self.parola_var.get()
        if not kullanici:
            messagebox.showwarning("Eksik", "E-posta boş.", parent=self)
            return None
        if "{eposta}" in url:
            # Şablon URL'i (Gmail): e-posta alandan doldurulur
            url = url.replace("{eposta}", kullanici)
        if not url:
            messagebox.showwarning("Eksik", "Sunucu adresi boş.", parent=self)
            return None
        if not ad:
            ad = kullanici
        return {
            "tur": "caldav",
            "ad": ad,
            "url": url,
            "kullanici": kullanici,
            "parola": parola,
        }

    def _ekle(self):
        veri = self._veri_al()
        if veri is None:
            return
        self.ana.ayarlar.takvim_ekle(veri)
        self._listeyi_doldur()
        self.ana.takvim_yuklendi = False
        self.ana.durum.set(f"Takvim hesabı eklendi: {veri['ad']}")
        # Bağlantıyı dene (arka planda)
        self._dene()

    def _guncelle(self):
        if not self._secili_id:
            messagebox.showwarning("Seçim", "Listeden bir hesap seçin.", parent=self)
            return
        veri = self._veri_al()
        if veri is None:
            return
        self.ana.ayarlar.takvim_guncelle(self._secili_id, veri)
        # Önbelleği temizle
        if hasattr(self.ana, "_caldav_istemciler"):
            self.ana._caldav_istemciler.pop(self._secili_id, None)
        self._listeyi_doldur()
        self.ana.takvim_yuklendi = False
        self.ana.durum.set("Takvim hesabı güncellendi.")

    def _sil(self):
        if not self._secili_id:
            messagebox.showwarning("Seçim", "Listeden bir hesap seçin.", parent=self)
            return
        if not messagebox.askyesno("Sil", "Bu takvim hesabı silinsin mi?", parent=self):
            return
        self.ana.ayarlar.takvim_sil(self._secili_id)
        if hasattr(self.ana, "_caldav_istemciler"):
            self.ana._caldav_istemciler.pop(self._secili_id, None)
        self._secili_id = ""
        self.ad_var.set(""); self.url_var.set("")
        self.kullanici_var.set(""); self.parola_var.set("")
        self._listeyi_doldur()
        self.ana.takvim_yuklendi = False
        self.ana.durum.set("Takvim hesabı silindi.")

    def _dene(self):
        """Bağlantıyı test eder (keşif)."""
        veri = self._veri_al()
        if veri is None:
            return
        self.ipucu.configure(text="Bağlanılıyor…")
        self.update_idletasks()

        def is_():
            from .caldav import CalDavIstemci, CalDavHata

            c = CalDavIstemci(veri["url"], veri["kullanici"], veri["parola"])
            try:
                koleksiyonlar = c.kesfet()
            except CalDavHata as exc:
                raise EwsHata(str(exc))
            if not koleksiyonlar:
                raise EwsHata("Sunucuda takvim koleksiyonu bulunamadı.")
            adlar = ", ".join(k.ad or k.url for k in koleksiyonlar[:5])
            return ("uyari", f"Bağlantı başarılı! Takvimler: {adlar}")

        threading.Thread(
            target=self.ana._arka_plan, args=(is_,), daemon=True
        ).start()
        # Sonucu ipucuna yaz (uyari diaolg yerine)
        self.after(300, self._dene_bekle)

    def _dene_bekle(self):
        # _arka_plan "uyari" sonucu messagebox gösterir; ipucu da güncelleriz
        pass


class AyarlarPenceresi(tk.Toplevel):
    """Genel + Takvim (Ay/Hafta/Gün renk ve font) ayarları penceresi."""

    # Renk anahtarı → Türkçe etiket
    RENK_ETIKET = {
        "hucre": "Hücre zemini",
        "hucre_metin": "Hücre metni",
        "diger_ay": "Diğer ay zemini",
        "diger_ay_metin": "Diğer ay metni",
        "bugun": "Bugün zemini",
        "bugun_metin": "Bugün metni",
        "secili": "Seçili gün zemini",
        "secili_metin": "Seçili gün metni",
        "bos": "Boş hücre",
        "hafta_sonu": "Hafta sonu zemini",
        "tum_gun": "Tüm gün zemini",
        "tum_gun_metin": "Tüm gün metni",
        "randevu": "Randevu zemini",
        "randevu_metin": "Randevu metni",
        "simdi": "Şu anki saat çizgisi",
    }
    # Font anahtarı → Türkçe etiket
    FONT_ETIKET = {
        "baslik_font": "Başlık yazı tipi",
        "gun_font": "Gün numarası yazı tipi",
        "saat_font": "Saat yazı tipi",
        "randevu_font": "Randevu yazı tipi",
    }
    GORUNUMLER = (("ay", "Ay"), ("hafta", "Hafta"), ("gun", "Gün"))

    def __init__(self, ana: Postacim):
        super().__init__(ana)
        self.ana = ana
        self.title("Ayarlar")
        self.geometry("580x560")
        self.minsize(520, 460)
        self.transient(ana)
        ana._pencere_simgesi(self)
        # Geçici kopya: Kaydet'e kadar dokunulmaz
        import copy as _copy
        self.stil = _copy.deepcopy(ana.takvim_stil)

        govde = ttk.Frame(self, padding=10)
        govde.pack(fill="both", expand=True)

        self.defter = ttk.Notebook(govde)
        self.defter.pack(fill="both", expand=True)

        self._genel_kur()
        self._takvim_kur()

        alt = ttk.Frame(govde)
        alt.pack(fill="x", pady=(8, 0))
        ttk.Button(alt, text="Kaydet", command=self._kaydet).pack(
            side="right", padx=(6, 0)
        )
        ttk.Button(alt, text="İptal", command=self.destroy).pack(side="right")
        ttk.Button(
            alt, text="Varsayılana dön", command=self._varsayilana_don
        ).pack(side="left")

        # grab: pencere haritalanana dek ertelenir (RandevuPenceresi ile aynı)
        self.after_idle(self._grab_al)

    def _grab_al(self, deneme=0):
        try:
            self.grab_set()
        except tk.TclError:
            if deneme < 20 and self.winfo_exists():
                self.after(50, lambda: self._grab_al(deneme + 1))

    # ------------------------------------------------------------ Genel

    def _genel_kur(self):
        sayfa = ttk.Frame(self.defter, padding=12)
        self.defter.add(sayfa, text="Genel")

        ttk.Label(sayfa, text="Tema:", font=("TkDefaultFont", 10, "bold")).grid(
            row=0, column=0, sticky="w", pady=(0, 6)
        )
        self.tema_degisken = tk.StringVar(value=self.ana.tema)
        for i, (deger, etiket) in enumerate((("light", "Açık"), ("dark", "Koyu"))):
            ttk.Radiobutton(
                sayfa, text=etiket, value=deger, variable=self.tema_degisken
            ).grid(row=0, column=1 + i, sticky="w", padx=(0, 12))

        ttk.Label(
            sayfa, text="Otomatik yenileme:", font=("TkDefaultFont", 10, "bold")
        ).grid(row=1, column=0, sticky="w", pady=(12, 6))
        self.otomatik_degisken = tk.StringVar()
        degerler = {
            0: "Kapalı", 30: "30 saniye", 60: "1 dakika",
            120: "2 dakika", 300: "5 dakika",
        }
        self.otomatik_combo = ttk.Combobox(
            sayfa, textvariable=self.otomatik_degisken, state="readonly",
            values=list(degerler.values()), width=16,
        )
        self.otomatik_combo.grid(row=1, column=1, columnspan=2, sticky="w")
        mevcut = int(self.ana.ayarlar.al("otomatik_yenile", 60))
        self.otomatik_degisken.set(degerler.get(mevcut, "1 dakika"))
        self._otomatik_degerler = degerler

        ttk.Label(
            sayfa,
            text="Takvim renk ve yazı tipleri için “Takvim” sekmesine geçin.",
            foreground="#666666",
        ).grid(row=2, column=0, columnspan=3, sticky="w", pady=(16, 0))

        ttk.Label(
            sayfa, text="Takvim otomatik yenileme:", font=("TkDefaultFont", 10, "bold")
        ).grid(row=3, column=0, sticky="w", pady=(12, 6))
        self.takvim_otomatik_degisken = tk.StringVar()
        takvim_degerler = {
            0: "Kapalı", 60: "1 dakika", 300: "5 dakika", 900: "15 dakika",
        }
        self.takvim_otomatik_combo = ttk.Combobox(
            sayfa, textvariable=self.takvim_otomatik_degisken, state="readonly",
            values=list(takvim_degerler.values()), width=16,
        )
        self.takvim_otomatik_combo.grid(row=3, column=1, columnspan=2, sticky="w")
        mevcut_takvim = int(self.ana.ayarlar.al("takvim_otomatik_yenileme", 300))
        self.takvim_otomatik_degisken.set(
            takvim_degerler.get(mevcut_takvim, "5 dakika")
        )
        self._takvim_otomatik_degerler = takvim_degerler

        # --- Bildirimler ---
        ttk.Label(
            sayfa, text="Bildirimler:", font=("TkDefaultFont", 10, "bold")
        ).grid(row=4, column=0, sticky="w", pady=(18, 6))
        self.bildirim_degisken = tk.BooleanVar(
            value=bool(self.ana.ayarlar.al("bildirim", True))
        )
        ttk.Checkbutton(
            sayfa,
            text="Yeni e-posta geldiğinde uyarı göster",
            variable=self.bildirim_degisken,
        ).grid(row=5, column=0, columnspan=3, sticky="w")

        self.balon_uyari = ttk.Label(
            sayfa,
            text="Sistem bildirim balonları kapalı — masaüstü uyarıları "
                 "görünmeyebilir.",
            foreground="#b3261e",
            wraplength=420,
        )
        self.balon_uyari.grid(row=6, column=0, columnspan=3, sticky="w", pady=(8, 0))
        ttk.Button(
            sayfa, text="Sistem bildirimlerini aç", command=self._balonlari_ac
        ).grid(row=7, column=0, sticky="w", pady=(6, 0))
        self._balon_uyarisini_guncelle()

    def _balon_uyarisini_guncelle(self):
        """Sistem balonlarının kapalı olup olmadığına göre uyarıyı gösterir."""
        try:
            if self.ana._bildirim_balonlari_kapali():
                self.balon_uyari.configure(
                    text="Sistem bildirim balonları kapalı — masaüstü uyarıları "
                         "görünmeyebilir.",
                    foreground="#b3261e",
                )
                self.balon_uyari.grid()
            else:
                self.balon_uyari.grid_remove()
        except tk.TclError:
            pass

    def _balonlari_ac(self):
        """GNOME'da bildirim balonlarını açar."""
        if self.ana._bildirim_balonlarini_ac():
            self._balon_uyarisini_guncelle()
            self.ana.durum.set("Sistem bildirim balonları açıldı.")
        else:
            self.ana.durum.set(
                "Bildirim balonları açılamadı — GNOME Ayarlar ▸ Bildirimler "
                "üzerinden açabilirsiniz."
            )

    # ------------------------------------------------------------ Takvim

    def _takvim_kur(self):
        sayfa = ttk.Frame(self.defter, padding=12)
        self.defter.add(sayfa, text="Takvim")

        # Görünüm seçici
        ust = ttk.Frame(sayfa)
        ust.pack(fill="x", pady=(0, 8))
        ttk.Label(ust, text="Görünüm:").pack(side="left")
        self.gorunum_degisken = tk.StringVar(value="ay")
        for deger, etiket in self.GORUNUMLER:
            ttk.Radiobutton(
                ust, text=etiket, value=deger, variable=self.gorunum_degisken,
                command=self._gorunum_goster,
            ).pack(side="left", padx=(8, 0))
        ttk.Button(
            ust, text="Bu görünümü varsayılana dön",
            command=self._gorunum_varsayilan,
        ).pack(side="right")

        # Kaydırılabilir alan (renk satırları çok olabilir)
        kaydir = ttk.Frame(sayfa)
        kaydir.pack(fill="both", expand=True)
        tuval = tk.Canvas(kaydir, highlightthickness=0, bd=0)
        kay = ttk.Scrollbar(kaydir, orient="vertical", command=tuval.yview)
        self.icerik = ttk.Frame(tuval)
        # İçerik değişince kaydırma alanı güncellensin
        self.icerik.bind(
            "<Configure>",
            lambda e: tuval.configure(scrollregion=tuval.bbox("all")),
        )
        tuval.create_window((0, 0), window=self.icerik, anchor="nw")
        tuval.configure(yscrollcommand=kay.set)
        kay.pack(side="right", fill="y")
        tuval.pack(side="left", fill="both", expand=True)
        # Tuval genişliği içeriğe eşitlensin (yatay kaydırma olmasın).
        # Tuvalin kendi <Configure> olayına bağlı: haritalanınca winfo_width()
        # doğrudur; icerik'e bağlansaydı ilk çizimde 1 piksile sıkışırdı.
        Postacim._icerigi_genislet(tuval)
        self._tuval = tuval

        self._renk_dugmeleri: dict = {}   # (gorunum, anahtar) → Button
        self._font_alanlari: dict = {}    # (gorunum, anahtar) → dict
        self._gorunum_goster()

    def _gorunum_goster(self):
        """Seçili görünümün renk/font satırlarını kurar (yeniden)."""
        for cocuk in self.icerik.winfo_children():
            cocuk.destroy()
        self._renk_dugmeleri.clear()
        self._font_alanlari.clear()
        g = self.gorunum_degisken.get() or "ay"
        stil = self.stil.get(g, {})

        # --- Renkler ---
        ttk.Label(
            self.icerik, text="Renkler", font=("TkDefaultFont", 10, "bold")
        ).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 4))
        satir = 1
        varsayilan = TAKVIM_STIL_VARSAYILAN[g]
        for anahtar, etiket in self.RENK_ETIKET.items():
            if anahtar not in varsayilan:
                continue
            deger = stil.get(anahtar, varsayilan[anahtar])
            ttk.Label(self.icerik, text=etiket + ":").grid(
                row=satir, column=0, sticky="w", pady=2, padx=(0, 8)
            )
            dugme = tk.Button(
                self.icerik, text=deger, width=12, bg=deger,
                relief="sunken", bd=1,
                command=lambda gg=g, aa=anahtar: self._renk_sec(gg, aa),
            )
            dugme.grid(row=satir, column=1, sticky="w", pady=2)
            self._renk_dugmeleri[(g, anahtar)] = dugme
            satir += 1

        # --- Yazı tipleri ---
        satir += 1
        ttk.Label(
            self.icerik, text="Yazı tipleri", font=("TkDefaultFont", 10, "bold")
        ).grid(row=satir, column=0, columnspan=3, sticky="w", pady=(8, 4))
        satir += 1
        import tkinter.font as tkfont
        aileler = sorted(tkfont.families(self))
        for anahtar, etiket in self.FONT_ETIKET.items():
            if anahtar not in varsayilan:
                continue
            deger = list(stil.get(anahtar, varsayilan[anahtar]))
            while len(deger) < 3:
                deger.append("")
            ttk.Label(self.icerik, text=etiket + ":").grid(
                row=satir, column=0, sticky="w", pady=2, padx=(0, 8)
            )
            alan = ttk.Frame(self.icerik)
            alan.grid(row=satir, column=1, columnspan=2, sticky="w", pady=2)

            aile = tk.StringVar(value=deger[0])
            boyut = tk.StringVar(value=str(deger[1]))
            kalin = tk.BooleanVar(value="bold" in str(deger[2]))
            italik = tk.BooleanVar(value="italic" in str(deger[2]))

            ttk.Combobox(
                alan, textvariable=aile, values=aileler, width=18,
                state="readonly",
            ).pack(side="left")
            ttk.Spinbox(
                alan, from_=6, to=48, textvariable=boyut, width=4,
            ).pack(side="left", padx=(4, 8))
            ttk.Checkbutton(alan, text="Kalın", variable=kalin).pack(
                side="left", padx=(0, 4)
            )
            ttk.Checkbutton(alan, text="İtalik", variable=italik).pack(
                side="left"
            )
            self._font_alanlari[(g, anahtar)] = {
                "aile": aile, "boyut": boyut, "kalin": kalin, "italik": italik,
            }
            satir += 1

    def _renk_sec(self, gorunum: str, anahtar: str):
        """Renk seçici açar; seçilirse düğmeyi ve geçici stili günceller."""
        from tkinter import colorchooser

        mevcut = self.stil.get(gorunum, {}).get(
            anahtar, TAKVIM_STIL_VARSAYILAN[gorunum][anahtar]
        )
        sonuc = colorchooser.askcolor(color=mevcut, parent=self,
                                      title=self.RENK_ETIKET.get(anahtar, anahtar))
        if not sonuc or not sonuc[1]:
            return
        yeni = sonuc[1]
        self.stil.setdefault(gorunum, {})[anahtar] = yeni
        dugme = self._renk_dugmeleri.get((gorunum, anahtar))
        if dugme is not None:
            dugme.configure(text=yeni, bg=yeni)

    def _gorunum_varsayilan(self):
        """Seçili görünümün tüm değerlerini varsayılana döndürür."""
        g = self.gorunum_degisken.get() or "ay"
        self.stil[g] = dict(TAKVIM_STIL_VARSAYILAN[g])
        self._gorunum_goster()

    def _varsayilana_don(self):
        """Tüm ayarları varsayılan değerlere döndürür (kaydetmeden ekranda)."""
        self.tema_degisken.set("light")
        self.otomatik_degisken.set("1 dakika")
        self.takvim_otomatik_degisken.set("5 dakika")
        self.stil = {
            g: dict(TAKVIM_STIL_VARSAYILAN[g]) for g in TAKVIM_STIL_VARSAYILAN
        }
        self._gorunum_goster()


    # ------------------------------------------------------------ Kaydet

    def _kaydet(self):
        # Geçici font alanlarını stile yaz
        for (g, anahtar), alan in self._font_alanlari.items():
            stil_txt = ""
            if alan["kalin"].get() and alan["italik"].get():
                stil_txt = "bold italic"
            elif alan["kalin"].get():
                stil_txt = "bold"
            elif alan["italik"].get():
                stil_txt = "italic"
            try:
                boyut = int(float(alan["boyut"].get()))
            except ValueError:
                boyut = TAKVIM_STIL_VARSAYILAN[g][anahtar][1]
            self.stil.setdefault(g, {})[anahtar] = [
                alan["aile"].get() or "TkDefaultFont", boyut, stil_txt,
            ]

        # Genel ayarlar
        yeni_tema = self.tema_degisken.get()
        if yeni_tema != self.ana.tema:
            self.ana._tema_degistir(yeni_tema)
        for saniye, etiket in self._otomatik_degerler.items():
            if etiket == self.otomatik_degisken.get():
                self.ana._otomatik_degistir(saniye)
                break
        for saniye, etiket in self._takvim_otomatik_degerler.items():
            if etiket == self.takvim_otomatik_degisken.get():
                self.ana._takvim_otomatik_degistir(saniye)
                break

        # Bildirim tercihi
        bildirim = bool(self.bildirim_degisken.get())
        if bildirim != self.ana._bildirim_acik:
            self.ana._bildirim_acik = bildirim
            self.ana.ayarlar.ayarla("bildirim", bildirim)
            self.ana.ayarlar.kaydet()
            if bildirim:
                self.ana.durum.set("Yeni e-posta uyarıları açıldı.")
            else:
                self.ana.durum.set("Yeni e-posta uyarıları kapatıldı.")

        # Takvim stili
        self.ana.takvim_stil = self.stil
        self.ana._stil_kaydet()
        self.ana._takvim_stil_uygula()
        self.ana.durum.set("Ayarlar kaydedildi.")
        self.destroy()
