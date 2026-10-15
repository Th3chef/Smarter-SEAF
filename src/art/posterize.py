# flat screen-print tones from the matcap render: black ink, a dark olive mid-tone, yellow where the fire rim hits
import sys, numpy as np
from PIL import Image, ImageFilter
src, out = sys.argv[1], sys.argv[2]
k = float(sys.argv[3]) if len(sys.argv) > 3 else 1.0
im = Image.open(src).convert('RGBA')
a = np.asarray(im).astype(float)
rgb, al = a[..., :3], a[..., 3]
r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
lum = rgb.mean(-1)
rim = (r - b)                       # the orange fire rim of the matcap
level = np.zeros(lum.shape, np.uint8)
level[lum > 34 * k] = 1             # mid-tone
level[(rim > 40 * k) & (r > 80 * k)] = 2   # rim highlight
# clean shapes: a median filter on the tone map (like a screen-print separation)
lv = Image.fromarray(level * 100).filter(ImageFilter.MedianFilter(5)).filter(ImageFilter.MedianFilter(3))
level = (np.asarray(lv) // 100).astype(np.uint8)
pal = np.array([[18, 17, 16], [52, 49, 40], [246, 231, 193]], float)
col = pal[level]
alpha = np.asarray(Image.fromarray(al.astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.8))).astype(float)
alpha = np.clip((alpha - 100) * 2.2, 0, 255)       # crisp cut edge
Image.fromarray(np.dstack([col, alpha]).astype(np.uint8), 'RGBA').save(out)
