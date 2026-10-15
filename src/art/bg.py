# battlefield backdrop: dark sky, warm fire glow on the horizon, drifting smoke, embers. usage: bg.py W H out.png [horizon 0-1] [glow_x 0-1]
import sys, numpy as np
from PIL import Image, ImageFilter
W, H, out = int(sys.argv[1]), int(sys.argv[2]), sys.argv[3]
hz = float(sys.argv[4]) if len(sys.argv) > 4 else 0.62
gx = float(sys.argv[5]) if len(sys.argv) > 5 else 0.78
rng = np.random.default_rng(7)
def vnoise(w, h, cell):
    gw, gh = int(np.ceil(w / cell)) + 2, int(np.ceil(h / cell)) + 2
    g = rng.random((gh, gw))
    y, x = np.mgrid[0:h, 0:w] / cell
    x0, y0 = x.astype(int), y.astype(int); fx, fy = x - x0, y - y0
    fx, fy = fx * fx * (3 - 2 * fx), fy * fy * (3 - 2 * fy)
    a = g[y0, x0] * (1 - fx) + g[y0, x0 + 1] * fx
    b = g[y0 + 1, x0] * (1 - fx) + g[y0 + 1, x0 + 1] * fx
    return a * (1 - fy) + b * fy
def fbm(w, h, base, oct=6):
    s, amp, tot = np.zeros((h, w)), 1.0, 0
    for o in range(oct):
        s += vnoise(w, h, max(2, base / 2 ** o)) * amp; tot += amp; amp *= 0.5
    return s / tot
y, x = np.mgrid[0:H, 0:W]; u, v = x / W, y / H
# sky: deep blue-grey at the top to warm brown at the horizon
top, mid, hor = np.array([10, 13, 17]), np.array([34, 30, 30]), np.array([120, 62, 26])
t = np.clip(v / hz, 0, 1)[..., None]
sky = top * (1 - t) ** 1.6 + (mid * (1 - t) + hor * t) * (1 - (1 - t) ** 1.6)
# fire glow on the horizon
d = np.sqrt(((u - gx) * W / H * 1.0) ** 2 + ((v - hz) * 2.2) ** 2)
glow = np.exp(-d * 3.2)[..., None] * np.array([255, 120, 35]) * 0.85
d2 = np.sqrt(((u - gx + 0.35) * W / H) ** 2 + ((v - hz) * 2.6) ** 2)
glow += np.exp(-d2 * 4.5)[..., None] * np.array([255, 100, 30]) * 0.35
img = sky + glow
# far ridge line and nearer hills (silhouettes), the ground soft below them
def ridge(base, amp, cell, seed):
    r = np.random.default_rng(seed); n = int(W / cell) + 3; pts = r.random(n)
    xs = np.arange(W) / cell; i = xs.astype(int); f = xs - i; f = f * f * (3 - 2 * f)
    line = pts[i] * (1 - f) + pts[i + 1] * f
    xs2 = np.arange(W) / (cell / 4); i2 = xs2.astype(int); f2 = xs2 - i2
    pts2 = r.random(int(W / (cell / 4)) + 3); line += 0.25 * (pts2[i2] * (1 - f2) + pts2[i2 + 1] * f2)
    return (base - amp * line) * H
far_r = ridge(hz + 0.01, 0.06, W / 5, 3)
near_r = ridge(hz + 0.07, 0.07, W / 3, 5)
far_m = (y > far_r[None, :])
near_m = (y > near_r[None, :])
fc = np.array([48, 30, 20]) + glow * 0.30
img = np.where(far_m[..., None], fc, img)
g = np.clip((v - hz) / (1 - hz), 0, 1)[..., None]
ground = np.array([20, 15, 12]) * (1 - g) + np.array([7, 6, 5]) * g + glow * 0.12 * (1 - g)
img = np.where(near_m[..., None], ground, img)
# smoke: billows (fbm with contrast) and darker plumes rising from the ridge, lit warm near the glow
sm = fbm(W, H, max(W, H) / 3.0, 7)
sm2 = fbm(W, H, max(W, H) / 8.0, 6)
smoke = np.clip((sm * 0.65 + sm2 * 0.35 - 0.45) * 3.2, 0, 1) ** 1.3
lit = np.clip(1.25 - d * 1.5, 0.1, 1)[..., None]
smoke_col = np.array([46, 40, 38]) * (1 - lit) + np.array([200, 115, 55]) * lit
band = np.exp(-((v - hz + 0.15) / 0.30) ** 2)
a = (smoke * (0.30 + 0.70 * band))[..., None]
img = img * (1 - a * 0.9) + smoke_col * a * 0.9
# plumes: dark columns of smoke rising from fires on the ridge
for px, pw in [(gx - 0.05, 0.10), (gx + 0.14, 0.07), (gx - 0.42, 0.08)]:
    col = np.exp(-((u - px - (hz - v) * 0.18) / (pw * (1 + (hz - v) * 1.6))) ** 2) * (v < hz + 0.02) * np.clip((hz - v) * 3, 0, 1)
    dens = (col * (0.45 + 0.55 * sm2))[..., None] * 0.75
    img = img * (1 - dens) + np.array([25, 22, 22]) * dens
# embers
emb = np.zeros((H, W))
for _ in range(int(W * H / 22000)):
    ex, ey = rng.integers(0, W), int(H * (hz - 0.45 + rng.random() * 0.6))
    if 0 <= ey < H: emb[ey, ex] = rng.random() ** 2 * 3
emb = np.array(Image.fromarray((np.clip(emb, 0, 1) * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.2))) / 255.0 * 4
img += np.clip(emb, 0, 1)[..., None] * np.array([255, 170, 80])
# vignette
vig = 1 - 0.55 * np.clip(np.sqrt(((u - 0.5) * 1.2) ** 2 + ((v - 0.45) * 1.1) ** 2) - 0.2, 0, 1) ** 1.4
img *= vig[..., None]
Image.fromarray(np.clip(img, 0, 255).astype(np.uint8)).save(out)
# the smoke alone (for haze in front of far things): RGBA
haze = np.dstack([smoke_col, (np.clip(smoke * 1.2 + 0.25 * band, 0, 1) * 255)]).astype(np.uint8)
Image.fromarray(np.clip(haze, 0, 255).astype(np.uint8), 'RGBA').save(out.replace('.png', '_haze.png'))
