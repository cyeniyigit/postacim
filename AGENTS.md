# AGENTS.md — Postacım projesinde çalışan yapay zekâ asistanları için

Bu dosyadaki kurallar her zaman geçerlidir.

## Kurallar

1. **Türkçe:** Her zaman Türkçe cevap verilmelidir (kod, yorum ve belge
   dilinin Türkçe olduğu proje).
2. **Tahmin yok:** Tahmin üzerine iş yapılamaz. Belirsizlik varsa
   kullanıcıdan teyit istenir; varsayımla kod değişikliği yapılmaz.
3. **İstek kaydı:** Kullanıcı bir istek verdiğinde istek, önce
   `istekler.md` dosyasına yazılır; işleme ondan sonra geçilir.
   `istekler.md` GitHub'da paylaşılamaz (.gitignore'da).
4. **Yerel dosyalar:** `kurallar.md` ve `istekler.md` GitHub'a
   yüklenmez/paylaşılamaz (bkz. .gitignore).

## Proje alışkanlıkları

- Değişiklik sonrası `tests/run_all.sh` koşulur; tüm testler geçmeden
  iş tamamlanmış sayılmaz.
- Her iş için `DEVAM.md`'ye oturum notu, `CHANGELOG.md`'ye sürüm girdisi
  yazılır.
- Sürüm numarası `postacim/__init__.py` içindeki `__version__`'dan
  yönetilir; GitHub Release etiketi (ör. `v0.1.24`) ile eşleşmelidir.
