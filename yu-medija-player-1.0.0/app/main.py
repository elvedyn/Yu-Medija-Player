"""Entry point: python -m app"""

from app.qt_backend import configure_linux_media_backend

configure_linux_media_backend()

from app.window import run


def main():
  raise SystemExit(run())


if __name__ == "__main__":
  main()
