from flask import Flask, send_file, request
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
import io
import os
import datetime
import math

# ------------------------------------------------------------------
# Flask 基本设置：public 目录作为静态目录
# ------------------------------------------------------------------
app = Flask(__name__, static_url_path='', static_folder='public')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(BASE_DIR, "public", "assets")

PAGE_WIDTH, PAGE_HEIGHT = A4

# ------------------------------------------------------------------
# 字体：用 ReportLab 自带日文字体
# ------------------------------------------------------------------
JP_FONT = "HeiseiKakuGo-W5"
pdfmetrics.registerFont(UnicodeCIDFont(JP_FONT))


# ------------------------------------------------------------------
# 工具：铺满整页背景
# ------------------------------------------------------------------
def draw_full_bg(c, filename):
    path = os.path.join(ASSETS_DIR, filename)
    img = ImageReader(path)
    c.drawImage(img, 0, 0, width=PAGE_WIDTH, height=PAGE_HEIGHT)


# ------------------------------------------------------------------
# 工具：日期格式化 YYYY-MM-DD → 2025年11月13日
# ------------------------------------------------------------------
def get_display_date(raw_date: str | None) -> str:
    if raw_date:
        try:
            d = datetime.datetime.strptime(raw_date, "%Y-%m-%d").date()
        except ValueError:
            d = datetime.date.today()
    else:
        d = datetime.date.today()
    return f"{d.year}年{d.month}月{d.day}日"


# ------------------------------------------------------------------
# 工具：在星盘上画小圆点 + 旁边的图标（PNG）
# ------------------------------------------------------------------
def draw_planet_point(
    c,
    center_x,
    center_y,
    radius,
    angle_deg,
    color_rgb,
    icon_filename,
    icon_offset=8,
    point_radius=2.5,
):
    """
    center_x, center_y : 星盘中心
    radius             : 这一圈的半径
    angle_deg          : 行星所在角度（0° 在最上方，逆时针）
    color_rgb          : 小圆点颜色 (r, g, b)
    icon_filename      : PNG 图标文件名（在 public/assets 下）
    icon_offset        : 图标相对小圆点向外的偏移量
    """
    theta = math.radians(90 - angle_deg)  # 把 0° 调整到 12 点方向
    px = center_x + radius * math.cos(theta)
    py = center_y + radius * math.sin(theta)

    # 小圆点
    r, g, b = color_rgb
    c.setFillColorRGB(r, g, b)
    c.circle(px, py, point_radius, fill=1, stroke=0)

    # 图标（放在圆点外侧一点，不要遮挡）
    icon_path = os.path.join(ASSETS_DIR, icon_filename)
    icon_img = ImageReader(icon_path)

    icon_size = 10  # 图标大小
    ix = px + icon_offset * math.cos(theta)
    iy = py + icon_offset * math.sin(theta)

    c.drawImage(
        icon_img,
        ix - icon_size / 2,
        iy - icon_size / 2,
        width=icon_size,
        height=icon_size,
        mask="auto",
    )


# ------------------------------------------------------------------
# 根路径 & test.html
# ------------------------------------------------------------------
@app.route("/")
def root():
    return "PDF server running."


@app.route("/test.html")
def test_page():
    return app.send_static_file("test.html")


