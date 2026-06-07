"""Génère l'icône/logo Cookeo (pot + vapeur) — icon.png 256, logo.png 512.

Style maison Info-DAM : fond bordeaux/rosé arrondi, pot anthracite, vapeur claire.
Lancer :  python scripts/make_icon.py
"""
from __future__ import annotations

import os

from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

BG_TOP = (124, 28, 52)      # bordeaux
BG_BOT = (190, 78, 110)     # rosé
POT = (38, 40, 46)          # anthracite
POT_LIGHT = (70, 74, 84)
LID = (52, 55, 63)
ACCENT = (245, 222, 230)    # vapeur / liseré
KNOB = (224, 122, 95)       # bouton cuivre


def _vgrad(size: int) -> Image.Image:
    img = Image.new("RGB", (size, size), BG_TOP)
    for y in range(size):
        t = y / max(1, size - 1)
        r = round(BG_TOP[0] + (BG_BOT[0] - BG_TOP[0]) * t)
        g = round(BG_TOP[1] + (BG_BOT[1] - BG_TOP[1]) * t)
        b = round(BG_TOP[2] + (BG_BOT[2] - BG_TOP[2]) * t)
        for x in range(size):
            img.putpixel((x, y), (r, g, b))
    return img


def _rounded_mask(size: int, radius: int) -> Image.Image:
    m = Image.new("L", (size, size), 0)
    d = ImageDraw.Draw(m)
    d.rounded_rectangle((0, 0, size - 1, size - 1), radius=radius, fill=255)
    return m


def draw_icon(size: int) -> Image.Image:
    ss = size * 4  # super-sampling pour des bords lisses
    img = _vgrad(ss).convert("RGBA")
    d = ImageDraw.Draw(img)
    cx = ss // 2

    def u(v: float) -> int:
        return round(v * ss)

    # vapeur (3 volutes)
    for dx, w in ((-0.16, 0.05), (0.0, 0.06), (0.16, 0.05)):
        x = cx + u(dx)
        d.line(
            [(x, u(0.20)), (x + u(0.04), u(0.27)), (x - u(0.04), u(0.33)), (x, u(0.40))],
            fill=ACCENT + (235,),
            width=u(w),
            joint="curve",
        )

    # corps du pot (cuve)
    body = (u(0.18), u(0.50), u(0.82), u(0.84))
    d.rounded_rectangle(body, radius=u(0.10), fill=POT)
    d.rounded_rectangle(
        (u(0.18), u(0.50), u(0.82), u(0.60)), radius=u(0.08), fill=POT_LIGHT
    )

    # poignées
    d.rounded_rectangle((u(0.10), u(0.58), u(0.20), u(0.68)), radius=u(0.03), fill=LID)
    d.rounded_rectangle((u(0.80), u(0.58), u(0.90), u(0.68)), radius=u(0.03), fill=LID)

    # couvercle
    d.rounded_rectangle(
        (u(0.16), u(0.42), u(0.84), u(0.52)), radius=u(0.05), fill=LID
    )
    # bouton/cuivre du couvercle
    d.ellipse((cx - u(0.05), u(0.36), cx + u(0.05), u(0.46)), fill=KNOB)

    # liseré « connecté » (arc façon ondes BLE)
    d.arc((cx - u(0.30), u(0.62), cx + u(0.30), u(1.05)), 200, 340, fill=ACCENT + (180,), width=u(0.015))

    img = img.resize((size, size), Image.LANCZOS)
    img.putalpha(_rounded_mask(size, round(size * 0.22)))
    return img


def draw_logo(width: int, height: int) -> Image.Image:
    icon = draw_icon(height)
    logo = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    logo.alpha_composite(icon, (0, 0))
    return logo


def main() -> None:
    icon = draw_icon(256)
    icon.save(os.path.join(ROOT, "icon.png"))
    icon.resize((512, 512), Image.LANCZOS).save(os.path.join(ROOT, "icon@2x.png"))
    draw_logo(512, 256).save(os.path.join(ROOT, "logo.png"))
    # copies pour un PR home-assistant/brands
    bdir = os.path.join(ROOT, "brands", "custom_integrations", "cookeo")
    os.makedirs(bdir, exist_ok=True)
    icon.save(os.path.join(bdir, "icon.png"))
    icon.resize((512, 512), Image.LANCZOS).save(os.path.join(bdir, "icon@2x.png"))
    draw_logo(512, 256).save(os.path.join(bdir, "logo.png"))
    print("icônes générées :", ROOT)


if __name__ == "__main__":
    main()
