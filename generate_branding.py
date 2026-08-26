"""
One-time local script (not part of the automated pipeline) that generates a
channel avatar + banner matching the actual video style: reuses the same
racer icons (race_sim.make_racer_icon) and maze color palette (MAZE_THEMES)
the videos are rendered with, so the channel art and the content look like
one system instead of a mismatched template.

Run once: python generate_branding.py
Then upload branding_profile.png / branding_banner.png manually in
YouTube Studio -> Customization -> Profile (Banner / Photo).
"""
from PIL import Image, ImageDraw, ImageFont, ImageFilter

from race_sim import make_racer_icon, MAZE_THEMES, get_font, RACER_POOL

THEME = next(t for t in MAZE_THEMES if t["name"] == "Neon Grid")
BG_TOP = tuple(max(0, c - 10) for c in THEME["floor"])
BG_BOTTOM = THEME["wall"]
ACCENT_A = THEME["accent"]
ACCENT_B = THEME["particle"]
WHITE = (250, 250, 252)


def vertical_gradient(size, top, bottom):
    w, h = size
    img = Image.new("RGB", size, top)
    px = img.load()
    for y in range(h):
        t = y / max(h - 1, 1)
        r = int(top[0] + (bottom[0] - top[0]) * t)
        g = int(top[1] + (bottom[1] - top[1]) * t)
        b = int(top[2] + (bottom[2] - top[2]) * t)
        for x in range(w):
            px[x, y] = (r, g, b)
    return img


def fit_font(text, max_width, start_size, min_size=20):
    size = start_size
    while size > min_size:
        font = get_font(size)
        bbox = font.getbbox(text)
        w = bbox[2] - bbox[0]
        if w <= max_width:
            return font
        size -= 2
    return get_font(min_size)


def draw_centered(draw, text, font, center_x, top_y, fill, shadow=None):
    """Draws `text` so its actual ink (not the font's raw bbox, which can
    include ascender/descender padding that threw off the first pass's
    manual height math and made the subtitle overlap the title) starts at
    `top_y`. Returns the ink height so the caller can stack the next line
    below it with a real gap."""
    bbox = draw.textbbox((0, 0), text, font=font)
    w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = center_x - w / 2 - bbox[0]
    y = top_y - bbox[1]
    if shadow:
        draw.text((x + 6, y + 6), text, font=font, fill=shadow)
    draw.text((x, y), text, font=font, fill=fill)
    return h


def _glow_blob(size, center, radius, color, alpha, blur):
    glow = Image.new("RGBA", size, (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    cx, cy = center
    gd.ellipse([cx - radius, cy - radius, cx + radius, cy + radius], fill=(*color, alpha))
    return glow.filter(ImageFilter.GaussianBlur(blur))


def racer_by_name(name):
    return next(r for r in RACER_POOL if r["name"] == name)


def make_profile(path):
    S = 800
    img = vertical_gradient((S, S), BG_TOP, BG_BOTTOM).convert("RGBA")

    glow = _glow_blob((S, S), (S / 2, S / 2), S * 0.42, ACCENT_A, 90, 70)
    img = Image.alpha_composite(img, glow)

    ring_d = ImageDraw.Draw(img)
    ring_r = S * 0.44
    ring_d.ellipse(
        [S / 2 - ring_r, S / 2 - ring_r, S / 2 + ring_r, S / 2 + ring_r],
        outline=(*ACCENT_B, 220), width=int(S * 0.014),
    )

    # Two racer icons mid-"race", one slightly ahead — reads as motion even
    # frozen, and keeps the avatar legible at tiny sizes (one clear subject
    # pair, not a busy scene).
    icon_size = int(S * 0.40)
    a = make_racer_icon(racer_by_name("Sky")["color"], icon_size).rotate(-14, resample=Image.BICUBIC, expand=True)
    b = make_racer_icon(racer_by_name("Sunny")["color"], icon_size).rotate(10, resample=Image.BICUBIC, expand=True)
    img.alpha_composite(b, (int(S * 0.30), int(S * 0.46)))
    img.alpha_composite(a, (int(S * 0.44), int(S * 0.22)))

    img.convert("RGB").save(path, "PNG")
    print(f"OK: {path}")


def make_banner(path):
    W, H = 2048, 1152
    img = vertical_gradient((W, H), BG_TOP, BG_BOTTOM).convert("RGBA")

    glow1 = _glow_blob((W, H), (W * 0.10, H * 0.18), 520, ACCENT_A, 70, 130)
    glow2 = _glow_blob((W, H), (W * 0.92, H * 0.84), 520, ACCENT_B, 55, 130)
    img = Image.alpha_composite(img, glow1)
    img = Image.alpha_composite(img, glow2)

    # decorative racer icons scattered outside the centered text-safe zone
    deco = [
        ("Cherry", 200, (150, 900), -18),
        ("Grape", 230, (1750, 950), 22),
        ("Pine", 170, (1860, 170), -28),
        ("Coral", 150, (130, 190), 16),
        ("Slate", 190, (1900, 620), 8),
    ]
    for name, isize, pos, angle in deco:
        icon = make_racer_icon(racer_by_name(name)["color"], isize).rotate(angle, resample=Image.BICUBIC, expand=True)
        img.alpha_composite(icon, (pos[0] - icon.width // 2, pos[1] - icon.height // 2))

    draw = ImageDraw.Draw(img)

    safe_w = 1546
    center_x = W / 2

    title = "MARBLE RACE"
    title_font = fit_font(title, safe_w * 0.95, 170, 70)
    subtitle = "New Maze Race Every Day — Who Wins?"
    sub_font = fit_font(subtitle, safe_w * 0.8, 54, 26)

    GAP = 40
    title_h = draw.textbbox((0, 0), title, font=title_font)[3] - draw.textbbox((0, 0), title, font=title_font)[1]
    sub_h = draw.textbbox((0, 0), subtitle, font=sub_font)[3] - draw.textbbox((0, 0), subtitle, font=sub_font)[1]
    block_h = title_h + GAP + sub_h
    top_y = H / 2 - block_h / 2

    used_h = draw_centered(draw, title, title_font, center_x, top_y, WHITE, shadow=(0, 0, 0, 170))
    draw_centered(draw, subtitle, sub_font, center_x, top_y + used_h + GAP, ACCENT_B)

    img.convert("RGB").save(path, "PNG")
    print(f"OK: {path}")


if __name__ == "__main__":
    make_profile("branding_profile.png")
    make_banner("branding_banner.png")
