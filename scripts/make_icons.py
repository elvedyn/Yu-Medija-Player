#!/usr/bin/env python3
"""Generiše Yu Medija Player ikone (PNG sve veličine + multi-size .ico).

Pokretanje (iz korijena projekta):
    .venv/bin/python scripts/make_icons.py                    # finalno (stil: ember)
    .venv/bin/python scripts/make_icons.py --style night
    .venv/bin/python scripts/make_icons.py --preview /tmp/icons

Dizajn: superellipse ("squircle") tile sa mekim gradijentom, suptilnim rim
svjetlom, bloom-om iza glyph-a i play glyph-om zaobljenih vrhova sa sopstvenim
gradijentom i odsjajem. Ispod 48 px koristi se pojednostavljena varijanta
(bez rim-a, bloom-a i odsjaja) da ikona ostane čista u taskbaru/meniju.
"""

from __future__ import annotations

import argparse
import math
import struct
from pathlib import Path

from PyQt6.QtCore import QBuffer, QIODevice, QPointF, QRectF, Qt
from PyQt6.QtGui import (
    QBrush,
    QColor,
    QGuiApplication,
    QImage,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPainterPathStroker,
    QPen,
    QRadialGradient,
)

ROOT = Path(__file__).resolve().parent.parent
ICON_DIR = ROOT / "icons"
ASSET_DIR = ROOT / "assets"

PNG_SIZES = (16, 24, 32, 48, 64, 128, 256, 512)
ICO_SIZES = (16, 24, 32, 48, 64, 128, 256)

STYLES = {
    # Tamni premium tile + amber glyph (nastavlja identitet aplikacije)
    "night": {
        "tile": ("#222a3a", "#131926", "#080b11"),
        "tile_glow": QColor(246, 174, 70, 66),
        "glyph": ("#ffe3ab", "#f9b747", "#e07d1c"),
        "glyph_gloss": QColor(255, 255, 255, 40),
        "shadow": QColor(0, 0, 0, 120),
        "rim": QColor(255, 255, 255, 70),
        "gloss": QColor(255, 255, 255, 24),
    },
    # Amber tile sa dubokim gradijentom + gotovo crni glyph (upečatljivo)
    "ember": {
        "tile": ("#ffd489", "#f4a63c", "#d96d10"),
        "tile_glow": QColor(255, 236, 190, 120),
        "glyph": ("#232c3d", "#141a25", "#070a0f"),
        "glyph_gloss": QColor(255, 255, 255, 40),
        "shadow": QColor(120, 55, 0, 90),
        "rim": QColor(255, 255, 255, 150),
        "gloss": QColor(255, 255, 255, 58),
    },
    # Minimal: skoro crni tile + bijeli/amber dvotonski glyph
    "noir": {
        "tile": ("#2a2f38", "#171a20", "#0a0b0e"),
        "tile_glow": QColor(250, 184, 80, 44),
        "glyph": ("#ffffff", "#ffe4b0", "#f2b04a"),
        "glyph_gloss": QColor(255, 255, 255, 62),
        "shadow": QColor(0, 0, 0, 140),
        "rim": QColor(255, 255, 255, 58),
        "gloss": QColor(255, 255, 255, 22),
    },
    # Duboki indigo sa dva meka svjetlosna izvora (amber + violet) i amber glyph
    "aurora": {
        "tile": ("#2a3050", "#161c30", "#070910"),
        "tile_glow": QColor(247, 170, 62, 84),
        "glyph": ("#ffe6b4", "#ffbc55", "#f0811a"),
        "glyph_gloss": QColor(255, 255, 255, 34),
        "shadow": QColor(0, 0, 0, 96),
        "rim": QColor(255, 255, 255, 52),
        "gloss": QColor(255, 255, 255, 14),
        "accent_glow": QColor(118, 112, 255, 74),
    },
}

DEFAULT_STYLE = "aurora"


def squircle(half: float, n: float = 4.4, steps: int = 256) -> QPainterPath:
    """Superellipse putanja (moderan 'squircle' oblik pločice)."""
    path = QPainterPath()
    exp = 2.0 / n
    for i in range(steps + 1):
        t = 2.0 * math.pi * i / steps
        c, s = math.cos(t), math.sin(t)
        x = math.copysign(abs(c) ** exp, c) * half
        y = math.copysign(abs(s) ** exp, s) * half
        if i == 0:
            path.moveTo(x, y)
        else:
            path.lineTo(x, y)
    path.closeSubpath()
    return path


def _play_glyph(s: float, detailed: bool) -> tuple[QPainterPath, float, QRectF]:
    """Play glyph zaobljenih vrhova; vraća putanju, debljinu olovke i bbox."""
    width = s * (0.345 if detailed else 0.372)
    height = s * (0.412 if detailed else 0.438)
    center_x = s * 0.522  # optičko centriranje (trougao vizuelno teži lijevo)
    center_y = s * 0.500
    left = center_x - width * 0.42
    top = center_y - height / 2

    path = QPainterPath()
    path.moveTo(left, top)
    path.lineTo(left + width, center_y)
    path.lineTo(left, top + height)
    path.closeSubpath()
    pen = max(1.0, s * (0.069 if detailed else 0.081))
    return path, pen, QRectF(left, top, width, height)


