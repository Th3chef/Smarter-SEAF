# Smarter SEAF propaganda poster: sunburst, sun disc, halftone, ridge with distant bugs, the squad as screen-print shapes,
# paper grain and worn ink. usage: poster.py spec.json
import sys, json, math, numpy as np
from PIL import Image, ImageDraw, ImageFilter
S = json.load(open(sys.argv[1])); W, H = S['W'], S['H']; cx, cy = S['sun']
rng = np.random.default_rng(11)
y, x = np.mgrid[0:H, 0:W].astype(float)
ang = np.arctan2(y - cy, x - cx); rad = np.hypot(x - cx, y - cy) / max(W, H)
Y1, Y2, CREAM, INK, RED = np.array([255, 196, 0]), np.array([238, 150, 10]), np.array([246, 231, 193]), np.array([18, 17, 16]), np.array([178, 26, 30])
rays = (np.floor((ang + math.pi) / (2 * math.pi) * S.get('rays', 28)) % 2)[..., None]
img = Y1 * (1 - rays) + Y2 * rays
# darker toward the edges, as halftone dots (45 degree screen)
dark = np.clip((rad - 0.22) / 0.6, 0, 1) ** 1.3 * S.get('dot_max', 0.6)
p = S.get('dot', 14); u = (x + y) / math.sqrt(2) / p; v = (x - y) / math.sqrt(2) / p
d = np.hypot(u - np.round(u), v - np.round(v))           # 0 at a dot centre, ~0.7 between
dots = (d < np.sqrt(dark / math.pi) * 1.05)[..., None]
img = np.where(dots, np.array([150, 70, 0]), img)
# the sun: a cream disc with a soft ring
r_s = S['sun_r']
sun = np.clip((r_s - np.hypot(x - cx, y - cy)) / 2.0, 0, 1)[..., None]
img = img * (1 - sun) + CREAM * sun
ring = np.clip(1 - np.abs(np.hypot(x - cx, y - cy) - r_s * 1.18) / 6, 0, 1)[..., None]
img = img * (1 - ring) + CREAM * ring
# ridge line: black hills with distant bugs on them
gy = S['ground']
xs = np.arange(W)
hill = gy - 18 * np.sin(xs / W * 7.1) - 10 * np.sin(xs / W * 19.3 + 1) - 6 * np.sin(xs / W * 41 + 2)
img = np.where((y > hill[None, :])[..., None], INK, img)
im = Image.fromarray(np.clip(img, 0, 255).astype(np.uint8)).convert('RGBA')
ch = Image.open(S['charger']); ch = ch.crop(ch.getbbox())
for (bx, bw) in S.get('bugs', []):
    c = ch.resize((bw, int(ch.height * bw / ch.width)), Image.LANCZOS)
    sil = Image.new('RGBA', c.size, tuple(INK) + (255,)); sil.putalpha(c.split()[3].point(lambda a: 255 if a > 90 else 0))
    gyb = int(hill[min(W - 1, bx + bw // 2)]) + 6
    im.alpha_composite(sil, (bx, gyb - c.height))
    if bw == max(b[1] for b in S['bugs']) and S.get('ping', True):   # a ping marker over the biggest one
        d_ = ImageDraw.Draw(im); px, py, r = bx + bw * 0.45, gyb - c.height - 46, 17
        d_.polygon([(px, py - r), (px + r, py), (px, py + r), (px - r, py)], outline=tuple(INK), width=6)
        d_.polygon([(px, py - r * 0.4), (px + r * 0.4, py), (px, py + r * 0.4), (px - r * 0.4, py)], fill=tuple(INK))
        d_.line([(px, py + r + 4), (px, gyb - c.height + 6)], fill=tuple(INK), width=4)
# the squad
sq = Image.open(S['squad']).convert('RGBA')
if S.get('sq_scale', 1) != 1: sq = sq.resize((int(sq.width * S['sq_scale']), int(sq.height * S['sq_scale'])), Image.LANCZOS)
im.alpha_composite(sq, (S.get('sq_x', 0), S.get('sq_y', 0)))
# bottom band for the title
d_ = ImageDraw.Draw(im)
if S['band'] < H:   # (the header has no band)
    d_.rectangle([0, S['band'], W, H], fill=tuple(INK))
    d_.rectangle([0, S['band'], W, S['band'] + 10], fill=tuple(RED))
a = np.asarray(im.convert('RGB')).astype(float)
# worn ink: specks knocked out of the dark ink, paper grain and fibers over everything
n = rng.random((H, W))
inkmask = (a.mean(-1) < 70)
specks = (np.asarray(Image.fromarray((n * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.1))) > 150) & inkmask & (rng.random((H, W)) > 0.55)
a[specks] = a[specks] * 0.4 + CREAM * 0.6 * 0.5
grain = np.asarray(Image.fromarray((rng.normal(128, 30, (H, W))).clip(0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.7))).astype(float) - 128
fib = np.asarray(Image.fromarray((rng.normal(128, 60, (H // 4, W // 16))).clip(0, 255).astype(np.uint8)).resize((W, H), Image.BICUBIC)).astype(float) - 128
a = a * (1 + (grain * 0.0012 + fib * 0.00025)[..., None])
# a print slightly off register: the dark ink layer shifted a pixel
Image.fromarray(np.clip(a, 0, 255).astype(np.uint8)).save(S['out'])
