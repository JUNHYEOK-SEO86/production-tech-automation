"""PE-AMS 바탕화면 아이콘용 기어(엔지니어링) 아이콘을 생성한다. (일회성 빌드 스크립트)"""
import math

from PIL import Image, ImageDraw

SIZE = 256
BG_COLOR = (17, 24, 39, 255)      # #111827 (사이드바 배경)
GEAR_COLOR = (37, 99, 235, 255)   # #2563eb (앱 포인트 컬러)
BOLT_COLOR = (148, 163, 184, 255)  # #94a3b8


def draw_gear(draw, cx, cy, outer_r, inner_r, teeth, color):
    points = []
    for i in range(teeth * 2):
        angle = math.pi * i / teeth - math.pi / 2
        r = outer_r if i % 2 == 0 else inner_r
        points.append((cx + r * math.cos(angle), cy + r * math.sin(angle)))
    draw.polygon(points, fill=color)


def main():
    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    draw.rounded_rectangle([6, 6, SIZE - 6, SIZE - 6], radius=52, fill=BG_COLOR)

    cx, cy = SIZE / 2, SIZE / 2

    # 큰 기어 (메인)
    draw_gear(draw, cx - 14, cy - 6, outer_r=82, inner_r=64, teeth=9, color=GEAR_COLOR)
    draw.ellipse([cx - 14 - 30, cy - 6 - 30, cx - 14 + 30, cy - 6 + 30], fill=BG_COLOR)
    draw.ellipse([cx - 14 - 14, cy - 6 - 14, cx - 14 + 14, cy - 6 + 14], fill=GEAR_COLOR)

    # 작은 기어 (보조, 우하단에 겹치게)
    draw_gear(draw, cx + 46, cy + 46, outer_r=38, inner_r=28, teeth=7, color=BOLT_COLOR)
    draw.ellipse([cx + 46 - 14, cy + 46 - 14, cx + 46 + 14, cy + 46 + 14], fill=BG_COLOR)
    draw.ellipse([cx + 46 - 6, cy + 46 - 6, cx + 46 + 6, cy + 46 + 6], fill=BOLT_COLOR)

    img.save("pe_ams_icon.ico", sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)])
    print("saved pe_ams_icon.ico")


if __name__ == "__main__":
    main()