def _stroked(painter: QPainter, path: QPainterPath, brush: QBrush, pen_width: float,
             alpha: int = 255) -> None:
    painter.setBrush(brush)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawPath(path)
    pen = QPen(brush, pen_width)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    if alpha != 255:
      pen.setColor(QColor(brush.color().red(), brush.color().green(), brush.color().blue(), alpha))
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawPath(path)


def _glyph_outline(path: QPainterPath, pen_width: float) -> QPainterPath:
    """Puna silueta glyph-a (trougao + zaobljeni potez) — koristi se za clip."""
    stroker = QPainterPathStroker()
    stroker.setWidth(pen_width)
    stroker.setCapStyle(Qt.PenCapStyle.RoundCap)
    stroker.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    return path.united(stroker.createStroke(path))


def render_master(style_name: str, detailed: bool = True, size: int = 1024) -> QImage:
    """Renderuje ikonu na zadatoj rezoluciji sa transparentnim uglovima."""
    style = STYLES[style_name]
    s = float(size)
    image = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)

    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

    c = QPointF(s / 2, s / 2)
    half = s / 2
    tile = squircle(half)
    tile.translate(c)

    # --- pločica: bazni gradijent -----------------------------------------
    tile_gradient = QLinearGradient(s * 0.16, 0.0, s * 0.84, s)
    tile_gradient.setColorAt(0.0, QColor(style["tile"][0]))
    tile_gradient.setColorAt(0.52, QColor(style["tile"][1]))
    tile_gradient.setColorAt(1.0, QColor(style["tile"][2]))
    painter.fillPath(tile, QBrush(tile_gradient))

    painter.save()
    painter.setClipPath(tile)

    # --- bloom iza glyph-a (dubina) ---------------------------------------
    if detailed:
        def soft_glow(center: QPointF, radius: float, color: QColor) -> None:
            glow = QRadialGradient(center, radius)
            glow.setColorAt(0.0, color)
            mid = QColor(color)
            mid.setAlpha(color.alpha() // 3)
            glow.setColorAt(0.48, mid)
            glow.setColorAt(1.0, QColor(color.red(), color.green(), color.blue(), 0))
            painter.fillRect(QRectF(0, 0, s, s), QBrush(glow))

        accent = style.get("accent_glow")
        if accent is not None:
            soft_glow(QPointF(s * 0.18, s * 0.12), s * 0.58, QColor(accent))
        soft_glow(QPointF(s * 0.61, s * 0.61), s * 0.46, QColor(style["tile_glow"]))

    # --- staklasti odsjaj pri vrhu ----------------------------------------
    gloss_alpha = QColor(style["gloss"])
    gloss = QLinearGradient(0.0, 0.0, 0.0, s * 0.62)
    gloss.setColorAt(0.0, gloss_alpha)
    gloss.setColorAt(0.62, QColor(255, 255, 255, 0))
    painter.fillRect(QRectF(0, 0, s, s * 0.62), QBrush(gloss))

    # --- donji odsjaj (refleksija poda, vrlo suptilno) --------------------
    if detailed:
        floor = QLinearGradient(0.0, s * 0.72, 0.0, s)
        floor.setColorAt(0.0, QColor(255, 255, 255, 0))
        floor.setColorAt(1.0, QColor(255, 255, 255, 16))
        painter.fillRect(QRectF(0, s * 0.72, s, s * 0.28), QBrush(floor))

    painter.restore()

    # --- rim svjetlo uz ivicu ---------------------------------------------
    if detailed:
        rim_color = QColor(style["rim"])
        rim = QLinearGradient(0.0, 0.0, s * 0.25, s)
        rim.setColorAt(0.0, rim_color)
        faded = QColor(rim_color)
        faded.setAlpha(0)
        rim.setColorAt(0.55, QColor(rim_color.red(), rim_color.green(), rim_color.blue(), rim_color.alpha() // 4))
        rim.setColorAt(1.0, faded)
        inset = s * 0.008
        inner = squircle(half - inset)
        inner.translate(c)
        pen = QPen(QBrush(rim), max(1.0, s * 0.006))
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(inner)

    # --- play glyph -------------------------------------------------------
    triangle, pen_width, box = _play_glyph(s, detailed)

    if detailed:
        # meka sjena: nekoliko sve širih poteza sa sve manjom alfom
        shadow_color = QColor(style["shadow"])
        painter.save()
        painter.translate(0, s * 0.007)
        for scale, alpha in ((1.16, 0.16), (1.09, 0.24), (1.03, 0.55)):
            tint = QColor(shadow_color)
            tint.setAlpha(int(shadow_color.alpha() * alpha))
            _stroked(painter, triangle, QBrush(tint), pen_width * scale)
        painter.restore()

    glyph_gradient = QLinearGradient(box.left(), box.top(), box.right(), box.bottom())
    glyph_gradient.setColorAt(0.0, QColor(style["glyph"][0]))
    glyph_gradient.setColorAt(0.52, QColor(style["glyph"][1]))
    glyph_gradient.setColorAt(1.0, QColor(style["glyph"][2]))
    _stroked(painter, triangle, QBrush(glyph_gradient), pen_width)

    # nježan odsjaj na gornjoj ivici glyph-a (samo gornja trećina)
    if detailed:
        painter.save()
        painter.setClipPath(_glyph_outline(triangle, pen_width))
        top_gloss = QLinearGradient(0.0, box.top(), 0.0, box.top() + box.height() * 0.42)
        top_gloss.setColorAt(0.0, QColor(style["glyph_gloss"]))
        top_gloss.setColorAt(1.0, QColor(255, 255, 255, 0))
        painter.fillRect(
            QRectF(box.left() - s, box.top() - s, box.width() + 2 * s, box.height() + s),
            QBrush(top_gloss),
        )
        painter.restore()

    painter.end()
    return image


def render_size(style_name: str, size: int) -> QImage:
    """Renderuje master pa glatko skalira; mali size-ovi bez sitnih detalja."""
    master = render_master(style_name, detailed=size >= 48)
    return master.scaled(
        size,
        size,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )


def _png_bytes(image: QImage) -> bytes:
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buffer, "PNG")
    return bytes(buffer.data())


def write_ico(path: Path, images: list[QImage]) -> None:
    """Multi-size ICO sa PNG kompresovanim slikama (Vista+ format)."""
    entries = []
    for image in images:
        width = 0 if image.width() >= 256 else image.width()
        height = 0 if image.height() >= 256 else image.height()
        entries.append((width, height, _png_bytes(image)))

    header = struct.pack("<HHH", 0, 1, len(entries))
    directory = b""
    offset = 6 + 16 * len(entries)
    payload = b""
    for width, height, data in entries:
        directory += struct.pack(
            "<BBBBHHII", width, height, 0, 0, 1, 32, len(data), offset + len(payload)
        )
        payload += data
    path.write_bytes(header + directory + payload)


def contact_sheet(style_name: str, path: Path) -> None:
    """Kontakt list: sve veličine na svijetloj i tamnoj podlozi (provjera čitljivosti)."""
    sizes = (512, 128, 64, 48, 32, 24, 16)
    pad, gap = 28, 26
    row_h = 512
    width = pad * 2 + row_h + sum(sizes[1:]) + gap * (len(sizes) - 1) + 40
    height = pad * 2 + row_h * 2 + 40
    sheet = QImage(width, height, QImage.Format.Format_ARGB32_Premultiplied)
    painter = QPainter(sheet)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.fillRect(QRectF(0, 0, width, row_h + 20), QColor("#f2f3f5"))
    painter.fillRect(QRectF(0, row_h + 20, width, height - row_h - 20), QColor("#14161b"))
    for row, baseline in enumerate((row_h - pad, height - pad)):
        x = pad
        for size in sizes:
            img = render_size(style_name, size)
            painter.drawImage(QPointF(x, baseline - size), img)
            x += size + (gap if size != 512 else 40)
    painter.end()
    sheet.save(str(path))


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate Yu Medija Player icons")
    parser.add_argument("--style", choices=sorted(STYLES), default=DEFAULT_STYLE)
    parser.add_argument("--preview", type=Path, default=None,
                        help="Samo sačuvaj preview PNG-ove u ovaj folder (ne dira icons/).")
    args = parser.parse_args()

    app = QGuiApplication.instance() or QGuiApplication([])  # noqa: F841

    if args.preview:
        args.preview.mkdir(parents=True, exist_ok=True)
        for style in STYLES:
            for size in (512, 256, 128, 64, 32, 16):
                render_size(style, size).save(str(args.preview / f"{style}-{size}.png"))
            render_master(style).save(str(args.preview / f"{style}-master.png"))
            contact_sheet(style, args.preview / f"{style}-sheet.png")
        print(f"Preview → {args.preview}")
        return 0

    ICON_DIR.mkdir(exist_ok=True)
    ASSET_DIR.mkdir(exist_ok=True)

    for size in PNG_SIZES:
        render_size(args.style, size).save(str(ICON_DIR / f"yu-medija-player-{size}.png"))
    # Naziv bez sufiksa koriste window icon i PyInstaller/spec (256 px).
    render_size(args.style, 256).save(str(ICON_DIR / "yu-medija-player.png"))
    render_size(args.style, 512).save(str(ASSET_DIR / "yu-medija-player.png"))

    write_ico(ICON_DIR / "yu-medija-player.ico", [render_size(args.style, s) for s in ICO_SIZES])

    # 1024 px izvor za buduće dorade (JPEG da ostane mali u repozitorijumu).
    render_master(args.style).save(str(ASSET_DIR / "yu-medija-player-icon-source.jpg"), "JPEG", 95)

    print(f"Ikone generisane (stil: {args.style})")
    for path in sorted(ICON_DIR.glob("yu-medija-player*")):
        print(f"  {path.relative_to(ROOT)}  {path.stat().st_size // 1024} KB")
    print(f"  assets/yu-medija-player.png  {(ASSET_DIR / 'yu-medija-player.png').stat().st_size // 1024} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
