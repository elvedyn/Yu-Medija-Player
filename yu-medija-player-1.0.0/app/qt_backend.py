"""Qt Multimedia backend setup (must run before importing QMediaPlayer)."""

from __future__ import annotations

import locale
import os
import sys


def configure_linux_media_backend() -> None:
  """Tune GStreamer/ffmpeg for Linux playback (local + IPTV HTTP VOD)."""
  # libmpv requires C numeric locale or it can segfault on start
  try:
    locale.setlocale(locale.LC_NUMERIC, "C")
  except locale.Error:
    pass
  os.environ.setdefault("LC_NUMERIC", "C")

  if not sys.platform.startswith("linux"):
    return
  # FFmpeg backend handles many IPTV .mkv URLs better than GStreamer+Qt.
  # Override: QT_MEDIA_BACKEND=gstreamer
  if "QT_MEDIA_BACKEND" not in os.environ:
    os.environ["QT_MEDIA_BACKEND"] = "ffmpeg"
  # Still used when GStreamer is selected explicitly
  os.environ.setdefault("GST_CURL_USERAGENT", "VLC/3.0.21 LibVLC/3.0.21")
  plugin_dir = "/usr/lib/x86_64-linux-gnu/gstreamer-1.0"
  if os.path.isdir(plugin_dir):
    os.environ.setdefault("GST_PLUGIN_SYSTEM_PATH_1_0", plugin_dir)
    if getattr(sys, "frozen", False):
      os.environ["GST_PLUGIN_PATH"] = plugin_dir
      os.environ["GST_PLUGIN_SYSTEM_PATH"] = plugin_dir