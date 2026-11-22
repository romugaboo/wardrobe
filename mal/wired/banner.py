"""Green LED banners for Wired.

Draw the default banner:
    py banner.py --default banner.png

Turn any picture into a banner:
    py banner.py picture.jpg my-banner.png [--shape round|square|circle] [--cell 8]
        [--contrast 1.4] [--cut 0.5] [--center 0.5] [--invert] [--keep-left]

Needs numpy and Pillow.
"""

import argparse

import numpy as np
from PIL import Image, ImageFilter, ImageOps

W, H = 1920, 432                               # MAL banners are about 4.5:1
GREEN = np.array([57, 255, 136], dtype=float)  # #39FF88
BG = np.array([4, 10, 6], dtype=float)


def make_dot(cell, shape):
    dot = np.zeros((cell, cell))
    if shape == 'circle':
        yy, xx = np.mgrid[0:cell, 0:cell] + 0.5
        r = cell / 2 - 1
        dot = np.clip(r + 0.5 - np.hypot(xx - cell / 2, yy - cell / 2), 0, 1)
    else:
        dot[1:cell - 1, 1:cell - 1] = 1
        if shape == 'round':
            dot[1, 1] = dot[1, -2] = dot[-2, 1] = dot[-2, -2] = 0.4
    return dot


def render(field, cell=8, shape='round', dark_left=True):
    """Draws a brightness grid (0..1, one value per LED) as a glowing banner."""
    lit = np.kron(field, make_dot(cell, shape))[:H, :W]
    lit_img = Image.fromarray(np.clip(lit * 255, 0, 255).astype(np.uint8))
    glow_small = np.asarray(lit_img.filter(ImageFilter.GaussianBlur(6)), dtype=float) / 255
    glow_big = np.asarray(lit_img.filter(ImageFilter.GaussianBlur(28)), dtype=float) / 255
    light = lit * 0.85 + glow_small * 0.55 + glow_big * 0.6

    vy, vx = np.mgrid[0:H, 0:W]
    vy, vx = vy / H, vx / W
    vignette = np.clip(1.3 - np.hypot((vx - 0.62) * 1.2, (vy - 0.4) * 1.5), 0, 1)
    if dark_left:
        vignette *= np.clip(0.35 + vx * 2.2, 0, 1)   # room for the boot text
    light *= vignette

    out = BG + light[..., None] * GREEN
    out += np.clip(light - 1.0, 0, 1)[..., None] * 160   # hot spots go white
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8))


def picture_field(path, cell=8, contrast=1.4, cut=0.5, center=0.5, invert=False):
    img = Image.open(path).convert('L')
    img = ImageOps.fit(img, (W, H), Image.LANCZOS, centering=(0.5, center))
    img = ImageOps.autocontrast(img, cutoff=1)
    if invert:
        img = ImageOps.invert(img)
    small = img.resize((-(-W // cell), -(-H // cell)), Image.LANCZOS)   # round up, render crops
    field = np.asarray(small, dtype=float) / 255
    field = np.clip((field - cut) * contrast + 0.5, 0, 1) ** 1.6
    return field * 1.1 + 0.028


def default_field(cell=8):
    """A signal made of LED bars plus an eight-point light flare."""
    gw, gh = W // cell, H // cell
    rng = np.random.default_rng(23)
    ys, xs = np.mgrid[0:gh, 0:gw].astype(float)
    field = np.zeros((gh, gw))

    # signal bars, tallest in the middle of the group
    for x in range(62, 147):
        center = 1 - abs(x - 104) / 44
        h = gh * (0.12 + 0.55 * center ** 1.6) * rng.uniform(0.55, 1.0)
        if rng.random() < 0.18:
            h *= rng.uniform(1.1, 1.45)
        top = gh - h
        column = np.clip((ys[:, x] - top) / max(h, 1), 0, 1)
        field[:, x] = np.maximum(field[:, x], (column > 0) * (0.35 + 0.65 * (1 - column) ** 0.6))
        # loose pixels floating above some bars
        for _ in range(rng.integers(0, 4)):
            y = int(top - rng.integers(2, 14))
            if 0 <= y < gh:
                field[y, x] = max(field[y, x], rng.uniform(0.3, 0.8))

    # thin vertical lines on the far right
    for x in (222, 227, 233):
        h = gh * rng.uniform(0.5, 0.95)
        field[int(gh - h):, x] = np.maximum(field[int(gh - h):, x], 0.45)

    # the flare: 8 rays plus a bright core
    cx, cy = 186, 19
    dx, dy = xs - cx, ys - cy
    r = np.hypot(dx, dy)
    for angle in np.radians([0, 45, 90, 135]):
        perp = np.abs(dx * np.sin(angle) - dy * np.cos(angle))
        length = 30 if angle in (0, np.pi / 2) else 15
        field = np.maximum(field, 0.9 * np.exp(-(perp / 0.8) ** 2) * np.exp(-r / length))
    field = np.maximum(field, np.exp(-(r / 2.6) ** 2) * 1.25)

    # faint grid of unlit LEDs and a little noise
    field += 0.028 + rng.normal(0, 0.01, field.shape)
    return np.clip(field, 0, 1.3)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Make a green LED banner.')
    parser.add_argument('files', nargs='+', metavar='file',
                        help='picture and output, or just the output with --default')
    parser.add_argument('--default', action='store_true', help='draw the default Wired banner')
    parser.add_argument('--shape', choices=['round', 'square', 'circle'], default='round',
                        help='LED shape')
    parser.add_argument('--cell', type=int, default=8, help='LED size in pixels')
    parser.add_argument('--contrast', type=float, default=1.4)
    parser.add_argument('--cut', type=float, default=0.5,
                        help='brightness that stays mid-lit, raise it to darken backgrounds')
    parser.add_argument('--center', type=float, default=0.5,
                        help='vertical crop position, 0 is the top and 1 the bottom')
    parser.add_argument('--invert', action='store_true', help='light areas become dark')
    parser.add_argument('--keep-left', action='store_true', help='do not darken the left side')
    args = parser.parse_args()

    if args.default and len(args.files) == 1:
        image = render(default_field(), 8, shape='square')
    elif not args.default and len(args.files) == 2:
        picture = args.files[0]
        field = picture_field(picture, args.cell, args.contrast, args.cut, args.center, args.invert)
        image = render(field, args.cell, args.shape, dark_left=not args.keep_left)
    else:
        parser.error('use "banner.py picture.jpg out.png" or "banner.py --default out.png"')

    output = args.files[-1]
    image.save(output, optimize=True)
    print('saved', output)
