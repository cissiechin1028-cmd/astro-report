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

# ---------------------------------------------------
# Flask + 目录
# ---------------------------------------------------
app = Flask(__name__, static_url_path='', static_folder='public')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(BASE_DIR, "public", "assets")

PAGE_WIDTH, PAGE_HEIGHT = A4

# ---------------------------------------------------
# 使用 ReportLab 内置日文字体
# ---------------------------------------------------
JP_FONT = "HeiseiKakuGo-W5"
pdfmetrics.registerFont(UnicodeCIDFont(JP_FONT))

# ---------------------------------------------------
# 透明 PNG 行星图标
# ---------------------------------------------------
PLANET_ICONS = {
    "sun":   ImageReader(os.path.join(ASSETS_DIR, "icon_sun.png")),
    "moon":  ImageReader(os.path.join(ASSETS_DIR, "icon_moon.png")),
    "asc":   ImageReader(os.path.join(ASSETS_DIR, "icon_asc.png")),
    "mars":  ImageReader(os.path.join(ASSETS_DIR, "icon_mars.png")),
    "venus": ImageReader(os.path.join(ASSETS_DIR, "icon_venus.png")),
}

# ---------------------------------------------------
# 工具：背景铺满
# ---------------------------------------------------
def draw_full_bg(c, filename):
    path = os.path.join(ASSETS_DIR, filename)
    img = ImageReader(path)
    c.drawImage(img, 0, 0, width=PAGE_WIDTH, height=PAGE_HEIGHT)

# ---------------------------------------------------
# 日期格式
# ---------------------------------------------------
def get_display_date(raw_date):
    if raw_date:
        try:
            d = datetime.datetime.strptime(raw_date, "%Y-%m-%d").date()
        except:
            d = datetime.date.today()
    else:
        d = datetime.date.today()
    return f"{d.year}年{d.month}月{d.day}日"

# ---------------------------------------------------
# 星盘：画一个行星（彩色圆点 + 图标 PNG）
# ---------------------------------------------------
def draw_planet(c, cx, cy, radius, angle_deg, color_rgb, icon_key):
    rad = math.radians(angle_deg)
    x = cx + radius * math.cos(rad)
    y = cy + radius * math.sin(rad)

    # 小圆点
    dot_r = 4
    c.setFillColorRGB(*color_rgb)
    c.circle(x, y, dot_r, fill=1, stroke=0)

    # 图标
    icon = PLANET_ICONS[icon_key]
    icon_size = 12
    c.drawImage(icon, x - icon_size/2, y - icon_size/2,
                width=icon_size, height=icon_size, mask='auto')

# ---------------------------------------------------
# 首页
# ---------------------------------------------------
@app.route("/")
def root():
    return "PDF server running."

@app.route("/test.html")
def test_page():
    return app.send_static_file("test.html")

# ---------------------------------------------------
# 主功能：生成 PDF
# ---------------------------------------------------
@app.route("/api/generate_report", methods=["GET"])
def generate_report():
    # 获取参数
    male = request.args.get("male_name", "太郎")
    female = request.args.get("female_name", "花子")
    date_raw = request.args.get("date")
    date_display = get_display_date(date_raw)

    # PDF 缓冲区
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)

    # ---------------------------------------------------
    # 封面
    # ---------------------------------------------------
    draw_full_bg(c, "cover.jpg")

    c.setFont(JP_FONT, 18)
    c.setFillColorRGB(0.3, 0.3, 0.3)
    c.drawCentredString(PAGE_WIDTH/2, 420, f"{male} さん ＆ {female} さん")

    c.setFont(JP_FONT, 12)
    c.drawCentredString(PAGE_WIDTH/2, 80, f"作成日：{date_display}")

    c.showPage()

    # ---------------------------------------------------
    # 目录页（你说不用改内容）
    # ---------------------------------------------------
    draw_full_bg(c, "index.jpg")
    c.showPage()

    # ---------------------------------------------------
    # 星盘页
    # ---------------------------------------------------
    draw_full_bg(c, "page_basic.jpg")

    # 星盘底图
    chart = ImageReader(os.path.join(ASSETS_DIR, "chart_base.png"))
    chart_size = 180
    left_x = 90
    left_y = 500
    right_x = PAGE_WIDTH - chart_size - 90
    right_y = left_y

    # 画星盘底图
    c.drawImage(chart, left_x, left_y, width=chart_size, height=chart_size)
    c.drawImage(chart, right_x, right_y, width=chart_size, height=chart_size)

    # 星盘中心坐标
    male_cx = left_x + chart_size / 2
    male_cy = left_y + chart_size / 2
    female_cx = right_x + chart_size / 2
    female_cy = right_y + chart_size / 2

    # 半径（图标放内圈）
    r_inner = chart_size * 0.33

    # 示例行星角度（以后你可以从数据库输入）
    male_angles = {
        "sun": 10, "moon": 85, "venus": 140, "mars": 220, "asc": 300
    }
    female_angles = {
        "sun": 15, "moon": 120, "venus": 210, "mars": 280, "asc": 340
    }

    # 男=蓝 女=粉
    male_color = (0.2, 0.4, 0.9)
    female_color = (0.9, 0.3, 0.6)

    # 男方行星
    for key, angle in male_angles.items():
        draw_planet(c, male_cx, male_cy, r_inner, angle, male_color, key)

    # 女方行星
    for key, angle in female_angles.items():
        draw_planet(c, female_cx, female_cy, r_inner, angle, female_color, key)

    # ---------------------------------------------------
    # 下方行星列表（字体细一点、居中）
    # ---------------------------------------------------
    c.setFont(JP_FONT, 9)
    c.setFillColorRGB(0.05, 0.05, 0.05)

    male_lines = [
        "太陽：牡羊座 12.3°",
        "月：双子座 5.4°",
        "金星：獅子座 17.8°",
        "火星：天秤座 3.2°",
        "上昇：山羊座 20.1°",
    ]
    female_lines = [
        "太陽：蟹座 8.5°",
        "月：乙女座 22.0°",
        "金星：蠍座 14.6°",
        "火星：水瓶座 2.9°",
        "上昇：魚座 28.4°",
    ]

    base_y = 390
    line_h = 11

    for i, line in enumerate(male_lines):
        c.drawCentredString(male_cx, base_y - i * line_h, line)

    for i, line in enumerate(female_lines):
        c.drawCentredString(female_cx, base_y - i * line_h, line)

    # 星盘下方姓名
    c.setFont(JP_FONT, 14)
    c.setFillColorRGB(0, 0, 0)
    c.drawCentredString(male_cx, left_y - 25, f"{male} さん")
    c.drawCentredString(female_cx, right_y - 25, f"{female} さん")

    c.showPage()

    # ---------------------------------------------------
    # 后续几页背景（仍然保持空白）
    # ---------------------------------------------------
    for bg in [
        "page_communication.jpg",
        "page_points.jpg",
        "page_trend.jpg",
        "page_advice.jpg",
        "page_summary.jpg",
    ]:
        draw_full_bg(c, bg)
        c.showPage()

    # ---------------------------------------------------
    # 输出 PDF
    # ---------------------------------------------------
    c.save()
    buffer.seek(0)

    filename = f"love_report_{male}_{female}.pdf"
    return send_file(buffer, as_attachment=True,
                     download_name=filename,
                     mimetype="application/pdf")

# ---------------------------------------------------
# Run
# ---------------------------------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
