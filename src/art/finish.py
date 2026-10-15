# print finish over the whole poster (type included): worn ink specks, paper grain. usage: finish.py in.png out.png
import sys, numpy as np
from PIL import Image, ImageFilter
a = np.asarray(Image.open(sys.argv[1]).convert('RGB')).astype(float); H, W = a.shape[:2]
rng = np.random.default_rng(5)
n = np.asarray(Image.fromarray((rng.random((H, W)) * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.0))).astype(float)
lum = a.mean(-1)
# light ink (cream/yellow type) gets a few dark specks; dark ink gets paper specks
sp_light = (n > 152) & (rng.random((H, W)) > 0.72) & (lum > 150)
sp_dark = (n > 150) & (rng.random((H, W)) > 0.6) & (lum < 60)
a[sp_light] *= 0.82
a[sp_dark] = a[sp_dark] * 0.55 + np.array([246, 231, 193]) * 0.18
g = np.asarray(Image.fromarray(rng.normal(128, 30, (H, W)).clip(0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.6))).astype(float) - 128
a *= (1 + g * 0.0011)[..., None]
Image.fromarray(np.clip(a, 0, 255).astype(np.uint8)).save(sys.argv[2])
