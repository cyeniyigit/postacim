"""python3 -m postacim"""
import sys

from .ui import Postacim


def main() -> int:
    try:
        uygulama = Postacim()
    except Exception as exc:
        print(f"Arayüz açılamadı: {exc}", file=sys.stderr)
        return 1
    uygulama.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
