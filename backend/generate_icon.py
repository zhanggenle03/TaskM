#!/usr/bin/env python3
"""
根据 SVG 路径生成 TaskM 应用图标（.ico 文件）

SVG path 描述了一个 3×3 任务看板网格。
使用 BMP 编码（非 PNG），确保与 PyInstaller --icon 完全兼容。
"""
import os
import struct
import io
from PIL import Image, ImageDraw

# ── 参数 ──
CANVAS = 1024
ICON_SIZES = [16, 32, 48, 64, 128, 256]

# TaskM 品牌蓝色 (#409EFF)
FILL_COLOR = (64, 158, 255, 255)
GAP = 64  # 网格间隙（viewBox=1024 坐标系）

# 9 个矩形的原始坐标（从 SVG path 解析）
SQUARES = [
    (128, 128, 320, 320),   # 左上
    (384, 128, 640, 320),   # 中上
    (704, 128, 896, 320),   # 右上
    (128, 384, 320, 640),   # 左中
    (384, 384, 640, 640),   # 中心
    (704, 384, 896, 640),   # 右中
    (128, 704, 320, 896),   # 左下
    (384, 704, 640, 896),   # 中下
    (704, 704, 896, 896),   # 右下
]


def draw_hires() -> Image.Image:
    """在 1024×1024 画布上绘制图标（RGBA）"""
    img = Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    half = GAP // 2
    for x1, y1, x2, y2 in SQUARES:
        draw.rectangle([x1 + half, y1 + half, x2 - half, y2 - half], fill=FILL_COLOR)
    return img


def _make_bmp_data(img: Image.Image) -> bytes:
    """
    将 RGBA Image 编码为 ICO 内嵌的 BMP DIB 数据（含 XOR mask + AND mask）。
    ICO 的 BMP 与标准 BMP 不同：
      - 没有 BMP 文件头（直接以 DIB header 开始）
      - height 是实际高度的两倍（XOR + AND）
      - 行序 bottom-up
    """
    w, h = img.size

    # ── DIB header (BITMAPINFOHEADER, 40 bytes) ──
    # ICO 规范：biHeight = 实际高度 × 2（XOR 掩码 + AND 掩码）
    dib = struct.pack(
        "<IiiHHIIiiII",
        40,             # biSize
        w,              # biWidth
        h * 2,          # biHeight（ICO 的 XOR+AND 双倍高）
        1,              # biPlanes（必须为 1）
        32,             # biBitCount（32-bit RGBA）
        0,              # biCompression (BI_RGB)
        0,              # biSizeImage
        0, 0, 0, 0,     # 可选字段
    )

    # ── XOR mask（像素数据，BGRA 格式，bottom-up） ──
    # Pillow 像素顺序是 RGBA，BMP 需要 BGRA
    r, g, b, a = img.split()
    bgra = Image.merge("RGBA", (b, g, r, a))

    # Bottom-up 行序
    rows = []
    for y in range(h - 1, -1, -1):
        row = bgra.crop((0, y, w, y + 1)).tobytes()
        # BMP 每行按 4 字节对齐
        pad = (4 - len(row) % 4) % 4
        if pad:
            row += b"\x00" * pad
        rows.append(row)
    xor_data = b"".join(rows)

    # ── AND mask（1-bit 透明蒙版，bottom-up） ──
    # 对于 32-bit 图标，透明度由 alpha 通道控制，AND mask 全 0
    and_row_size = ((w + 31) // 32) * 4
    and_data = b"\x00" * (and_row_size * h)

    return dib + xor_data + and_data


def make_ico(images: list, sizes: list) -> bytes:
    """构造 BMP 编码的多分辨率 ICO 文件"""
    count = len(sizes)
    # 头部
    header = struct.pack("<HHH", 0, 1, count)

    # 编码每帧为 BMP DIB
    bmp_blocks = []
    for img, (w, h) in zip(images, sizes):
        bmp_blocks.append(_make_bmp_data(img))

    # 目录项
    offset = 6 + count * 16
    directory = b""
    for i in range(count):
        w, h = sizes[i]
        bmp = bmp_blocks[i]
        directory += struct.pack(
            "<BBBBHHII",
            0 if w >= 256 else w,  # w=0 → 256
            0 if h >= 256 else h,  # h=0 → 256
            0,   # 调色板颜色数
            0,   # 保留
            1,   # 颜色平面
            32,  # bpp
            len(bmp),
            offset,
        )
        offset += len(bmp)

    return header + directory + b"".join(bmp_blocks)


def main():
    backend_dir = os.path.dirname(os.path.abspath(__file__))
    ico_path = os.path.join(backend_dir, "taskm.ico")

    hi = draw_hires()
    sizes = [(s, s) for s in ICON_SIZES]
    images = [hi.resize((s, s), Image.LANCZOS) for s in ICON_SIZES]

    ico_bytes = make_ico(images, sizes)
    with open(ico_path, "wb") as f:
        f.write(ico_bytes)

    file_size = os.path.getsize(ico_path)
    print(f"[图标] 已生成: {ico_path} ({file_size} bytes)")
    print(f"[图标] 包含尺寸: {ICON_SIZES}")

    # 清理临时文件
    for f in ("test_icon.png", "test_icon_256.png", "ico_preview.png"):
        fp = os.path.join(backend_dir, f)
        if os.path.isfile(fp):
            os.remove(fp)


if __name__ == "__main__":
    main()
