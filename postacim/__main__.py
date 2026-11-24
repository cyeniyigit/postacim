"""python3 -m postacim"""
import os
import sys


def _cokme_izini_kur():
    """Segfault gibi süreci düşüren C düzeyi çökmelerde iz bırakır.

    Tkhtml3 (C) bazı bozuk e-postalarda segfault üretebilir; iz olmadan
    çökmenin kaynağı bilinemez. faulthandler, Python geri çağrı
    zincirini aynı hata.log'a yazar.
    """
    try:
        import faulthandler

        gunluk_dizin = os.path.join(
            os.environ.get("XDG_STATE_HOME", "")
            or os.path.join(os.path.expanduser("~"), ".local", "state"),
            "postacim",
        )
        os.makedirs(gunluk_dizin, exist_ok=True)
        dosya = open(os.path.join(gunluk_dizin, "hata.log"), "a", encoding="utf-8")
        faulthandler.enable(file=dosya)
    except (OSError, ImportError):
        pass  # kayıt yazılamıyorsa uygulama yine açılsın


def main() -> int:
    _cokme_izini_kur()
    # Arayüz içe aktarılırken oluşan hatalar (eksik tkinter, bozuk kurulum)
    # kullanıcıya anlaşılır biçimde bildirilir; aksi hâlde yalnızca iz
    # (traceback) görünür ve masaüstünden başlatıldığında hiçbir şey olmaz.
    try:
        from .ui import Postacim
    except ImportError as exc:
        print(f"Postacım arayüzü yüklenemedi: {exc}", file=sys.stderr)
        if "tkinter" in str(exc):
            print(
                "Tkinter eksik olabilir. Kurulum:  sudo apt install python3-tk",
                file=sys.stderr,
            )
        elif "postacim" in str(exc):
            print(
                "Kurulum bozuk görünüyor. Postacım klasöründe yeniden kurun:  ./kur.sh",
                file=sys.stderr,
            )
        return 1

    try:
        uygulama = Postacim()
    except Exception as exc:
        print(f"Arayüz açılamadı: {exc}", file=sys.stderr)
        return 1
    uygulama.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
