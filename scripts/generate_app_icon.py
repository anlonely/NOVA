from __future__ import annotations

import math
import struct
import subprocess
from pathlib import Path
import zlib

ROOT = Path(__file__).resolve().parents[1]
ICON_DIR = ROOT / "assets" / "icons"
ICONSET = ICON_DIR / "NovaInterp.iconset"
PNG_PATH = ICON_DIR / "nova_interp_icon_1024.png"
ICNS_PATH = ICON_DIR / "nova_interp.icns"
ICO_PATH = ICON_DIR / "nova_interp.ico"
SVG_PATH = ICON_DIR / "nova_interp_icon.svg"


def clamp(value: float, lo: int = 0, hi: int = 255) -> int:
    return max(lo, min(hi, int(round(value))))


def mix(a: tuple[int, int, int], b: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    return tuple(clamp(a[i] * (1 - t) + b[i] * t) for i in range(3))


def smoothstep(edge0: float, edge1: float, x: float) -> float:
    if edge0 == edge1:
        return 1.0 if x >= edge1 else 0.0
    t = max(0.0, min(1.0, (x - edge0) / (edge1 - edge0)))
    return t * t * (3.0 - 2.0 * t)


def blend(dst: list[int], src: tuple[int, int, int], alpha: float) -> None:
    alpha = max(0.0, min(1.0, alpha))
    inv = 1.0 - alpha
    dst[0] = clamp(src[0] * alpha + dst[0] * inv)
    dst[1] = clamp(src[1] * alpha + dst[1] * inv)
    dst[2] = clamp(src[2] * alpha + dst[2] * inv)
    dst[3] = clamp(255 * alpha + dst[3] * inv)


def rounded_rect_alpha(x: float, y: float, size: int, radius: float) -> float:
    cx = size / 2
    cy = size / 2
    px = abs(x - cx) - (size / 2 - radius)
    py = abs(y - cy) - (size / 2 - radius)
    outside = math.hypot(max(px, 0.0), max(py, 0.0)) + min(max(px, py), 0.0) - radius
    return 1.0 - smoothstep(-1.2, 1.2, outside)


def line_distance(px: float, py: float, ax: float, ay: float, bx: float, by: float) -> float:
    vx = bx - ax
    vy = by - ay
    wx = px - ax
    wy = py - ay
    denom = vx * vx + vy * vy
    t = 0.0 if denom == 0 else max(0.0, min(1.0, (wx * vx + wy * vy) / denom))
    qx = ax + t * vx
    qy = ay + t * vy
    return math.hypot(px - qx, py - qy)


def draw_icon(size: int) -> bytearray:
    data = bytearray(size * size * 4)
    cx = cy = size / 2
    bg_top = (12, 18, 34)
    bg_bottom = (27, 12, 54)
    cyan = (36, 235, 255)
    violet = (138, 92, 255)
    magenta = (255, 77, 210)
    white = (235, 252, 255)

    for y in range(size):
        for x in range(size):
            index = (y * size + x) * 4
            px = x + 0.5
            py = y + 0.5
            alpha = rounded_rect_alpha(px, py, size, size * 0.215)
            t = py / size
            base = list(mix(bg_top, bg_bottom, t)) + [0]
            vignette = math.hypot((px - cx) / cx, (py - cy) / cy)
            glow = max(0.0, 1.0 - math.hypot((px - cx) / (size * 0.50), (py - cy) / (size * 0.42)))
            base[0] = clamp(base[0] + 26 * glow - 18 * vignette)
            base[1] = clamp(base[1] + 18 * glow - 12 * vignette)
            base[2] = clamp(base[2] + 54 * glow - 16 * vignette)
            base[3] = clamp(255 * alpha)

            dx = px - cx
            dy = py - cy
            r = math.hypot(dx, dy)
            angle = math.atan2(dy, dx)

            for radius, width, color, phase, power in (
                (size * 0.335, size * 0.018, cyan, 0.0, 0.78),
                (size * 0.405, size * 0.014, violet, 1.6, 0.58),
                (size * 0.258, size * 0.010, magenta, 3.1, 0.46),
            ):
                arc = 0.58 + 0.42 * math.sin(angle * 3 + phase)
                dist = abs(r - radius)
                line_a = (1.0 - smoothstep(width * 0.45, width * 1.35, dist)) * arc * power
                blend(base, color, line_a * alpha)

            for i, amp in enumerate((0.17, 0.25, 0.34, 0.44, 0.34, 0.25, 0.17)):
                bx = cx + (i - 3) * size * 0.052
                h = size * amp
                d = line_distance(px, py, bx, cy - h / 2, bx, cy + h / 2)
                bar_alpha = 1.0 - smoothstep(size * 0.012, size * 0.024, d)
                color = mix(cyan, violet, i / 6)
                blend(base, color, bar_alpha * 0.95 * alpha)

            n_points = [
                (cx - size * 0.235, cy + size * 0.155),
                (cx - size * 0.235, cy - size * 0.155),
                (cx + size * 0.235, cy + size * 0.155),
                (cx + size * 0.235, cy - size * 0.155),
            ]
            segments = [(n_points[0], n_points[1]), (n_points[1], n_points[2]), (n_points[2], n_points[3])]
            for a, b in segments:
                d = line_distance(px, py, a[0], a[1], b[0], b[1])
                n_alpha = 1.0 - smoothstep(size * 0.018, size * 0.038, d)
                blend(base, white, n_alpha * 0.95 * alpha)

            star = max(0.0, 1.0 - r / (size * 0.070))
            blend(base, (255, 255, 255), star * 0.92 * alpha)
            for ray_angle in (0, math.pi / 2, math.pi / 4, -math.pi / 4):
                ray = abs(math.sin(angle - ray_angle)) * r
                ray_alpha = (1.0 - smoothstep(size * 0.003, size * 0.013, ray)) * (1.0 - smoothstep(size * 0.04, size * 0.18, r))
                blend(base, (255, 255, 255), ray_alpha * 0.35 * alpha)

            data[index:index+4] = bytes(base)
    return data


def png_bytes(width: int, height: int, rgba: bytes) -> bytes:
    def chunk(kind: bytes, payload: bytes) -> bytes:
        return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)

    raw = bytearray()
    stride = width * 4
    for y in range(height):
        raw.append(0)
        raw.extend(rgba[y * stride:(y + 1) * stride])
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(bytes(raw), 9)) + chunk(b"IEND", b"")


