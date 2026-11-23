"""Dosya açma/kaydetme iletişim kutuları.

Tk'nin sade `filedialog` penceresi yerine önce masaüstü ortamının kendi
dosya seçicisi kullanılır:

* GNOME / XFCE / MATE → `zenity` (GTK seçici: yerler çubuğu, arama,
  son kullanılanlar, çoklu seçim, yer imleri)
* KDE / Plasma → `kdialog`
* Hiçbiri yoksa → tkinter `filedialog` (eski davranış)

Seçici `POSTACIM_DOSYA_SECICI` ortam değişkeniyle zorlanabilir:
`zenity`, `kdialog` veya `tk`. Son kullanılan dizin hatırlanır.

Not: Bu modül tkinter'a bağımlıdır; yalnızca arayüz süreci içinde kullanılır.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from tkinter import filedialog

# Ek seçiminde sunulan hazır süzgeçler (ilk süzgeç varsayılan olur)
EK_TURLERI = [
    ("Tüm dosyalar", "*.*"),
    ("Belgeler", "*.pdf *.doc *.docx *.odt *.rtf *.txt *.md"),
    ("Tablolar", "*.xls *.xlsx *.ods *.csv"),
    ("Sunular", "*.ppt *.pptx *.odp"),
    ("Resimler", "*.png *.jpg *.jpeg *.gif *.bmp *.webp *.svg"),
    ("Arşivler", "*.zip *.rar *.7z *.tar *.gz"),
    ("E-posta", "*.eml *.msg"),
]

_son_dizin: str | None = None


def _ev_dizini() -> str:
    """Varsayılan başlangıç dizini: İndirilenler (varsa) yoksa ev dizini."""
    ev = os.path.expanduser("~")
    for ad in ("İndirilenler", "Downloads", "Belgeler", "Documents"):
        yol = os.path.join(ev, ad)
        if os.path.isdir(yol):
            return yol
    return ev


def _baslangic_dizini() -> str:
    global _son_dizin
    if _son_dizin and os.path.isdir(_son_dizin):
        return _son_dizin
    return _ev_dizini()


def _dizini_hatirla(yol: str) -> None:
    global _son_dizin
    if not yol:
        return
    dizin = yol if os.path.isdir(yol) else os.path.dirname(yol)
    if dizin and os.path.isdir(dizin):
        _son_dizin = dizin


def _desenler(desen) -> list[str]:
    """Tk süzgeç desenini (`"*.pdf *.doc"`) liste hâline getirir."""
    if isinstance(desen, (list, tuple)):
        parcalar = [str(p) for p in desen]
    else:
        parcalar = str(desen).split()
    # Tk'nin "tüm dosyalar" deseni zenity/kdialog için "*" demektir
    return [("*" if p == "*.*" else p) for p in parcalar if p]


def _zenity_filtreleri(turler) -> list[str]:
    sonuc = []
    for etiket, desen in turler or []:
        parcalar = _desenler(desen)
        if parcalar:
            sonuc.append(f"{etiket} | {' '.join(parcalar)}")
    return sonuc


def _kdialog_filtreleri(turler) -> str:
    sonuc = []
    for etiket, desen in turler or []:
        parcalar = _desenler(desen)
        if parcalar:
            sonuc.append(f"{etiket} ({' '.join(parcalar)})")
    return "\n".join(sonuc)


def _komut_sec() -> str:
    """Kullanılacak seçiciyi belirler: zenity | kdialog | tk."""
    zorla = os.environ.get("POSTACIM_DOSYA_SECICI", "").strip().lower()
    if zorla == "tk":
        return "tk"
    if zorla in ("zenity", "kdialog") and shutil.which(zorla):
        return zorla
    if shutil.which("zenity"):
        return "zenity"
    if shutil.which("kdialog"):
        return "kdialog"
    return "tk"


def _calistir(komut: list[str]) -> tuple[bool, str]:
    """Komutu çalıştırır; `(başarılı, çıktı)` döndürür.

    İptalde (çıkış kodu ≠ 0) başarısız sayılır. Komut hiç başlatılamazsa
    `OSError` yükseltir; çağıran tkinter yedeğine düşer.
    """
    try:
        sonuc = subprocess.run(
            komut, capture_output=True, text=True, encoding="utf-8",
            errors="replace", check=False,
        )
    except FileNotFoundError:
        raise
    if sonuc.returncode != 0:
        return False, ""
    return True, sonuc.stdout.rstrip("\n")


def _zenity_ac(baslik: str, baslangic: str | None,
               turler, coklu: bool) -> tuple[bool, str]:
    komut = ["zenity", "--file-selection", f"--title={baslik}", "--modal"]
    if coklu:
        komut += ["--multiple", "--separator=\n"]
    for filtre in _zenity_filtreleri(turler):
        komut.append(f"--file-filter={filtre}")
    if baslangic:
        yol = baslangic
        if os.path.isdir(yol) and not yol.endswith(os.sep):
            yol += os.sep
        komut.append(f"--filename={yol}")
    return _calistir(komut)


def _zenity_kaydet(baslik: str, hedef: str, turler) -> tuple[bool, str]:
    komut = [
        "zenity", "--file-selection", "--save", "--modal",
        f"--title={baslik}", f"--filename={hedef}",
    ]
    for filtre in _zenity_filtreleri(turler):
        komut.append(f"--file-filter={filtre}")
    return _calistir(komut)


def _kdialog_ac(baslik: str, baslangic: str | None,
                turler, coklu: bool) -> tuple[bool, str]:
    komut = ["kdialog", "--title", baslik, "--getopenfilename"]
    if coklu:
        komut.append("--multiple")
    komut.append(baslangic or _baslangic_dizini())
    filtre = _kdialog_filtreleri(turler)
    if filtre:
        komut.append(filtre)
    return _calistir(komut)


def _kdialog_kaydet(baslik: str, hedef: str, turler) -> tuple[bool, str]:
    komut = ["kdialog", "--title", baslik, "--getsavefilename", hedef]
    filtre = _kdialog_filtreleri(turler)
    if filtre:
        komut.append(filtre)
    return _calistir(komut)


def _tk_ac(baslik: str, baslangic: str | None,
           turler, coklu: bool) -> tuple[bool, str]:
    secenekler = {"title": baslik}
    if baslangic:
        if os.path.isdir(baslangic):
            secenekler["initialdir"] = baslangic
        else:
            dizin = os.path.dirname(baslangic)
            ad = os.path.basename(baslangic)
            if dizin:
                secenekler["initialdir"] = dizin
            if ad:
                secenekler["initialfile"] = ad
    if turler:
        secenekler["filetypes"] = list(turler)
    if coklu:
        secilen = filedialog.askopenfilenames(**secenekler)
        yollar = [p for p in secilen if p]
        return bool(yollar), "\n".join(yollar)
    secilen = filedialog.askopenfilename(**secenekler)
    return bool(secilen), secilen or ""


def _tk_kaydet(baslik: str, hedef: str, turler,
               varsayilan_uzanti: str | None) -> tuple[bool, str]:
    secenekler = {"title": baslik}
    if hedef:
        dizin = os.path.dirname(hedef)
        ad = os.path.basename(hedef)
        if dizin:
            secenekler["initialdir"] = dizin
        if ad:
            secenekler["initialfile"] = ad
    if turler:
        secenekler["filetypes"] = list(turler)
    if varsayilan_uzanti:
        secenekler["defaultextension"] = varsayilan_uzanti
    secilen = filedialog.asksaveasfilename(**secenekler)
    return bool(secilen), secilen or ""


def dosya_ac(baslik: str = "Dosya seç", baslangic: str | None = None,
             turler=None, coklu: bool = False):
    """Dosya seçtirir.

    `coklu=False` ise seçilen yol (iptalde `""`), `coklu=True` ise seçilen
    yolların listesi döner.
    """
    arac = _komut_sec()
    try:
        if arac == "zenity":
            basarili, cikti = _zenity_ac(baslik, baslangic, turler, coklu)
        elif arac == "kdialog":
            basarili, cikti = _kdialog_ac(baslik, baslangic, turler, coklu)
        else:
            basarili, cikti = _tk_ac(baslik, baslangic, turler, coklu)
    except OSError:
        basarili, cikti = _tk_ac(baslik, baslangic, turler, coklu)

    if not basarili or not cikti:
        return [] if coklu else ""
    if coklu:
        yollar = [satir for satir in cikti.split("\n") if satir]
        for yol in yollar:
            _dizini_hatirla(yol)
        return yollar
    _dizini_hatirla(cikti)
    return cikti


def dosya_ac_coklu(baslik: str = "Dosya seç", baslangic: str | None = None,
                   turler=None) -> list[str]:
    """Birden çok dosya seçtirir; iptalde boş liste döner."""
    return dosya_ac(baslik, baslangic, turler, coklu=True)  # type: ignore[return-value]


def dosya_kaydet(baslik: str = "Kaydet", baslangic: str | None = None,
                 turler=None, varsayilan_uzanti: str | None = None) -> str:
    """Kaydedilecek dosya yolunu seçtirir; iptalde `""` döner.

    `baslangic` yalnızca dosya adıysa son kullanılan (yoksa İndirilenler)
    dizinle birleştirilir.
    """
    if baslangic:
        hedef = (baslangic if os.path.isabs(baslangic)
                 else os.path.join(_baslangic_dizini(), baslangic))
    else:
        hedef = _baslangic_dizini() + os.sep

    arac = _komut_sec()
    try:
        if arac == "zenity":
            basarili, cikti = _zenity_kaydet(baslik, hedef, turler)
        elif arac == "kdialog":
            basarili, cikti = _kdialog_kaydet(baslik, hedef, turler)
        else:
            basarili, cikti = _tk_kaydet(
                baslik, hedef, turler, varsayilan_uzanti
            )
    except OSError:
        basarili, cikti = _tk_kaydet(baslik, hedef, turler, varsayilan_uzanti)

    if not basarili or not cikti:
        return ""
    if varsayilan_uzanti and not cikti.lower().endswith(
        varsayilan_uzanti.lower()
    ):
        kok, mevcut = os.path.splitext(cikti)
        if not mevcut:
            cikti += varsayilan_uzanti
    _dizini_hatirla(cikti)
    return cikti
