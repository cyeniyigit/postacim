# Katkı rehberi — Postacım

Postacım'a katkıda bulunmak için hoş geldiniz. Proje Python 3.10+ ve
Tkinter ile yazılmıştır; harici bağımlılıklar `requirements.txt` içindedir.

## Hızlı başlangıç

```bash
git clone https://github.com/<kullanici>/postacim.git
cd postacim
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m postacim
```

## Testler

Değişiklik göndermeden önce testleri çalıştırın:

```bash
./tests/run_all.sh
```

Arayüz testleri Xvfb kullanır (`xvfb-run`); Xvfb yoksa bir masaüstü
oturumunda çalıştırılabilir. Canlı sunucu gerektiren testler
(`tests/test_ews.py`, `tests/ui_smoke.py`, `tests/takvim_ui_test.py`)
kendi hesabınızla çalıştırılır — **parolaları koda yazmayın**.

Her push ve PR'da testler GitHub Actions tarafından otomatik çalıştırılır.

## Kod düzeni

```
postacim/
  ews.py       EWS (Exchange Web Services) SOAP istemcisi
  imap.py      IMAP/SMTP istemcisi
  caldav.py    CalDAV istemcisi + iCalendar (ICS) üretimi/ayrıştırma
  tekrar.py    RRULE (tekrarlayan olay) ayrıştırma ve üretimi
  config.py    ayarların saklanması (çoklu hesap, 0600 izin)
  ui.py        Tkinter arayüzü
```

## Kurallar

- **Kişisel bilgi girmeyin**: sunucu adresi, e-posta adresi, parola,
  kurum içi IP ya da etiketler koda/ teste girmez. Testlerde
  `mail.ornek.gov.tr`, `KURUM\kullanici`, `ornek@ornek.com` gibi
  örnekler kullanın.
- **Parolalar diske yalnız kullanıcı isterse** yazılır (`~/.config/postacim/`,
  dosya izni 0600).
- Yeni özellik için önce **gerekçe** yazın (README'deki "Kalan işler"
  listesine ekleyebilirsiniz), sonra kodu yazın.
- Türkçe yorumlar ve docstring kullanılır (proje dili Türkçe).
- Sürüm numarası `pyproject.toml` içinde güncellenir.

## Commit mesajı

Kısa ve emir kipinde olsun:

```
Takvim: tekrarlayan olaylarda EXDATE desteği
IMAP: LOGOUT sonrası yeniden bağlanma
```

## Hata bildirimi

Yeni bir konu açarken şunları yazın: Postacım sürümü, Python sürümü,
dağıtımınız (Pardus/Fedora/openSUSE…), ne olmasını bekliyordunuz, ne oldu,
konsol çıktısı. **Parola veya kişisel e-posta adresi eklemeyin.**
