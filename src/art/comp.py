# composite: backdrop + Charger (hazed, far) + ping marker + squad + tracer + bottom shade. usage: comp.py spec.json
import sys, json, numpy as np
from PIL import Image, ImageDraw, ImageFilter
S = json.load(open(sys.argv[1]))
W, H = S['W'], S['H']
bg = Image.open(S['bg']).convert('RGB')
img = np.asarray(bg).astype(float)
def paste(layer, x, y, alpha_mul=1.0, haze=0.0, tint=None):
    global img
    L = np.asarray(layer).astype(float); h, w = L.shape[:2]
    x0, y0 = int(x), int(y); xs, ys = max(0, x0), max(0, y0); xe, ye = min(W, x0 + w), min(H, y0 + h)
    if xe <= xs or ye <= ys: return
    sub = L[ys - y0:ye - y0, xs - x0:xe - x0]; a = sub[..., 3:4] / 255 * alpha_mul; rgb = sub[..., :3]
    base = img[ys:ye, xs:xe]
    if tint is not None: rgb = rgb * np.array(tint)
    if haze: rgb = rgb * (1 - haze) + base * haze
    img[ys:ye, xs:xe] = base * (1 - a) + rgb * a
# the Charger, far off
ch = Image.open(S['charger']); bb = ch.getbbox(); ch = ch.crop(bb)
cw = S['ch_w']; ch = ch.resize((cw, int(ch.height * cw / ch.width)), Image.BICUBIC)
if S.get('ch_blur'): ch = ch.filter(ImageFilter.GaussianBlur(S['ch_blur']))
cx, cy = S['ch_x'], S['ch_ground'] - ch.height
paste(ch, cx, cy, haze=S.get('ch_haze', 0.35), tint=S.get('ch_tint', [0.55, 0.42, 0.36]))
# ping marker over it (an in-game style ping: a yellow diamond with a line down)
glow = Image.new('RGBA', (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(glow)
px, py = cx + ch.width * S.get('ping_dx', 0.42), cy - S.get('ping_up', 70)
r = S.get('ping_r', 22)
d.polygon([(px, py - r), (px + r, py), (px, py + r), (px - r, py)], outline=(255, 214, 40, 255), width=5)
d.polygon([(px, py - r * 0.45), (px + r * 0.45, py), (px, py + r * 0.45), (px - r * 0.45, py)], fill=(255, 214, 40, 255))
d.line([(px, py + r + 6), (px, cy + ch.height * 0.25)], fill=(255, 214, 40, 170), width=3)
g2 = glow.filter(ImageFilter.GaussianBlur(9))
paste(Image.blend(g2, g2, 0), 0, 0, alpha_mul=0.9); paste(glow, 0, 0)
# the squad: one layer per soldier, back to front, each rendered small and upscaled softly, with its own depth blur
# (depth of field) and haze; a light wrap from the fire behind
def soldier_layer(f, blur):
    L = Image.open(f).convert('RGBA').resize((W, H), Image.BICUBIC)
    return L.filter(ImageFilter.GaussianBlur(blur)) if blur else L
for f, blur, haze in S['squad']:
    sq = soldier_layer(f, blur)
    al = sq.split()[3].filter(ImageFilter.GaussianBlur(7 + blur))
    wrap = Image.merge('RGBA', (Image.new('L', sq.size, 255), Image.new('L', sq.size, 135), Image.new('L', sq.size, 45), al.point(lambda v: int(v * 0.38))))
    paste(wrap, S.get('sq_x', 0), S.get('sq_y', 0))
    paste(sq, S.get('sq_x', 0), S.get('sq_y', 0), haze=haze, tint=S.get('sq_tint', [1.22, 1.12, 1.02]))
# tracers from the lead rifle toward the Charger
tr = Image.new('RGBA', (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(tr)
for (x1, y1, x2, y2, w) in S.get('tracers', []):
    d.line([(x1, y1), (x2, y2)], fill=(255, 200, 90, 255), width=w)
tg = tr.filter(ImageFilter.GaussianBlur(5)); paste(tg, 0, 0, alpha_mul=1.0, tint=[1, 0.8, 0.5]); paste(tr, 0, 0)
for (mx, my, mr) in S.get('flash', []):
    f = Image.new('RGBA', (W, H), (0, 0, 0, 0)); ImageDraw.Draw(f).ellipse([mx - mr, my - mr * 0.6, mx + mr, my + mr * 0.6], fill=(255, 210, 120, 255))
    paste(f.filter(ImageFilter.GaussianBlur(mr * 0.5)), 0, 0)
# shade for the title: dark from shade_y down
y = np.arange(H)[:, None]; s0, s1 = S['shade_y0'], S['shade_y1']
sh = np.clip((y - s0) / (s1 - s0), 0, 1) ** 1.2 * S.get('shade_max', 0.94)
img = img * (1 - sh[..., None]) + np.array([6, 6, 7]) * sh[..., None]
# bloom: the bright parts (fire, rims, tracers) glow
lum = img.mean(-1, keepdims=True) / 255
bright = np.clip((lum - S.get('bloom_t', 0.42)) / 0.4, 0, 1) * img
for r, k in [(10, 0.35), (40, 0.45)]:
    b = np.asarray(Image.fromarray(np.clip(bright, 0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(r))).astype(float)
    img = 255 - (255 - img) * (1 - b / 255 * k)          # screen
# soften the whole picture a little (a game capture, not a crisp render)
img = np.asarray(Image.fromarray(np.clip(img, 0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(S.get('soft', 0.7)))).astype(float)
# lens fringing toward the edges: red out, blue in
yy, xx = np.mgrid[0:H, 0:W]; rr = np.sqrt(((xx - W / 2) / W) ** 2 + ((yy - H / 2) / H) ** 2)
sh = S.get('fringe', 2.0)
def shift(ch, k):
    dx = ((xx - W / 2) * k * rr / max(W, H) * sh * 2).astype(int); dy = ((yy - H / 2) * k * rr / max(W, H) * sh * 2).astype(int)
    return ch[np.clip(yy + dy, 0, H - 1), np.clip(xx + dx, 0, W - 1)]
img = np.dstack([shift(img[..., 0], -1), img[..., 1], shift(img[..., 2], 1)])
# grade: warm highlights, cool deep shadows; grain (soft, a little stronger)
lum = img.mean(-1, keepdims=True) / 255
img = img * (1 + 0.06 * lum) + (1 - lum) ** 3 * np.array([-2, 2, 6])
gr = np.random.default_rng(3).normal(0, 1, (H, W)).astype(np.float32)
gr = np.asarray(Image.fromarray(((gr * 40) + 128).clip(0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.6))).astype(float) - 128
img += gr[..., None] * S.get('grain', 0.16)
Image.fromarray(np.clip(img, 0, 255).astype(np.uint8)).save(S['out'])
