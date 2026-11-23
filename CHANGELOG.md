# Sürüm Geçmişi

Bu dosya [Keep a Changelog](https://keepachangelog.com/tr/1.1.0/) biçimindedir
ve proje [SemVer](https://semver.org/lang/tr/) sürümleme kullanır.

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
