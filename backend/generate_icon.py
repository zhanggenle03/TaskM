#!/usr/bin/env python3
"""
根据 SVG 路径生成 TaskM 应用图标（.ico 文件）。

生成单帧 256×256 PNG 编码的 ICO，兼容所有主流 PyInstaller 版本。
Windows 10+ 原生支持多尺寸缩放，单帧足够。
"""
import os
from PIL import Image, ImageDraw

CANVAS = 1024
FILL_COLOR = (64, 158, 255, 255)    # #409EFF
GAP = 64

SQUARES = [
    (128, 128, 320, 320), (384, 128, 640, 320), (704, 128, 896, 320),
    (128, 384, 320, 640), (384, 384, 640, 640), (704, 384, 896, 640),
    (128, 704, 320, 896), (384, 704, 640, 896), (704, 704, 896, 896),
]


def main():
    backend_dir = os.path.dirname(os.path.abspath(__file__))
    ico_path = os.path.join(backend_dir, "taskm.ico")

    img = Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    half = GAP // 2
    for x1, y1, x2, y2 in SQUARES:
        draw.rectangle([x1 + half, y1 + half, x2 - half, y2 - half], fill=FILL_COLOR)

    ico = img.resize((256, 256), Image.LANCZOS)
    ico.save(ico_path, format="ICO")

    print(f"[图标] 已生成: {ico_path} ({os.path.getsize(ico_path)} bytes)")


if __name__ == "__main__":
    main()
