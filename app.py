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
# 工具：星盘用的极坐标转换 + 在内圈画行星点和符号
# ------------------------------------------------------------------
def chart_polar(cx, cy, radius, deg):
    """
    cx, cy : 圆心
    deg    : 角度（0° 在 12 点方向，顺时针增加）
    """
    rad = math.radians(90 - deg)
    x = cx + radius * math.cos(rad)
    y = cy + radius * math.sin(rad)
    return x, y


def draw_planet(c, cx, cy, chart_size, angle_deg, color_rgb, symbol, font_name):
    """
    在星盘内圈画一个行星：
      - 外圈彩色小圆点（位置）
      - 内圈占星符号（☉☽♀♂ / ASC）
    都在内圈，不挡外圈星座符号
    """
    base_r = chart_size / 2.0
    # 这两个半径你可以微调：点稍外，符号再往里一点
    dot_r = base_r * 0.78   # 小圆点
    text_r = base_r * 0.55  # 符号

    # 小圆点
    x_dot, y_dot = chart_polar(cx, cy, dot_r, angle_deg)
    r, g, b = color_rgb
    c.setFillColorRGB(r, g, b)
    c.circle(x_dot, y_dot, 2.2, stroke=0, fill=1)

    # 符号（小一号、细一点）
    x_txt, y_txt = chart_polar(cx, cy, text_r, angle_deg)
    c.setFont(font_name, 9)
    c.setFillColorRGB(r, g, b)
    c.drawCentredString(x_txt, y_txt - 2, symbol)


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
    # 背景：page_basic.jpg + chart_base.png + 行星位置 + 行星リスト
    # ------------------------------------------------------------------
    draw_full_bg(c, "page_basic.jpg")

    chart_path = os.path.join(ASSETS_DIR, "chart_base.png")
    chart_img = ImageReader(chart_path)

    # 星盘尺寸 + 位置
    chart_size = 200
    left_x = 90
    left_y = 520
    right_x = PAGE_WIDTH - chart_size - 90
    right_y = left_y

    # 圆心
    left_cx = left_x + chart_size / 2
    left_cy = left_y + chart_size / 2
    right_cx = right_x + chart_size / 2
    right_cy = right_y + chart_size / 2

    # 背景星盘
    c.drawImage(chart_img, left_x, left_y,
                width=chart_size, height=chart_size, mask="auto")
    c.drawImage(chart_img, right_x, right_y,
                width=chart_size, height=chart_size, mask="auto")

    # ------------  行星角度（示例数据，将来可以改成真实数据） ------------
    # 用列表保证顺序：太陽 → 月 → 金星 → 火星 → ASC
    male_planets = [
        {"deg": 12.3,  "label": "太陽：牡羊座 12.3°",  "symbol": "☉"},
        {"deg": 65.4,  "label": "月：双子座 5.4°",    "symbol": "☽"},
        {"deg": 147.8, "label": "金星：獅子座 17.8°", "symbol": "♀"},
        {"deg": 183.2, "label": "火星：天秤座 3.2°",  "symbol": "♂"},
        {"deg": 220.1, "label": "ASC：山羊座 20.1°", "symbol": "ASC"},
    ]

    female_planets = [
        {"deg": 8.5,   "label": "太陽：蟹座 8.5°",     "symbol": "☉"},
        {"deg": 150.0, "label": "月：乙女座 22.0°",   "symbol": "☽"},
        {"deg": 214.6, "label": "金星：蠍座 14.6°",    "symbol": "♀"},
        {"deg": 262.9, "label": "火星：水瓶座 2.9°",   "symbol": "♂"},
        {"deg": 288.4, "label": "ASC：魚座 28.4°",    "symbol": "ASC"},
    ]

    # 男 = 蓝色 / 女 = 粉色
    male_color = (0.15, 0.45, 0.9)
    female_color = (0.9, 0.35, 0.65)

    # ------------  在星盘内圈画行星点 + 符号 ------------
    for info in male_planets:
        draw_planet(
            c,
            left_cx,
            left_cy,
            chart_size,
            info["deg"],
            male_color,
            info["symbol"],
            font,
        )

    for info in female_planets:
        draw_planet(
            c,
            right_cx,
            right_cy,
            chart_size,
            info["deg"],
            female_color,
            info["symbol"],
            font,
        )

    # ------------  星盘下方姓名 ------------
    c.setFont(font, 14)
    c.setFillColorRGB(0, 0, 0)
    c.drawCentredString(left_cx, left_y - 25, f"{male_name} さん")
    c.drawCentredString(right_cx, right_y - 25, f"{female_name} さん")

    # ------------  星盘下方 5 行列表（往上挪一点、字体变细） ------------
    c.setFont(font, 9)  # 小一号，看起来更细
    c.setFillColorRGB(0, 0, 0)

    # 男方列表
    text = c.beginText()
    text.setTextOrigin(left_cx - 70, left_y - 55)  # 位置你不满意再一起调
    for info in male_planets:
        text.textLine(info["label"])
    c.drawText(text)

    # 女方列表
    text2 = c.beginText()
    text2.setTextOrigin(right_cx - 70, right_y - 55)
    for info in female_planets:
        text2.textLine(info["label"])
    c.drawText(text2)

    # 不再额外画「総合相性スコア」「太陽・月・上昇の分析」标题，
    # 因为底图中已经有了
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
