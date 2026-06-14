"""Generate inp-tool-gui.ico for Windows EXE bundling.

调用方式(本地一次性,产物 commit 进仓库):
    conda run -n cfdchanger python scripts/generate_gui_icon.py

输出:
    inp_tool/inp_tool_gui/resources/inp-tool-gui.ico
        - 256x256 (Vista+ 真实大尺寸,Win7 用 64x64 子图)
        - 多分辨率: 16, 32, 48, 64, 128, 256(嵌入 ICO 格式)
    inp_tool/inp_tool_gui/resources/inp-tool-gui.png
        - 256x256 PNG(备用,docs/README 显示用)

设计:深蓝底 + 白色 "CFD" 字 + 一道流线(暗示流体)。
不依赖外部资源,纯 Pillow stdlib + 默认字体。
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT_DIR = Path(__file__).resolve().parent.parent / "inp_tool" / "inp_tool_gui" / "resources"
ICO_PATH = OUT_DIR / "inp-tool-gui.ico"
PNG_PATH = OUT_DIR / "inp-tool-gui.png"

# 多分辨率(嵌入同一 .ico 文件,Win7/8/10 各取所需)
ICO_SIZES = (16, 32, 48, 64, 128, 256)


def render_icon(size: int) -> Image.Image:
    """生成指定尺寸的图标 RGBA 图。"""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # 圆角矩形底(深蓝 #1E40AF,Win7 任务栏友好)
    margin = max(1, size // 16)
    radius = max(1, size // 8)
    draw.rounded_rectangle(
        [margin, margin, size - margin, size - margin],
        radius=radius,
        fill=(30, 64, 175, 255),  # 深蓝
    )

    # 顶部一道流线(青色 #06B6D4),暗示流体动力学
    line_y = size // 3
    line_w = size // 12
    for offset in range(-1, 2):
        draw.line(
            [(size // 6, line_y + offset), (size * 5 // 6, line_y + offset)],
            fill=(6, 182, 212, 255),
            width=max(1, line_w),
        )

    # "CFD" 文字(白色,粗体)。小尺寸(<=32)省文字,只用流线表示流体符号
    if size >= 48:
        font_size = max(8, size // 4)
        try:
            # Pillow 默认字体在 conda env 里不一定能找到 DejaVu,fallback 到 default
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", font_size)
        except OSError:
            font = ImageFont.load_default()
        text = "CFD"
        # textbbox 替代 deprecated textsize
        bbox = draw.textbbox((0, 0), text, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        text_x = (size - text_w) // 2 - bbox[0]
        text_y = size * 2 // 3 - text_h // 2 - bbox[1]
        draw.text((text_x, text_y), text, fill=(255, 255, 255, 255), font=font)

    return img


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # PNG 主图(256,用于 docs/README 显示)
    base = render_icon(256)
    base.save(PNG_PATH, format="PNG")
    print(f"✓ {PNG_PATH} ({PNG_PATH.stat().st_size // 1024} KB)")

    # 多分辨率 ICO:Pillow 的 ICO save 一次只支持单尺寸,
    # 但支持 bitmap_format='png' + sizes=[...] 把所有尺寸打包进同一文件。
    # 用最大尺寸(256)做 base,其他尺寸 append。
    images = [render_icon(s) for s in ICO_SIZES]
    largest = images[-1]  # 256x256
    largest.save(
        ICO_PATH,
        format="ICO",
        sizes=[(s, s) for s in ICO_SIZES],
        append_images=images[:-1],
    )
    print(f"✓ {ICO_PATH} ({ICO_PATH.stat().st_size} bytes), sizes={ICO_SIZES}")

    # 校验生成的 .ico 包含所有尺寸
    from PIL import IcoImagePlugin
    with IcoImagePlugin.IcoImageFile(ICO_PATH) as ico:
        actual_sizes = sorted(ico.ico.sizes())
        print(f"  embedded sizes: {actual_sizes}")
        if set(actual_sizes) != set(ICO_SIZES):
            print(f"  ⚠ 警告:期望 {set(ICO_SIZES)},实际 {set(actual_sizes)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())