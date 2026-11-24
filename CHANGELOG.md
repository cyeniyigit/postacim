# Sürüm Geçmişi

Bu dosya [Keep a Changelog](https://keepachangelog.com/tr/1.1.0/) biçimindedir
ve proje [SemVer](https://semver.org/lang/tr/) sürümleme kullanır.

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
