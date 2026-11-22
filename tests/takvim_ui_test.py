"""Takvim sekmesi UI denetimi (EWS + IMAP geçişi)."""
import faulthandler, time, threading, traceback, os, sys
faulthandler.enable()
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from postacim.ui import Postacim

app = Postacim()
print("start aktif=", app.ayarlar.aktif_hesap().get("ad"), flush=True)

def is_akisi():
    try:
        for i in range(30):
            app.update(); time.sleep(0.15)

        # EWS hesabına geç (GMail aktifse)
        if app.ayarlar.aktif_hesap().get("tur") != "ews":
            ews = next(h for h in app.ayarlar.hesaplar() if h.get("tur") == "ews")
            # IMAP sekmesi uyarısını önce dene
            app.defter.select(1)
            app.update()
            degerler = [
                app.ajanda.item(c, "values") for c in app.ajanda.get_children()
            ]
            print("imap ajanda:", degerler, flush=True)
            # CalDAV hesabı bağlıysa takvim kaynak vardır → "bağlı takvim
            # hesabı yok" uyarısı GÖRÜNMEMELİ; bağlı değilse uyarı görünmeli.
            if app.ayarlar.takvimler():
                assert not any(
                    "bağlı takvim hesabı yok" in str(v).lower()
                    for d in degerler for v in d
                ), degerler
                print("CalDAV bagli → uyari yok OK", flush=True)
            else:
                assert any(
                    "takvim" in str(v).lower() or "EWS" in str(v)
                    for d in degerler for v in d
                ), degerler
                print("IMAP uyarisi OK", flush=True)
            assert app._hesap_degistir(ews["id"]), "EWS geçişi başarısız"
            print("hesap gecis OK", flush=True)
        else:
            print("zaten EWS aktif", flush=True)

        for i in range(50):
            app.update(); time.sleep(0.15)
            if app.klasor_liste:
                break
        print("klasor", len(app.klasor_liste), flush=True)

        # Takvim sekmesi + yükleme
        app.defter.select(1)
        app.update()
        # Sekme değişikliği olayı bazen hemen gelmez: doğrudan çağır
        if not app.takvim_yuklendi and not app._takvim_ciziliyor:
            app._takvim_cek()
        for i in range(100):
            app.update(); time.sleep(0.2)
            if i % 15 == 0:
                print(
                    f"  t={i * 0.2:.0f} yuk={app.takvim_yuklendi} "
                    f"n={len(app.randevular)} ciz={app._takvim_ciziliyor}",
                    flush=True,
                )
            if app.takvim_yuklendi:
                break
        print("yuklendi", app.takvim_yuklendi, "randevu", len(app.randevular), flush=True)
        assert app.takvim_yuklendi, "takvim yüklenmedi"
        assert len(app.randevular) > 0, "randevu yok"

        print("baslik", app.takvim_baslik.cget("text"), flush=True)
        # Randevulu bir aya git (hepsi geçmişte olabilir)
        from datetime import date as _date
        ilk = app.randevular[0]
        from postacim.ews import iso_yerel
        dt = iso_yerel(ilk.baslangic)
        assert dt is not None
        # Ay ızgarası kontrolü için Ay görünümüne dön
        app.takvim_gorunum_degisken.set("ay")
        app._gorunum_degistir()
        app.takvim_ay = (dt.year, dt.month)
        app.takvim_gun = dt.date()
        app._takvim_ciz()
        app.update()
        print("hedef ay", app.takvim_baslik.cget("text"), flush=True)
        dolu = sum(
            1 for k in app._gun_hucreleri.values()
            if k["gun"] and app._gun_randevulari(k["gun"])
        )
        print("randevulu hucre", dolu, flush=True)
        assert dolu > 0, "ızgarada randevulu gün yok"

        hedef = next(
            k for k in app._gun_hucreleri.values()
            if k["gun"] and app._gun_randevulari(k["gun"])
        )
        app._hucre_tikla(hedef["hucre"])
        app.update()
        satirlar = app.ajanda.get_children()
        print("secili gun", hedef["gun"], "ajanda", len(satirlar), flush=True)
        assert len(satirlar) >= 1

        # Ajanda satır seç → detay
        if satirlar:
            app.ajanda.selection_set(satirlar[0])
            app.event_generate("<<TreeviewSelect>>", when="tail")
            app.update()

        app._ay_degistir(1)
        app.update()
        print("sonraki ay", app.takvim_baslik.cget("text"), flush=True)
        app._bugune_git()
        app.update()
        print("bugun", app.takvim_baslik.cget("text"), flush=True)

        print("TAKVIM UI OK", flush=True)
        app.destroy()
    except Exception:
        traceback.print_exc()
        try: app.destroy()
        except Exception: pass

threading.Thread(target=is_akisi, daemon=True).start()
app.mainloop()
print("done", flush=True)
