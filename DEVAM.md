# Postacım — geliştirme günlüğü

> Bu dosya projenin geliştirme sürecini anlatır: hangi sorun çözüldü, hangi
> sunucu tarafı kısıtıyla karşılaşıldı, hangi kararlar alındı.

## Güncelleme kuralı (zorunlu)

Her güncellemede bu sıra izlenir; hiçbir adım atlanmaz:

1. **Kişisel posta bilgilerini ayıkla.** Commit öncesi gerçek e-posta
   adresleri, kullanıcı adları, parolalar, gerçek sunucu adları/IP'leri ve
   kişi listeleri koddan/dokümandan çıkarılır; yerine yer tutucu yazılır
   (`ornek@ornek.com`, `mail.kurum.gov.tr`, `KURUM\kullanici`).
   `hesap.json` / `kisiler.json` hiçbir zaman depoya eklenmez.
2. **Sızıntı denetimi yap.** `git status` incelenir ve izlenen dosyalarda
   şu aramalar temiz çıkmalıdır (yer tutucular hariç):
   ```bash
   git grep -n -I -E '[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}'
   git grep -n -i -I -E 'parola|şifre|password'
   ```
3. **Testleri çalıştır.** `./tests/run_all.sh` geçmeden commit edilmez.
4. **GitHub'ı güncelle.** Değişiklikler commit'lenip `origin/main`e gönderilir:
   `git push origin main`.
5. **Yerel kurulu kopyayı güncelle.** Menüdeki Postacım yeni sürümü
   çalıştırmalıdır:
   ```bash
   ~/.local/share/postacim/venv/bin/python -m pip install .
   # ya da: ./kur.sh
   ```

Bugün büyük ilerleme kaydedildi. Proje artık **çalışır durumda**.
Bugün büyük ilerleme kaydedildi. Proje artık **çalışır durumda**.

## Kurum teşhisi (doğrulandı)
- `mail.kurum.gov.tr` → Exchange 2013 CU2 (build 15.2.x, DAG/CAS sunucu adları gizlendi)
- **IMAP (143/993) ve SMTP (25/465/587) dışarıdan KAPALI** → Thunderbird/Evolution/Outlook bağlanamaz
- **EWS açık**: `https://mail.kurum.gov.tr/EWS/Exchange.asmx` (NTLM)
- **REST API açık**: `https://mail.kurum.gov.tr/api/v2.0/` (MAPI over HTTP, NTLM)
- NTLM NetBIOS alanı: `KURUM`, kullanıcı: `KURUM\kullanici`

## 🔴 sunucu yöneticilerine bildirilmesi gerekenler (sunucu tarafı hatalar)
Aşağıdaki EWS işlemleri **sunucuda** hata veriyor; istemci tarafında düzeltilemez.
`GetFolder`, `GetItem`, `CreateItem`, `MoveItem`, `DeleteItem`, `SyncFolderItems` çalışıyor.

| EWS işlemi | Hata | Not |
|---|---|---|
| `FindItem` | `ErrorInternalServerError` (500) | Tüm klasörlerde, tüm şema sürümlerinde. **Çözümü: `SyncFolderItems`** |
| `UpdateItem` | "The request is invalid." | **İstemci hatasıydı** (`m:ItemChange` → `t:ItemChange`); 22.11 gece düzeltildi, okundu işareti artık yazılıyor |
| `GetAttachment` | `ErrorInternalServerError` (500) | **Aşıldı**: ek mesajın MIME içeriğinden çıkarılıyor (`GetItem` + `IncludeMimeContent`) |
| `ResolveFolder` | "The request is invalid." | Kullanılmıyor, alternatif yol var |

Ayrıca **TMG (203.0.113.10) filtreleri**:
- Sorgu dizesinde `$` karakteri → "Request Rejected" (`$top`, `$filter`, `$skip` kullanılamıyor)
- `PUT` / `PATCH` / `DELETE` metotları engelli (yalnız `GET` ve `POST`)
- `/owa/auth.owa` POST'u (form girişi) engelli → OWA tarayıcı dışından kullanılamıyor
- REST API sayfa boyutu **10** ile sınırlı (`Prefer: odata.maxpagesize` yok sayılıyor)
- REST'te mesaj kimliğindeki `/` yol ayracına dönüşüyor → kimlik bazlı REST çağrıları çalışmıyor

## Çalışan kısımlar
- `ews.py`: SOAP istemcisi (NTLM), **sürüm hataları düzeltildi**, geçici hatalarda retry
- **Mesaj listeleme `SyncFolderItems` ile**: 512'şer adetlik gruplar, `SyncState` ile
  artımlı devam → tüm klasör (1453 mesaj ≈ 3,5 sn) tek tekil listede
- `config.py`: ayarlar `~/.config/postacim/hesap.json` (0600)
- `ui.py`: klasör listesi (sayaçlı), mesaj listesi, **sayfalama**, okuyucu, arama
  (istemci tarafında, tüm klasör üzerinde), yazma, taslak, sil/taşı, ek indirme
- `tests/`: `test_ews.py` (bağlantı + liste + arama), `ui_smoke.py` (arayüz duman testi),
  `finditem_dene.py`, `alternatif_dene.py`, `rest_kesif.py`, `eas_dene.py`, `sync_dene.py`

## Bugün düzeltilen hatalar
1. **Sunucu sürümü hatası (kritik)**: `istek()` cevaptaki `15.2` değerini
   `RequestServerVersion` olarak gönderiyordu → sunucu "The request is invalid"
   veriyordu ve **ilk istekten sonraki tüm istekler** bozuluyordu. Artık
   `15.2 → Exchange2013` eşlenmesi yapılıyor.
2. `MessageDisposition` öznitelik yerine eleman olarak yazılıyordu → gönderme çalışmıyordu
3. `t:EmailAddress` adresi öznitelik değil **metin** → alıcılar ve gönderen adresleri boştu
4. `t:AttachmentId` öznitelik olarak okunmalıydı → ek kimliği boştu
5. `taslağa_kaydet` içinde `MessageDisposition="SaveOnly"` yoktu → taslak kaydetme çalışmıyordu
6. `ui.py`: `Listbox.selection()` yok → `curselection()` kullanılmalı
7. `ui.py`: klasörler yüklenirken `yenile()` kendini çağırıyordu (sonsuz döngü)
8. `ui.py`: Tk değişkenleri arka plan iş parçacığından okunuyordu → "main thread is not in main loop"
9. `ui.py`: kuyruk mesajları ("okundu", "okundu_hata") hata sanılıyordu, oturum düşüyordu

## Arayüz güzelleştirmesi (2026-11-16 akşam)
- **Düğme ikonları**: `postacim/ikonlar/*.png` (Pillow ile üretildi, 20x20) —
  Yenile, Yeni e-posta, Ara, Temizle, Önceki, Sonraki, Gönder, Taslak, Ek ekle
- **Klasör ikonları**: `klasor_<kimlik>.png` (inbox, sentitems, drafts,
  deleteditems, junkemail, archive, outbox). Klasör listesi `Listbox`'tan
  **`ttk.Treeview`**'a geçirildi (Listbox görüntü desteklemez); `iid` = klasör
  kimliği olduğu için seçim doğrudan kimlikle yapılıyor, satır yüksekliği 26px
- **Bölmeler arası boşluk kaldırıldı**: `pack` sırası yüzünden Treeview kendi
  doğal genişliğinde (690px) kalıyor, pane ile arasında ~83px boşluk oluşuyor,
  sayfalama çubuğu ise o dar boşluğa sıkışıp "Sonraki" kırpılıyordu.
  Çözüm: sayfalama çubuğu önce, liste alanı sonra paketlendi; sütun
  genişlikleri düşürüldü (esneme sütunları fazlayı alıyor), kaydırıcı önce
  paketlendi
- Okuyucu `Text` widget'inin PanedWindow'a talebi 80 karakterden 40'a
  indirildi → pane paylaşma düzeldi (liste 486→593px, okuyucu 280→477px)
- Yazma penceresi: düğmeler alt bara taşındı (0. sütun etiketleri
  genişletiyordu, "Kime/Konu" alanlarından ayrı düşüyordu)