def write_png(path: Path, size: int) -> None:
    path.write_bytes(png_bytes(size, size, draw_icon(size)))


def make_ico(path: Path, sizes: list[int]) -> None:
    images = []
    for size in sizes:
        images.append((size, png_bytes(size, size, draw_icon(size))))
    header = struct.pack("<HHH", 0, 1, len(images))
    directory = bytearray()
    offset = 6 + 16 * len(images)
    payload = bytearray()
    for size, image in images:
        directory.extend(struct.pack("<BBBBHHII", 0 if size == 256 else size, 0 if size == 256 else size, 0, 0, 1, 32, len(image), offset))
        payload.extend(image)
        offset += len(image)
    path.write_bytes(header + directory + payload)


def write_svg(path: Path) -> None:
    path.write_text('''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1024 1024">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#0C1222"/><stop offset="1" stop-color="#1B0C36"/></linearGradient>
    <linearGradient id="neon" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#24EBFF"/><stop offset="1" stop-color="#8A5CFF"/></linearGradient>
  </defs>
  <rect x="48" y="48" width="928" height="928" rx="220" fill="url(#bg)"/>
  <circle cx="512" cy="512" r="360" fill="none" stroke="#24EBFF" stroke-width="28" opacity=".65"/>
  <circle cx="512" cy="512" r="430" fill="none" stroke="#8A5CFF" stroke-width="18" opacity=".45"/>
  <g stroke="url(#neon)" stroke-linecap="round" stroke-width="28">
    <path d="M352 604V420"/><path d="M405 640V384"/><path d="M458 688V336"/><path d="M512 736V288"/><path d="M566 688V336"/><path d="M619 640V384"/><path d="M672 604V420"/>
  </g>
  <path d="M270 670V354L754 670V354" fill="none" stroke="#EBFCFF" stroke-linecap="round" stroke-linejoin="round" stroke-width="54"/>
  <path d="M512 438v148M438 512h148M460 460l104 104M564 460 460 564" stroke="#fff" stroke-linecap="round" stroke-width="18"/>
</svg>
''', encoding='utf-8')


def main() -> None:
    ICON_DIR.mkdir(parents=True, exist_ok=True)
    ICONSET.mkdir(parents=True, exist_ok=True)
    write_png(PNG_PATH, 1024)
    write_svg(SVG_PATH)
    iconset_specs = {
        "icon_16x16.png": 16,
        "icon_16x16@2x.png": 32,
        "icon_32x32.png": 32,
        "icon_32x32@2x.png": 64,
        "icon_128x128.png": 128,
        "icon_128x128@2x.png": 256,
        "icon_256x256.png": 256,
        "icon_256x256@2x.png": 512,
        "icon_512x512.png": 512,
        "icon_512x512@2x.png": 1024,
    }
    source_png = PNG_PATH
    for name, size in iconset_specs.items():
        target = ICONSET / name
        if size == 1024:
            target.write_bytes(source_png.read_bytes())
        else:
            subprocess.run(["sips", "-z", str(size), str(size), str(source_png), "--out", str(target)], check=True, stdout=subprocess.DEVNULL)
    subprocess.run(["iconutil", "-c", "icns", str(ICONSET), "-o", str(ICNS_PATH)], check=True)
    for ico_size in [256, 128, 64, 48, 32, 24, 16]:
        subprocess.run(["sips", "-z", str(ico_size), str(ico_size), str(source_png), "--out", str(ICON_DIR / f"ico_{ico_size}.png")], check=True, stdout=subprocess.DEVNULL)
    make_ico(ICO_PATH, [16, 24, 32, 48, 64, 128, 256])
    print(PNG_PATH)
    print(ICNS_PATH)
    print(ICO_PATH)


if __name__ == "__main__":
    main()
