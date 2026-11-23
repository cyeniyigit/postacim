"""python3 -m postacim"""
import sys


def main() -> int:
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
