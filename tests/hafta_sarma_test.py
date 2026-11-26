"""Hafta görünümü başlık sarma testi (çevrimdışı, Xvfb).

Başlık etiketi sabit 90 pikselde kırılıyordu ("Gökhan da Beyin" erken
ikiye bölünüyor); artık hücrenin gerçek genişliğine göre sarılır.
"""

import os
import sys
import unittest
from unittest import mock

os.environ["POSTACIM_GUNCELLEME"] = "0"  # gerçek ağ denetimi asla başlamasın

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, KOK)


class HaftaSarmaTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import tkinter as tk
            root = tk.Tk()
            root.destroy()
        except tk.TclError:
            raise unittest.SkipTest("Grafik ortam yok (Xvfb gerekir)")

    def _uygulamayi_kur(self):
        import json, tempfile
        import postacim.ui as ui
        from postacim.ews import Klasor

        dizin = tempfile.mkdtemp(prefix="hafta_sarma_")
        yol = os.path.join(dizin, "hesap.json")
        with open(yol, "w", encoding="utf-8") as f:
            json.dump({
                "hesaplar": [{"id": "g1", "ad": "GMail", "tur": "imap",
                              "kullanici": "deneme@gmail.com",
                              "parola": "p", "yontem": "parola",
                              "gelen_sunucu": "127.0.0.1",
                              "gelen_port": 1,
                              "giden_sunucu": "127.0.0.1",
                              "giden_port": 1, "guvenli": "ssl",
                              "son_klasor": "inbox"}],
                "aktif": "g1", "tema": "light", "otomatik_yenile": 0,
            }, f)

        class SahteIstemci:
            def __init__(self, hesap): self.hesap = hesap
            def klasor_listesi(self):
                return [Klasor(kimlik="inbox", ad="Gelen Kutusu",
                               toplam=1, okunmamis=0)]
            def guncelle(self, k=None): return {}
            def mesajlar(self, *a, **k): return [], 0
            def gelen_sayisi(self): return 1
            def cozumle(self, *a, **k): return []
            def mesaj_detay(self, m): return m
            def detay_hazirla(self): pass
            def tasi(self, m, h="deleteditems"): pass
            def gonder(self, *a, **k): return ""
            def mesaj_mime(self, mid): return b"From: x\r\n\r\n"
            def ek_indir(self, ek): return b""
            def okundu_isaretle(self, m, o=True): pass
            def bayrakla(self, *a, **k): pass

        eski_a, eski_k = ui.Ayarlar, ui.Postacim._istemci_kur
        ui.Ayarlar = lambda: __import__(
            "postacim.config", fromlist=["Ayarlar"]).Ayarlar(yol)
        ui.Postacim._istemci_kur = lambda self, h: SahteIstemci(h)
        return ui, eski_a, eski_k

    def test_baslik_hucre_genisligine_gore_sarar(self):
        import time
        from datetime import datetime, timedelta
        from postacim.ews import Randevu

        ui, eski_a, eski_k = self._uygulamayi_kur()
        uyg = None
        try:
            uyg = ui.Postacim()
            uyg.geometry("1280x820+0+0")
            uyg.defter.select(1)  # Takvim sekmesi
            bas = (datetime.now().replace(
                hour=14, minute=0, second=0, microsecond=0))
            r = Randevu(item_id="o1", baslik="Gökhan da Beyin",
                        baslangic=bas.strftime("%Y-%m-%dT%H:%M:%S"))
            uyg.randevular = [r]
            uyg.takvim_yuklendi = True
            uyg.takvim_gorunum_degisken.set("hafta")
            uyg._gorunum_degistir()
            for _ in range(30):
                uyg.update()
                time.sleep(0.03)
            uyg._takvim_ciz()
            for _ in range(20):
                uyg.update()
                time.sleep(0.03)

            # Olayın etiketi: (saat, gün) hücresinin ilk çocuğu
            bulunan = []
            for (saat, g), kayit in uyg._hafta_hucreler.items():
                for cocuk in kayit["hucre"].winfo_children():
                    if isinstance(cocuk, __import__("tkinter").Label) and \
                            "Gökhan" in str(cocuk.cget("text")):
                        bulunan.append(cocuk)
            self.assertTrue(bulunan, "randevu etiketi bulunamadı")
            etiket = bulunan[0]
            genislik = etiket.winfo_width()
            sar = etiket.cget("wraplength")
            self.assertGreater(
                genislik, 90,
                f"etiket genişliği beklenmedik: {genislik}px")
            self.assertGreater(
                sar, 90,
                f"wraplength hâlâ sabit: {sar} (hücre {genislik}px)")
            # Tek satır: etiket yüksekliği tek font satırına yakın
            from tkinter import font as tkfont
            yazi = tkfont.Font(font=etiket.cget("font"))
            tek_satir = yazi.metrics("linespace")
            self.assertLess(
                etiket.winfo_height(),
                2 * tek_satir + 6,
                "başlık hâlâ iki satıra kırılıyor",
            )
        finally:
            if uyg is not None:
                uyg.destroy()
            ui.Ayarlar, ui.Postacim._istemci_kur = eski_a, eski_k


if __name__ == "__main__":
    unittest.main(verbosity=2)