- `tests/ui_smoke.py`'ye yazma penceresi açma kontrolü eklendi
  (ikon `KeyError`'ı burada yakalandı)

## Modern tema (2026-11-16, gece)
- **sv-ttk (Sun Valley)** kuruldu → Windows 11 tarzı düz görünüm
  (`requirements.txt`'e eklendi, `run.sh` kendiliğinden kurar)
- **Görünüm menüsü**: Açık/Koyu tema seçimi, tercih `hesap.json`'a yazılır
  (`tema` anahtarı) ve açılışta uygulanır
- Tema-bağımlı renkler tek yerden yönetiliyor (`_tema_renkleri`,
  `_vurgu_rengi`, `_stil_uygula`): okuyucu `Text`, yazma penceresi
  `Text`/`Listbox`, durum çubuğu — koyu temada beyaz kutu kalmıyor
- Tk klasik **menüleri tema almaz** → `_menu_renkleri()` ile seçenek
  veritabanından boyanıyor, tema değişince menü yeniden kuruluyor
- Yazı tipi: **Ubuntu 10** (okuyucu gövdesi önce monospace'ti → orantılı)
- Doğrulama: ekran görüntüleri piksel histogramıyla ölçüldü
  (açık tema %79 açık, koyu tema %94 koyu)

## Sağ tuş menüsü (2026-11-16, gece)
Mesaj listesinde sağ tuş → **Outlook tarzı bağlam menüsü** (`_mesaj_menu_olustur`):

| Öğe | Not |
|---|---|
| Yanıtla / **Yanıtla Herkese** / İlet | Herkese: Kime = gönderen + tüm alıcılar, Bilgi = orijinal Cc (kendim hariç) |
| Okundu olarak işaretle / Okunmadı yap | ✓ çalışıyor (22.11 gece düzeltildi) |
| **Taşı →** | alt menüde klasör listesi (aktif klasör hariç) |
| Sil | Silinmiş Öğeler'e taşır |
| Kopyala (`Ctrl+C`) | Gönderen/Kime/Konu/Tarih + gövde → pano |
| **Farklı Kaydet (.eml)** | `mesaj_mime()` ile tam MIME diske yazılır |
| **Bilgiler…** | özellik penceresi (gönderen, Kime, Cc, tarih, kimlik…) |
| Yenile | F5 |

Eklemeler: yazma penceresine **Bilgi (Cc)** alanı eklendi (`gonder(cc=...)`),
`Mesaj.alici`/`Mesaj.bilgi` alanları `mesaj_detay`'da dolduruluyor,
`Ctrl+Shift+R` kısayolu, liste üzerinde `Ctrl+C` (Text widget'larını bozmaz).

## Gönder/Al butonu (2026-11-18)
- **Araç çubuğu + `F9` + Dosya menüsü: "Gönder/Al"** — kutu istendiği an
  tazelenir (Outlook'taki gibi). Ne yapar:
  1. klasör sayaçlarını çeker (`GetFolder`)
  2. onbellekli **tüm klasörlerde** artımlı güncelleme yapar (mevcut
     `SyncState` ile klasör başına tek `SyncFolderItems` isteği — tam senkron
     3,5-5 sn iken **~0,1 sn**)
  3. aktif klasörün listesini onbellekten yeniler; durum çubuğunda
     "Gönder/Al tamamlandı — N yeni mesaj • 50 mesaj / 1454 toplam"
- `ews.py`: `guncelle()` eklendi; `_senkronize` artık onbellek güncelken tam
  yeniden çekmek yerine yalnızca değişiklikleri alır; `mesajlar(..., tazele=False)`
  saf onbellek okuması yapar
- **Sayfalama artık ağ yapmıyor** (`tazele=False`) → sayfa geçişleri anlık
- `ikonlar/gonder_al.png` (çift ok, Pillow 20x20)
- Testler: `tests/guncelle_dene.py` (canlı: 1454 mesaj, 5,2 sn → 0,1 sn,
  sayı tutarlı), `ui_smoke.py`'ye Gönder/Al kontrolü eklendi

## Hesaptan Çıkış (2026-11-18)
- **Dosya menüsü + üst çubuk düğmesi + `Ctrl+Q`: "Hesaptan Çıkış…"**
  — Outlook'taki gibi oturumu kapatır:
  1. onay sorulur; iptal edilirse hiçbir şey değişmez
  2. `istemci = None`, kuyrukta bekleyen sonuçlar yutulur (`oturum=False`
     bayrağı ile), mesaj/klasör onbellekleri ve arayüz temizlenir
  3. **kayıtlı parola silinir** (`ayarlar`), durum çubuğunda "Oturum kapalı"
  4. 200 ms sonra giriş penceresi açılır; bağlanılırsa oturum yeniden açılır
- Üst çubukta en sağda, kırmızı kapı-çıkış ikonu (`ikonlar/cikis.png`,
  Pillow 20×20)
- Çıkış sonrası geciken arka plan sonuçları hata dialogu açmadan yutulur
- Testler: `ui_smoke.py`'ye menü + düğme varlık kontrolü eklendi; canlı
  çıkış/giriş akışı ayrı doğrulandı (iptal, onay, kuyruk yutma, yeniden giriş)

## Bağlanamama → giriş penceresi (2026-11-18)
- **Kimlik hatası (401) veya sunucuya ulaşılamadığında kullanıcı adı–parola
  yeniden sorulur** — önce sadece hata dialogu çıkıyordu, kullanıcı hatalı
  bilgiyle tekrar denemek zorundaydı
- `_arka_plan`: `EwsYetkiHatasi` ve `requests.RequestException` artık
  `("giris", mesaj)` turuyla kuyruğa düşer (diğer EwsHatalar eskisi gibi
  hata dialogu)
- `_giris_iste()`: istemci sıfırlanır → giriş penceresi açılır →
  onaylanırsa `yenile()` ile otomatik yeniden bağlanır; iptal edilirse
  durum çubuğunda "giriş iptal edildi"
- `_kimlik_sor(hata=...)`: hata metni pencerenin başında kırmızı etiket
  olarak gösterilir (kullanıcı neden yeniden sorulduğunu görür)
- **Yeniden giriş kuyruğu güvencesi:** `_giris_soruluyor` bayrağı ile aynı
  anda ikinci bir giriş penceresi açılmaz (kuyrukta art arda401+Ağ hatası
  gelse tek pencere açılır)
- Testler: `ui_smoke.py`'ye 401 + ağ hatası senaryosu, iptal/onay akışı ve
  yeniden bağlanma kontrolü eklendi (canlı: 2 istek → tek tip akış,50 mesaj
  yeniden yüklendi)

## Çoklu seçim + taşıma sonrası yenileme (2026-11-18)
- **Mesaj listesi `selectmode="extended"`:** Ctrl ile tek tek, Shift ile
  aralık seçimi (Outlook tarzı) — `browse` iken tek seçime bağlıydı
- `_secili_mesajlar()`: seçili satırlardan mesaj listesi (sıralı) — sil,
  taşı, sağ tuş "Taşı" hepsi çoklu çalışır
- Çoklu seçimde durum çubuğu: "N mesaj seçildi — Sil/İçin Delete veya sağ tuş";
  önizleme ilk mesaja açılır
- **Taşıma/silme sonrası otomatik yenileme:** `_tasi_cek` artık
  `("yenile", …)` sonucu döndürür → `_sonuc_isle` durumu yazar ve `yenile()`
  çağırır (liste + klasör sayaçları tazelenir); eskisiyle sadece durum
  yazılıyordu, taşınan mesaj listede görünmeye devam ediyordu
- Onay penceresi çokluda: "Seçili N mesaj Silinmiş Öğeler'e taşınacak."
- Sağ tuş menüsü seçimi bozmaz (seçimdeyse korur, değilse o satıra düşer)
- Testler: `ui_smoke.py`'ye selectmode + 3'lü seçim + "yenile" sonucu kontrolü
  eklendi (canlı: 3 mesaj seçildi, yenile 1 kez çağrıldı)

## Ek listesinde uzantı ikonları (2026-11-18)
- **Ekler çerçevesi Listbox → Treeview** (`Ek.Treeview`, satır 26px): Listbox
  ikon desteklemiyordu; Treeview `image=` ile satır başına ikon gösterir
- **11 yeni ikon** (`ikonlar/ek_*.png`, Pillow 18×18): kıvrımlı sayfa +
  renkli alt bant + uzantı etiketi —
  `ek_pdf` (kırmızı), `ek_doc` (mavi), `ek_xls` (yeşil), `ek_ppt` (turuncu),
  `ek_zip` (sarı), `ek_resim` (mor), `ek_metin` (gri), `ek_eposta` (turkuaz),
  `ek_video` (menekşe), `ek_ses` (pembe), `ek_dosya` (genel gri)
- `_ek_ikonu(dosya_adi)`: uzantı → ikon eşlemesi (pdf/doc(x)/xls(x)/ppt(x)/
  zip/rar/7z/tar/gz/jpg…png/gif/webp/txt/log/md/json/xml/eml/msg/mp4…/mp3…);
  bilinmeyen uzantı → genel sayfa, ikon yoksa → `ek.png`
- `ek_indir()` Treeview API'ye taşındı (`selection()` + `int(iid)`), iid = sıra
  no; `hesaptan_cikis` temizliği `delete(*get_children())`
- Canlı doğrulama: "YEMEK LİSTESİ.xlsx" satırında ikon görünüyor,
  11 uzantı eşlemesi + bilinmeyen uzantı sıfır hata

## Otomatik yenileme (2026-11-19)
- **Dosya → Otomatik yenileme** alt menüsü: Kapalı / 30 sn / **1 dakika** (varsayılan)
  / 2 dk / 5 dk; tercih `hesap.json` → `otomatik_yenile` (saniye, 0 = kapalı)
- Her tikte **seçili klasör** sessizce tazelenir: `klasor_listesi()` (sayaçlar) +
  `mesajlar(tazele=True)` (artımlı `SyncState`, ~0,1 sn) — yalnızca bağlıyken;
  devam eden bir iş varsa tik atlanır (`_is_sayaci` / `_otomatik_bekliyor`),
  giriş penceresi asla otomatik açılmaz
- Durum çubuğu **yalnızca yeni mesaj gelirse** yazılır ("Otomatik yenileme — N
  yeni mesaj"); aksi halde sessiz
- **Seçim ve kaydırma korunur** (polling'li arayüzde liste zıplamasın): yenileme
  öncesi seçili mesajların `item_id`'leri alınır, liste yeniden kurulunca aynı
  mesajlar geri seçilir ve `yview_moveto` ile kaydırma konumu iade edilir
- Yapay `<<TreeviewSelect>>` olayları **yutulur** (`_secim_olayi_yut`: delete +
  selection_set başına 1) — yenileme detay çekmez (`GetItem`), "N mesaj seçildi"
  durumu bozulmaz. Denendi: Tk'de olaylar `selection_set`'te senkron değil,
  idle'da kuyruklanıyor; unbind/rebind ile bastırılamıyor
- `hesaptan_cikis` sayaçları sıfırlar; zamanlayıcı `_otomatik_baslat/_durdur`
  ile yönetilir (aralık değişince yeniden kurulur)
- Doğrulama: çevrimdışı işlevsel test (Xvfb, sahte istemci) 16/16 — zamanlayıcı
  tıklaması, seçim/kaydırma koruması, sessizlik, atlama koşulları, tercih
  kaydı; `ui_smoke.py`'ye menü + seçim koruması kontrolü eklendi

## Kişi tamamlama (2026-11-19)
Outlook'taki "Kime/Cc'ye yazınca kurum e-postasını bulma" eklendi.
- **`ews.py` → `cozumle(metin)`**: EWS **`ResolveNames`** (SearchScope
  `ContactsActiveDirectory`, olmazsa `ActiveDirectory`; `ReturnFullContactData=false`)
  → `[(ad, eposta), ...]`. `ErrorNameResolutionNoResults` boş liste sayılır
- **`config.py` → `KisiDefteri`**: `~/.config/postacim/kisiler.json` (0600),
  en yeni kullanılan başta, en çok 200 kişi; gönderilen kişiler (`gonder()`)
  ve seçilen öneriler deftere yazılır
- **`ui.py` → `_AdTamamlama`**: Kime/Bilgi Entry'lerine bağlı. İmleçteki son
  parça (`;`/`,` sonrası) **kurum dizininde filtrelenir** — kurum e-postası
  olan tüm kişiler arasından eşleşmeler önerilir (yazma durunca 200 ms sonra
  `ResolveNames`, arka planda). Açılır liste (Toplevel+Listbox) Entry
  altında; `↓/↑` gezinme, `Enter`/`Tab`/tıklama kabul ("Ad Soyad <adres>; "),
  `Esc` kapatır, odak kaybı kapatır. Değiştirilen aralık imleçteki parça
  (ortadan düzenleme de çalışır); parça değiştiyse **bayat öneri kabul
  edilmez** (`_sonuc_parca` kontrolü). Kayıtlı kişiler **yalnızca** kurum
  dizini kullanılamadığında (`cozum_yok`) yedek olarak önerilir
- **Dayanıklılık**: pencere kapanınca bekleyen `after` geri çağrıları
  `TclError`'a karşı korumalı; Tk'ye yalnız ana iş parçacığında dokunulur
- **Sunucu durumu (2026-11-19 canlı doğrulandı):** `ResolveNames` bu sunucuda
  **çalışıyor**. Kritik pürüz: sunucu `<t:Resolution>` (**types** alanı)
  döndürür — `m:Resolution` aranınca **boş liste** görünüyordu ("çalışmıyor"
  belirtisinin kök nedeni); `cozumle()` artık iki isim alanına da bakıyor.
  Eşleşme **adın herhangi bir parçasında** oluyor (ad/orta ad/soyad/e-posta):
  "ali" → ALİ KARA; "ayse y" → aynı kişi; "meh" → 20 kişi.
  Sunucu istek başına en çok **100** sonuç veriyor (`IncludesLastItemInRange=false`),
  `cozumle()` en fazla 20 döndürüyor. Eşleşme yoksa `ErrorNameResolutionNoResults`
  yerine `NoError` + boş `ResolutionSet` geliyor (ikisi de boş liste sayılır).
  İstemci desteklemiyorsa `cozum_yok` bayrağı + tek uyarı (yedek: kayıtlı kişiler)
- `_adres_listesi` artık "Ad Soyad <adres>" biçiminden adresi ayıklıyor
  (Outlook'tan yapıştırılan listeler de gönderilir)
- Doğrulama: **canlı** (2026-11-19, gerçek sunucu): yazma penceresinde
  "ali" yazınca dizinden "ALİ KARA" bulundu ve `Enter` ile alana
  yazıldı. Çevrimdışı test 21/21 (Xvfb, sahte istemci) — XML üretimi ve
  ayrıştırma (t:Resolution), kapsam reddi → yedek kapsam, **yalnız dizin
  sonuçları** (kayıtlı kişiler karışmıyor), bayat öneri reddi, çoklu alıcıda
  son parçanın tamamlanması, Esc/Enter, yedek (kayıtlı kişiler) yolu,
  hata → bayrak+uyarı; `ui_smoke.py`'de yedek yolu sabit kontrol + canlı
  dizin sayısı raporu

## Çoklu hesap + Gmail (IMAP) desteği (2026-11-19)

**Talep:** "farklı e-posta adreslerimi de ekleyebilmeyi istiyorum, mesela
gmail.com adresimi de eklemek istiyorum." → Evolution tarzı: her hesabın
klasörleri hesap adının altında ayrı ayrı, tek tıkla geçiş.

### Kararlar (kullanıcı onaylı)
- Gmail erişimi: **Uygulama Parolası** (2 Adımlı Doğrulama açıkken üretilen
  16 haneli parola; OAuth2 değil)
- Görünüm: **birleşik gelen kutusu değil** — hesap → klasör hiyerarşisi

### `config.py` — çoklu hesap modeli
- `hesap.json` → `{"hesaplar": [...], "aktif": id, tema/otomatik_yenile…}`;
  eski tek-hesap biçiminden **otomatik göç** (`_goc_et`: kullanici/parola/
  sunucu/yontem/son_klasor ilk hesaba taşınır)
- Hesap türleri: `ews` (kurum) ve `imap` (Gmail; gelen/giden sunucu+port+ssl)
- Yeni API: `hesaplar()/hesap()/aktif_hesap()/hesap_ekle/hesap_guncelle/
  hesap_sil/aktif_ayarla`; `son_klasor` artık **hesap başına**
- Geriye dönük uyum: `al("kullanici")` gibi eski anahtarlar aktif hesaptan
  okunur → eski test betikleri (`*_dene.py`) değişmeden çalışır

### `imap.py` (yeni) — `ImapIstemci`
`EwsIstemci` ile **aynı arayüz** (`klasor_listesi/mesajlar/guncelle/
mesaj_detay/ek_indir/mesaj_mime/gonder/taslağa_kaydet/cozumle/
okundu_isaretle/tasi/kalici_sil`) — `ui.py` ikisini aynı çağrılarla kullanır.
- **Bağlantı:** `IMAP4_SSL` (ya da STARTTLS); kimlik hatası →
  `EwsYetkiHatasi` (giriş penceresi), ağ hatası → `RequestException`
  (yine giriş), kopan bağlantıda **1 otomatik yeniden bağlanma**
- **Klasörler:** `LIST` + SPECIAL-USE eşleme (`\Sent`→sentitems, `\Trash`→
  deleteditems, `\All`→archive…), `\Noselect` atlanır, `INBOX` ad yedeği;
  adlar **değiştirilmiş UTF-7** ile taşınır (`_utf7_kodla/_utf7_coz` —
  komutlar için ham ascii, görünüm için çözülmüş: "Gönderilmiş"), `[Gmail]/`
  öneki sadeleştirilir, bilinmeyen klasörler kendi adıyla; `STATUS` ile
  sayaçlar
- **Mesajlar:** `UID SEARCH ALL` + `UID FETCH (RFC822.HEADER)` — zarf
  onbelleği (en yeni 5000), bayraklar (`\Seen`→okundu), tarih `Date`
  başlığından, ek sezgisi multipart'tan; sayfalama/arama istemci tarafında
  (EWS ile aynı davranış); **arama sunucu tarafında** `SEARCH TEXT/FROM`
  (UTF-8; desteklemeyen sunucuda tam onbellek + istemci filtresine düşer)
- **Detay/ek/.eml:** `UID FETCH (BODY.PEEK[])` → MIME onbelleği (8 mesaj);
  gövde HTML→düz metin; ekler `Content-Disposition: attachment`'tan;
  `ek_indir` mevcut `_mime_den_ek` ile
- **Yazma:** SMTP (`SSL465`/STARTTLS) ile gönderme; Gmail'e gönderilen için
  Sent kopyası **atlanır** (Gmail SMTP gönderisini kendisi kaydeder), diğer
  sunucularda `APPEND`; taslak `APPEND` (`\Draft`); **okundu/taşıma/silme
  IMAP'ta çalışır** (STORE/MOVE — EWS'teki UpdateItem bozukluğu yok)
- Kişi çözümleme yok → `cozum_yok` (UI, IMAP aktifken kurar) → kayıtlı
  kişilerden öneri

### `ui.py` — hesap ağacı ve geçiş
- **İki kademeli klasör ağacı:** kök `hesap:<id>` (hesap adı), çocuk
  `<hesap_id>|<klasor>`; iid ayrıştırılır, başka hesabın klasörüne tıklayınca
  `_hesap_degistir()` çalışır
- **`_hesap_degistir`:** kuyruk yutulur → aktif değişir → başlık/menü
  işareti/cozum_yok güncellenir → istemci önbellekten alınır (yoksa kurulur)
  → klasör varsa mesajlar yüklenir, yoksa `yenile()`; giriş gerekirse açılır
  (iptal → False, menü işareti geri alınır)
- **İstemci önbelleği** `_istemciler` (hesap başına bir istemci; hesaptan
  çıkışta/silmede düşer); klasör listeleri `_hesap_klasorleri`
- **Diğer hesapların klasörleri** açılışta arka planda çekilir
  (`_diger_hesaplari_yukle`,1.5 sn sonra; parolası olmayanlar atlanır) →
  kuyrukta `("ok", ("hesap_klasorler", id, klasorler))` biçimiyle gelir
- **Hesaplar menüsü:** radyo düğmeleriyle hızlı geçiş + Hesap Ekle/Düzenle/Sil
- **`HesapPenceresi`:** tür radyoları (Kurum EWS / Gmail veya IMAP) — düzenlemede
  kilitli; türe göre alan çerçeveleri; **"Gmail'e ayarla"** düğmesi
  (imap.gmail.com:993, smtp.gmail.com:465); Gmail için IMAP yardım metni
  (uygulama parolası + IMAP etkinleştirme); yeni hesap kaydedilince ona geçilir
- **Giriş penceresi hesap duyarlı:** IMAP'ta "E-posta / Uygulama parolası"
  alanları + Gmail yardımı; alan boşsa kayıtlı parola korunur
- **Hesaptan Çıkış yalnız aktif hesabı** etkiler (diğerleri bağlı kalır);
  `hesaptan_cikis` → `_kuyrugu_yut`/`_mesaj_alanini_temizle` yardımcıları
  paylaşıldı; başlık/yeni e-posta penceresi aktif hesadı gösterir

### Testler (hepsi geçti)
- `tests/coklu_hesap_test.py` (**çevrimdışı**, 50+ kontrol): göç, ekle/sil,
  geriye dönük `al()`; UTF-7, LIST ayrıştırma, SPECIAL-USE eşleme, STATUS,
  zarf onbelleği/sıralama/sayfalama, sunucu araması, MOVE/STORE/APPEND,
  yanlış parola → `EwsYetkiHatasi`, SMTP gönderimi (mock'lu `imaplib`/`smtplib`)
- `tests/hesap_ui_test.py` (**çevrimdışı, Xvfb**, 34 kontrol): 2 hesaplı
  ağaç, klasöre tıklayınca geçiş (aktif/başlık/mesaj/cozum_yok/menü işareti),
  geri dönüş, Hesaplar menüsü, HesapPenceresi + Gmail hazır ayarı + kaydet,
  hesap silme
- `tests/ui_smoke.py` (**canlı EWS**): göç sonrası gerçek sunucuda tam akış
  (7 klasör, 1448 mesaj, arama, sayfalama, Gönder/Al, giriş hata akışları,
  çoklu seçim, yazma penceresi, kurum dizini, ek indirme) + yeni hesap
  ağacı/menü varlık kontrolleri — **istisna yok**
- `py_compile` OK; yeni bağımlılık **yok** (imaplib/smtplib/email stdlib)

### Bilinen sınırlar
- Gmail hesabında kurum dizini (ResolveNames) yok → kişiler `kisiler.json`
- Ek sezgisi listede multipart'tan (kesin `HasAttachments` değil); indirme
  MIME üzerinden kesin
- Klasör sayaçları `STATUS` ile klasör başına bir istek (çok etiketli
  Gmail'de ilk yükleme birkaç saniye sürebilir)
- Gmail uygulama parolası + IMAP etkinleştirme kullanıcının elinde (README'de
  adım adım)

### Düzeltme: "Beklenmeyen Hata: LIST command error" (2026-11-19)

**Şikayet:** Gmail hesabı eklenince "Beklenmeyen Hata — List command error"
dialogu çıktı.

**Kök neden (ölçüldü):** `klasor_listesi()` `imap.list("", "*")` çağrısında
dizin argümanı **boş string** geçiliyordu; imaplib bunu argümansız bırakınca
sunucuya `LIST  *` (tek argüman) gidiyordu → RFC'ye aykırı → sunucu **BAD**
yanıtı → imaplib `IMAP4.error("LIST command error: BAD …")` fırlatıyordu ve
bu hata hiçbir yerde yakalanmadan `_arka_plan`'ın genel `except`'ine düşüp
"Beklenmeyen Hata" olarak gösteriliyordu. imaplib'in doğru kullanımı (ve
kendi `list()` varsayılanı) tırnaklı boş: `'""'` → `LIST "" *`.

**Düzeltmeler:**
1. `imap.py → klasor_listesi()`: `self.imap.list('""', "*")` (ham tel
   doğrulandı: `EOBL2 LIST "" *`)
2. `imap.py → _komut()`: `IMAP4.error` (sunucunun NO/BAD reddi) artık
   **yeniden denenmeden** `EwsHata("IMAP komutu reddedildi: …")` olarak
   yukarı çıkar → arayüzde okunur Türkçe hata, "Beklenmeyen Hata" değil.
   (Bağlantı kopması `abort`/`OSError` olarak ayrılır: bir kez yeniden
   bağlanma korunur; `abort` > `error` alt sınıfı olduğu için sıralama önemli.)

**Testler (yeni ikisi de geçti):**
- `tests/coklu_hesap_test.py`'ye regresyon: sahte sunucu artık hatalı LIST
  argümanına **BAD** ile reddediyor → `EwsHata("IMAP komutu reddedildi:
  LIST command error: BAD …")` doğrulanıyor
- `tests/imap_yerel_sunucu_test.py` (**yeni**): gerçek `imaplib` üzerinden
  yerel mini IMAP sunucusuna bağlanır, **ham tel kaydını** denetler —
  `LIST "" *` gönderiliyor, hatalı `LIST  *` gönderilmiyor; LOGIN, STATUS,
  utf-7 klasör adı (`G&APY-nderilmi&AV8-`) ve sayaç okuma da doğrulanır

### Düzeltme: Gmail ağacı "Bağlanıyor"da takılıyordu + etiketler görünmüyordu (2026-11-19)

**Şikayet:** Gmail Inbox yüklenirken "Bağlanıyor" aşamasında kalıyordu;
ayrıca Gmail'deki özel klasörler (etiketler) hiç görünmüyordu.

**Teşhis (üç ayrı hata, hepsi ölçüldü):**

1. **`TclError: value for "-image" missing`** — `_agaci_yenile()` her klasör
   için `image=self.ikon.get(...)` veriyordu. Eski düz ağaçta tüm EWS
   klasörlerinin ikonu vardı; **Gmail etiketlerinin ikonu olmadığı** için
   `None` gidiyordu ve `ttk.Treeview.insert` bunu **çökertiyordu**
   (Xvfb'de doğrulandı: `image=None` → hata). Ağaç kurulumu yarıda kalıyor,
   etiketler hiç eklenmiyordu. → İkon varsa veriliyor, yoksa `image`
   seçeneği hiç gönderilmiyor.
2. **Kuyruk yoklama ölüyordu** — `_kuyruk_yokla` içindeki istisna zinciri
   kırılıyordu (`except queue.Empty` dışında kalan hata fonksiyonu sonlandırıyor
   ve sonraki `after(120, …)` hiç kurulmuyordu) → arayüz süresiz
   "Bağlanıyor"da kalıyordu. → Her sonuç kendi `try`'sinde; zamanlayıcı
   `finally` ile her koşulda yeniden kuruluyor; ayrıca `image` hatası da
   bu sayede dialogla karşılanıyor.
3. **imaplib bağlantısı bozulunca kurtarılamıyordu** — canlı testte üst üste
   `command SELECT/FETCH/LIST illegal in state LOGOUT` görüldü:
   - `_komut()` yeniden denemede **eski bağlı metodu** (`self.imap.select`)
     kullanıyordu; bağlantı yenilenince bile LOGOUT'taki eski nesneye
     basıyordu → artık **metot adıyla** (`_komut("select", …)`) çağrılıyor,
     her denemede `getattr(self.imap, …)` taze bağlantıyı çözüyor.
   - Sunucu BYE gönderince imaplib `state='LOGOUT'`'ta kalıyor ve sonraki
     her komut reddediliyordu → `_baglan()` LOGOUT'taki bağlantıyı atıp
     yeniden bağlıyor; `_komut()` hata yolunda da LOGOUT görürse bir kez
     yeniden deniyor.
   - **Eşzamanlı kullanım:** imaplib bağlantısı birden fazla arka plan iş
     parçacığıyla aynı anda kullanılamaz (yanıt eşleşmesi bozulur) →
     `_kilitli` dekoratörü (RLock) tüm genel işlemleri (`klasor_listesi`,
     `mesajlar`, `gonder`, `tasi`, …) seri yürütüyor.

**Doğrulama:**
- `tests/coklu_hesap_test.py`'ye3 regresyon: komut ortasında LOGOUT →
  otomatik yeniden bağlanma; kalıcı LOGOUT → bağlantı atılıp yeniden liste;
  hatalı LIST → okunur `EwsHata` (toplam testler geçti)
- `tests/imap_yerel_sunucu_test.py` (tel denetimi) geçti
- `tests/hesap_ui_test.py`'ye ikonsuz/türkçe etiketli klasör eklendi —
  ağaç hatasız kuruluyor
- **Canlı `ui_smoke.py` (gerçek Gmail + EWS):** ✓ istisna yok — 26 Gmail
  klasörü (tüm etiketler listelenmişti),50 mesaj
  yüklendi, LOGOUT hatası kalmadı

**Bilinen davranış:** Gmail'de ilk açılışta tüm gelen kutusunun zarfları
çekilir (en yeni5000 mesaj,200'lük gruplar) — büyük kutularda ilk liste
10-20 sn sürebilir; durum çubuğunda "Mesajlar yükleniyor…" görünür.

## Klasör silme (sağ tuş) (2026-11-19)

**Talep:** "önceden oluşturduğum herhangi bir klasörü silmek istiyorum"
(Gmail etiketleri).

### Değişiklikler
- **`imap.py → klasor_sil(kimlik)`**: IMAP `DELETE <klasör>`; `_kilitli`.
  - **Özel klasör koruması:** `SIRA` (inbox, sentitems, drafts, deleteditems,
    junkemail, archive, outbox) silinemez → `EwsHata` (Gmail'in "Tüm
    Postaları" (\All→archive) da bu korumada)
  - Sunucu reddederse (NO → `tip != "OK"`, BAD → `_komut` hata yolu) okunur
    `EwsHata`; başarıda klasör onbellekleri (`_onbellek`, `_klasor_adlari`,
    `_secili`) temizlenir
- **`ui.py`:**
  - Klasör ağacına **sağ tuş** bağlandı (`<Button-3>` → `_klasor_menusu`);
    tıklanan satır seçilir, hesap düğümünde menü açılmaz
  - `_klasor_menu_olustur(iid)`: **"Klasörü Sil…" yalnız aktif IMAP
    hesabında + özel olmayan klasörde** (EWS hesaplarında ve başka hesapların
    klasörlerinde öğe yok → menü hiç açılmaz)
  - `klasor_sil(kimlik, ad)`: onay penceresi (Gmail'de etiket kaldırılır,
    **mesajlar silinmez** açıklamasıyla) → arka planda `_arka_plan` →
    `("yenile", "Klasör silindi")` sonucu → klasör listesi + sayaçlar
    yenilenir; silinen klasör aktifse ilk klasöre düşülür
    (`_klasorleri_doldur` mekanizması)

### Testler (hepsi geçti)
- `coklu_hesap_test.py`: inbox silme → koruma hatası; `DELETE "Proje X"`
  komutu + haritadan düşme; sunucu reddi → okunur `EwsHata`
- `imap_yerel_sunucu_test.py`: **tel denetimi** — `HMDA6 DELETE "Proje X"`
  ham komutu doğrulandı
- `hesap_ui_test.py`: aktif IMAP'te menü yalnızca özel olmayan klasörde;
  başka hesapta/EWS'te menü yok; onay akışında `istemci.klasor_sil`
  çağrılıyor

## Gövde resimleri — Evolution tarzı yer tutucu (2026-11-20)

HTML iletilerdeki `<img>` ögeleri düz metin dönüşümünde sessizce atılıyordu;
resimler hiç görünmüyordu (kurum iletilerindeki logolar, uzak görseller vb.).

### Değişiklikler
- **`ews.py`** — `Resim` veri modeli (`ad`, `kaynak`, `yer_tutucu`);
  `Ek.content_id` alanı (EWS `t:ContentId`/`t:ContentLocation`, IMAP
  `Content-ID` başlığı); `html_metni` artık `<img>` yerine **`[resim: ad]`**
  yer tutucusu bırakır ve `resimler` listesini doldurur (ad çözümlemesi:
  eşleşen ek → alt metni → URL/cid dosya adı). Yeni `resim_verisi()`
  çözümleyici: `data:` gömülü → `http(s)` indirme (401'de NTLM oturumuyla
  yeniden dener) → MIME'da Content-Id/dosya adı arama → `ek_indir` yedeği
- **`ui.py`** — yer tutucular tıklanabilir (mavi/altı çizili, imleç el);
  tıklayınca resim gövdede belirir (büyük resimler pencereye göre
  küçültülür; Pillow varsa JPEG vb., yoksa Tk'ın PNG/GIF desteği).
  Okuyucuda **"Resimleri göster (N)"** düğmesi tüm resimleri sırayla
  yükler; indirilemeyen resim gövdede "görüntülenemedi" olarak belirir.
  Mesaj değişince eski yükleme sonuçları gövdeye yazılmaz
- **`imap.py`** — ekler gövdeden önce toplanır (yer tutucu adları ek
  adlarından gelir); eklerde `content_id`
- **`requirements.txt`** — `Pillow` (JPEG/WebP vb. gövde resimleri için;
  yoksa PNG/GIF yine çalışır)

### Testler (hepsi geçti)
- `tests/resim_test.py` (yeni): yer tutucu üretimi, `resim_verisi`
  çözümlemesi (data URI, yerel http sunucu, 401→NTLM, cid→MIME, ek yedeği),
  EWS+IMAP `mesaj_detay` ayrıştırması, Xvfb altında arayüz: tıkla-göster,
  "Resimleri göster", düğme pasifleşmesi, mesaj geçişinde sıfırlama
- `imap_yerel_sunucu_test.py` + `ui_smoke.py`: regresyon yok (gerçek sunucu)

## HTML gövde gösterimi — tkinterweb (2026-11-20, akşam)

Okuyucu düz metin yerine artık gövdeyi **gerçek HTML olarak** çiziyor
(Tkhtml3 tabanlı `tkinterweb`): kalın/italik/renkli yazı, tablolar, fontlar,
bağlantı biçimleri korunur; dış bağlantılar tarayıcıda açılır.

### Değişiklikler
- **`ews.py`** — `govde_html_gosterim(mesaj, gecen)`: `<img>`'leri yer
  tutucu bağlantıya (`postacim-resim:sıra` → `[resim: ad]`) ya da
  çözüldüyse gömülü `data:` URI'ye çevirir; `script`/`base`/`meta refresh`
  atılır. Düz metin iletiler kaçırılmış `<pre>` olarak gösterilir.
  `data_uri_verisi()` dışa açıldı (arayüz gömme/engelleme için)
- **`ui.py`** — okuyucu `HtmlFrame` oldu (`tkinterweb` yoksa eski `tk.Text`
  okuyucuya düşer, `self.html_modu`). Yer tutucu bağlantısına tıklama
  `_html_baglanti_tikla` ile çözülür; çözülen resim Pillow ile
  küçültülüp PNG `data:` URI olarak gömülür ve sayfa yeniden çizilir.
  **`request_func` ile dış ağ istekleri engellenir** (uzak resimler,
  arka plan görselleri yüklenmez — gizlilik); yalnız gömülü `data:`
  resimlerine izin var. `script` kapalı, `forms`/`objects` kapalı
- **`requirements.txt`** — `tkinterweb`

### Gövde resimleri akışı (değişmedi)
Evolution tarzı: önce dosya adı yer tutucusu → tıklayınca resim gövdede →
"Resimleri göster" düğmesiyle tümü. İndirilemeyen resim "görüntülenemedi"
notuyla yerinde belirir.

### Testler (hepsi geçti)
- `tests/resim_test.py`: `govde_html_gosterim` birim testleri; arayüz
  testleri **iki modda** (düz metin + HTML) — yer tutucu görünümü,
  tıkla-göster, "Resimleri göster", dış istek engelleme, düğme
  pasifleşmesi, mesaj geçişinde sıfırlama
- `imap_yerel_sunucu_test.py` + `ui_smoke.py` (gerçek sunucu): regresyon yok

## Kalan sınırlar


- **Ek indirme**: sunucuda `GetAttachment` bozuk olduğu için tek ek, mailin tam
  **MIME içeriğinden** ayrılıyor → indirme sırasında mailin tüm ekleri ağdan
  geçer, diske **yalnızca tıklanan** yazılır; MIME mesaj başına bir kez çekilir
  ve oturum boyunca önbelleklenir (8 mail ile sınırlı)
- OWA tarayıcı dışından kullanılamıyor (TMG form girişini engelliyor) → OWA'ya bağlı
  bir yedek yol kurmak da mümkün değil
- Arama istemci tarafında (tüm klasör bellekte) — büyük klasörlerde biraz yavaş

## Sonraki adımlar (opsiyonel)
- [ ] sunucu yöneticilerinden `GetAttachment` hatasının giderilmesi
      (`GetAttachment` düzelirse ekler tek tek, MIME çekmeden iner)
- [ ] sunucu yöneticilerinden TMG'de `$` ve `PATCH`/`DELETE` engellerinin kaldırılması
      (REST API'nin sayfalama ve güncelleme yetenekleri açılır)
- [ ] EWS `FindItem` düzelirse liste yolu daha hızlı olur (senkronizasyon yerine)

---

# 2026-11-20/21 — Takvim özelliği + hata düzeltmeleri

> **Kaldığımız yer (21.11.2026 02:41):** Takvim sekmesi çalışıyor — Gmail
> (CalDAV) bağlı ve doğrulandı (28 randevu), Ay/Hafta/Gün görünümleri Evolution
> gibi çiziliyor. Aşağıdaki "Kalan işler" bölümünden devam edilecek.

## Takvim özelliği (20 Kas akşamı — bu belgeye henüz işlenmemişti)

Tek pencerede **Posta | Takvim** sekmeleri (Evolution tarzı).

### `caldav.py` (yeni, 591 satır) — CalDAV istemcisi
- Keşif (`kesfet`): `current-user-principal` → `calendar-home-set` → koleksiyonlar;
  **Google eski uçta bu özelliği vermez** → başlangıç adresi koleksiyon olarak denenir
- `randevular()` `calendar-query` REPORT (time-range), `randevu_ekle/guncelle/sil`
  PUT/DELETE; `If-Match` etag; ICS (RFC 5545) ayrıştırma/üretme — bağımlılık yok
- `RandevuKaydi` alanı EWS `Randevu` ile uyumlu (`item_id`/`change_key`/`gun`)

### `ews.py` — EWS takvimi
- `Randevu` modeli; takvim klasörü `SyncFolderItems` ile (`FindItem` bozuk olduğu için)
- `randevu_ekle` (CreateItem), `randevu_sil` (HardDelete),
  `randevu_guncelle` → **sil + yeniden oluştur** (takvimde `UpdateItem`
  `ErrorSendMeetingInvitationsOrCancellationsRequired` veriyor)

### `config.py` / `ui.py`
- `takvimler()` kayıt listesi (`hesap.json`, 0600) — `takvim_ekle/guncelle/sil`
- `_takvim_kur`: görünüm seçici (Ay|Hafta|Gün), ◀/▶/Bugün, Yeni Randevu,
  Takvim Hesapları, sağda **ajanda** (seçili günün randevuları + detay)
- Ay ızgarası (6×7), Hafta (7×24, kaydırıcı), Gün (24 saat, kaydırıcı),
  "şu an" kırmızı çizgisi, hücreye çift tık → Gün görünümü / yeni randevu
- `RandevuPenceresi` (başlık/tüm gün/tarih-saat/konum/açıklama, düzenle/sil),
  `TakvimHesapPenceresi` (Gmail/iCloud/Yahoo/Nextcloud şablonlu CalDAV hesabı)
- Klar kaynak: `_takvim_kaynaklari()` = aktif EWS + kayıtlı tüm CalDAV hesapları
  (CalDAV, aktif e-posta hesabından bağımsız çalışır)

## 🔧 21.11.2026 düzeltmeleri (canlı doğrulandı)

### 1. Gmail takvim hesabı bağlanamıyordu — WRONG URL
- **Belirti:** "Bağlantı hatası: … Failed to resolve 'apidata.google.com'"
- **Kök neden:** `TakvimHesapPenceresi.SABLONLAR["Gmail"]` adresi
  `https://apidata.google.com/caldav/v2/calendars/default` — **bu host DNS'te yok**
- Google'ın yeni ucu `apidata.googleusercontent.com/caldav/v2/…` yalnız
  **OAuth2** kabul ediyor (Basic + uygulama parolası → 401); uygulama parolasıyla
  çalışan tek uç **eski** `https://www.google.com/calendar/dav/<eposta>/events`
- **Düzeltmeler:**
  - `ui.py`: şablon `https://www.google.com/calendar/dav/{eposta}/events`;
    `_sablon()` ve `_veri_al()` `{eposta}`'yı e-posta alanından dolduruyor
    (kullanıcı kontrolü: boşsa uyarı, sıraya göre "E-posta boş" önce)
  - `caldav.py → kesfet()`: `current-user-principal` yoksa erken `return`
    kaldırıldı; `home`/başlangıç `/user` ile bitiyorsa **`/events` yedeği**
    deneniyor (Google `/user` başlangıcında çocuk koleksiyon döndürmüyor)
- **Doğrulama:** keşif + 28 randevu okundu; PUT/DELETE (If-Match 412 → izin var,
  ekle+sil döngüsü) çalıştı; uçtan uca UI akışı: "Bağlantı başarılı! Takvimler:
  kullanici@ornek.com" → takvim yüklendi

### 2. "Randevu gün bazında gösterilmiyor"
- **Kök neden:** `_takvim_sonuc()` veriyi güncelliyor ama **çizim yapmıyordu** —
  ızgara/ajanda ilk (boş) çizimde kalıyordu; ay/geçiş değişince kendiliğinden
  görünüyordu
- **Düzeltme:** `_takvim_sonuc` sonunda `self._takvim_ciz()`

### 3. "Sadece Ay ızgarası görünüyor, Hafta/Gün görünmüyor"
- **Kök neden (ölçüldü):** içerik çerçevesi (`icerik`) canvas'ın **kardeşi**
  olarak yaratılıyordu; canvas sonra eklendiğinde **X yığında canvas üstte
  kalıyor**, içerik arkada çiziliyordu → tuval zemini (`#1c1c1c`) görünüyor,
  ızgara hiç yoktu. `icerik.lift()` anında düzeltiyordu (kanıt)
- **Düzeltme:** `icerik = ttk.Frame(canvas)` — içerik canvas'ın **çocuğu**
  (kanonik desen), hem `_hafta_izgara_kur` hem `_gun_izgara_kur`

### 4. Evolution'a yakın görünüm
- `_icerigi_genislet(canvas)`: canvas `<Configure>` → pencere öğesi genişliği
  tuvale eşitlenir → **Gün görünümü tüm genişlikte** (dar kol değil),
  **Hafta kırpılmadan** (içerik 986px > tuval 934px idi)
- Hafta **gün başlıkları**: koyu temada `#202124` metin okunmuyordu →
  `_metin_rengi(tema_zemini)`; bugün `#c5221f` korundu
- Ay **gün numaraları**: `ttk.Label` tema zemini beyaz hücreyle çakışıyordu
  (siyah kutu görünüyordu) → `tk.Label` + `bg=arka` (her çizimde)

### Testler (21.11 hepsi geçti)
- `tests/takvim_ui_test.py`: CalDAV **bağlıyken** "bağlı takvim hesabı yok"
  uyarısı bekleyen eski varsayım güncellendi; `sys.path` başlığı eklendi
  (doğrudan `python tests/…` ile çalışıyordu)
- Çevrimdışı: `coklu_hesap_test`, `hesap_ui_test`, `imap_yerel_sunucu_test`,
  `resim_test` — ✓; canlı `takvim_ui_test` → **TAKVIM UI OK**
- Görsel doğrulama: Xvfb + ffmpeg x11grab ile Ay/Hafta/Gün ekran görüntüleri

### Ortam notları
- Aktif hesap **GMail**'e döndürüldü (canlı test EWS'e çevirmişti)
- Test kalıntıları temizlendi: CalDAV 28, EWS 6 randevu, `GosterimTesti*` yok
- Kullanıcının kendi `Test` (21.11.2026 09:00) randevusu **dokunulmadı**
- **Dikkat:** `/tmp/opencode/bisect.py` stdlib `bislect`'i gölgeliyor —
  `/tmp/opencode` içindeki betikler "circular import / tkinterweb Random" hatası
  verir; test betiklerini **temiz dizinde** çalıştır (ör. `/tmp/opencode/tcal/`)

## Kalan işler (21.11) — ✅ 22.11'de tamamlandı
- [x] **README'ye takvim bölümü** yazıldı (CalDAV kurulumu, Gmail uygulama
      parolası, eski uç notu) + `DEVAM.md` takvim bölümü aşağıda
- [x] **Tekrarlayan olaylar (RRULE)** açılıyor — `tekrar.py` ile genişletiliyor
      (detay: aşağıdaki 22.11 bölümü)
- [x] **Birden fazla CalDAV hesabı** — kaynak takibi eklendi (`kaynak_id`),
      silme/güncelleme doğru hesaba gidiyor, yeni randevuda hesap seçimi var
- [x] CalDAV'da **TZID** destekleniyor (`zoneinfo` ile UTC'ye çevrilir)
- [x] CalDAV `randevu_ekle` **ETag döndürmüyorsa** PROPFIND ile soruluyor
- [ ] Google modern uç (OAuth2) desteği — uygulama parolası eskidiğinde gerekecek
- [x] Takvim `otomatik_yenileme` ile tazeleniyor (Ayarlar → Genel)
- [x] Ay ızgarasında hücre içi etiketler tema ile uyumlu (stil sistemi
      `randevu` / `randevu_metin` anahtarlarından geliyor)

---

# 2026-11-22 — Tekrarlayan olaylar, çoklu takvim hesabı, otomatik yenileme

> **Kaldığımız yer (22.11.2026):** Takvim sekmesi olgunlaştı: RRULE (tekrarlayan
> olay) desteği hem CalDAV hem EWS'te çalışıyor, tekrarlayan randevu
> **oluşturulabiliyor**, birden çok CalDAV hesabı doğru ayrıştırılıyor,
> takvim otomatik yenileniyor. README'ye takvim bölümü eklendi.

## 1. Tekrarlayan olaylar (RRULE) — yeni `postacim/tekrar.py`

Tekrar kurallarını ayrıştırıp üreten **bağımlılıksız** yeni modül:

| Desteklenen | Not |
|---|---|
| `FREQ=DAILY/WEEKLY/MONTHLY/YEARLY` | `INTERVAL`, `COUNT`, `UNTIL` |
| `BYDAY` | sıralı biçim de: `2MO` (2. pazartesi), `-1FR` (son cuma) |
| `BYMONTHDAY`, `BYMONTH`, `BYSETPOS`, `WKST` | negatif gün numaraları da |
| `EXDATE` / `RDATE` | hariç tutulan / eklenen tarihler |

- **Hızlı ileri atlama:** sınırsız kurallarda pencereye atlama aritmetik
  yapılır (2020'den başlayan "her gün" kuralı 2026 penceresinde anında çözülür)
- `COUNT` varsa atlama yapılmaz — kaçıncı tekrar olduğu baştan sayılmalı
- `tekrar.kural_ozeti()` → "Her hafta (Pzt, Çar) — 10 kez" (arayüz ipucu)
- `tekrar.kural_olustur()` → kullanıcı seçiminden RRULE üretimi

### Arayüzde genişletme
- `Postacim._tekrar_genislet()`: **görünür pencereye** göre (Ay 42 gün,
  Hafta 7 gün, Gün 1 gün) tekrarlar üretilir; pencere değişince önbellek
  yeniden hesaplanır
- Her tekrar için **kopya** kayıt üretilir (`occurrence_id` benzersiz) →
  ajanda seçimi, "tamamlandı" işareti ve çizim doğru çalışır
- `_gun_randevulari()` genişletilmiş listeyi kullanır; hafta görünümü de
  genişletilmiş listeyi çizer

### CalDAV (`caldav.py`)
- `ics_randevulari()` artık **RRULE / EXDATE / RDATE** satırlarını toplar
- **TZID desteği:** `DTSTART;TZID=Europe/Istanbul` → `zoneinfo` ile UTC'ye
  çevrilir (10:00 İstanbul = 07:00Z). `VTIMEZONE` içindeki özel dilimler
  çözülemezse yerel saat varsayılır
- `RandevuKaydi` alanları: `rrule`, `exdate`, `rdate`, `kaynak_id`,
  `kaynak_tur`, `occurrence_id`, `kimlik` (property)

### EWS (`ews.py`)
- `t:Recurrence` → RRULE dönüşümü (`_rrule_uret`): Daily/Weekly/Monthly
  (göreli ve mutlak)/Yearly desenleri + `t:Range` → `COUNT`/`UNTIL`
- `SyncFolderItems` isteğine `<t:Recurrence/>` eklendi (canlı doğrulandı:
  sunucu kabul ediyor, hata vermiyor)

## 2. Tekrarlayan randevu **oluşturma** (yeni)
- Randevu penceresine **Tekrar** seçimi: Tek seferlik / Her gün / Her hafta /
  Her ay / Her yıl + "kaç kez" alanı; özet metni anlık gösterilir
- CalDAV: ICS'e `RRULE:` satırı yazılır
- EWS: RRULE → `t:Recurrence` XML'ine çevrilir (`_recurrence_xml`)
- Mevcut tekrarlı randevu düzenlenirken seçim **kuraldan doldurulur**, seçenek
  "tek seferlik"e çevrilirse RRULE satırı ICS'ten silinir
- Düzenleme/silme uyarısı: "Bu randevu tekrarlı — tüm tekrarlar silinecek /
  değişiklikler tüm tekrarlara uygulanır"

## 3. Düzeltilen gerçek hatalar (CalDAV güncelleme)
`randevu_guncelle()` yalnız **SUMMARY/LOCATION** alanlarını güncelliyordu:
- **Başlangıç/bitiş saati değişmiyordu** → `_ics_zaman_degistir()` eklendi
  (`VALUE=DATE` korunur)
- **Açıklama hiç güncellenmiyordu** → eklendi (boşaltma da çalışır)
- RRULE satırı güncellenmiyordu → eklendi (`;` kaçışı bozulmasın diye
  `_ics_alan_degistir(..., kacis=False)`)

## 4. Birden çok CalDAV hesabı — kaynak takibi
- Her randevu **kaynağını** taşır (`kaynak_id`, `kaynak_tur`)
- Silme/güncelleme artık `kaynaklar[0]` yerine **hangi hesaptan geldiyse
  oraya** gider (`_kaynak_caldav(kaynak_id)`)
- Yeni randevu penceresinde **takvim hesabı seçimi** komboboxu var
  ("Gmail (CalDAV)", "Kurum (EWS)")

## 5. ETag yedeği (CalDAV)
`randevu_ekle`/`randevu_guncelle` sunucudan `ETag` gelmezse `_etag_al()`
ile **PROPFIND** yapılır (Google PUT cevabında vermeyebilir) → sonraki
güncellemede `If-Match` doğru gider.

## 6. Takvim otomatik yenileme
- Ayarlar → Genel → **Takvim otomatik yenileme**: Kapalı / 1 dk / 5 dk / 15 dk
  (varsayılan 5 dk, `hesap.json` → `takvim_otomatik_yenileme`)
- Yalnız **takvim sekmesi etkinken** ve devam eden başka iş yokken tazelenir
  (artımlı: EWS `SyncState`, CalDAV `calendar-query`)

## 7. Takvim renkleri temaya uyuyor (koyu tema)
- Takvim ızgarası **sabit açık renklerde** kalıyordu (koyu temada beyaz
  kutular) → `TAKVIM_STIL_KOYU` varsayılanları eklendi; tema **koyu** ise
  koyu renkler kullanılır, tema değişince ızgara yeniden çizilir
- Kullanıcı Ayarlar → Takvim'den **kendi rengini seçtiyse** (`takvim_stil`
  kayıtlıysa) tema değişimi renkleri ezmez — kullanıcı tercihi korunur
- Ay ızgarasında **başka aya ait hücrelerdeki** randevu etiketi artık
  hücre rengine değil **randevu rengine** boyanıyor (metin soluk) → diğer
  aylardaki tekrarlar da görünür

## 8. Testler
- **Yeni:** `tests/tekrar_test.py` — kural ayrıştırma/üretimi (DAILY/WEEKLY/
  MONTHLY/YEARLY, COUNT/UNTIL/EXDATE/RDATE, uzak pencere), iCalendar
  ayrıştırma (RRULE/TZID/EXDATE), EWS `t:Recurrence` dönüşümü, tekrarlı
  randevu üretimi (ICS + EWS XML), **arayüz** (genişletme, işaret korunumu,
  kaynak takibi, hesap seçimi) — hepsi geçti
- **Canlı uçtan uca (Gmail CalDAV):** tekrarlı randevu oluşturuldu →
  geri okundu (RRULE ayrıştırıldı) → 3 tekrar üretildi (23/30 Kasım,
  7 Aralık) → **saat değiştirilip güncellendi** (DTSTART/DTEND + RRULE korundu)
  → silindi. **Test kalıntısı bırakılmadı.**
- **Canlı EWS:** `t:Recurrence` istek şekli sunucu tarafından kabul edildi
  (6 randevu çekildi, hata yok)
- `tests/ui_smoke.py` **düzeltildi:** okuyucu HTML moduna geçince
  `ayrinti.get()` yok → HTML modunda düz metin gövde mesajdan okunuyor
  (test 21.11'den beri HTML okuyucu eklendiğinden beri kırıktı)

## Kalan işler
- [ ] Google modern uç (OAuth2) desteği — uygulama parolası eskidiğinde gerekecek
- [ ] CalDAV'da `VTIMEZONE` içindeki özel saat dilimleri çözülmüyor (yerel saat)
- [ ] Tekrarlayan bir randevunun **tek bir tekrarını** silmek/gizlemek
      (şu an tekrarın tamamı siliniyor/değişiyor) — `RECURRENCE-ID` gerekir
- [ ] Kurum (EWS) takviminde `UpdateItem` → `ErrorSendMeetingInvitationsOrCancellationsRequired`
      → düzenleme "sil + yeniden oluştur" (yeni kimlik verilir; kopya oluşabilir)
- [ ] Takvim randevuları için arama/kategori etiketi

---

# 2026-11-22 (gece) — Genelleştirme ve dağıtıma hazırlık

> **Amaç:** Projeyi tek bir kuruma özgü olmaktan çıkarıp **açık kaynak**
> olarak, herhangi bir Linux kullanıcısının kurup kullanabileceği hâlde
> getirmek.

## Kuruma özgü olmaktan çıkarma (genelleştirme)
- **Varsayılan sunucu kaldırıldı**: boş bırakıldı; kullanıcı Exchange
  sunucu adresini kendisi yazar (`EwsIstemci` boş sunucuda okunur `EwsHata`
  verir, `_baglan()` bunu dialogla karşılar)
- Hesap penceresi: "Kurum sunucusu (EWS)" → **"Exchange sunucusu (EWS)"**;
  ipuçları genelleştirildi (`mail.kurum.gov.tr`, `KURUM\kullanici`)
- Tüm metinlerde kurum/alan adı yerine **örnek** adresler kullanılıyor

## Dağıtıma hazırlık
- **`LICENSE`**: GNU GPL v3 tam metin
- **`pyproject.toml`**: `postacim` paketi, sürüm 0.1.0, `gui-scripts`
  giriş noktası, ikonlar paket verisi olarak; **wheel doğrulandı**
  (`python -m build` → `postacim-0.1.0-py3-none-any.whl`, ikonlar dahil)
- **`.gitignore`**: venv, `__pycache__`, egg-info, yerel ayar dosyaları
  (parola içerebilecek `*.local.json`)
- **README** baştan yazıldı: genel "Exchange (EWS) / IMAP / CalDAV istemcisi"
  anlatımı, CalDAV kurulumu, lisans ve katkı bölümleri eklendi
- **GitHub Actions**: testler her push/PR'da otomatik çalışır

## Doğrulama
- Tüm çevrimdışı testler + canlı arayüz testleri geçti
- Wheel `python -m build` ile sorunsuz üretildi

## Kalan işler (yayın öncesi)
- [ ] Uygulama ikonu (`postacim/ikonlar/` içindeki düğme ikonları var;
      uygulama için 128×128 PNG gerekli)
- [ ] Sürüm bilgisi tek yerde (`pyproject.toml` + `UYGULAMA_ADI`/sürüm
      sabiti) — şu an sürüm yalnız pyproject'ta
- [ ] Fedora/openSUSE/Pardus paket dosyaları (spec / debian/)

---

# 2026-11-22 (gece 2) — Yeni randevu eklenemiyordu (düzeltildi) + depo düzeni

> **Kaldığımız yer:** Kullanıcı takvimde 25.11.2026 01:00–01:30'a not eklerken
> hata aldı. Canlı olarak yeniden üretildi, kök neden bulundu ve düzeltildi.

## 1. Hata: "Beklenmeyen hata: 'datetime.datetime' object is not subscriptable"
- **Belirti:** "Yeni Randevu" penceresinde kaydet → hata penceresi; randevu
  hiçbir yere yazılmıyordu. (Tarih/saatla ilgisi yoktu; **her** yeni randevu
  ekleme denemesi bu hatayı veriyordu.)
- **Kök neden:** `RandevuPenceresi._kaydet_cek()` içinde seçilen takvim
  kaynağı **yanlış sıradan** okunuyordu:

  ```python
  secilen = islev[2]          # "ekle"de islev[2] = başlangıç datetime'i!
  hedef_tur = secilen[0]      # → TypeError: datetime.subscriptable değil
  ```
  `ekle` işlevi 9 elemanlı: `(ekle, baslik, bas, bit, konum, aciklama,
  tum_gun, kaynak, kural)` → kaynak **7.** sırada. `guncelle` işlevinde ise
  kaynak gerçekten 2. sırada (`("guncelle", randevu, kaynak)`) — bu yüzden
  düzenleme çalışırken ekleme çalışmıyordu.
- **Düzeltme:** işleve göre kaynak ayrıştırılıyor; EWS hedefinde artık
  **seçilen** Exchange hesabı kullanılıyor (daima aktif posta hesabı değil);
  düzenlemede kayıt **kendi hesabına** (`kaynak_id`) gidiyor.
- **Doğrulama:** canlı olarak
  - EWS (Exchange) takvimine 25.11.2026 01:00–01:30 randevu eklendi ✓
  - CalDAV (Gmail) takvimine aynı randevu eklendi ✓
  - ikisi de `2026-11-24T22:00Z` (yerel 01:00) olarak doğru yazıldı ✓
  - **Test kayıtları silindi, kalıntı yok.**

## 2. Yeni test: `tests/randevu_ekle_test.py`
- Sahte istemcilerle ekleme/güncelleme akışı: CalDAV mı EWS mi hedeflendi,
  saatler aktarıldı mı, tüm gün/RRULE aktarıldı mı.
- **Regresyon kanıtı:** hatalı sürüm geri konulunca test aynı hatayla
  (`TypeError: 'datetime.datetime' object is not subscriptable`) düşüyor.
- `tests/run_all.sh` ve GitHub Actions akışına eklendi.

## 3. Depo düzeni
- `~/postacim` artık **git çalışma kopyası**; önceden ayrı bir kopya olarak
  duruyordu ve GitHub'daki depodan (CI, rozetler, `CONTRIBUTING.md`,
  ekran görüntüleri, `tests/run_all.sh`) ayrışmıştı.
- Yedek: `~/postacim_yerel_20261122_2135.tar.gz`
- Sürüm **0.1.3** (`postacim/__init__.py` → `__version__`, `pyproject.toml`
  bunu okur).

## Kalan işler
- [ ] Tekrarlayan bir randevunun **tek bir tekrarını** silmek/gizlemek
      (`RECURRENCE-ID`)
- [ ] Google modern uç (OAuth2) desteği
- [ ] CalDAV'da `VTIMEZONE` içindeki özel saat dilimleri çözülmüyor (yerel saat)
- [ ] Kurum (EWS) takviminde `UpdateItem` bozuk → düzenleme "sil + yeniden oluştur"
- [ ] Takvim randevuları için arama/kategori etiketi
- [ ] Fedora/openSUSE/Pardus paket dosyaları (spec / debian/)

---

# 2026-11-22 (gece 3) — "Okundu bilgisi sunucuya yazılamadı" uyarısı

> **Kaldığımız yer:** Durum çubuğunda sürekli *"Okundu bilgisi sunucuya
> yazılamadı (EWS UpdateItem hatası)"* uyarısı çıkıyordu. Kayıt sunucuya
> yazılmıyordu. **Hata sandığımız gibi sunucuda değilmiş — istemcideymiş.**

## 1. Teşhis
- **Belirti:** mesaj açıldığında okundu işareti gönderiliyor, sunucu
  `ErrorInvalidArgument — "The request is invalid."` dönüyor → istemci
  sessizce geçiyor, durum çubuğunda uyarı.
- **Önceki teşhis (yanlış):** "sunucudaki `UpdateItem` bozuk" sanıldı ve
  sunucu yöneticisine bildirildi. Oysa `FindItem`, `CreateItem`,
  `MoveItem`, `DeleteItem`, `SyncFolderItems` sorunsuz çalışıyordu.
- **Gerçek neden:** EWS şemasında `ItemChange` elemanı **types** ad
  alanında (`t:ItemChange`) olmalı. İstemci `<m:ItemChange>` gönderiyordu
  (messages ad alanı) → Exchange isteği geçersiz sayıyor.

  ```python
  # YANLIŞ (sunucu hatası sanılıyordu)
  "<m:ItemChanges><m:ItemChange>…</m:ItemChange></m:ItemChanges>"
  # DOĞRU
  "<m:ItemChanges><t:ItemChange>…</t:ItemChange></m:ItemChanges>"
  ```
- **Kanıt:** aynı istek 8 varyantla denendi; `t:ItemChange` içeren tek
  varyant (`t:ItemChange`, diğer 7'si `m:ItemChange`) kabul edildi.
  `ConflictResolution`, `MessageDisposition`, `ChangeKey` ve alan seçiminin
  (`message:IsRead` / `message:MessageFlags`) hiçbir etkisi yok — hata
  yalnızca ad alanındaydı.
- **Canlı doğrulama:** mesaj okundu işaretlendi → sunucudan geri okundu
  (`IsRead: true`) → eski durumuna (okunmadı) geri alındı. Uyarı artık
  çıkmıyor.

## 2. Düzeltme
- `ews.py`: `okundu_isaretle` artık `<t:ItemChange>` kullanıyor; gövde
  ayrı bir yardımcıya çıkarıldı (`_okundu_govde`) ki test edilebilsin.
- `tests/coklu_hesap_test.py` → "ews: SOAP gövde ad alanları" bölümü:
  `t:ItemChange` var, `m:ItemChange` yok.

## 3. Takvimde `UpdateItem` hâlâ çalışmıyor (sunucu tarafı)
- Takvim kaydı güncellemede (`calendar:Start`/`End`/`Subject`) sunucu
  `ErrorSendMeetingInvitationsOrCancellationsRequired` veriyor — `SendOnly`,
  `SaveOnly`, `SendMeetingInvitations`, `SendMeetingCancellations`
  varyantlarının hepsi denendi, hepsi aynı hata. Bu sefer gerçekten
  sunucu kaynaklı görünüyor; mevcut çözüm (sil + yeniden oluştur) korundu.

## Kalan işler
- [ ] Tekrarlayan bir randevunun **tek bir tekrarını** silmek/gizlemek
      (`RECURRENCE-ID`)
- [ ] Google modern uç (OAuth2) desteği
- [ ] CalDAV'da `VTIMEZONE` içindeki özel saat dilimleri çözülmüyor (yerel saat)
- [ ] Takvim randevuları için arama/kategori etiketi
- [ ] Fedora/openSUSE/Pardus paket dosyaları (spec / debian/)

---

# 2026-11-23 — Dosya seçici: yerel masaüstü iletişim kutusu

> **Kaldığımız yer:** Ek ekleme ve dosya kaydetme, Tk'nin kendi sade
> `filedialog` penceresiyle yapılıyordu; yerler çubuğu, arama, son
> kullanılanlar ve çoklu seçim yoktu. Kullanıcı "daha işlevli ve kullanıcı
> dostu" bir seçici istedi.

## 1. Yaklaşım
- Tk'nin penceresini yeniden yazmak yerine **masaüstünün kendi seçicisi**
  kullanıldı: GNOME/XFCE/MATE'de `zenity` (GTK dosya seçici), KDE'de
  `kdialog`. İkisi de yoksa eski `filedialog`a düşülür.
- Yeni modül: `postacim/dosya_secici.py` (`dosya_ac`, `dosya_ac_coklu`,
  `dosya_kaydet`).
- Seçici `POSTACIM_DOSYA_SECICI=tk|zenity|kdialog` ile zorlanabilir; testler
  `tk` ile deterministik çalışır.

## 2. Değişiklikler
- `ui.py`: üç çağrı noktası (`ek_ekle`, `_ek_kaydet`, `farkli_kaydet`) yeni
  yardımcıya bağlandı; `filedialog` içe aktarımı kaldırıldı.
- Ek seçimi artık **çoklu**: seçilen her dosya tek tek okunur; açılamayan
  dosya için `messagebox` hatası gösterilir, diğerleri eklenmeye devam eder.
- Ek seçimine belge/tablo/sunu/resim/arşiv/e-posta süzgeçleri eklendi.
- Son kullanılan dizin süreç içinde hatırlanır; ilk açılışta İndirilenler
  (yoksa ev dizini). Kaydetmede eksik uzantı (`.eml`, `.bin`) tamamlanır.

## 3. Testler
- Yeni `tests/dosya_secici_test.py`: zenity/kdialog süzgeç biçimi, seçici
  zorlama, tek/çoklu çıktı çözümleme, iptal, uzantı ekleme ve zenity
  başlatılamadığında tk yedeği.
- `tests/ui_smoke.py`: canlı testte pencere açılmasın diye `tk` seçiciye
  sabitlendi.
- `tests/run_all.sh` listesine eklendi; tüm çevrimdışı testler geçti.
- `zenity` seçenekleri Xvfb altında denendi (aç/kaydet pencereleri hatasız
  açıldı).

---

# 2026-11-23 (2) — Birden çok eki topluca indirme

> **Kaldığımız yer:** Ek listesi tek seçimlikti (`selectmode="browse"`);
> her ek için ayrı ayrı "farklı kaydet" penceresi açılıyordu. Kullanıcı
> birden çok eki seçip tek seferde indirmek istedi. (Sürüm 0.1.8)

## 1. Arayüz
- `ek_listesi` → `selectmode="extended"`: Ctrl/Shift ile çoklu seçim,
  Ctrl+A ile tümü, sağ tık menüsü ("Seçilenleri indir (N)",
  "Tümünü indir…").
- Tek ek seçilirse eski davranış korunur (dosya adı sorulur).
- Birden çok ekte `dosya_secici.dizin_sec` ile hedef klasör sorulur
  (zenity `--directory` / kdialog / tk yedeği).

## 2. İndirme
- `_ekleri_indir_cek`: ekleri tek arka plan işinde indirir, her birini
  hedef klasöre yazar. Yol ayırıcıları ve geçersiz karakterler
  (`_temiz_dosya_adi`) dosya adından temizlenir.
- Aynı ad çakışması `_benzersiz_yol` ile ` (1)`, ` (2)` eklenerek çözülür;
  var olan dosyanın üzerine yazılmaz.
- Tek ek hatası diğerlerini durdurmaz; sonuçta "Bazı ekler indirilemedi"
  uyarısı ve durum çubuğunda kaydedilen sayı gösterilir.

## 3. Testler
- `tests/ek_indir_test.py`: ad temizliği, çakışma çözümü, toplu kayıt ve
  kısmi hata dayanıklılığı.
- `tests/dosya_secici_test.py`: klasör seçimi (`zenity --directory`).
- `tests/run_all.sh` güncellendi; tüm çevrimdışı testler geçti.

## Kalan işler
- [ ] Kurum sunucusunda EWS `FindFolder`/`CreateFolder` canlı doğrulaması
      (klasör oluşturma özelliği testli ama canlı deneme kullanıcı onayında)
- [ ] EWS kullanıcı klasörlerinde sağ tuş → silme (Exchange `DeleteFolder`)
- [ ] Tekrarlayan bir randevunun **tek bir tekrarını** silmek/gizlemek
      (`RECURRENCE-ID`)
- [ ] Google modern uç (OAuth2) desteği
- [ ] CalDAV'da `VTIMEZONE` içindeki özel saat dilimleri çözülmüyor (yerel saat)
- [ ] Takvim randevuları için arama/kategori etiketi
- [ ] Fedora/openSUSE/Pardus paket dosyaları (spec / debian/)

## Klasör oluşturma (sağ tuş) (2026-11-23)

**Talep:** "posta kutularımda yeni klasör oluşturmak istiyorum" (IMAP/Gmail
ve Exchange).

### Değişiklikler
- **`imap.py → klasor_olustur(ad)`**: IMAP `CREATE <klasör>`; `_kilitli`.
  - Adlar değiştirilmiş UTF-7 ile gider (`_utf7_kodla`) → Türkçe karakterler
    telde ascii (`Yeni Klas&APY-r`); `_tirnakla` ile tırnaklı.
  - Boş ad / kontrol karakterli ad → okunur `EwsHata`; sunucu reddi
    (NO) → `EwsHata("Klasör oluşturulamadı: … — sunucu reddetti.")`
  - Başarıda yeni kimlik (kodlanmış sunucu adı) `_klasor_adlari`ya eklenir —
    listeleme yenilenmeden önce de komutlar yeni klasörde çalışır.
- **`ews.py`:**
  - `klasor_olustur(ad, ebeveyn="msgfolderroot")`: `CreateFolder`; klasör adı
    `_kacis` ile XML'e kaçışlı yazılır; **tekrar=1** (geçici hatada istek
    tekrarlanırsa sunucuda iki klasör oluşabilir) → `FolderId` döner ve
    FindFolder önbelleği düşürülür.
  - **Kullanıcı klasörleri artık listeleniyor:** `_ozel_klasorler()` —
    `FindFolder Traversal="Shallow"` `msgfolderroot` altında; posta olmayan
    klasörler (`FolderClass` IPF.Note değilse) ve varsayılan adlar
    (`VARSAYILAN_KLASOR_ADLARI`, İngilizce + Türkçe) elenir. Sunucu
    FindFolder'ı desteklemiyorsa sessizce 7 varsayılanla devam edilir
    (EwsYetkiHatasi yukarı fırlar). Sonuç **60 sn önbelleklenir**
    (`_ozel_klasor_onbellek`) — otomatik yenileme ek istek atmasın.
  - `_klasor_id_xml(kimlik)`: bilinen 7 klasör `DistinguishedFolderId`,
    kullanıcı klasörleri `t:FolderId` ile — `_senkronize` (SyncFolderItems)
    ve `tasi` (MoveItem) artık her klasör türüyle çalışır.
- **`ui.py`:**
  - `_klasor_menu_olustur(iid)`: **"Yeni Klasör…" yalnız aktif hesapta**
    (IMAP + EWS), klasör düğümünde *ve* hesap düğümünde (`hesap:<id>`)
    görünür; "Klasörü Sil…" eskisi gibi yalnız aktif IMAP'te özel olmayan
    klasörde (önce ayrıcı eklenir). Başka hesabın klasöründe menü yine yok.
  - `klasor_olustur(ad=None)`: ad verilmezse `_klasor_adi_penceresi()` açılır
    (ttk diyalog; Enter = Oluştur, Esc = İptal, `grab_set`); boş ad →
    `showwarning`, istemciye gitmez. Oluşturma `_arka_plan`da;
    `("yenile", "Klasör oluşturuldu: …")` → klasör listesi + sayaçlar tazelenir.
  - Yeni ikon: `ikonlar/klasor_ekle.png` (20×20, klasör + artı).

### Testler (hepsi geçti)
- `ews_klasor_test.py` (**yeni**): CreateFolder gövdesi (kök, kaçışlı ad),
  FolderId döndürme, önbellek düşürme; FindFolder listeleme — varsayılan
  adlar/Takvim (IPF.Appointment) elenir, sayaçlar okunur; **60 sn
  önbellek** (ikinci çağrıda istek yok); FindFolder hatasında 7 klasörle
  devam; EwsYetkiHatasi yukarı; `_klasor_id_xml` ve kullanıcı klasörüne
  taşıma (`t:FolderId`). İstek mock'lu → çevrimdışı.
- `coklu_hesap_test.py`: sahte IMAP'ta `CREATE "Özel Notlar"` utf-7 adla;
  haritaya ekleme; NO reddi ve boş ad → `EwsHata`
- `imap_yerel_sunucu_test.py`: tel denetimi — ham komut
  `CREATE "Yeni Klas&APY-r"` gerçek `imaplib` üzerinden
- `hesap_ui_test.py`: menüde "Yeni Klasör…" aktif hesapta (inbox, özel
  klasör, hesap düğümü), başka hesapta menü yok; oluşturma akışı hem IMAP
  hem EWS istemcisine ulaşır; boş ad uyarı verip oluşturmaz; "Klasörü
  Sil…" beklentileri korundu

### Not / risk
- Kurum Exchange sunucusunun `FindFolder`/`CreateFolder` desteği canlı
  olarak denenmedi (FindItem sunucuda zaten bozuk). Desteklemiyorsa:
  klasörler listelenmez/oluşturulamaz ama uygulama çalışmaya devam eder
  (hata yolları testli). Canlı deneme kullanıcının onayına bırakıldı.

## Klasör yeniden adlandırma (sağ tuş) (2026-11-23)

**Talep:** "varolan bir klasörün adını değiştirmek istiyorum" (0.1.9'daki
oluşturma/silme eksik bıraktı).

### Değişiklikler
- **`imap.py → klasor_yeniden_adlandir(kimlik, yeni_ad)`**: `RENAME`.
  - IMAP'te **kimlik = ad**: başarılı olunca yeni kimlik (utf-7 kod) döner,
    `_klasor_adlari` taşıınır (eski düşer, yeni eklenir) ve eski klasörün
    `_onbellek` kaydı bırakılır (ilk açılışta baştan çekilir).
  - `SIRA` koruması (inbox, sentitems, … reddedilir); boş ad/kontrol
    karakteri hata; sunucu reddi → okunur `EwsHata`; aynı ad no-op
    (sunucuya gitmez).
- **`ews.py → klasor_yeniden_adlandir(kimlik, yeni_ad)`**: kimlik **değişmez**.
  - Exchange yazmada güncel ChangeKey ister → önce tek `GetFolder`
    (Default shape) ile `Id + ChangeKey` tazelenir, sonra `UpdateFolder`
    + `SetItemField folder:DisplayName` (her ikisi **tekrar=1**).
  - `KLASORLER` (7 varsayılan) reddedilir; boş ad hata; başarıda
    FindFolder önbelleği düşer → ağaçta yeni ad hemen görünür.
- **`ui.py`:**
  - Menüde **"Yeniden Adlandır…"** — aktif hesap + özel olmayan klasör
    (IMAP etiketi *veya* EWS kullanıcı klasörü; `kimlik not in SIRA and
    kimlik not in KLASORLER`). IMAP'te adlandırmanın altında ayrıca
    "Klasörü Sil…"; EWS'te silme yok.
  - `_klasor_adi_penceresi(ilk, baslik)`: öndoldurma + `selection_range`
    (tümü seçili) + düğme metni "Değiştir"; aynı ad → no-op; boş ad →
    `showwarning`. `_arka_plan`da çalışır; `("yenile", …)` ile liste tazelenir.

### Testler (hepsi geçti)
- `ews_klasor_test.py`: UpdateFolder gövdesi (ChangeKey tazeleme,
  FieldURI, yeni ad), kimlik değişmez, önbellek düşer; varsayılan klasör ve
  boş ad reddi
- `coklu_hesap_test.py`: RENAME teli (ascii + utf-7 ad), harita/önbellek
  taşıma, `SIRA` koruması, sunucu reddi, boş ad, aynı-ad no-op
- `imap_yerel_sunucu_test.py`: ham `RENAME "Proje X" "Proje 2"`
- `hesap_ui_test.py`: menü öğeleri (IMAP özel klasörde adlandır+sil;
  EWS kullanıcı klasöründe yalnız adlandır; inbox/hesap düğümünde yok),
  akış IMAP + EWS istemcisine ulaşır, aynı ad/boş ad uyarısı

### Not
- IMAP'te aktif klasörün adlandırılması: kimlik değiştiği için yenileme
  sonrası seçim ilk klasöre düşer (silme ile aynı mekanizma).
- EWS `UpdateFolder` canlı sunucuda denenmedi (testler mock'lu);
  `CreateFolder`/`FindFolder` gibi kullanıcı onayında canlı doğrulanacak.

## Gmail aramasında sayfa silme sonrası seçim çökmesi (2026-11-23)

**Rapor:** "Gmail'de 'Hepsi' araması yaptım; ilk sayfayı Shift ile seçip
sildim, ikinci sayfa yüklenince fare ile seçerken program kırılıp kapandı."

### Teşhis
- Sahte istemciyle birebir senaryo (`tests/silme_sayfa_test.py`):
  aramalı sayfalı sonuç → toplu sil → yeni sayfa → seçim → **yeniden
  üretilemedi** → çökme Tk/Tcl düzeyinde (mock'ta olmayan gerçek
  zamanlama/X ortamı).
- En olursu yol: toplu taşıma sonrası `yenile` sonucu geldiğinde
  `_mesajlari_doldur` listeyi `delete` + `insert` ile **yeniden kurarken**
  kullanıcı listede fare/Shift seçim sürüklemesi sürüyordu; Tcl'de seçim
  sürüklemesi sırasında öğe silinmesi bazı Tk sürümlerinde çökertiyor.
- Ayrıca Tk geri çağrı hataları üretimde yalnız terminale yazılıyordu
  (menüden açılan uygulamada iz yok) → hata görünmez.

### Değişiklikler
- **`ui.py → _mesajlari_doldur`**: kullanıcı listede fare düğmesini basılı
  tutarken liste yeniden kurulmaz — sonuç `_bekleyen_doldurma`'da bekler,
  `<ButtonRelease-1>`'de uygulanır (`_bekleyen_doldurma_uygula`; bayrak
  takılı kalırsa ~3 sn sonra yine uygulanır).
  Bağlantılar: `<Button-1>` → `_mouse_bastı` (bayrak + zaman), `<ButtonRelease-1>`
  → `_mouse_birakti`.
- **`ui.py → _tk_hata_yakala`** (yeni, `report_callback_exception` olarak
  kurulu): beklenmeyen Tk hataları `~/.local/state/postacim/hata.log`a yazılır
  (README'de uzun zamandır vaat edilen yol; kod artık gerçekten yazıyor,
  400 KB'de döner) + kullanıcıya kısa açıklama diyalogu; uygulama kapanmaz.
- `_secili_mesajlar`: beklenmedik satır kimliği gelirse atlanır (çökmez).

### Testler (hepsi geçti)
- `silme_sayfa_test.py` (**yeni**, `run_all.sh`'e eklendi): kullanıcı
  senaryosu + sayfa küçülme yolu + fare basılıyken erteleme / bırakınca
  uygulama + `hata.log` yazımı (XDG_STATE_HOME test dizinine yönlendirilir)

## Seçilen mail klasör yüklenirken beklemesin (2026-11-23)

**Rapor:** "seçtiğim mail, inbox yüklenirken biraz bekleme yapıyor;
iyileştirme yapılabilir mi?"

### Teşhis
Seçilen mesajın gövdesi (`BODY.PEEK[]`) ana IMAP oturumunu kullanan
`mesaj_detay`'dan geliyordu; `mesaj_detay` `@_kilitli` olduğundan klasör
senkronizasyonu (tam senkron ~15 sn) bitmeden **kuyrukta bekliyordu** —
"Gelen Kutusu yüklenirken maili seçiyorum, açılmıyor" un nedeni bu seri
bağlanmaydı.

### Değişiklikler (`imap.py`)
- **Ayrı gövde oturumu:** `_detay_imap` (+ `_kilit_detay`), `_yeni_baglanti`
  ortak bağlantı kurucuya çıkarıldı; `_baglan_detay`, `_komut_detay`
  (BYE/abort kurtarmalı), `_sec_detay` (readonly SELECT) eklendi.
- `mesaj_detay`, `ek_indir`, `mesaj_mime` artık `_kilitli` değil — ağ kısmı
  `_mime_cek` → `_mime_detay_cek` (ayrı oturum) içinde `_kilit_detay` altında.
- **Yedek yol:** sunucu ikinci oturumu reddederse `_mime_ana_cek` (ana
  oturum, eski davranış) çalışır.
- `_mesaj_klasoru` artık `_onbellek` taramasını ana kilitte yapar
  (paralel taramada dict mutation çökmesin).
- `_kop` gövde oturumunu da kapatır.
- `detay_hazirla()`: gövde oturumunu önden açar (hataları yutar).
- `gelen_sayisi` üstündeki yanlışlıkla çift `@_kilitli` temizlendi.

### `ui.py`
- `_mesajlari_cek`: klasör yüklendikten sonra arka planda `detay_hazirla`
  çağrılır → ilk seçimde bağlantı kurulma beklemesi olmaz.
- `_mesaj_secildi`: seçilen mesajın gövdesi zaten önbellekteyse (daha önce
  görüntülenmiş) `_detay_goster` **anında** çalışır; ağ yok.

### Testler (hepsi geçti)
- `coklu_hesap_test.py`: sahte IMAP'a tam gövde FETCH (`BODY.PEEK[]`)
  desteği eklendi; ana oturum `LOGOUT`'a düşürülmüşken (senkron kilitli
  gibi) `mesaj_detay` gövdeyi ayrı oturumdan yükler; FETCH'ler ana
  oturuma gitmez; To/Cc + ek listesi ayrıştırılır; `ek_indir` (PDFICERIK),
  `mesaj_mime`; ikinci çağrı önbellekten (yeni FETCH yok)

### Not
- İki IMAP oturumu Gmail'de sorun olmaz. Bağlantı sayısı sınırı olan
  sunucularda yedek yol devrede kalır (eski davranış, beklemeli).
- Daha büyük kazanç (ekteki mesajlarda gövdeyi kısmi çekmek: BODYSTRUCTURE
  + parça bazlı FETCH) ayrı bir iş olarak değerlendirilebilir — henüz
  yapılmadı.

## Gmail "Hepsi" aramasında mail seçimi → segfault (2026-11-23)

**Rapor:** "Gmail'de Hepsi filtresinde daha ilk maili seçtiğim gibi
kırılma oldu. İstersen kendin test ederek hatayı izleyebilirsin."

### İzleme (canlı, kullanıcı onayıyla)
- `hata.log` boştu → çöken oturum eski sürümdeydi. **0.1.13 için canlı
  yeniden üretim yapıldı** (başlık altında gerçek hesap, SALT OKUMA:
  arama "Hepsi" → ilk mail seçimi): `exit=139 Segmentation fault` —
  birebir tekrarlandı. Tk geri çağrı kaydı (hata.log) segfault'u
  yakalayamaz; yerli bileşen çöküyor.
- Metin modunda aynı akım **çökmedi** → sorun HTML gösterim yolu
  (`tkinterweb`/Tkhtml3).
- İzole döngü: UI'ın yüklediği dönüştürülmüş HTML dosyaya alındı; tek
  başına `HtmlFrame.load_html(...)` → segfault.
  (**Not:** ara betik `bisect.py` adıyla kaydedilmişti; stdlib `bisect`
  modülünü gölgelendirdiği için `tkinterweb` zinciri onu içe aktarıp
  betiği çalıştırdı — "asılı" görünen denemeler bu yüzdendi. Dosya
  adlandırırken stdlib gölgelenmemeli!)
- Kademeli sadeleştirme (her deneme ayrı Xvfb sürecinde):
  - yer tutucu linkler / <a> / <style> kaldırımı → hâlâ çöküyor
  - **tablolar kaldırılınca → çökme yok**
  - tablo bazlı bisection: tablo4 (1419 bayt) kaldırılınca düzeliyor
  - iskelet testi: tablolar 0-4'ün yalnız **açılış etiketleri** bile
    çökertiyor → içerik değil, yapı
  - **minimal tetikleyici:** `<table><table></table></table>` — boş
    tabloda bile segfault. (`<table><td>` içine sarılı normal iç içe
    tablo sorun değil; sorun çocuğun **hücresiz bölgede** açılması.)

### Değişiklikler (`ews.py`)
- **`html_tablolar_onar(html)`**: tablo ailesi etiketlerinde durum
  makinesi; `hucre=False` (hücresiz) bölgede açılan her çocuk `<table>`
  `<tr><td>…</td></tr>` içine sarılır (tarayıcı kuralı). `</table>`
  kapanışında sarmalama `</td></tr>` ile kapatılır; dosya sonunda açık
  tabloların sarmalamaları da kapatılır. Art arda çıplak çocuklar tek tek
  sarılır; hücre içi normal iç içe tablola **dokunulmaz**.
- `govde_html_gosterim`: `html_taglari_kapat` sonrası onarım çağrısı.

### Doğrulama
- Düzenlenmiş HTML izole Tkhtml ortamında sorunsuz (60 döngü render).
- **Canlı uçtan uca:** gerçek hesap + "Hepsi" araması + ilk mail seçimi →
  exit=0, 0 istisna.
- Metin modundaki `unknown option "-state"` hatası test artefaktı
  çıktı (bayrak kurulumdan sonra zorlanınca widget türü uyuşmuyor;
  gerçekte html_modu sabit) — kod değişikliği gerekmedi.

### Testler (hepsi geçti)
- `resim_test.py → test_html_tablolar_onar`: sarma/açılış/kapanış,
  art arda çocuklar, hücre içi dokunulmazlık, tbody altı, kapanmamış
  tablo, gösterim entegrasyonu.

## Çöp kutusunu boşalt + spam temizle (sağ tuş) (2026-11-23)

**Talep:** "çöp kutusunu boşaltma ve spam mesajları silme sağ tuş
menüsünü ilave edelim."

### Değişiklikler
- **`imap.py → klasoru_bosalt(kimlik)`** (yedekli): yalnız
  `deleteditems`/`junkemail`'e izin (okunur `EwsHata`). `UID SEARCH ALL`
  → `_uid_kumeleri` (aralık kümeleri `1:5,9`, ≤300/istek) →
  `UID STORE +FLAGS.SILENT (\Deleted)` → `EXPUNGE`. Gmail'de çöp
  kutusu/spam'i gerçekten boşaltır. `_onbellek[kimlik]` düşürülür; sayı
  döner (boş klasörde 0).
- **`ews.py → klasoru_bosalt(kimlik)`**: yine yalnız iki klasör.
  `EmptyFolder` yerine `SyncFolderItems` (IdOnly, 512/tur) + toplu
  `DeleteItem HardDelete` (≤100/istek) — kurum sunucusunda
  **doğrulanmış** işlemler (FindItem bozuk ama Sync/Delete çalışıyor);
  sayı sayılabilir kalır, `_senkronizasyon.pop` ile klasör yeniden
  senkronize edilir. Dikkat: yanıt öğeleri `.//m:Changes//t:ItemId`
  altından okunur (SyncFolderItems yanıtı `m:Items` içermiyor).
- **`ui.py`:**
  - `_klasor_menu_olustur`: "Yeni Klasör…" altına, **Silinmiş Öğeler**
    düğümünde "Çöp Kutusunu Boşalt…", **Önemsiz** düğümünde "Spam'i
    Temizle…" (yalnız aktif hesap; IMAP + EWS; ayırıcı ile).
  - `klasoru_bosalt(kimlik)`: `askyesno` onayı ("kalıcı, geri alınamaz")
    → `_arka_plan` → `("yenile", "Çöp kutusu boşaltıldı (N mesaj)")`.

### Testler (hepsi geçti)
- `coklu_hesap_test.py`: SahteImap'a `expunge_sayisi` eklendi; store
  kümesi `101:103` aralığıyla, EXPUNGE sayacı, sayı=3, önbellek düşer,
  gelen kutusu kısıtı, boş klasör → 0
- `imap_yerel_sunucu_test.py`: tel — `UID SEARCH ALL`,
  `UID STORE 101 +FLAGS.SILENT (\Deleted)`, `EXPUNGE`
- `ews_klasor_test.py`: `sync_yaniti`/`deleteitem_yaniti` eklendi;
  HardDelete gövdesi iki ItemId, sayı, önbellek pop, kısıt
- `hesap_ui_test.py`: menü öğeleri (IMAP çöp/spam, EWS çöp/spam; inbox'ta
  ve diğer klasörlerde yok; başka hesabın çöp kutusunda menü yok), akış
  hem IMAP hem EWS istemcisine ulaşır

### Not / risk
- Gmail IMAP'te EXPUNGE çöp kutusunda mesajları kalıcı siler; 30 günlük
  otomatik temizliğe ekstra bir yol olur. Kurum EWS'te HardDelete geri
  alınamaz — onay diyalogu zorunlu.
- Çok büyük klasörlerde (binlerce mesaj) süre uzun olabilir; durum
  çubuğu iş sürerken "boşaltılıyor…" gösterir.

## EWS boşaltmada ErrorItemNotFound (2026-11-23)

**Rapor:** "Kurum mailinde çöp kutusunu boşalt dediğimde EWS Yanıt Kodu:
ErrorItemNotFound."

### Teşhis / Değişiklikler
- SyncFolderItems döndürdüğü ItemId'ler **ChangeKey'siz** DeleteItem'a
  yazılıyordu; ayrıca senkron ile silme arasında öğe kaybolursa toplu
  istek komple düşüyordu.
- `_kalici_sil_coklu`: öğeler artık `(Id, ChangeKey)` çifti; gövde
  `_kalici_sil_govdesi` ChangeKey'i de yazar. Toplu istek
  ErrorItemNotFound verirse **tek tek** denenir; bulunamayanlar atlanır
  (sayılmaz), diğer hatalar yükselir. `silinen == 0` ve bulunamayan > 0
  ise okunur hata: "N öğe sunucuda bulunamadı".
- Test düzeltmesi: mock `istek` gerçek davranışı taklit etmeli —
  ResponseCode hatasında **EwsHata fırlat** (eskisi hatayı eleman olarak
  döndürüyor, kontrol hiç çalışmıyordu → yanlış "başarı" sayısı).

### Canlı doğrulama (kurum sunucusu, kullanıcı talebiyle)
- Salt okuma SyncFolderItems: deleteditems 0 öğe (o an boş — hata
  yeniden üretilemedi), junkemail 560, inbox 1444 → senkron sağlıklı.
- `klasoru_bosalt("junkemail")` canlı: **1120 mesaj ~4 sn, hata yok**;
  sonrasında salt okuma senkron junkemail = 0 → gerçekten boşaldı.

### Testler (hepsi geçti)
- `ews_klasor_test.py`: `sync_yaniti` ChangeKey'li; toplu HardDelete
  (Id+ChangeKey); toplu başarısızsa tek tek (X1/X3 silinir, X2 atlanır →
  sayı 2); hepsi yok → okunur hata; kısıt/önbellek kontrolleri.

## Karşılama penceresi + kendini güncelleme (2026-11-24)

**Talep:** "GitHub versiyonu güncellendiğinde otomatik olarak programda
kullanıcının indirmesine gerek kalmadan kendini güncellemesi gerekir.
Ancak açılırken ortada bir UI olmalı karşılama penceresi gibi, Outlook ya
da Anaconda gibi resimli. Ortadaki karşılama UI'sinde güncelleme yapıp
yapmadığı, neyi güncellediği ve % kaçının tamamlandığı gösterilmeli."

### Yeni modül: `guncelleme.py`
- `son_surum()`: Releases API (`tag_name`); boşsa yedek olarak `main`
  dalındaki `postacim/__init__.py` okunur; ikisi de olmazsa `(None, None)`
  (hata fırlatmaz — açılış engellenmez).
- `daha_yeni(yeni, eski)`: nokta ayrık sayısal karşılaştırma ("v" öneki atılır).
- `indir(adres, dizin, ilerleme)`: `requests.get(stream)` + `iter_content`;
  `ilerleme(yuklenen, toplam)` — Content-Length yoksa çağrılmaz.
- `_arsiv_ayikla`: tar.gz → geçici dizin; `postacim/__init__.py` içeren
  kök aranır (GitHub tarball'ı `postacim-main/` altında açılır).
- `kur(arsiv, hedef_surum, ilerleme, venv_python)`: aşama yüzdesi 0–100
  (ayıklama 75 → pip 85 → gereksinim 92 → doğrulama 97 → tamam 100);
  `pip install --no-deps <kaynak>` + `pip install -r requirements.txt`;
  doğrulama **taze süreçte** `import postacim; print(__version__)` ile
  (modül önbelleği yanıltmasın), uyuşmazsa `GuncellemeHatasi`.
- `yeniden_baslat()`: `os.execv(sys.executable, [python, "-m", "postacim"])`
  — paket göreli içe aktarma kullandığı için `-m` zorunlu.
- `otomatik_izin(ayarlar)`: tercih (`guncelleme_otomatik`, varsayılan açık)
  × `POSTACIM_GUNCELLEME` ortam değişkeni × **geliştirme koruması**:
  `sys.executable` `.../share/postacim/venv/bin` altında değilse
  (kaynaktan `.venv`) otomatik denetim yapılmaz.

### `ui.py`
- **`Karsilama(tk.Toplevel)`**: overrideredirect, koyu mavi panel
  (#0f3c66), paket içi `ikonlar/uygulama_128.png` logosu, ad, sürüm,
  durum etiketi + `Karşılama.Horizontal.TProgressbar` (0–100);
  `_ortala` ekran ortası (20/300/800 ms'de yeniden — haritalanma
  sırasında konum sıfırlanabildiği için); `durum(metin, yuzde)`,
  `bitti(surum)` → %100 + "Yeniden Başlat"/"Kapat" düğmeleri, `kapat()`.
- `Postacim.__init__`: karşılama arayüz kurulmadan ÖNCE oluşturulur ve
  `update_idletasks` ile çizilir; `after(600, _guncelleme_baslat)`,
  `after(8000, _karsilama_zamani_doldu)` (yedek kapanış).
- İlk `_klasorleri_doldur` → `_karsilama_kapat()` (güncelleme sürerken /
  kurulmuşsa beklemez — `_guncelleme_sureci` / `_guncelleme_kurulu` korur).
- `_guncelleme_denetle(elle)`: denetim → yeni sürüm varsa indir-kur;
  ilerleme `is_kuyrugu`'na `("guncelleme_durum", metin, %)` olarak yazılır
  (karşılama penceresi + durum çubuğu). Bitiş: `guncelleme_bitti`
  (kuruldu ekranı ya da pencere kapalıysa `askyesno` yeniden başlatma).
- Yardım menüsü: "Güncellemeleri Kontrol Et…" + "Otomatik güncelleme
  (açılışta)" işareti (terci `hesap.json`'a yazılır).

### Bilinen notlar
- Xvfb'de `attributes("-topmost")` / erken `lift()` overrideredirect
  pencerenin konumunu (0,0)'a sıfırlıyor — lift yalnız `winfo_viewable()`
  olduktan sonra yapılıyor; konum 20/300/800 ms'de yeniden uygulanıyor.
- Karşılama "Güncelleme denetleniyor…" → indiriliyor (0–%70) → kurulum
  aşamaları (75–%100) sırasını izler; "ne yi güncellediği" aşama adında.
- Güncelleme sürerken kullanıcı ana pencereyi kullanmaya devam edebilir;
  kurulum bitince bilgi durum çubuğunda ve pencerede kalır.
- GitHub API'si hız sınırına girerse yedek raw okuma devrede; ağ yoksa
  sessiz atlanır (durum çubuğunda "denetlenemedi" görünmez, denetim yapılmaz).

### Testler (hepsi geçti)
- `tests/guncelleme_test.py` (çevrimdışı, GUI'siz): karşılaştırma, API/
  yedek/ağ-yok, indirme + %, arşiv ayıklama (+paketsiz hata), sahte venv
  python ile `kur` (aşama yüzdesi artan, pip çağrıları kaydı, doğrulama
  uyuşmazlığı), `otomatik_izin` üç kuralı.
- `tests/karsilama_test.py` (Xvfb): pencere açık, logo, sürüm etiketi,
  ekran ortası, hazır olunca kapanış, %42 çubuk, bitti → düğmeler +
  `_guncelleme_kurulu`, hata metni, elle denetim akışı (sahte modül ile
  indirme-kurulum ve yeniden başlatma sorusu).
- `run_all.sh`: 15 test — hepsi geçti.


## Çift monitörde karşılama ortalaması (2026-11-24)

**Talep:** "programın çalıştığı monitörü tespit etmesi ve o monitörün
ortasında güncelleme ui penceresini açması gerekir" — çift monitörlü
kurulumda karşılama penceresi iki monitörün ortasına (bezin ortasına)
düşüyordu.

### Değişiklikler (`ui.py`)
- `_xrandr_coz(çıktı)`: xrandr çıktısından bağlı monitör dikdörtgenlerini
  (`(x, y, gen, yüksek)`) çözümler (saf fonksiyon, test edilebilir).
- `_xrandr_monit_orlari()`: `xrandr --current --query` çalıştırır;
  **her hata yutulur** (Wayland/xrandr yok/bozuk → `[]`), karşılama
  penceresi asla monitör tespiti yüzünden sorun çıkarmaz.
- `_monit_sec(monit_orlar, x, y)`: noktayı içeren dikdörtgeni seçer.
- `Karsilama._hedef_monit_or`: referans nokta ana pencerenin merkezi
  (görünürse), değilse **imleç konumu** (başlatıcının tıklandığı
  monitör); sonuç `_monit_onbellek`'e alınır (xrandr açılışta 1 kez).
- `_ortala`: hedef monitör bulunduysa o monitörün ortasına (+ üst
  boşluk −40px), bulunamadıysa eski davranış (tüm ekranın ortası).
- `bitti`: düğmeler pencereyi uzattığı için 50 ms sonra yeniden
  `_ortala` (pencere yeniden ölçülür ve ortalanır).

### Testler (hepsi geçti)
- `tests/karsilama_test.py`'a eklendi: xrandr çözümü (2 monitör + boş
  çıktı), `_monit_sec` (sağ monitör + monitör dışı → None), sahte
  `(1920, 0, 1920, 1080)` dikdörtgeniyle `_ortala` → pencere x ≥ 1920.
- Ara bulgu: ilk denemede `_xrandr_monit_orlari` içinde
  `islem.ok` hatası (CompletedProcess'te yok) `after` geri çağrısında
  AttributeError → `_tk_hata_yakala` başsız ortamda **modal showerror**
  açıp testi sonsuza kadar blokluyordu (hata.log'a bakılıyor;
  faulthandler.dump_traceback_later ile teşhis edildi). Düzeltildi
  (`returncode == 0`) ve çözümleyici istisnasız hale getirildi.
- `run_all.sh`: 15 test — hepsi geçti.

### Güncelleme testi notu (kullanıcı akışı)
- GitHub Releases'ta yayınlanan sürüm hâlâ v0.1.6 (v0.1.7 taslakta kalmış
  ya da yayınlanmamış); `main`'deki `__version__` 0.1.17 → güncelleyici
  doğru şekilde "yeni sürüm yok" diyor. Test için: GitHub'da
  `__version__ = "0.1.18"` işlemesi + **v0.1.18** etiketiyle Release
  yayınlanmalı (tag ile `__version__` eşleşmeli — `kur()` doğruluyor).
  Kurulu uygulama (0.1.17) açılışta bu sürümü indirip kurar.


## Açılışta güncelleme: ana pencere güncelleme bitince açılır (2026-11-24)

**Talep:** "açılışta öncelikle güncelleme esnasında program direkt
açılmasın. güncelleme penceresi öncelikle gelsin güncelleme tamamen
bittikten sonra program tamamen açılsın böylece kullanıcı yeniden
başlatmak zorunda kalmasın."

### Değişiklikler (`ui.py`)
- `Postacim.__init__`: ana pencere `withdraw()` ile gizli başlar; hesap
  bağlantı planlaması (`_hesap_ekle_penceresi` / `yenile` /
  `_ilk_baglanti` / `_diger_hesaplari_yukle` / `_bildirim_baslat` /
  `_otomatik_baslat`) yeni `_acilisi_surdur()`'a taşındı.
- `_acilis_bekliyor` bayrağı: güncelleme kararı bekleniyor.
- `_acilisi_surdur()`: kapıyı açar (deiconify + açılış planlaması +
  4 sn sonra karşılama yedeği); beklenmiyorsa işlem yapmaz (idempotent).
- `_acilis_koruma()` (20 sn): denetim sonucu kuyruğa hiç gelmezse
  açılışı kilitlenmekten kurtarır.
- `_guncelleme_baslat`: denetim izni yoksa (geliştirme/tercih/env)
  doğrudan `_acilisi_surdur()` — uygulama hemen açılır.
- `_guncelleme_bitti_isle`:
  - boş sürüm (güncelleme yok) → `_acilisi_surdur()` + karşılama kapanır;
  - **açılışta kurulum bitti** → "uygulama yeniden başlatılıyor…"
    (%100) ve 2 sn sonra **otomatik** `_guncelleme_yeniden_baslat`
    (kullanıcıya soru sorulmaz, düğme çıkmaz);
  - elle denetimde eski davranış korundu (düğmeler / askyesno).
- `_sonuc_isle` `guncelleme_hata`: açılış bekleniyorsa karşılama
  penceresinde **"Devam Et"** düğmesi (`Karsilama.hata(metin, devam)`)
  — güncelleme kurulamadıysa da kullanıcı uygulamayı açabilir; 20 sn
  koruma zamanlayıcısı da yedekler.
- `_karsilama_kapat` koruması `_acilis_bekliyor`'u da kapsar (8 sn'lik
  zamanlayıcı "Devam Et" düğmesini silemez).

### Testler (hepsi geçti)
- `tests/karsilama_test.py`: açılışta pencere gizli (`withdrawn`),
  güncelleme yokken uygulama açılır (`normal`), açılış kurulumunda
  otomatik yeniden başlatma (sahte `yeniden_baslat` kaydı), hata
  sonrası "Devam Et" ile açılışın sürmesi.
- `tests/resim_test.py`: uygulama oluşturunca `_acilisi_surdur()` ile
  güncelleme beklemesi atlanır (yoksa çubuk haritalanma denetimi 600 ms'
  lik karar penceresine takılıyor).
- `run_all.sh`: 15 test — hepsi geçti.


## "Orijinali göster" gövde alanında orijinal hal (2026-11-24)

**Talep:** "orjinalini göster de ben kodu göstermesini istemedim. benim
istediğim mail in body kısmının programda gösterildiği yerde orijinal
halinin gösterilmesiydi." — önceki uygulama ayrı pencerede ham MIME kodu
açiyordu; doğrusu gövde alanının orijinal (işlenmemiş) HTML'e geçmesi.

### Değişiklikler (`ui.py`)
- `orijinal_goster()` düğmesi **geçiş (toggle)** oldu:
  - orijinal modda değilken: `mesaj.govde_html` arka planda hazırlanıp
    **aynı gövde alanına** yüklenir; düğme "İşlenmiş hali göster" olur.
  - orijinal moddayken: sunucuya gitmeden işlenmiş gösterime döner
    (`_govde_yeniden_ciz` — `_detay_goster`'dan ayıklanan gövde çizimi).
- `_orijinal_html(mesaj)`: orijinal HTML üretimi —
  - `mesaj.resimler` (cid) + HTML'deki http/https src'ler arka planda
    `resim_verisi(self.istemci, …)` ile indirilip `_resim_data_uri` ile
    gömülür (kurum NTLM resimleri de çalışır); çözülemeyen resim olduğu
    gibi kalır,
  - `script` + yönlendiren `meta` atılır; `html_taglari_kapat` +
    `html_tablolar_onar` korunur (Tkhtml3 çökmesin),
  - `_GOSTERIM_STILI` artık ews'ten içe aktarılıyor.
- `_orijinal_goster_uygula`: kuyruk sonucu — mesaj değişmediyse /
  mod hâlâ açıksa `ayrinti.load_html`.
- `orijinal_hata` sonucu → `_govde_orijinal_resetle`: düğme + mod
  sıfırlanır, durum çubuğunda "Orijinal gösterilemedi: …".
- Korumalar: mesaj seçili değilken uyarı; `html_modu` yoksa (tkinterweb
  kurulu değil) ve mesaj düz metinse (`govde_html` boş) tıklama
  bilgilendirir; mesaj değişince (`_detay_goster`) mod + düğme yazısı
  sıfırlanır.
- Eski `_orijinal_cek` / `_orijinal_pencere` (ham MIME penceresi)
  kaldırıldı; .eml indirme (`Farklı Kaydet`, `mesaj_mime`) aynen durur.
- `ews.py`'den içe aktarımlara `html_taglari_kapat`, `html_tablolar_onar`,
  `_GOSTERIM_STILI` eklendi.

### Testler (hepsi geçti)
- `tests/orijinal_goster_test.py` baştan yazıldı: işlenmiş gösterimde yer
  tutucu görünür; orijinalde yer tutucu kalkar, içerik aynı alanda
  görünür, script sızmaz, cid resmi gömülür (`image_names`), düğme
  yazıları değişir; işlenmiş hal geri yüklenir; düz metin mesajda
  bilgilendirme; `_orijinal_html` hata fırlatınca düğme sıfırlanıp durum
  bildirilir; mesaj yokken uyarı. Testte `messagebox` yamalanır
  (başsız ortamda modal dialog bloklamasın).
- Not: `Resim` veri sınıfı yalnız `ad/kaynak/yer_tutucu` alır — testte
  `content_id=` geçmek AttributeError + modal showerror + takılma
  üretti (faulthandler ile bulundu).
- `run_all.sh`: 15 test — hepsi geçti.


## Orijinal görünümde kırık resimler (2026-11-24)

**Bildirim:** "orjinalini göster dediğimde resimler doğru
gösterilemiyor" — kırık resim ikonu (kullanıcı onayı).

### Kök nedenler (`ui.py`)
1. cid değiştirme yalnız `src="cid:…"` **çift tırnak + birebir** eşleşme
   arıyordu; tek tırnak / `SRC='CID:…'` / boşluklu yazım kaçırıyordu.
2. Çözümleme yalnız `mesaj.resimler` kayıtlarına bakıyordu; resimler
   listesi eksikse HTML'deki cid src'ler çözülmüyordu.
3. `_resim_data_uri` Pillow açamayan veride (SVG/bozuk) istisna
   fırlatıp tüm orijinal görünümü düşürüyor (orijinal_hata) ve her
   zaman `image/png` mime'ı kullanıyordu.

### Düzeltmeler
- `_orijinal_html`: HTML'deki **her** `<img src>` değeri regex ile
  bulunup çözülür (cid/http/göreli; `&amp;` çözümü ile tekrar deneme);
  değişim de regex tabanlı (`src\s*=` — tırnak tipi bağımsız; yalnız
  çözülenler değişir). cid eşleşmesinde küçük harf denemesi ekli
  (`cid:II_1` → MIME `Content-ID: <ii_1>`).
- `<base>` etiketi de atılır (göreli adresler zaten engelli).
- Yeni `_veri_mime`: bayt imzasından MIME (PNG/JPEG/GIF/BMP/WEBP/ICO/SVG).
- `_resim_data_uri`: GIF/SVG ham gömülür (animasyon/vektör bozulmasın);
  Pillow yoksa/açamazsa ham baytlar doğru mime ile gömülür — istisna
  tüm gösterimi düşürmez.

### Testler (hepsi geçti)
- `tests/orijinal_goster_test.py`'a m3: tek tırnak + `CID:II_1` büyük
  harf + boş `resimler` listesi → resim gömülür, içerik görünür.
- `run_all.sh`: 15 test — hepsi geçti.


## Orijinal görünümde uzak resimlerin kırık kalması (2026-11-24)

**Bildirim:** "hala gösterilmiyor" + ekran kaydı (`~/hata.png`) —
Hepsiburada sipariş postası; orijinal mod açık, resimler kırık
(alt metinleri görünüyordu), HTML düzeni doğru çiziliyordu.

### Kök neden
- Deneysel ölçüm: `requests.get(url)` **User-Agent'sız** → CDN 403;
  tarayıcı UA'lı → 200. Uygulama resim indirmeleri python-requests
  varsayılan kimliğiyle gittiği için Hepsiburada gibi CDN'ler
  reddediyordu (işlenmiş modda uzak resimler zaten engellendiğinden
  fark edilmemişti).

### Düzeltmeler
- `ews.py`: `TARAYICI_BASLIK` (Mozilla UA + Accept) eklendi;
  `resim_verisi` http yolu hem doğrudan istekte hem NTLM oturum
  yeniden denemesinde bu başlıkları kullanır (tıkla-göster akışı da
  yararlanır).
- `ui.py`: orijinal moda girince "Resimleri göster" çubuğu gizlenir
  (geri dönüşte `_resim_cubugunu_guncelle` yeniden gösterir);
  çözülemeyen resim sayısı durum çubuğunda "(N resim yüklenemedi)"
  olarak bildirilir.

### Testler (hepsi geçti)
- `tests/resim_test.py`: yerel sunucu artık `/resim.png` isteklerinin
  User-Agent'ını kaydeder; `resim_verisi` http isteğinin `Mozilla/5.0`
  kimliği taşıdığı doğrulanır. `SahteOturum.get` `headers` kabul eder.
- `run_all.sh`: 15 test — hepsi geçti.


## Orijinal görünüm: teşhis + MIME bir kez (2026-11-24)

**Bildirim:** "yok hala aynı" — 0.1.22/0.1.23 sonrası kırık resim
devam ediyor (kullanıcı 0.1.23'ü kurup test etmiş; hata.log'da yeni
istisna yok → hatalar sessiz yutuluyor).

### Düzeltmeler (`ui.py`, `ews.py`)
- `resim_verisi(..., ham=None)`: önceden çekilmiş MIME kabul eder;
  `ham` verilirse `istemci.mesaj_mime` tekrar çağrılmaz.
- `_orijinal_html`: MIME **bir kez** çekilir (26 resimli posta → 26
  EWS MimeContent çağrısı yerine 1; kısıtlama/hız sorunu giderilir).
- Çözülemeyen her resim "adres → hata" olarak `_orijinal_gunluk`'a
  toplanır ve `_orijinal_goster_uygula`
  `~/.local/state/postacim/orijinal.log`'a yazdırır — kullanıcı bir
  kez deneyip bizim doğrudan okuyabileceğimiz gerçek teşhis verisi
  üretir. Durum çubuğunda "(N resim yüklenemedi)" sayısı sürer.
- Testler: 15/15 geçti.


## Kırık resimlerin asıl nedeni: eksik içe aktarım (2026-11-24)

**Bildirim:** "yok hala aynı" (0.1.23 kurulu testte) → kurallar
gereği tahmin bırakılıp 0.1.24'ün teşhis kaydı okundu:
`orijinal.log` → `cid:ii_1 → NameError: name 'Resim' is not defined`.

### Kök neden
- `ui.py`'deki `.ews` içe aktarım listesinde `Resim` eksikti;
  `_orijinal_html`'in `gom()`'i `Resim(kaynak=…)` anında NameError
  fırlatıyor, `except Exception` bunu yutuyor, HER resim çözülemeden
  kalıyordu. Hata 0.1.20'den beri sürüyordu; önceki "düzeltmeler"
  (regex/UA) hiç çalıştırılmamıştı.
- Testteki "gömüldü" denetimi de yanıltıcıydı: tkinterweb kırık
  `<img>` için bile dahili görüntü adı ürettiğinden `image_names`
  sayımı 1 gösteriyordu (yanlış-pozitif).

### Düzeltmeler
- `.ews` içe aktarımına `Resim` eklendi.
- Test denetimi gerçek hale getirildi: `_orijinal_html` çıktısında
  `data:image/png;base64,` var mı, `src="cid:ii_1"` kalmadı mı,
  `_orijinal_basarisiz == []` mı — m1 ve zorlu m3 için.
- Doğrulama: orijinal.log BOŞ (hiç çözülemedi kaydı yok); run_all.sh
  15/15.


## Bağlantı tıklaması beyaz sayfa + "Resimleri göster" düğmesinin kaldırılması (2026-11-24)

**Bildirim:** "mail body de her hangi bir linke tıkladığımda mail body
nin gösterildiği kısım beyaza dönüşüyor... bu aslında ön tanımlı browser
ile açılmalı" ve "aynı zamanda tüm resimleri göster butonunu da
kaldıralım" (kapsam netleştirildi: yalnız düğme).

### Kök neden (tkinterweb 4.25.5 kaynağından)
- `handlers.py::_handle_link_click` işleyiciyi **iç** `TkinterWeb`
  parçacığından okur (`self.html.on_link_click`); `ui.py` ise işleyiciyi
  HtmlFrame kabuğunun düz özniteliğine atıyordu → asla ulaşmıyordu.
  İç parçacık varsayılan `load_url` ile bağlantıyı gövdenin İÇİNDE
  yüklemeye çalışıyor (request_func kaynakları engellediğinden beyaz
  sayfa) — içerik gidiyordu. Önceki test bu atamayı aynı yüzeysel
  öznitelikten okuduğu için yakalayamamıştı.

### Düzeltmeler (`ui.py`)
- `on_link_click=self._html_baglanti_tikla` artık `HtmlFrame(...)`
  yapılandırıcısına verilir (önerilen yol; `_tkinterweb_options` üzerinden
  iç parçacığa uygulanır). Ölü öznitelik ataması kaldırıldı.
- `_html_baglanti_tikla`: `webbrowser.open` başarısız olursa (mailto)
  `xdg-open` yedeği.
- `resim_dugmesi` kaldırıldı; `_resim_cubugunu_guncelle` yalnız sayaç
  gösterir: gizli resim varken "(N gizli — göstermek için [resim: …]
  üzerine tıklayın)". `tum_resimleri_goster` yöntemi durur (testler
  doğrudan çağırır).

### Testler (hepsi geçti)
- `tests/resim_test.py`: bağlayıcı denetimi `ayrinti.cget(
  "on_link_click")` ile iç parçacıktan okunur; toplu gösterim
  `tum_resimleri_goster()` ile çağrılır; sayaç "gizli" bildirmez denetimi.
- `run_all.sh`: 15 test — hepsi geçti.


## Hava durumu göstergesi (MGM) + üst çubuk sadeleştirme (2026-11-24)

**Talep:** "meteoroloji.gov.tr den istediğimiz her hangi bir yerin hava
durumunu çekerek programın uygun bir alanında gösterilmesini istiyorum.
hatta üzerinde tıkladığımızda daha ayrıntılı bilgileri ayrı bir ui
açarak göstermeli" — netleştirmede: Gönder/Al, Yenile, Hesaptan Çıkış
düğmeleri kalkacak; Yeni e-posta Temizle'nin yanına alınacak; boşluğa
hava durumu; varsayılan İstanbul; konum Ayarlar'dan değiştirilebilir.

### Servis doğrulaması (tahmin yok — canlı test)
- MGM sayfasının Angular servisi (`ililceler.js`) okundu; gerçek uç
  noktalar `servis.mgm.gov.tr/web/...`: merkezler/iller, merkezler/
  ililcesi?il=, merkezler?il=&ilce= (ilce boşsa öncelikli merkez),
  sondurumlar?merkezid=, tahminler/gunluk?istno= — curl ile canlı
  doğrulandı (Ankara Keçiören: 6.1°C, PB…).

### Yeni modül `postacim/meteoroloji.py`
- `iller`, `ililcesi(il)`, `merkez(il, ilce)`, `sondurum(merkezid)`,
  `gunluk_tahmin(istno)`; `MeteorolojiHatasi`; `_il_temizle`
  (İstanbul→istanbul, I→ı); `TARAYICI_BASLIK` tarzı başlıklar (UA +
  Origin/Referer); `HADISELER` kod eşlemesi (A☀️, AB🌤️, PB⛅, CB☁️,
  Y🌧️, K🌨️, TS⛈️, S🌫️…) + `hadise_goster` bilinmeyen kod yedeği.

### Değişiklikler (`ui.py`)
- `_ust_cubuk_kur`: Gönder/Al, Yenile, Hesaptan Çıkış düğmeleri
  kaldırıldı (işlevler menü/kısayol: F5, Ctrl+Q); Yeni e-posta
  Temizle'nin yanına; sağda `hava_gosterge` düğmesi.
- `_hava_yenile` (30 dk zamanlayıcı) + `_hava_cek` (arka plan:
  merkez→sondurum→tahmin) → kuyruk ("hava", …) / ("hava_hata", …).
- `_hava_uygula`: gösterge "⛅ Bakırköy 6.1°C"; `_hava_pencere`: anlık
  durum + 5 günlük tahmin (gün adları Pzt…, en yüksek/düşük, rüzgâr),
  kaynak bilgisi; -9999 yok-değerleri filtrelenir; Rüzgâr yönü pusulaya
  çevrilir; "Yenile"/"Kapat" düğmeleri; Esc.
- Ayarlar penceresi ▸ Genel: "Hava durumu konumu" — il combobox
  (readonly, MGM'den) + ilçe combobox; listeler arka planda kuyrukla
  ("hava_iller"/"hava_ilceler") yüklenir; `_kaydet` tercihi
  `hava_konum` olarak yazar ve `_hava_yenile` tetikler.
- `_ayarlar_penceresi` artık `self.ayarlar_penceresi` referansı tutar
  (kuyruk sonuçları pencere açıkken combobox'ları doldurur).
- Varsayılan: {"il": "İstanbul", "ilce": ""} → öncelikli merkez.

### Testler (hepsi geçti)
- `tests/hava_test.py` (yeni, çevrimdışı; run_all.sh'a eklendi): sahte
  `requests.get` ile uç noktalar/çözümleme, hadise eşlemesi + yedek,
  hata yolları; üst çubukta gösterge var / kaldırılan düğmeler yok;
  kuyruk sonucu etiketi günceller; ayrıntı penceresi içeriği; hata
  sonrası nötr gösterge. Not: sahte istekçi `params=` değişkenini
  denetlemeli (URL'de sorgu taşınmıyor).
- `run_all.sh`: 16 test — hepsi geçti.


## Ayarlar ilçe kilitlenmesi + hava durumu paneli (2026-11-24)

**Bildirim:** "ayarlar da ili Bursa olarak seçtiğim de ilçe dropdownu
yüklenmiyor ve pencere askıda kalıyor" + hata metni:
"AyarlarPenceresi.hava_ilceler_doldur() missing 1 required positional
argument: 'ilceler'". Ek istek: sağdaki gösterge buton değil panel gibi
olsun, Nem ve Rüzgâr da görünsün.

### Düzeltmeler
- `_sonuc_isle` "hava_ilceler" dalı: çağrı `hava_ilceler_doldur(veri[1],
  veri[2])` olarak düzeltildi (il+ilçe) — tek argümanlı çağrı TypeError
  üretip grab'lı Ayarlar penceresinde modal showerror blokluyordu.
- Hava göstergesi butondan **panele** dönüştü: `hava_paneli` çerçevesi
  + `hava_baslik` (simge+yer+sıcaklık) + `hava_ayrinti` ("Nem %83 •
  Rüzgâr 3.6 m/s B"); tıklama alanı tüm panel; paylaşılan `_pusula`
  yardımcısı (ayrıntı penceresiyle ortak).

### Testler (hepsi geçti)
- `tests/hava_test.py`: panel satırları (sıcaklık + nem/rüzgâr),
  ayrıntıda Nem/Rüzgâr satırları; Ayarlar penceresinde il listesi
  doldurma ve `hava_ilceler` kuyruk sonucuyla ilçe doldurma (geri dönüş
  denetimi); hata sonrası nötr panel.
- `run_all.sh`: 16 test — hepsi geçti.


## Güncelleme doğrulama hatası: etiket/sürüm uyumsuzluğu (2026-11-24)

**Bildirim:** "güncelleme başarısız hatası alıyorum" — kurulu 0.1.28;
yayınlanan Release etiketi **v1.0.28** (yanlışlıkla 1.0.x yazılmış).
Güncelleyici (1,0,28) > (0,1,28) sanıp indirip kuruyor; arşivdeki
__version__ 0.1.28 olduğundan `kur()` doğrulaması
"0.1.28 ≠ 1.0.28" ile reddediyor — beklenen davranış.

### Düzeltmeler
- `guncelleme.py::kur`: doğrulama hatası artık ipucu içerir
  ("Release etiketi ile koddaki __version__ uyuşmuyor — etiketi koddaki
  sürümle aynı numarayla yeniden yayınlayın").
- Sürüm 0.1.29'a yükseltildi; kullanıcıya v0.1.29 etiketiyle yeniden
  yayın talimatı verildi (eski release+tag silinerek).
- `guncelleme_test.py` mesajın ön ekini denetlediği için uyumlu;
  run_all.sh 16/16.


## Visual Studio tarzı "Mavi" tema (2026-11-24)

**Talep:** "birde visual studio da olduğu gibi koyu mavi tema ekleyelim"

### Değişiklikler (`ui.py`)
- Yeni tema değeri `"mavi"`: sv_ttk **koyu** tabanı üzerine lacivert
  palet uygulanır (arka #0d2137, satır/panel #143653, metin #e6eef7,
  vurgu #2b6cb0) — TFrame/TLabel/TButton/TEntry/TCombobox/TNotebook/
  TLabelframe/TCheckbutton/TRadiobutton/Treeview + kök pencere zemini.
- `_tema_degistir` ve açılış `sv_ttk.set_theme` çağrısı "mavi"→"dark"
  eşlemesi yapar; takvim için "mavi" de TAKVIM_STIL_KOYU'nu alır.
- Ayarlar ▸ Genel: tema radyo düğmelerine "Mavi" eklendi.

### Testler (hepsi geçti)
- `tests/tema_test.py` (yeni; run_all.sh'a eklendi): mavi tercihli
  açılışta palet uygulanır (Treeview/kök/vurgu), light'a dönüş + tercih
  kaydı, maviye geri dönüş, Ayarlar'da "Mavi" seçeneği.
- `run_all.sh`: 17 test — hepsi geçti.


## Ayarlar penceresi taşması + Görünüm menüsü kaldırma (2026-11-24)

**Bildirim:** "~/ayhata.png da görebileceğin gibi mavi tema ui ın
dışına çıkıyor. ayrıca üst menüden Görünüm kısmını çıkaralım"
(ekran kaydı: Ayarlar'da "Mavi" radyo düğmesi pencere kenarından
taşıyor).

### Düzeltmeler (`ui.py`)
- AyarlarPenceresi: 580x560 → 680x560, minsize 520→620 (Açık/Koyu/Mavi
  radyo satırı tek satırda sığıyor).
- `_menu_kur`: "Görünüm" menüsü kaldırıldı (tema Ayarlar ▸ Genel'den);
  `tema_degisken` `_tema_degistir` uyumu için tutulur.
- `tests/tema_test.py` radyo taraması derinleştirildi (notebook sayfası
  içi widget'lar da taranır).
- run_all.sh 17/17.


## Mavi tema: clam tabanlı tam palet (0.1.32, 2026-11-24)

**Bildirim:** "mavi tema ui ın dışına çıkıyor" sonrası kalan siyah/uyumsuz
parçalar (kullanıcı önizlemede gördü: "label, button, panel arka planları
siyah kalmış, sırıtıyor").

### Kök neden
- sv_ttk "sun-valley" koyu teması bazı parçalarda görsel öğeler/kendi
  renkleri kullandığı için parça parça `style.configure` yamaları tam
  kapsamıyordu; siyah alanlar lacivert arasında sırıtıyordu.

### Düzeltme (`ui.py`)
- `MAVI_PALET` + `MAVI_TEMA_AYARLARI` modül düzeyinde tanımlandı.
- `Postacim._mavi_tema_uygula()`: "mavi" adlı **clam tabanlı tam ttk
  teması** oluşturulur (tüm parçalar: TFrame, TLabel, TButton, TEntry,
  TCombobox, TSpinbox, TNotebook(.Tab), Treeview(+Heading), TPanedwindow,
  TScrollbar, TProgressbar, TCheckbutton, TRadiobutton, TLabelframe(.Label))
  ve `theme_use("mavi")` ile etkinleşir; combobox açılır listeleri ve
  kök pencere de boyanır.
- `_stil_uygula` mavi dalı yalnız `_mavi_tema_uygula()` çağırıp
  arka/on/vurgu değerlerini paletten alır; `_tema_degistir` ve açılış
  akışı buna göre sadeleşti (mavi'de sv_ttk atlanır).
- `_pusula` yardımcısı panel + ayrıntı penceresinde ortak.

### Testler (hepsi geçti)
- `tests/tema_test.py`: Treeview zemini #143653, kök #0d2137, seçim
  vurgusu #2b6cb0, light↔mavi geçişler, tercih kaydı, Ayarlar'da
  "Mavi" gösterimi.
- `run_all.sh`: 17 test — hepsi geçti.


## AliExpress 08.10.2025 postası çökertiyor (2026-11-24)

**Bildirim:** "AliExpress in 08.10.2025 tarihli mailine tıklayınca
program çöküyor ve kapanıyor"

### Soruşturma (/tmp/opencode/ali, ikili_arama.py + ddmin)
- Postanın gövdesi yalnız-okuma çekildi (ali_cikar.py → govde.html).
- Karakter düzeyi ikili arama yanıltıcı çıktı (`</style>` silinince
  kalan belge CSS metni sayılıp gövde hiç ayrıştırılmıyordu).
- Etiket sınırlarında ddmin → 34 KB'lık `.body-wrapper` bölgesi.
- Kritik bulgu: **ham gövde Tkhtml'de çökmüyor**; postacim'in
  `govde_html_gosterim` çıktısı çökertiyor.
- Basamak testi: `html_tablolar_onar` tek başına segfault üretiyor.
- Kök neden: onarım fonksiyonları etiketleri yorumların içinden de
  sayıyordu; mso koşullu yorumlardaki hayalet `<table>` sayısına göre
  gerçek akışa yanlış `<tr><td>`/`</td></tr>` yerleşiyordu.

### Düzeltme (`postacim/ews.py`)
- `_YORUM_DUZEN` + `_opak_bolunmus()`: yorum (mso koşullu yorum dâhil)
  ve script/style gövdeleri opak bölge.
- `html_taglari_kapat` ve `html_tablolar_onar` artık segment segment
  işler; opak bölgeden geçmez.
- `tests/resim_test.py`'ya yorum opaklığı denetimi eklendi.
- run_all.sh 17/17 geçti.

### Doğrulama
- Gerçek gövdeyle `govde_html_gosterim` çıktısı Tkhtml'de 15 sn
  canlı kaldı (eskiden segfault); önizleme ekran görüntüsü alındı
  (/tmp/opencode/ali/onek_onizleme.png) ve kullanıcıya gösterildi.
- Push bekliyor (kural 5-7).


## HTML gövde render'ının alt süreçte çökme denetimi (2026-11-24)

**Bildirim:** "Tkhtml terk edilmiş; Chromium gibi bir kütüphane daha
mantıklı değil mi?" tartışması sonrası seçilen çözüm: pywebview/
WebKitGTK gömme yerine **alt süreç çökme izolasyonu** (maliyeti en az,
bağımlılık eklemez).

### Yeni modül: `postacim/govde_denetim.py`
- `html_guvenli_mi(html)`: gösterim HTML'ini **alt süreçte** (gizli
  pencere, dış istekler kapalı, uygulama ayarlarıyla aynı HtmlFrame)
  yükler; ~2 sn hayatta kalırsa True, segfault'ta False, denetlenemediyse
  None (gösterim engellenmez — eski davranış).
- `cokme_logla()`: alt süreç çökmesini hata.log'a yazar.
- `__main__.py`: `faulthandler` açıldı — gelecek segfaultlarda iz
  hata.log'a düşer (bugüne kadar çökme kayıpsız geliyordu).

### `ews.py`
- `govde_metin_gosterim(mesaj, gecen)`: çökme üreten ileti için güvenli
  `<pre>` metin gösterimi; resim yer tutucuları tıklanabilir bağlantı,
  çözülen resim yer tutucunun yerine geçer.

### `ui.py`
- `_html_yukle` artık `_gövde_goster` kapısından geçer: mesaj + tür
  ("islenmis"/"orijinal") başına önbellek. Denetimsizken güvenli metin
  gösterilir, denetim arka planda koşar; True'da HTML'e geçilir,
  False'ta metin kalır + durum uyarısı + hata.log.
- Orijinal gösterim ("orijinal" türü) da aynı kapıdan geçer.
- Hata zincirinden düzeltmeler: denetim sonucunda eski (resimsiz)
  bekleyen HTML'in geri yüklenmesi; orijinal moda geçişte
  `_gövde_html_aktif` sıfırlanması.

### Testler
- `tests/govde_denetim_test.py` (yeni; run_all.sh'a eklendi): temiz
  HTML True, bilinen çökertici (hücresiz iç içe tablo) False, boş HTML
  geçer, çökme kaydı yazılır, govde_metin_gosterim denetimleri.
- Uçtan uca: gerçek AliExpress postası `_detay_goster` ile — metin
  görünümü anında, denetim ~2,5 sn sonra True, HTML'e geçiş; uygulama
  ayakta (önizleme: /tmp/opencode/ali/izolasyon_onizleme.png).
- run_all.sh 18/18 geçti.


## Gövde yükleme flaşının azaltılması (2026-11-24)

**Bildirim:** "mail gövdesi yükleme anında düz metin gösteriliyor,
birkaç saniye sonra mail yükleniyor — itici duruyor"

### Ölçüm
- Bilinen çökertilier yüklemeyi izleyen ~0,4 sn içinde ölüyor (sentetik
  ve AliExpress çökertilier: 0,34-0,40 sn).
- Alt süreç toplam süresi 2,0 sn pencereyle ~2,5 sn; 1,0 sn pencereyle
  ~1,3 sn.

### Düzeltme
- `govde_denetim.denetim_gerekmez(html)`: HTML tablo içermiyorsa
  (`<table[\s>/]`) bilinen çökme sınıflarının hepsi tablo tabanlı
  olduğundan denetim atlanır → **HTML anında** gösterilir (tablosuz
  iletilerde flaş + alt süreç tamamen yok; ölçüm 0,07 sn).
- Gözlem penceresi 2,0 → 1,0 sn (çökertilier 0,4 sn'de öldüğünden
  yeterli marj) → tablolu iletilerde metin flaşı ~1,2 sn'ye indi
  (AliExpress ile ölçüldü: 1,23 sn).
- `tests/govde_denetim_test.py`'ya denetim_gerekmez denetimleri eklendi;
  run_all.sh 18/18 geçti.


## Denetim sırasında düz metin yükleme kaldırma (2026-11-24)

**Bildirim:** "kontrole düz metin olarak hiç yüklenmesin; sadece
açamayacağı durumda düz metin olarak yüklesin"

### Düzeltme (`ui.py`)
- `_gövde_goster`: tablolu HTML denetlenirken gövde **boş** kalır
  (`load_html("")` + `_gövde_govdeyi_temizle`), durum çubuğu
  "İleti HTML olarak hazırlanıyor…" der; düz metin gösterilmez.
- Düz metin yalnız denetim False saptarsa (`coktu=True`) yüklenir.
- `_detay_goster` durum çubuğu ezmesi engellendi (denetim sürerken
  tarih•gönderen yazılmaz; sonuçta geri gelir).
- İleti/tür anahtarı (`_gövde_html_anahtar`) eklendi: ileti değişiminde
  eski içeriğin ekranda kalması ve denetimsiz HTML'in atlanarak
  yüklenmesi engellendi.

### Doğrulama
- Tablolu ileti: denetim sırasında gövde boş + durum çubuğu
  hazırlanıyor; ~1,3 sn sonra HTML + tarih•gönderen durumu.
- Fallback (denetim False): güvenli metin görünümü + çökme uyarısı.
- run_all.sh 18/18 geçti.

---

# 2026-11-25 — Google OAuth2 desteği (Gmail posta + takvim)

> **Kaldığımız yer:** OAuth2 akışı kodlandı ve çevrimdışı testlerle
> doğrulandı. Gerçek yetkilendirme + canlı IMAP/CalDAV doğrulaması
> kullanıcı akışıyla yapılacak. Önizleme gösterildi — onay +
> "github push" bekleniyor.

## İstek
"bu google oauth2 sistemini öncelikle ekleyelim"

Kullanıcı kararları (netleştirme sorusuyla):
- İstemci kimliği: **uygulamaya gömülü değil, kullanıcının Google Cloud
  kurulumundan** (Personal mod — token 7 günde sona ermez, doğrulama
  gerekmez). Bir kez client_secret JSON seçilir; `~/.config/postacim/
  google_istemci.json` altına 0600 ile kopyalanır (depoya girmez).
- Kapsam: **posta + takvim birlikte** (tek yetkilendirme:
  `https://mail.google.com/` + `https://www.googleapis.com/auth/calendar`).
- Uygulama parolası yöntemi **yedekte kalmaya devam** eder.

## Google Cloud tarafı (kullanıcı tamamladı)
- Proje: personal-mode-app (`orbital-bank-515817-v7`), OAuth2 istemcisi
  **Desktop app** türü; client_secret JSON indirildi.
- **CalDAV API etkinleştirildi** (etkin değilken CalDAV istekleri 403).

## Değişiklikler
- **`postacim/google_oturum.py` (yeni):** PKCE (S256) + loopback
  (`http://localhost:<port>`) yetkilendirme akışı; `yetkilendir()`,
  `tazele()`, `token_al()`; token kaydını çağıran saklar (hesap.json,
  0600). `access_type=offline` + `prompt=consent` ile refresh token
  garantisi. XOAUTH2 dize üreticisi (`_xoauth2_dize`).
- **`imap.py`:** `yontem="oauth2"` hesaplarında IMAP `AUTHENTICATE
  XOAUTH2` ve SMTP `AUTH XOAUTH2` (`_xoauth2_giris`, `_smtp_xoauth2`);
  hata yanıtları SASL gereği boş yanıtla tamamlanır; token süresi
  dolduğunda sessiz yenileme + `token_sakla` geri çağrısıyla
  hesap.json'a yazım.
- **`caldav.py`:** `CalDavIstemci(..., oauth=..., token_sakla=...)`;
  OAuth2 modunda Basic auth yerine **Bearer** başlığı; 401'de tek
  yenileme ile isteği tekrarlar.
- **`config.py`:** IMAP hesap varsayılanına `yontem: "parola"`.
- **`ui.py`:**
  - Hesap penceresi (IMAP): "Kimlik" combobox (Uygulama parolası /
    Google (OAuth2)); OAuth2'de parola alanı gizlenir, "Google ile
    yetkilendir…" düğmesi + durum etiketi; kayıtta `yontem`/`oauth`
    yazılır, eski parola temizlenir.
  - Takvim Hesapları: "Yöntem" combobox + **Gmail (OAuth2)** şablonu
    (yeni uç `apidata.googleusercontent.com/caldav/v2/{eposta}/events`);
    aynı yetkilendirme düğmesi.
  - `_istemci_kur` / `_caldav_istemci`: token_sakla bağları
    (hesap_guncelle / takvim_guncelle ile 0600 kayıt).
  - `_google_istemci_hazirla`: client_secret JSON seçim penceresi
    (bir kez; kopyalanır).

## Testler
- **`tests/google_oturum_test.py` (yeni, çevrimdışı, 16 denetim):**
  XOAUTH2 dize biçimi, istemci kimliği kaydet/oku (0600), token
  yenileme (refresh korunumu), `token_al` ağsızlık, loopback yetki
  akışı (sahte tarayıcı → kod → token), izin reddi, IMAP XOAUTH2
  girişi (sahte bağlantı), CalDAV Bearer başlığı + 401 yenileme,
  Basic yolların bozulmadığı denetimleri.
- run_all.sh **19/19 geçti** (yeni test dahil).
- Önizleme: `tests/oauth_onizleme.py` — Hesap ekle + Takvim Hesapları
  pencerelerinin OAuth2 görünümleri Xvfb'de çizildi.

## Kalan (bir sonraki oturum)
- [ ] Canlı doğrulama: kullanıcı Hesap Ekle → Gmail (OAuth2) ile
      yetkilendirecek; IMAP listeleme + SMTP + CalDAV çekme
      gerçek hesapta test edilecek.
- [ ] README'nin Gmail bölümlerine OAuth2 seçeneği eklenecek (push
      öncesi).
- [ ] Hesaptan Çıkış'ta OAuth token'ının korunması/mantığı (şu an
      korunur — yalnız parola silinir) karar olarak belgelenecek.

→ KULLANICI (2026-11-25): "test yapalım… evet geçir, dağıtıma çıkalım"
→ CANLI DOĞRULAMA: tarayıcı yetkilendirmesi (Postacım branding) +
  IMAP XOAUTH2 (13 klasör) + SMTP XOAUTH2 + CalDAV keşif + 30 günlük
  randevu çekimi — hepsi OK. Yolda saptanan hata düzeltildi:
  imaplib authenticate geri çağrısı HAM bayt döndürmeliydi (çift
  base64 → "Invalid SASL argument"); test de güncellendi (16/16).
  Kullanıcının Gmail hesabı hesap.json'da yontem=oauth2'ye geçirildi
  (öncesi .oauth2_oncesi_yedek yedeği, 0600). README Gmail/Takvim
  bölümlerine OAuth2 yöntemi eklendi. Sızıntı denetimi temiz
  (canlı test betiği e-postayı env'den okur: POSTACIM_OAUTH_TEST_KULLANICI).

→ KULLANICI: "github push" (2026-11-25)
→ GERÇEKLEŞTİ: 0.1.36 (MEB desteği + sertifika onarımı + pencere
taşmaları) GitHub'a push edildi. Kullanıcı v0.1.36 release'ini
yayınlamalı (v0.1.35 tag'i zaten 5da1614'te yayımlanmıştı).
