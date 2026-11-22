# Sürüm Geçmişi

Bu dosya [Keep a Changelog](https://keepachangelog.com/tr/1.1.0/) biçimindedir
ve proje [SemVer](https://semver.org/lang/tr/) sürümleme kullanır.

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