# ------------------------------------------------------------------
# 生成 PDF 主入口
# ------------------------------------------------------------------
@app.route("/api/generate_report", methods=["GET"])
def generate_report():
    # ---- 1. 读取参数 ----
    male_name = request.args.get("male_name", "太郎")
    female_name = request.args.get("female_name", "花子")
    raw_date = request.args.get("date")
    date_display = get_display_date(raw_date)

    # ---- 2. 准备 PDF 缓冲区 ----
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)

    font = JP_FONT

    # ------------------------------------------------------------------
    # 封面：cover.jpg
    # ------------------------------------------------------------------
    draw_full_bg(c, "cover.jpg")

    # 姓名
    c.setFont(font, 18)
    c.setFillColorRGB(0.3, 0.3, 0.3)
    couple_text = f"{male_name} さん ＆ {female_name} さん"
    c.drawCentredString(PAGE_WIDTH / 2, 420, couple_text)

    # 作成日
    c.setFont(font, 12)
    date_text = f"作成日：{date_display}"
    c.drawCentredString(PAGE_WIDTH / 2, 80, date_text)

    c.showPage()

    # ------------------------------------------------------------------
    # 第 2 页：目录页（index.jpg）
    # ------------------------------------------------------------------
    draw_full_bg(c, "index.jpg")
    c.showPage()

    # ------------------------------------------------------------------
    # 第 3 页：基本ホロスコープと総合相性
    # ------------------------------------------------------------------
    draw_full_bg(c, "page_basic.jpg")

    # 星盘底图
    chart_path = os.path.join(ASSETS_DIR, "chart_base.png")
    chart_img = ImageReader(chart_path)

    chart_size = 180
    left_x = 90
    left_y = 500
    right_x = PAGE_WIDTH - chart_size - 90
    right_y = left_y

    # 画两个底盘
    c.drawImage(
        chart_img,
        left_x,
        left_y,
        width=chart_size,
        height=chart_size,
        mask="auto",
    )
    c.drawImage(
        chart_img,
        right_x,
        right_y,
        width=chart_size,
        height=chart_size,
        mask="auto",
    )

    # 星盘中心
    left_cx = left_x + chart_size / 2
    left_cy = left_y + chart_size / 2
    right_cx = right_x + chart_size / 2
    right_cy = right_y + chart_size / 2

    orbit_r = chart_size * 0.33  # 行星所在的一圈半径

    # 示例数据（之后再换成真实计算结果）
    male_planets = {
        "sun": 12.3,
        "moon": 65.4,
        "venus": 147.8,
        "mars": 213.2,
        "asc": 290.1,
    }
    female_planets = {
        "sun": 98.5,
        "moon": 152.0,
        "venus": 196.6,
        "mars": 222.9,
        "asc": 328.4,
    }

    icon_files = {
        "sun": "icon_sun.png",
        "moon": "icon_moon.png",
        "venus": "icon_venus.png",
        "mars": "icon_mars.png",
        "asc": "icon_asc.png",
    }

    # 男方：蓝色
    for key, deg in male_planets.items():
        draw_planet_point(
            c,
            left_cx,
            left_cy,
            orbit_r,
            deg,
            color_rgb=(0.2, 0.4, 0.9),
            icon_filename=icon_files[key],
            icon_offset=10,
        )

    # 女方：粉色
    for key, deg in female_planets.items():
        draw_planet_point(
            c,
            right_cx,
            right_cy,
            orbit_r,
            deg,
            color_rgb=(0.9, 0.3, 0.6),
            icon_filename=icon_files[key],
            icon_offset=10,
        )

    # 名字
    c.setFont(font, 14)
    c.setFillColorRGB(0, 0, 0)
    c.drawCentredString(left_cx, left_y - 25, f"{male_name} さん")
    c.drawCentredString(right_cx, right_y - 25, f"{female_name} さん")

    # 行星列表（行距拉开一点，细体、小一号）
    c.setFont(font, 9)
    c.setFillColorRGB(0, 0, 0)

    # 左侧列表
    left_text_x = left_cx
    text_y = left_y - 55
    lines_left = [
        f"太陽：牡羊座 12.3°",
        f"月：双子座 5.4°",
        f"金星：獅子座 17.8°",
        f"火星：天秤座 3.2°",
        f"ASC：山羊座 20.1°",
    ]
    for line in lines_left:
        c.drawCentredString(left_text_x, text_y, line)
        text_y -= 12

    # 右侧列表
    right_text_x = right_cx
    text_y = right_y - 55
    lines_right = [
        f"太陽：蟹座 8.5°",
        f"月：乙女座 22.0°",
        f"金星：蠍座 14.6°",
        f"火星：水瓶座 2.9°",
        f"ASC：魚座 28.4°",
    ]
    for line in lines_right:
        c.drawCentredString(right_text_x, text_y, line)
        text_y -= 12

    c.showPage()

    # ------------------------------------------------------------------
    # 后面几页只铺背景（先占位）
    # ------------------------------------------------------------------
    for bg in [
        "page_communication.jpg",
        "page_points.jpg",
        "page_trend.jpg",
        "page_advice.jpg",
        "page_summary.jpg",
    ]:
        draw_full_bg(c, bg)
        c.showPage()

    # ------------------------------------------------------------------
    # 收尾
    # ------------------------------------------------------------------
    c.save()
    buffer.seek(0)

    filename = f"love_report_{male_name}_{female_name}.pdf"
    return send_file(
        buffer,
        as_attachment=True,
        download_name=filename,
        mimetype="application/pdf",
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
