#!/usr/bin/env python3
"""
根据 SVG 路径生成 TaskM 应用图标（.ico 文件）

SVG path 描述了一个 3×3 任务看板网格。
策略：先在 1024×1024 高分辨率画布上精确绘制，再缩放到各 ICO 尺寸。
"""
import os
import struct
import io
from PIL import Image, ImageDraw

# ── 参数 ──
CANVAS = 1024
# ICO 多尺寸（Windows 支持的常用分辨率）
# 注意：16/32/48 用于资源管理器列表，256 用于大图标/属性面板
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


def make_ico(images: list, sizes: list) -> bytes:
    """
    手工构造多分辨率 ICO 文件。
    ICO 格式：6 字节头 + 16 字节/个的目录项 + N 个嵌入 PNG/BMP。
    """
    # 所有尺寸转换为 PNG 字节
    png_data_list = []
    for img, (w, h) in zip(images, sizes):
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        png_data_list.append(buf.getvalue())

    # ── 构造 ICO 文件 ──
    count = len(sizes)
    # 头部：reserved(2) + type(2=ico) + count(2)
    header = struct.pack("<HHH", 0, 1, count)

    # 目录项偏移：header(6) + 目录项(count*16)
    data_offset = 6 + count * 16
    directory = b""
    png_payload = b""
    for i in range(count):
        w, h = sizes[i]
        png = png_data_list[i]
        # 目录项：w(1) + h(1) + palette(1) + reserved(1) + planes(2) + bpp(2) + size(4) + offset(4)
        # w/h=0 表示 256
        directory += struct.pack(
            "<BBBBHHII",
            0 if w >= 256 else w,
            0 if h >= 256 else h,
            0,  # 调色板
            0,  # 保留
            1,  # 颜色平面
            32,  # 每像素位数 (RGBA)
            len(png),
            data_offset,
        )
        png_payload += png
        data_offset += len(png)

    return header + directory + png_payload


def main():
    backend_dir = os.path.dirname(os.path.abspath(__file__))
    icon_path = os.path.join(backend_dir, "taskm.ico")

    # 高分辨率原图
    hi = draw_hires()

    # 生成各尺寸缩略图
    sizes = [(s, s) for s in ICON_SIZES]
    images = [hi.resize((s, s), Image.LANCZOS) for s in ICON_SIZES]

    # 手工构建多帧 ICO
    ico_bytes = make_ico(images, sizes)
    with open(icon_path, "wb") as f:
        f.write(ico_bytes)

    file_size = os.path.getsize(icon_path)
    print(f"[图标] 已生成: {icon_path} ({file_size} bytes)")
    print(f"[图标] 包含尺寸: {ICON_SIZES}")

    # 清理测试文件
    for f in ("test_icon.png", "test_icon_256.png", "ico_preview.png"):
        fp = os.path.join(backend_dir, f)
        if os.path.isfile(fp):
            os.remove(fp)


if __name__ == "__main__":
    main()
