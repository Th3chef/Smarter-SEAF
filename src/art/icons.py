# Arsenal option icons, 256x256: blurred backdrop from the mod's art, thick yellow frame, one glyph (drawn at 1024)
import math, numpy as np
from PIL import Image, ImageDraw, ImageFilter
S = 1024; Y = (255, 231, 16); WH = (235, 235, 235); GR = (150, 150, 150)
art = Image.open('layers/comp_wide.png').convert('RGB')
def backdrop(box, blur=10, dark=0.55, sharp=False):
    im = art.crop(box).resize((S, S), Image.LANCZOS)
    if not sharp: im = im.filter(ImageFilter.GaussianBlur(blur))
    a = np.asarray(im).astype(float) * dark
    return Image.fromarray(a.clip(0, 255).astype(np.uint8)).convert('RGBA')
def frame(im):
    d = ImageDraw.Draw(im); w = 44
    d.rectangle([w // 2, w // 2, S - w // 2 - 1, S - w // 2 - 1], outline=Y, width=w)
    return im
def person(d, cx, cy, s, col):
    d.ellipse([cx - 0.17 * s, cy - 0.62 * s, cx + 0.17 * s, cy - 0.28 * s], fill=col)
    d.rounded_rectangle([cx - 0.30 * s, cy - 0.22 * s, cx + 0.30 * s, cy + 0.42 * s], radius=int(0.14 * s), fill=col)
def reticle(d, cx, cy, r, col, w, crossed=False, bg=None):
    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=col, width=w)
    for a in range(4):
        ang = a * math.pi / 2
        d.line([(cx + math.cos(ang) * r * 0.45, cy + math.sin(ang) * r * 0.45), (cx + math.cos(ang) * r * 1.35, cy + math.sin(ang) * r * 1.35)], fill=col, width=w)
    if crossed:
        k = r * 1.25
        if bg: d.line([(cx - k, cy - k), (cx + k, cy + k)], fill=bg, width=int(w * 2.6))
        d.line([(cx - k, cy - k), (cx + k, cy + k)], fill=col, width=w)
def shield(d, cx, cy, s, fill, outline=None, ow=0):
    pts = [(cx - s, cy - s * 0.95), (cx + s, cy - s * 0.95), (cx + s, cy + 0.15 * s), (cx, cy + s * 1.15), (cx - s, cy + 0.15 * s)]
    d.polygon(pts, fill=fill, outline=outline, width=ow)
def badge(d, cx, cy, s):   # a yellow shield badge with a crossed-out reticle (as SGD's safety icons)
    shield(d, cx, cy, s, Y)
    reticle(d, cx, cy - s * 0.1, s * 0.42, (25, 25, 25), int(s * 0.10), crossed=True, bg=Y)
def save(im, name):
    im = frame(im).resize((256, 256), Image.LANCZOS); im.save('icons/' + name)
    return im
import os; os.makedirs('icons', exist_ok=True)
out = {}
# the mod: the lead rifleman from the art itself (sharp), framed
im = backdrop((1080, 300, 1500, 720), sharp=True, dark=1.15); out['option_core.png'] = save(im, 'option_core.png')
# Friendly Fire Safety (and "Helldivers and other troopers"): a helldiver and a trooper behind a yellow badge
im = backdrop((300, 200, 800, 700)); d = ImageDraw.Draw(im)
person(d, 360, 640, 420, (205, 205, 205)); person(d, 610, 680, 360, (150, 150, 150)); badge(d, 720, 330, 190)
out['option_friendly_fire.png'] = save(im, 'option_friendly_fire.png')
# only helldivers: one figure + badge
im = backdrop((300, 200, 800, 700)); d = ImageDraw.Draw(im)
person(d, 420, 660, 470, WH); badge(d, 720, 330, 190); out['option_helldivers.png'] = save(im, 'option_helldivers.png')
# only other troopers: three small figures in a row + badge
im = backdrop((300, 200, 800, 700)); d = ImageDraw.Draw(im)
for i, (x, c) in enumerate([(250, (140, 140, 140)), (470, (175, 175, 175)), (690, (210, 210, 210))]): person(d, x, 700, 300, c)
badge(d, 760, 290, 160); out['option_troopers.png'] = save(im, 'option_troopers.png')
# Armor Intelligence: a grey armor plate with a yellow reticle on it
im = backdrop((1460, 470, 1860, 870)); d = ImageDraw.Draw(im)
shield(d, 512, 470, 300, (70, 72, 75), outline=(140, 142, 146), ow=26)
d.line([(240, 390), (784, 390)], fill=(45, 46, 48), width=22)
reticle(d, 512, 500, 125, Y, 34); d.ellipse([492, 480, 532, 520], fill=Y)
out['option_armor.png'] = save(im, 'option_armor.png')
# Ping Targeting: the in-game style ping diamond over an enemy
im = backdrop((1460, 470, 1860, 870)); d = ImageDraw.Draw(im)
ch = Image.open('layers/L_charger.png'); ch = ch.crop(ch.getbbox()); ch = ch.resize((560, int(ch.height * 560 / ch.width)))
sil = Image.new('RGBA', ch.size, (40, 32, 28, 255)); sil.putalpha(ch.split()[3]); im.alpha_composite(sil, (232, 900 - ch.height))
glow = Image.new('RGBA', (S, S), (0, 0, 0, 0)); g = ImageDraw.Draw(glow)
cx, cy, r = 512, 300, 150
for dd in (g, d):
    dd.polygon([(cx, cy - r), (cx + r, cy), (cx, cy + r), (cx - r, cy)], outline=Y, width=38)
    dd.polygon([(cx, cy - r * 0.42), (cx + r * 0.42, cy), (cx, cy + r * 0.42), (cx - r * 0.42, cy)], fill=Y)
    dd.line([(cx, cy + r + 20), (cx, 610)], fill=Y, width=26)
im = Image.alpha_composite(im, glow.filter(ImageFilter.GaussianBlur(26))); d = ImageDraw.Draw(im)
d.polygon([(cx, cy - r), (cx + r, cy), (cx, cy + r), (cx - r, cy)], outline=Y, width=38)
d.polygon([(cx, cy - r * 0.42), (cx + r * 0.42, cy), (cx, cy + r * 0.42), (cx - r * 0.42, cy)], fill=Y)
d.line([(cx, cy + r + 20), (cx, 610)], fill=Y, width=26)
out['option_ping.png'] = save(im, 'option_ping.png')
# contact sheet: 256 and 48 px
names = list(out)
sheet = Image.new('RGB', (len(names) * 272 + 16, 272 + 80), (30, 30, 32))
for i, n in enumerate(names):
    sheet.paste(out[n], (16 + i * 272, 16)); sheet.paste(out[n].resize((48, 48), Image.LANCZOS), (16 + i * 272 + 104, 290))
sheet.save('layers/icons_sheet.png')
