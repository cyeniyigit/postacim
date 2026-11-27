# Sürüm Geçmişi

Bu dosya [Keep a Changelog](https://keepachangelog.com/tr/1.1.0/) biçimindedir
ve proje [SemVer](https://semver.org/lang/tr/) sürümleme kullanır.

## [0.1.42] — 2026-11-27

### Değiştirilen
- **Üst çubuk deprem paneli en yeni depremi gösterir:** hava durumu
  panelinin yanındaki gösterge artık yalnızca en yeni ≥4.0 depremi
  değil, günün en yeni depremini büyüklük eşiği olmaksızın yazıyor
  (ayrıntı penceresindeki "Son deprem" kuralıyla aynı). Alt satır
  saat + günün en büyüğünü vermeye devam eder; ikon günün en
  büyüğüne göre seçilir (ML≥6 önemli, ML≥5 uyarı, aksi bilgi).
  "Deprem yok" artık yalnız gün hiç deprem yokken görünür.

### Testler
- `tests/kandilli_test.py` panel denetimleri yeni kurala göre
  güncellendi (49 denetim); `run_all.sh` 28/28 geçti.

## [0.1.41] — 2026-11-27

### Eklenen
- **Deprem ayrıntı penceresinde "Son deprem" bölümü:** pencere artık
  günün en yeni depremini (büyüklüğünden bağımsız) saat, büyüklük ve
  yerle gösterir; özet bloğunun altında, konum listesinin üstünde
  yer alır. En yeni deprem, paneldeki kuralın aynısı gibi tarih+saat
  birleşiminden bulunur (sayfadaki sıraya güvenilmez). Böylece 4.0
  üzeri deprem çıkmayan günlerde de en son olan deprem görünür.

### Testler
- `tests/kandilli_test.py` genişletildi (48 denetim): tam veride "Son
  deprem" bölümünün yeri ve içeriği; ≥4.0 deprem yokken de pencerede
  son depremin görünmesi. `run_all.sh` 28/28 geçti.

## [0.1.40] — 2026-11-26

### Eklenen
- **Kandilli deprem göstergesi:** üst çubukta hava durumu panelinin
  solunda bugünkü en yeni ML 4.0 üzeri deprem gösterilir (altında saati
  ve günün en büyüğü); 4.0 üzeri deprem yokken soluk "Deprem yok" yazar.
  Panel simgesi kandilli-quake eklentisi kuralıyla günün en büyüğüne
  göre değişir (ML≥5 uyarı, ML≥6 önemli). Panele tıklayınca ayrıntı
  penceresi: büyüklük simgeli günlük özet, konum pini ile en çok deprem
  olan konumlar ve ML 4.0 üzeri liste. Veri Kandilli Rasathanesi'nden
  (KOERI) 5 dakikada bir alınır.

### Düzeltilen
- **Kurulum:** `kur.sh` masaüstü girdisini (`postacim.desktop`) artık
  geçici dosya + `mv` ile atomik yazıyor; içerik değişmediyse hiç
  dokunmuyor. Önceden dosya kesilip yeniden yazıldığından GNOME menüsü
  (ArcMenu) yarım dosyayı okuyup gnome-shell'i çökertebiliyordu.

## [0.1.39] — 2026-11-26

### Eklenen
- **Randevu hatırlatıcıları:** randevudan X dakika önce masaüstü
  bildirimi ("10 dakika önce / 30 dakika önce / 1 saat önce / Kapalı";
  varsayılan 10 dakika — Ayarlar ▸ Genel ▸ Bildirimler). Tamamlanmış
  ya da başlamış randevular uyarılmaz; bir randevu için oturum
  başına yalnız kez uyarılır. Mevcut sistem bildirimi altyapısı
  (notify-send / D-Bus) kullanılır.
- **Gelen kutusu kuralları:** Ayarlar ▸ Kurallar sekmesinde
  gönderen/konu "içeren metin" kuralları tanımlanır; gelen kutusuna
  düşen YENİ iletiler Gönder/Al ve otomatik yenilemede otomatik
  hedef klasöre taşınır (EWS MoveItem / IMAP MOVE, olmazsa
  COPY+sil). Kurallar hesaba bağlıdır; sonradan eklenen kurallar
  mevcut postaları topluca taşımaz (taban çizgisi ilk tam çekilişte
  alınır). Taşınamayan iletiler yerinde kalır; posta akışı kesilmez.

### Testler
- `tests/hatirlatici_test.py` (yeni, 6 denetim): yaklaşan randevu
  uyarısı, tek-kez uyarı, pencere dışı/tamamlanmış/kapalı/takvimsiz
  durumlar.
- `tests/kural_test.py` (yeni, 10 denetim): eşleştirme (gönderen/
  konu, harf duyarsız), taban çizgisi, yeni ileti taşıma, diğer
  hesap kuralının atlanması, taşıma hatasında sessiz devam.
  run_all.sh 43/43 geçti.

## [0.1.38] — 2026-11-26

### Eklenen
- **Tamamlandı işaretinin makinelar arası senkronu:** takvimde
  işaretlenen "tamamlandı" artık sunucudaki olayın kendisine yazılır
  (CalDAV: `X-POSTACIM-TAMAMLANDI` alanı; EWS: `PostacimTamamlandi`
  genişletilmiş özelliği) ve tüm makinelarda aynı görünür. İşareti
  kaldırmak da sunucuya yazılır. Tekrarlayan serinin **tek kopyaları**
  için işaret yine yereldir (Google CalDAV kopya yazımını kabul
  etmiyor — canlı doğrulandı); seriyi kapsayan işaret tüm kopyalara
  yansır. Eski sürümden kalan yerel işaretler ilk çekilişte sunucuya
  otomatik taşınır. Kurum EWS'te UpdateItem takvim öğelerinde engelli
  olduğundan yazım sil + yeniden oluştur yoluyla da çalışır (canlı
  doğrulandı: CreateItem/GetItem/SyncFolderItems alanı koruyor).

### Düzeltilen
- **Açıklamaya hatırlatıcı metni karışması:** Google'ın olaylara
  gömdüğü hatırlatıcı bloğu (VALARM) kendi
  "This is an event reminder" açıklamasını olayın açıklamasına
  katıyordu (düzenleyip kaydedince kalıcılaşıyordu). Ayrıştırıcı artık
  VEVENT içine gömülü bileşenleri atlar; olay açıklaması temiz gelir.

### Testler
- `tests/tamamlanan_sunucu_test.py` (yeni, çevrimdışı, 16 denetim):
  CalDAV X- okuma/yazma/kaldırma, EWS ExtendedProperty okuma/yazma
  (UpdateItem + yedek yol), arayüz işaret birleştirmesi (sunucu esas,
  kopya yerel işareti, eski kayıt taşıma).
- `tests/ics_valarm_test.py` (yeni, çevrimdışı, 4 denetim): VALARM
  bloğunun açıklamaya katılmaması (gerçek Google çıktısıyla).

## [0.1.37] — 2026-11-25

### Eklenen
- **Takip (bayrak) işareti:** sağ tuş → "Takip" (Bugün / Yarın /
  1 hafta / Bayrağı kaldır; çoklu seçim çalışır). Listede takipli
  mesajlar konu önünde ⚑ gösterir. IMAP'ta \Flagged (Gmail'de
  yıldız), EWS'te item:Flag ile yazar; takip son tarihi sunucuda
  saklanır (EWS) / istemci alanıdır (IMAP).
- **Global arama:** arama çubuğuna "Bu klasör / Tüm klasörler" kapsam
  seçimi; aktif hesabın tüm klasörleri tek sonuçta (IMAP'ta klasör
  başına sunucu SEARCH, EWS'te istemci filtresi). Sonuçlar önbellekten
  sayfalanır, "Klasör" sütunu yalnız global aramada görünür ve
  mesajın hangi klasörden geldiğini gösterir. Tercih hatırlanır.

## [0.1.36] — 2026-11-25

### Eklenen
- **MEB (meb.gov.tr) e-posta desteği:** Hesap penceresinde "MEB'e
  ayarla" düğmesi — IMAP `epostagelen.meb.gov.tr:993` + SMTP
  `epostagiden.meb.gov.tr:465` (SSL); parola yerine MEBBİS → Kişisel
  Bilgiler → Uygulama Şifreleri'nden üretilen **uygulama kodu** kullanılır.
- **`postacim/sertifika.py`:** sunucu sertifika zincirini eksik
  gönderirse (MEB'de ara sertifika yok) AIA'dan (RFC 5280) ara
  sertifika indirilir ve doğrulama AÇIK kalarak bağlantı kurulur;
  birleşik CA deposu 0600 izinle önbelleklenir. IMAP + SMTP yollarında
  etkin.

### Düzeltilen
- **Pencere taşmaları:** Hesap penceresi (470→640px) ve Takvim
  Hesapları penceresinde alanlar/düğmeler pencere dışına taşıyordu;
  ölçüme dayalı boyutlandırma + şablon düğmelerinin 2 sütunlu ızgarası.

### Testler
- `tests/sertifika_test.py` (yeni, çevrimdışı): PEM/DER çevirisi, AIA
  çözümleme, birleşik CA yazımı (0600), onarım akışı. run_all.sh
  **20/20** geçti.

## [0.1.35] — 2026-11-25

### Eklenen
- **Google OAuth2 desteği (Gmail posta + takvim):** uygulama parolasına
  alternatif olarak Google hesabı tarayıcıda tek bir yetkilendirmeyle
  IMAP/SMTP (XOAUTH2) ve CalDAV (Bearer) erişimi alır.
  - `postacim/google_oturum.py` (yeni): PKCE + loopback yetkilendirme
    akışı, token depolama (0600) ve sessiz yenileme. İstemci kimliği
    (client_secret JSON) bir kez seçilir, `~/.config/postacim/
    google_istemci.json` altına kopyalanır (depoya girmez).
  - `imap.py`: `yontem="oauth2"` hesaplarında IMAP `AUTHENTICATE
    XOAUTH2` ve SMTP `AUTH XOAUTH2`; token süresi dolduğunda
    otomatik yenilenir ve `hesap.json`'a yazılır.
  - `caldav.py`: OAuth2 hesaplarında Bearer başlığı; 401'de tek
    yenileme ile yeniden dener. Google için **yeni** uç
    (`apidata.googleusercontent.com/caldav/v2/…`) kullanılır
    (eski uç deprecated).
  - Hesap penceresi: IMAP'ta "Kimlik" seçimi — Uygulama parolası /
    Google (OAuth2) + "Google ile yetkilendir…" düğmesi.
  - Takvim hesapları: "Yöntem" seçimi + **Gmail (OAuth2)** şablonu.
  - Not: Google Cloud tarafında CalDAV API etkin olmalı; Personal
    mod istemci tokende 7 günlük süre koymaz.

### Düzeltilen
- **OAuth2 hesapta açılışta parola sorulması:** arayüzdeki 4 kimlik
  denetimi parola arıyordu; OAuth2 hesabında parola boş olduğundan
  açılışta giriş penceresi açılıyordu. `_hesap_kimlik_tam()` yardımcısı
  eklendi (OAuth2'de refresh token kimlik sayılır). Giriş penceresi
  OAuth2 hesabında "Google ile yetkilendir…" düğmesi gösterir.
- **Giriş penceresi zemini temaya uydu** (koyu/mavi temalarda gri
  kalmıyordu).
- **Global tema paleti:** `_stil_uygula` artık `tk_setPalette` ile Tk'nın
  klasik paletini temaya çevirir — tüm açık pencereler ve bundan sonra
  açılacak alt pencereler (dialog zeminleri, menüler) seçili temayı
  izler; pencereye pencere düzeltme gerekmez.

### Testler
- `tests/google_oturum_test.py` (yeni, çevrimdışı): XOAUTH2 dizesi,
  istemci kimliği 0600 kayıt/okuma, token yenileme, loopback
  yetkilendirme akışı (sahte tarayıcı), IMAP/SMTP girişi, CalDAV
  Bearer + 401 yenileme. run_all.sh **19/19** geçti.

## [0.1.34] — 2026-11-24

### Değiştirilen
- **Gövde yükleme flaşı azaltıldı:**
  - Tablo içermeyen HTML artık alt süreç denetiminden geçmez — anında
    gösterilir (bugüne dek gözlenen Tkhtml3 çökme sınıflarının hepsi
    tablo tabanlı; ölçüm: 0,07 sn).
  - Tablolu HTML'de gözlem penceresi 2,0 → 1,0 sn indirildi (bilinen
    çökertilier yüklemeyi izleyen ~0,4 sn'de ölüyor); tablolu
    iletilerde HTML'e geçiş ~1,2 sn.
  - Denetim sırasında gövde artık **düz metinle doldurulmuyor**: boş
    kalır, durum çubuğu "İleti HTML olarak hazırlanıyor…" der. Düz
    metin yalnız denetim çökme saptayıp metin görünümüne düşerken
    yüklenir.
  - İleti değişiminde eski iletinin içeriğinin ekranda kalması ve
    denetim sürerken denetimsiz HTML'in atlanarak yüklenmesi
    engellendi (`_gövde_html_anahtar`).

### Testler
- `tests/govde_denetim_test.py`'ya `denetim_gerekmez` denetimleri
  eklendi; run_all.sh 18/18 geçti.

## [0.1.33] — 2026-11-24

### Eklenen
- **Gövde HTML'i için alt süreç çökme denetimi** (`postacim/
  govde_denetim.py`): Tkhtml3 (C) bazı bozuk e-postalarda segfault
  üretip uygulamayı düşürebiliyordu. Gösterim HTML'i artık alt süreçte
  bir kez denenir (mesaj + gösterim türü başına önbellek): hayatta
  kalırsa HTML gösterilir; çökme üretirse ileti güvenli **metin
  görünümünde** açılır ve çökme ayrıntısı hata.log'a yazılır. Denetim
  sürerken de metin görünümü gösterilir (boş bekleme yok).
- `govde_metin_gosterim`: çökme üreten iletilerin güvenli metin
  gösterimi (tıklanabilir resim yer tutucularıyla).
- Uygulama başlangıcında `faulthandler`: C düzeyi çökmelerde iz
  hata.log'a düşer.

### Düzeltilen
- **AliExpress 08.10.2025 postası programı çökertiyordu:** ham e-posta
  HTML'i zararsızdı; çöküntü `govde_html_gosterim`'in onarım adımlarından
  geliyordu. `html_taglari_kapat` ve `html_tablolar_onar` etiket
  tararken **HTML yorumlarının içindeki** (`<!--[if mso | IE]>…
  <![endif]-->`) tablo etiketlerini de sayıyordu; hayalet etiketler
  gerçek akışa yanlış `<tr><td>`/`</td></tr>` yerleştirip tabloyu
  bozunca Tkhtml3 (C) segfault üretiyordu. Artık yorumlar ile
  script/style gövdeleri (`_opak_bolunmus`) onarım geçişlerinde
  dokunulmazdır. İkili arama (ddmin) ile tetikleyici bu postada
  doğrulandı; posta artık tam içeriğiyle açılıyor.

### Testler
- `tests/govde_denetim_test.py` eklendi (run_all.sh'a da): temiz HTML
  geçer, bilinen çökertici False döner, çökme kaydı yazılır,
  govde_metin_gosterim denetlenir.
- `tests/resim_test.py`'ya "yorum opaklığı" denetimi eklendi
  (yorum/script/style içindeki etiketler onarımı yanıltamaz).
- `run_all.sh` 18/18 geçti.

## [0.1.28] — 2026-11-24

### Düzeltilen
- **Ayarlar'da il seçince ilçe listesi gelmiyordu ve pencere askıda
  kalıyordu:** arka plan sonucu işlenirken `hava_ilceler_doldur` çağrısı
  tek argümanla yapılıyordu (il eksik) → `TypeError` → grab'lı pencerede
  modal hata penceresi bloklanıyordu. Çağrı il+ilçe ile yapılmaya
  başlandı; regresyon denetimi eklendi.

### Değiştirilen
- Üst çubuktaki hava durumu göstergesi buton yerine **küçük panele**
  dönüştü: 1. satır fenomen simgesi + yer + sıcaklık, 2. satır
  **"Nem %83 • Rüzgâr 3,6 m/s B"**. Panelin herhangi bir yerine
  tıklayınca ayrıntı penceresi açılır (ayrıntıda da nem ve rüzgâr
  satırları var).

## [0.1.27] — 2026-11-24

### Eklenen
- **Hava durumu göstergesi (MGM):** üst araç çubuğunda seçilen konumun
  anlık hava durumu görünür — fenomen simgesi + sıcaklık (örn.
  "⛅ Bakırköy 6.1°C", 30 dakikada bir yenilenir). Göstergelere
  tıklayınca ayrıntı penceresi açılır: anlık durum (hissedilen, nem,
  rüzgâr, basınç) ve **5 günlük tahmin**. Kaynak: Meteoroloji Genel
  Müdürlüğü (servis.mgm.gov.tr).
- **Konum seçimi:** Ayarlar ▸ Genel bölümünde il/ilçe seçicileri
  (il listesi MGM'den doldurulur); tercih `hesap.json`'a kaydedilir.
  Varsayılan: İstanbul (ilin öncelikli merkezi).

### Değiştirilen
- Üst araç çubuğu sadeleştirildi: **Gönder/Al**, **Yenile** ve
  **Hesaptan Çıkış** düğmeleri kaldırıldı (işlevler menülerde ve
  kısayollarda sürer: F5, Ctrl+Q); **Yeni e-posta** düğmesi Temizle'nin
  yanına alındı. Boşalan alana hava durumu göstergesi yerleşti.

## [0.1.26] — 2026-11-24

### Düzeltilen
- **Gövdedeki bağlantılara tıklama gövdeyi beyazlatıyordu:** tıklama
  işleyicisi (`on_link_click`) yanlış yere (HtmlFrame kabuğunun
  özniteliğine) atanıyordu; tkinterweb tıklamayı iç parçacığından
  okuduğu için bağlantı gövdenin içinde gezinmeye çalışıyor, içerik
  gidiyordu. İşleyici artık yapılandırıcıyla iç parçacıktan verilir;
  bağlantılar **varsayılan tarayıcıda** açılır (`mailto:` için
  `xdg-open` yedeği dâhil).

### Değiştirilen
- **"Resimleri göster" düğmesi kaldırıldı:** resim çubuğu ve sayacı
  durur; resimler gövdedeki `[resim: …]` yer tutucularına tıklayarak
  açılır. Sayaç, gizli resim varken "(N gizli — göstermek için [resim:
  …] üzerine tıklayın)" şeklinde yol gösterir.

## [0.1.25] — 2026-11-24

### Düzeltilen
- **Orijinal görünümde tüm resimlerin kırık kalmasının asıl nedeni
  giderildi:** `ui.py`'de `Resim` sınıfı içe aktarım listesine
  eklenmemişti; orijinal moddaki her resim çözümlemesi `NameError`
  ile sessizce düşüyor (0.1.20'den beri). Artık satır içi (cid) ve
  uzak resimler gerçekten gömülüyor.
- Test: "gömüldü" denetimi, kırık resimde de artan tkinterweb dahili
  adlarına dayandığı için yanıltıcıydı; artık üretilen HTML'de
  `data:` URI'nin gerçekten var olduğu ve cid adresinin kalmadığı
  doğrulanır, çözülemeyen resim kalmadığı da denetlenir.

## [0.1.24] — 2026-11-24

### Değiştirilen
- Orijinal görünüm hazırlanırken mesajın MIME içeriği artık **bir kez**
  çekilir — çok resimli mesajlarda (ör. 26 resimli sipariş postası)
  sunucuya her resim için ayrı istek gitmez (hız + sunucu kısıtlaması
  riski azalır).
- Çözülemeyen resimlerin adresleri ve hata nedenleri
  `~/.local/state/postacim/orijinal.log` dosyasına yazılır (teşhis için).

## [0.1.23] — 2026-11-24

### Düzeltilen
- **Orijinal görünümde uzak resimler kırık görünüyordu:** birçok CDN
  (ör. Hepsiburada) tarayıcı kimliği (User-Agent) taşımayan istekleri
  403 ile reddediyor. Uzak resim indirmeleri artık tarayıcı kimliği ve
  resim kabul başlığıyla yapılır (elle gösterilen resimlerde de geçerli).
- Orijinal gösterimde işlenmiş moda ait "Resimleri göster" çubuğu artık
  gizlenir; yüklenemeyen resim varsa durum çubuğu sayısını bildirir.

## [0.1.22] — 2026-11-24

### Düzeltilen
- **Orijinal görünümde kırık resimler:** gövde HTML'indeki **tüm**
  `<img src>` değerleri artık çözülür — `cid:` adresleri büyük/küçük
  harf ve tırnak biçimi (tek/çift/çıplak) bağımsız eşleşir, `mesaj.resimler`
  kaydı eksikse bile MIME/eklerden bulunur; uzak resimler kurum oturumuyla
  (NTLM) indirilir. Pillow'un açamadığı veriler (SVG, bozuk baytlar) tüm
  orijinal görünümü düşürmek yerine ham olarak doğru MIME türüyle gömülür;
  hareketli GIF'ler ham gömülür (animasyon/şeffaflık korunur). `<base>`
  etiketi de atılır.

## [0.1.21] — 2026-11-24

### Değiştirilen
- **"Orijinali göster" yeniden tasarlandı:** düğme artık ayrı bir
  pencerede ham MIME kodu göstermiyor; mail'in **gönderildiği orijinal
  halini aynı gövde alanında** görüntülüyor. Satır içi (cid) ve uzak
  (http/https) resimler arka planda indirilip gövdeye gömülür (kurum
  NTLM resimleri dâhil); düğme orijinal ↔ işlenmiş görünüm arasında
  geçiş yapar, geri dönüş sunucuya gitmeden yapılır. `script` ve
  yönlendiren `meta` yine atılır, bozuk etiket/tablo onarımı korunur;
  düz metin mesajlarda bilgilendirilir.

## [0.1.20] — 2026-11-24

### Değiştirilen
- **"Orijinali göster" artık gövdeyi olduğu gibi gösterir:** düğme
  ayrı bir pencerede ham MIME kodu yerine, mail'in **gönderildiği
  orijinal halini aynı gövde alanında** gösterir — resim yer tutucuları
  ve sadeleştirmeler kalkar; satır içi (cid) ve uzak (http/https)
  resimler arka planda indirilip gövdeye gömülür. Düğme "İşlenmiş hali
  göster"e dönüşür; tekrar tıklanınca normal gösterime dönülür (sunucuya
  tekrar gidilmez). `script` ve yönlendiren `meta` etiketleri yine de
  atılır; kapanmamış etiket/tablo onarımı korunur (görüntüleyici
  çökmesin). Düz metin mesajlarda ve HTML okuyucu (tkinterweb) yokken
  düğme bilgilendirir.

### Eklenen
- Sürüm numarası artık ana pencerenin başlık çubuğunda da görünür
  ("Postacım 0.1.20 — Hesap Adı") — güncelleme sonrası yeni sürümün
  çalıştığı tek bakışta anlaşılır.

## [0.1.19] — 2026-11-24

### Değiştirilen
- **Açılışta güncelleme varken ana pencere artık açılmaz:** uygulama
  açılışta önce güncelleme kararını verir; yeni sürüm bulunursa yalnız
  güncelleme penceresi görünür (indirme + kurulum %'si), kurulum bitince
  uygulama **otomatik olarak yeni sürümle yeniden başlar** — kullanıcı
  "Yeniden Başlat" demek zorunda kalmaz. Güncelleme yoksa (ya da
  denetlenemezse/kurulamazsa) uygulama her zamanki gibi açılır; kurulama
  hatasında karşılama penceresinde "Devam Et" düğmesi sunulur.

## [0.1.18] — 2026-11-24

### Düzeltilen
- **Karşılama penceresi çift monitörde ortalanıyor:** pencere artık tüm
  ekranın (iki monitörün birleşiminin) değil, **uygulamanın çalıştığı
  monitörün** ortasında açılıyor. Monitör dikdörtgenleri `xrandr`'dan
  çözülür; referans nokta ana pencerenin merkezi (görünürse), değilse
  imleç konumudur (başlatıcının tıklandığı monitör). Monitör listesi
  alınamazsa eski davranış (tüm ekranın ortası) korunur; her hata
  yutulur, karşılama penceresi asla sorun çıkarmaz.
- Güncelleme kurulunca çıkan "Yeniden Başlat/Kapat" düğmeleri pencereyi
  uzattığı için pencere yeniden ölçülüp yeniden ortalanıyor.

## [0.1.17] — 2026-11-24

### Eklenen
- **"Orijinali göster" düğmesi:** gövde araç çubuğuna (Gövde: −/+ , Sığdır
  satırına) eklendi. Tıklandığında mesajın **ham MIME kaynağı** (.eml —
  başlıklar + gövde + ekler) ayrı bir pencerede monospace yazı tipiyle
  gösterilir (Thunderbird'ün "Kaynağı Görüntüle"si tarzı). İçerik arka
  planda `mesaj_mime` ile çekilir (IMAP `BODY.PEEK[]` / EWS `MimeContent`).
  - Büyük mesajlarda arayüzü kilitlememek için pencerede ilk 2 MB
    gösterilir; not olarak "Farklı Kaydet (.eml)" yoluna işaret edilir.
  - Mesaj seçili değilken tıklama hata vermez; durum çubuğu bilgilendirir.
  - `Esc` ya da "Kapat" ile pencere kapanır.
- **Açılış karşılama penceresi (splash):** uygulama açılırken ekranın
  ortasında logolu, "Postacım + sürüm" yazan koyu mavi bir karşılama
  penceresi görünür (Outlook/Anaconda tarzı); alt kısmında durum metni ve
  **ilerleme çubuğu (%)** vardır. Uygulama hazır olunca (ilk klasör
  listesi) ya da 8 saniyede kapanır; güncelleme sürerken açık kalır.
- **Kendini güncelleme (otomatik):** açılışta GitHub'daki en yeni sürüm
  arka planda denetlenir (Releases API; olmazsa `main` dalındaki
  `__init__.py` okunur). Kurulu sürümden yeniyse **kullanıcı bir şey
  indirmeden** güncelleme kurulur:
  1. arşiv akışla indirilir — karşılama penceresinde
     "0.1.18 indiriliyor… %N" gösterilir (Content-Length'e göre gerçek %),
  2. arşiv ayıklanır, yeni paket çalışan sanal ortama (`pip install`)
     ve gereksinimleri kurulur, aşamalar % cinsinden gösterilir,
  3. kurulum taze bir süreçte doğrulanır (sürüm uyuşmazsa hata).
  Bitince karşılama penceresinde **"Yeniden Başlat"** düğmesi çıkar;
  uygulama aynı komutla (`python -m postacim`) yeni sürümle yeniden açılır.
  Karşılama penceresi kapalıysa kurulum bitince yeniden başlatma sorulur.
- **Yardım menüsü → "Güncellemeleri Kontrol Et…"** (elle denetim; sonuç
  iletişim kutusuyla bildirilir) ve **"Otomatik güncelleme (açılışta)"**
  işareti (terci `hesap.json`'da saklanır, varsayılan açık).
- **Kurallar:** geliştirme ortamından (kaynaktan `.venv`) çalışırken
  otomatik denetim yapılmaz (geliştiricinin ortamına sessiz kurulum
  olmasın); `POSTACIM_GUNCELLEME=0` ortam değişkeni denetimi kapatır.
  Ağ yoksa denetim sessizce atlanır — açılış hiçbir koşulda engellenmez.

### Testler
- `tests/orijinal_goster_test.py` (yeni, çevrimdışı): düğme varlığı,
  mesaj seçilmeden tıklamada uyarı, tıklamada `mesaj_mime` istemciden
  çağrılır, "Orijinal — <konu>" penceresi açılır, ham başlıklar/gövde
  görünür, büyük mesaj 2 MB'de sınırlanır ve not eklenir.
- `tests/guncelleme_test.py` (yeni, çevrimdışı): sürüm karşılaştırma,
  API/yedek/ağ-yok yolları, akışla indirme + %, arşiv ayıklama, sahte
  venv python ile `kur` aşamaları + doğrulama, `otomatik_izin` kuralları.
- `tests/karsilama_test.py` (yeni, Xvfb): karşılama penceresi (logo,
  sürüm etiketi, ekran ortası), % çubuğu, "guncelleme_durum/bitti/hata"
  kuyruk sonuçları, hazır olunca kapanış, elle denetim akışı.
  Üçü de `run_all.sh`a eklendi.

## [0.1.15] — 2026-11-23

### Düzeltmeler
- **Kurum (EWS) hesabında "Çöp Kutusunu Boşalt" `ErrorItemNotFound`
  veriyordu.** Silme istekleri artık `ItemId + ChangeKey` ile gönderilir;
  toplu istek `ErrorItemNotFound` verirse öğeler **tek tek** denenir ve
  artık sunucuda bulunmayan öğeler atlanır (senkron ile silme arasında
  kaybolanlar). Hiçbir öğe silinemediyse okunur hata verilir.
- **Canlı doğrulama (kurum sunucusu):** spam klasörü yeni yolla
  boşaltıldı — 1120 mesaj ~4 saniyede, hata yok; salt okuma senkron
  ile klasörün gerçekten boşaldığı doğrulandı.

## [0.1.14] — 2026-11-23

### Eklenen
- **Sağ tuş menüsünde klasör boşaltma:** klasör ağacında **Silinmiş
  Öğeler**'e sağ tıklayın → **"Çöp Kutusunu Boşalt…"**, **Önemsiz**
  klasörüne sağ tıklayın → **"Spam'i Temizle…"** (yalnız aktif hesapta;
  IMAP ve EWS). Onay penceresi sorar ("kalıcı olarak silinecek, geri
  alınamaz"); işlem arka planda yapılır, bitince klasör listesi ve
  sayaçlar yenilenir ve durum çubuğu silinen mesaj sayısını gösterir.
  - **IMAP/Gmail:** klasör seçilir, tüm mesajlar `UID SEARCH ALL` ile
    listelenir, aralık kümeleriyle (`1:5,9,11:14`, 300'lük gruplar)
    `\Deleted` işaretlenir ve `EXPUNGE` ile gerçekten silinir.
  - **Exchange (EWS):** `EmptyFolder` yerine SyncFolderItems +
    toplu `DeleteItem HardDelete` (istek başına ≤100 mesaj) — kurum
    sunucusunda çalıştığı doğrulanmış işlemler; silinen sayı sayılabilir
    kalır ve klasörün senkron önbelleği düşürülür.
  - İstemci düzeyinde yalnız çöp kutusu ve spam klasörüne izin verilir;
    başka klasör okunur hata verir.

### Testler
- `tests/coklu_hesap_test.py` — IMAP `klasoru_bosalt`: `UID STORE
  101:103 +FLAGS.SILENT (\Deleted)` + EXPUNGE, sayı 3, önbellek
  bırakılır; gelen kutusu kısıtı; boş klasörde 0.
- `tests/imap_yerel_sunucu_test.py` — tel denetimi: ham `UID SEARCH
  ALL`, `UID STORE 101 +FLAGS.SILENT (\Deleted)`, `EXPUNGE`.
- `tests/ews_klasor_test.py` — SyncFolderItems + HardDelete gövdesi
  (iki mesaj tek istekte), sayı, senkron önbelleği düşer, kısıt.
- `tests/hesap_ui_test.py` — menüde öğeler (IMAP + EWS, diğer
  klasörlerde yok, başka hesapta menü yok), akış istemciye ulaşır
  (çöp kutusu + spam).

## [0.1.13] — 2026-11-23

### Düzeltmeler
- **Gmail aramasında mail seçince uygulama çöküyordu (segfault) — kök
  neden çözüldü.** "Hepsi" aramasının ilk sonucu (bozuk HTML'li
  tanıtım e-postası) görüntülenirken Tkhtml3 yerli bileşeni çöküyordu.
  Canlı izleme ve kademeli sadeleştirme (bisection) ile tetikleyici
  bulundu: **`<table>` çocuğu doğrudan başka bir `<table>` olan bozuk
  HTML** (`<table><table>…</table></table>`, arada `<tr><td>` yok).
  Tarayıcılar bunu sessizce sarar; Tkhtml3 herhangi bir içerikte, boş
  tabloda bile segfault üretir.
  - Çözüm: `govde_html_gosterim` artık `html_tablolar_onar` ile her
    çıplak çocuğu tarayıcı kuralının aynısı olan
    `<table><tr><td><table>…</table></td></tr></table>` biçimine sarar.
  - Canlı doğrulama: aynı e-posta, aynı adım (arama → ilk mail seçimi)
    artık çökmüyor; düzenlenmiş HTML sadeleştirilmiş ortamda sorunsuz
    render ediliyor.

### Testler
- `tests/resim_test.py` — `html_tablolar_onar`: çıplak çocuk sarma,
  art arda çocuklar, hücre içi tablolara dokunmama, tbody altı,
  kapanmamış tablo, `govde_html_gosterim` entegrasyonu.

## [0.1.12] — 2026-11-23

### Düzeltmeler
- **Seçilen mail artık klasör yüklenirken de beklemiyor.** Gövde
  indirmeleri (mesaj detayı, ek indirme, .eml kaydı) **ayrı bir IMAP
  oturumunda** yürür; eskiden hepsi klasör senkronizasyonunu tutan ana
  oturumun kuyruğunda bekliyordu — "Gelen Kutusu yüklenirken maili
  seçiyorum, açılması uzun sürüyor" durumunun asıl nedeni buydu.
  - Gövde oturumu klasör listesi yüklenirken **önden açılır**
    (`detay_hazirla`); ilk seçimde bağlantı kurulma beklemesi kalmaz.
  - Sunucu ikinci oturumu reddederse eski yola (ana oturum) sessizce
    dönülür.
  - Daha önce görüntülenen bir mail yeniden seçildiğinde gövde
    önbellekten **anında** gösterilir (ağ yok).
  - `gelen_sayisi` üstündeki yanlışlıkla çiftlenmiş kilit dekoratörü
    temizlendi.

### Testler
- `tests/coklu_hesap_test.py` — ana oturum BYE'e düşürülmüşken (klasör
  senkronu kilitliyken) `mesaj_detay` gövdeyi ayrı oturumdan yükler;
  `BODY.PEEK[]` FETCH'leri ana oturuma gitmez; ek indirme/.eml; ikinci
  çağrı önbellekten okunur.

## [0.1.11] — 2026-11-23

### Düzeltmeler
- **Mesaj listesi, fare seçimi sürerken yeniden kurulmaz.** Toplu silme/
  taşıma sonrası yeni sayfa yüklenirken kullanıcı listede seçim yapıyorsa
  (Shift ile çoklu seçim vb.) liste `delete`+`insert` ile anında yeniden
  kuruluyordu; bu Tcl/Tk seçim sürüklemesiyle çakışıp bazı ortamlarda
  çökmeye yol açabiliyordu (kullanıcı raporu: Gmail arama sonuçları →
  1. sayfayı sil → 2. sayfa → fare ile seçerken program kapandı). Artık
  sonuç, fare düğmesi bırakılınca uygulanır (en fazla ~3 sn bekler).
- **Beklenmeyen Tk hataları artık kayda alınıp gösterilir.** Tk varsayılanında
  arayüz geri çağrılarındaki hatalar yalnız terminale yazılır; menüden
  açılan uygulamada hiçbir iz kalmıyordu. Artık iz
  `~/.config/postacim/hata.log`a yazılır ve kullanıcıya kısa bir açıklama
  gösterilir; uygulama kapanmaz.
- Çoklu seçimde beklenmedik satır kimliği gelirse seçim çökmesin
  (`int()` dönüşümü korunumlu).

### Testler
- `tests/silme_sayfa_test.py` (yeni) — kullanıcı senaryosu sahte istemciyle:
  aramalı sayfalı sonuçlar → ilk sayfayı topluca sil → yeni sayfa → seçim;
  sayfa küçülme yolu; **fare basılıyken liste yeniden kurulmaz, bırakınca
  uygulanır** (Xvfb).

## [0.1.10] — 2026-11-23

### Eklenen
- **Klasör yeniden adlandırma (sağ tuş):** klasör ağacında özel/kullanıcı
  klasörüne sağ tıklayın → **"Yeniden Adlandır…"** (yalnız aktif hesapta;
  IMAP ve EWS). Ad penceresi mevcut adla öndoldurulur, tamamı seçilidir
  (üzerine yazmak tek hareket; Enter = Değiştir, Esc = İptal). Aynı ad
  girilirse işlem yapılmaz; boş ad uyarı verir. İşlem arka planda yapılır,
  bitince klasör listesi ve sayaçlar yenilenir.
  - **IMAP/Gmail:** `RENAME <eski> <yeni>`; adlar değiştirilmiş UTF-7 ile.
    Etiketin kimliği değiştiği için eski adın önbelleği bırakılır ve harita
    güncellenir. Özel klasörler (gelen kutusu, gönderilmiş, …) reddedilir.
  - **Exchange (EWS):** `UpdateFolder` ile `folder:DisplayName` güncellenir;
    klasör kimliği değişmez. Exchange güncel ChangeKey istediği için önce
    tek `GetFolder` ile tazelenir, sonra yazılır (tekrar edilmez).
    Varsayılan 7 klasör reddedilir.

### Testler
- `tests/ews_klasor_test.py` — UpdateFolder gövdesi (ChangeKey tazeleme,
  alan URI), kimlik değişmez, önbellek düşürme, varsayılan klasör/boş ad
  reddi.
- `tests/coklu_hesap_test.py` — IMAP `RENAME` (ascii ve utf-7 adlar),
  harita/önbellek güncellemesi, özel klasör koruması, sunucu reddi, boş ad
  ve aynı-ad no-op.
- `tests/imap_yerel_sunucu_test.py` — tel denetimi: ham
  `RENAME "Proje X" "Proje 2"` komutu.
- `tests/hesap_ui_test.py` — menüde "Yeniden Adlandır…" (IMAP özel klasör +
  EWS kullanıcı klasörü; inbox'ta yok), adlandırma akışı istemciye ulaşır
  (IMAP ve EWS), aynı ad/boş ad davranışları.

## [0.1.9] — 2026-11-23

### Eklenen
- **Klasör oluşturma (sağ tuş):** klasör ağacında hesap ya da herhangi bir
  klasöre sağ tıklayın → **"Yeni Klasör…"** (yalnız aktif hesapta; IMAP ve
  EWS). Ad penceresi küçük bir diyalogdur (Enter = Oluştur, Esc = İptal);
  boş ad uyarı verir. Oluşturma arka planda yapılır; bitince klasör listesi
  ve sayaçlar otomatik yenilenir.
  - **IMAP/Gmail:** `CREATE` komutu; adlar değiştirilmiş UTF-7 ile gider
    (Türkçe karakterler telde ascii). Yeni klasör, listelenmeden önce de
    komutlarda kullanılabilir.
  - **Exchange (EWS):** `CreateFolder` istekleri kök (`msgfolderroot`) altında
    açılır; yeniden deneme yapılmaz (geçici hatada aynı klasör iki kez
    oluşmasın).
- **EWS'te kullanıcı klasörleri artık listeleniyor.** 7 varsayılan klasörün
  yanına `FindFolder` (`msgfolderroot`, Shallow) ile kullanıcı klasörleri de
  eklenir; posta olmayan klasörler (takvim, kişiler, görevler) ve varsayılan
  adlar elenir. `FindFolder` desteklemeyen sunucularda liste 7 klasörle
  devam eder; sonuçlar 60 sn önbelleklenir.
- Kullanıcı klasörüne taşıma: mesaj sağ tuş → Taşı listesinde artık
  Exchange kullanıcı klasörleri de görünür (`FolderId` ile taşınır).

### Testler
- `tests/ews_klasor_test.py` (yeni) — CreateFolder gövdesi, FolderId
  döndürme, FindFolder listeleme/eleme/önbellek/hata yolları, kullanıcı
  klasörüne taşıma (istek mock'lu, çevrimdışı).
- `tests/coklu_hesap_test.py` — IMAP `CREATE` komutu (utf-7), harita
  güncellemesi, sunucu reddi ve boş ad hataları.
- `tests/imap_yerel_sunucu_test.py` — tel denetimi: ham `CREATE "Yeni
  Klas&APY-r"` komutu.
- `tests/hesap_ui_test.py` — menüde "Yeni Klasör…" (aktif hesap, klasör ve
  hesap düğümü), oluşturma akışı istemciye ulaşır, boş ad uyarısı, EWS
  hesapta oluşturma çalışır.

## [0.1.8] — 2026-11-23

### Eklenen
- **Birden çok ek seçip topluca indirme.** Ek listesi artık çoklu seçime
  açık (Ctrl/Shift ile tıklama, Ctrl+A ile tümü). Birden fazla ek seçilince
  hedef klasör sorulur ve tüm ekler tek işlemde oraya yazılır; tek ek
  seçiminde eskisi gibi "farklı kaydet" penceresi açılır.
- Ek listesinde sağ tık menüsü: "Seçilenleri indir (N)" ve "Tümünü indir…".
- Aynı adlı dosyalar üzerine yazılmaz; `ad (1).uzantı`, `ad (2).uzantı` …
  biçiminde benzersiz ad üretilir. Yol ayırıcıları ve geçersiz karakterler
  dosya adından temizlenir.
- Bir ek indirilemezse diğerleri kaydedilmeye devam eder; sonunda hangi
  eklerin indirilemediği uyarı olarak gösterilir.
- Klasör seçimi de yerel dosya seçiciyi kullanır (`dosya_secici.dizin_sec`).

### Testler
- `tests/ek_indir_test.py` — dosya adı temizliği, çakışma çözümü, toplu
  indirme ve kısmi hata dayanıklılığı.
- `tests/dosya_secici_test.py` — klasör seçimi (zenity `--directory`).

## [0.1.7] — 2026-11-23

### Değişen
- **Dosya ekleme ve kaydetme pencereleri artık masaüstünün yerel dosya
  seçicisiyle açılıyor.** Tk'nin sade penceresi yerine GNOME/XFCE/MATE'de
  `zenity` (yerler çubuğu, arama, son kullanılanlar, yer imleri), KDE'de
  `kdialog` kullanılır; ikisi de yoksa eski `filedialog`a düşülür.
  `POSTACIM_DOSYA_SECICI=tk|zenity|kdialog` ile seçici zorlanabilir.
- **Ek seçiminde birden çok dosya** seçilebilir; belge, tablo, sunu, resim,
  arşiv ve e-posta süzgeçleri eklendi. Açılamayan dosya için hata gösterilir.
- Son kullanılan dizin hatırlanır (ilk açılışta İndirilenler). Ek kaydetme ve
  "Mesajı farklı kaydet" aynı dizinle açılır; eksik uzantı (.eml/.bin) eklenir.
- **Depo güvenliği:** `hesap.json` ve `kisiler.json` `.gitignore`a eklendi;
  testteki kişisel ad yer tutucuyla değiştirildi; güncelleme sırasında kişisel
  posta bilgilerinin ayıklanması kuralı `DEVAM.md`ye işlendi.

### Eklenen
- `tests/dosya_secici_test.py` — süzgeç çevirisi, seçici zorlama,
  zenity/kdialog çıktısının çözümlenmesi, iptal ve tk yedeği testleri.

## [0.1.6] — 2026-11-23

### Düzeltilen
- **Başlatıcı, çalışan uygulama kapatıldığında yanlış uyarı veriyordu.**
  Uygulama bir sinyal ile sonlandırıldığında (ör. kapatıldığında) artık
  "Postacım başlatılamadı" iletişim kutusu gösterilmiyor; yalnızca gerçek
  başlatma hatalarında gösteriliyor. Uzun süre çalışıp kapanan uygulamada
  "beklenmeyen şekilde kapandı" başlığı kullanılır.
- **Yeni e-posta geldiğinde işletim sistemi bildirimi çıkmıyordu.** Üç düzeltme:
  - Bildirim artık uygulamanın kendi simgesiyle (`postacim`) gönderiliyor;
    `notify-send` yoksa doğrudan D-Bus (`org.freedesktop.Notifications`)
    üzerinden gönderilir.
  - GNOME'da bildirim balonları kapalıyken (`show-banners=false`) uyarı
    **hiç görünmüyordu**. Artık uygulama içinde geçici bir uyarı penceresi
    (toast) gösterilir ve durum çubuğu da yeni postayı bildirir.
  - Sistem balonları kapalıysa durum çubuğunda uyarı verilir; Ayarlar ▸
    Genel'deki "Sistem bildirimlerini aç" düğmesi ayarı açar.
- **Gövde içeriği sağa kayıyordu ve okunamıyordu.** Geniş içerikli
  (geniş tablo, sabit aralıklı metin) postalarda içerik görüntü alanından
  taşıyor, yatay kaydırma çubuğu da olmadığı için bir kısmı hiç
  erişilemiyordu. Artık:
  - Gövde alanında **yatay kaydırma çubuğu** var (`horizontal_scrollbar="auto"`).
  - **"Sığdır"** düğmesi içeriği pencere genişliğine sığdırır (zoom).
  - **"Genişliğe sığdır"** seçeneği açıkken pencere yeniden boyutlandırıldığında
    içerik otomatik sığdırılır.
  - Ctrl+tekerlek ile yakınlaştırma/uzaklaştırma, Ctrl+0 ile sıfırlama.

### Eklenen
- Ayarlar ▸ Genel ▸ Bildirimler: "Yeni e-posta geldiğinde uyarı göster"
  seçeneği ve sistem bildirim balonlarını açma düğmesi.
- `tests/bildirim_test.py` — bildirim karar mantığı, komut kurulumu ve
  uygulama içi uyarı testleri.
- `tests/govde_test.py` — yatay kaydırma çubuğu, sığdırma ve zoom testleri.

## [0.1.5] — 2026-11-23

### Düzeltilen
- **Uygulama menüde kurulu görünüyor ama hiç açılmıyordu (GNOME)**: Masaüstü
  girdisinden başlatılan uygulamanın hata çıktısı ekrana basılmaz; hata yalnızca
  oturum günlüğüne düşer. Kullanıcı "hiçbir şey olmuyor" görüyordu. Üç neden
  giderildi:
  - Kurulum **editable** yapılıyordu (`pip install -e`); Postacım klasörü
    taşındığında/silindiğinde uygulama `No module named postacim` ile ölüyordu.
    Artık normal kurulumda paket sanal ortama **kopyalanır**; kaynak klasör
    taşınsa bile uygulama çalışır. (Editable kurulum yalnızca `--gelistirici`
    seçeneğinde kullanılır.)
  - **Tk (tkinter) eksikse** kurulum "başarılı" görünüyor, uygulama ise hiç
    açılmıyordu. Artık `kur.sh` kurulumdan önce `tkinter` varlığını kontrol
    eder ve eksikse `python3-tk` yolunu gösterir.
  - Kurulum sonrası **doğrulama** yapılır (`import tkinter, postacim`); bozuk
    kurulum "başarılı" diye bildirilmez.
- `kur.sh` artık **root (sudo) ile çalıştırılmayı reddeder**: kullanıcı
  dizinine kurulan dosyaların sahibi root olur ve uygulama sessizce açılmaz.

### Eklenen
- `tools/baslatici.sh` — hata yutmayan başlatıcı: başlatma hatası
  `~/.local/state/postacim/hata.log` dosyasına yazılır ve (varsa `zenity`,
  `kdialog` ya da `xmessage` ile) kullanıcıya **iletişim kutusunda** gösterilir.
  Hata türüne göre çözüm önerilir (eksik `tkinter`, bozuk sanal ortam,
  kaynak klasörün taşınmış olması).
- `postacim/__main__.py` — arayüz içe aktarılamadığında (eksik `tkinter`,
  bozuk kurulum) anlaşılır hata mesajı basar; iz (traceback) yerine
  "yeniden kurun" yönergesi verir.
- README'ye "kurulu görünüyor ama açılmıyor" senaryosu için sorun giderme
  satırları ve `python3-tk` gereksinimi.

## [0.1.4] — 2026-11-22

### Düzeltilen
- **Okundu/okunmadı işareti artık sunucuya yazılıyor**: EWS isteğinde
  `ItemChange` elemanı yanlış ad alanında (`m:ItemChange`) gönderiliyordu;
  Exchange "ErrorInvalidArgument — The request is invalid." döndürüyor ve
  durum çubuğunda *"Okundu bilgisi sunucuya yazılamadı"* uyarısı çıkıyordu.
  Doğrusu `t:ItemChange` (types ad alanı) — düzeltildi ve canlı doğrulandı
  (sunucudan geri okundu).
  *Not: bu hata sunucudan değil, istemciden kaynaklanıyordu.*

### Eklenen
- `tests/coklu_hesap_test.py` → EWS SOAP gövdesi ad alanı testleri
  (`t:ItemChange` kullanımı, `m:ItemChange` kullanılmaması)

## [0.1.3] — 2026-11-22

### Düzeltilen
- **Takvimde yeni randevu eklenemiyordu**: randevu penceresinde kaydetme
  sırasında seçilen takvim kaynağı yanlış alandan okunuyordu (başlangıç
  tarihi) → *"Beklenmeyen hata: 'datetime.datetime' object is not
  subscriptable"*. Artık EWS ve CalDAV hedefleri doğru seçiliyor; saat
  (gece yarısı dahil) olduğu gibi aktarılıyor.
- Randevu **düzenlenirken** kayıt kendi takvim hesabına gider (`kaynak_id`),
  listede başka hesap seçili olsa bile.
- Birden çok Exchange hesabı varken yeni randevu, seçilen EWS hesabına yazılır
  (daima aktif posta hesabına değil).

### Eklenen
- `tests/randevu_ekle_test.py` — randevu ekleme/güncelleme akışının
  çevrimdışı regresyon testi (`tests/run_all.sh` ve CI'a eklendi)

## [0.1.2] — 2026-11-22

### Eklenen
- **Kaldırıcı**: `postacim-kaldir` (kurulumdan sonra `~/.local/bin/` altına
  kurulur, kaynak klasörü silinse bile çalışır). `--tumu` ile hesaplar ve
  ayarlar da silinir, `--ayarlar` yalnız ayarları siler
- **Uygulama içinden kaldırma**: Yardım → "Postacım'ı Kaldır…"
- `kur.sh --kaldir` artık simgeleri de kaldırır ve ayarları sorar

## [0.1.1] — 2026-11-22

### Eklenen
- **Pencere simgesi**: başlık çubuğunda uygulama simgesi (64×64 ölçekli
  PNG), görev çubuğu/launcher eşleşmesi için `WM_CLASS` (`tk appname`)
- **Hakkında penceresi**: logolu, sürüm bilgili özel pencere (eskiden düz
  `messagebox` idi)
- **Sürüm tek kaynaktan**: `postacim/__init__.py` → `__version__`;
  `pyproject.toml` bunu okur

### Düzeltilen
- `wm class` komutu Tk'de yoktu; pencere eşleşmesi `tk appname` ile yapılıyor

## [0.1.0] — 2026-11-22

İlk açık kaynak sürümü.

### Eklenen
- **Uygulama simgesi**: zarf + pull motifli, 256×256 PNG (`postacim/ikonlar/
  uygulama.png`) ve vektör SVG; `tools/ikon_olustur.py` betiğiyle yeniden
  üretilebilir. `kur.sh` 16–256 boyutlarını üretip `~/.local/share/icons/`
  altına kurar, uygulama menüsü girdisi `Icon=postacim` olur
- **Kurulum betiği (`kur.sh`)**: sanal ortamı oluşturur, bağımlılıkları kurar,
  uygulamayı kurar, `~/.local/bin/postacim` başlatıcısı ve uygulama menüsü
  girdisi (`.desktop`) oluşturur; `--kaldir` ile kaldırma, `--gelistirici`
  ile yalnız geliştirici ortamı seçenekleri
- **`run.sh`**: sanal ortam yoksa kendisi kurup uygulamayı başlatır
- **EWS istemcisi**: `GetFolder`, `SyncFolderItems` (artımlı liste),
  `GetItem`, `CreateItem`, `MoveItem`, `DeleteItem`, `GetAttachment`,
  `ResolveNames` (kişi tamamlama) ve REST API yedeği
- **IMAP/SMTP istemcisi**: Gmail ve genel IMAP hesapları; klasör listesi,
  UTF-7 ad çözümleme, özel klasör koruması, etiket silme
- **CalDAV istemcisi**: takvim keşfi, randevu okuma/yazma/silme,
  iCalendar üretimi ve ayrıştırma, TZID desteği, ETag yönetimi
- **Takvim arayüzü**: Ay / Hafta / Gün görünümleri, ajanda paneli,
  randevu penceresi (tekrar seçimi dâhil), tekrarlayan olayların
  (RRULE) görünür pencereye göre genişletilmesi
- **Çoklu hesap**: hesap ağacı, hesaplar arası geçiş, "Hesaptan Çıkış"
- **Okuyucu**: HTML gövde gösterimi (tkinterweb), Evolution tarzı resim
  yer tutucuları, "Resimleri göster", dış kaynak engelleme
- **Yazma**: yeni e-posta, yanıtla/yanıtla herkese/ilet, Cc, ek ekleme,
  kurum dizininde kişi tamamlama
- **Otomatik yenileme** (posta ve takvim için), Gönder/Al (F9)
- **Tema**: Sun Valley (açık/koyu), tema uyumlu takvim renkleri
- **Paketleme**: `pyproject.toml`, GPL-3 lisansı, GitHub Actions test akışı

### Bilinen sınırlar
- Bazı Exchange sunucularında `UpdateItem` ve `GetAttachment` bozuktur;
  istemci alternatif yola geçer (okundu işaretleme kaydedilemez, ekler
  MIME içeriğinden ayrılır)
- OWA tarayıcı dışından kullanılamayan sunucularda web arayüzüne geçilemez
- Arama istemci tarafındadır (büyük klasörlerde yavaşlayabilir)

## [0.1.29] — 2026-11-24

### Düzeltilen
- Güncelleme doğrulama hatası artık nedeni açıkça söyler: kurulan sürüm
  beklenenden farklıysa "Release etiketi ile koddaki __version__
  uyuşmuyor" ipucu da gösterilir (v1.0.28 gibi etiket/kod uyumsuzluğu
  sık karşılaşılan bir durumdur).

### Not
- Sürüm 0.1.29: önceki yayınlanan etiket `v1.0.28` (koddaki 0.1.28 ile
  uyuşmadığı için güncelleme doğrulamada reddedilmişti). Bu sürümü
  almak için Release etiketi `v0.1.29` olmalıdır.

## [0.1.30] — 2026-11-24

### Eklenen
- **"Mavi" teması:** Visual Studio tarzı koyu lacivert görünüm — lacivert
  zemin (#0d2137), koyu mavi satır/paneller (#143653), mavi seçim vurgusu
  (#2b6cb0). Ayarlar ▸ Genel'de Açık/Koyu seçeneklerinin yanında
  "Mavi" seçeneği; takvim de koyu palete geçer. Tercih hesap.json'da
  saklanır.

## [0.1.32] — 2026-11-24

### Düzeltilen
- **"Mavi" temada siyah/uyumsuz parçalar:** tema artık sv_ttk koyu
  temasının üzerine parça parça yamalanmıyor; clam tabanlı **tam ttk
  teması** olarak tanımlı (`MAVI_TEMA_AYARLARI`) — tüm paneller,
  listeler, giriş alanları, sekmeler, kaydırma çubukları, combobox
  açılır listeleri ve kök pencere paletten renk alıyor.
- Rüzgâr yönü pusula çevirisi panele ve ayrıntı penceresine ortak
  yardımcıyla yapılır.

## [0.1.31] — 2026-11-24

### Düzeltilen / Değiştirilen
- Ayarlar penceresi genişletildi: "Mavi" tema seçeneği artık pencereden
  taşmıyor (Açık/Koyu/Mavi tek satırda).
- Üst menüden "Görünüm" menüsü kaldırıldı — tema tercihi Ayarlar ▸
  Genel'den yapılıyor.

