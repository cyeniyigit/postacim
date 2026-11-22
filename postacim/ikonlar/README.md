# Uygulama simgeleri

`postacim/ikonlar/` altındaki PNG'ler arayüz düğmeleri ve klasör simgeleri
içindir (20×20, `tk.PhotoImage` ile yüklenir).

## Uygulama simgesi

- `uygulama.png` — **256×256** uygulama simgesi (zarf + pull)
- `tools/ikon_olustur.py` — simgeyi üreten betik; yeniden üretmek için:
  ```bash
  python3 tools/ikon_olustur.py
  ```
- `data/icons/hicolor/scalable/apps/postacim.svg` — vektör sürüm

`kur.sh` kurulum sırasında ana PNG'den 16/24/32/48/64/128/256 boyutlarını
üretip `~/.local/share/icons/hicolor/` altına kurar ve uygulama menüsü
girdisini `Icon=postacim` ile bağlar.
