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
# 字体设置：只用 ReportLab 自带日文字体，彻底不用 Noto 文件
# ------------------------------------------------------------------
JP_FONT = "HeiseiKakuGo-W5"   # 无衬线
pdfmetrics.registerFont(UnicodeCIDFont(JP_FONT))

# ------------------------------------------------------------------
# 示例用：行星数据（之后会用真数据替换）
# 角度：0° = 牡羊座0°，在星盘上方（12 点方向），顺时针增加
# ------------------------------------------------------------------
SAMPLE_MALE_PLANETS = [
    {"key": "sun",   "label": "太陽", "symbol": "☉", "sign": "牡羊座", "degree": "12.3°", "lon": 12.3},
    {"key": "moon",  "label": "月",   "symbol": "☽", "sign": "双子座", "degree": "5.4°",  "lon": 65.4},
    {"key": "venus", "label": "金星", "symbol": "♀", "sign": "獅子座", "degree": "17.8°", "lon": 137.8},
    {"key": "mars",  "label": "火星", "symbol": "♂", "sign": "天秤座", "degree": "3.2°",  "lon": 183.2},
    {"key": "asc",   "label": "上昇", "symbol": "ASC","sign": "山羊座", "degree": "20.1°", "lon": 270.1},
]

SAMPLE_FEMALE_PLANETS = [
    {"key": "sun",   "label": "太陽", "symbol": "☉", "sign": "蟹座",   "degree": "8.5°",  "lon": 98.5},
    {"key": "moon",  "label": "月",   "symbol": "☽", "sign": "乙女座", "degree": "22.0°", "lon": 172.0},
    {"key": "venus", "label": "金星", "symbol": "♀", "sign": "蠍座",   "degree": "14.6°", "lon": 224.6},
    {"key": "mars",  "label": "火星", "symbol": "♂", "sign": "水瓶座", "degree": "2.9°",  "lon": 302.9},
    {"key": "asc",   "label": "上昇", "symbol": "ASC","sign": "魚座",   "degree": "28.4°", "lon": 358.4},
]

# ------------------------------------------------------------------
# 小工具：铺满整页背景图
# ------------------------------------------------------------------
def draw_full_bg(c, filename):
    """
    将 public/assets/filename 这张图拉伸铺满 A4 页面
    """
    path = os.path.join(ASSETS_DIR, filename)
    img = ImageReader(path)
    c.drawImage(img, 0, 0, width=PAGE_WIDTH, height=PAGE_HEIGHT)


# ------------------------------------------------------------------
# 小工具：处理日期参数，输出 2025年11月13日 这种格式
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
# 极坐标 → 画布坐标
# 0° = 上方（12点方向），顺时针增加
# ------------------------------------------------------------------
def polar_to_xy(cx, cy, radius, deg):
    theta = math.radians(90.0 - deg)   # 0°=上，顺时针为正
    x = cx + radius * math.cos(theta)
    y = cy + radius * math.sin(theta)
    return x, y


# ------------------------------------------------------------------
# 在单个星盘上画 5 个点 + 符号（图标在内圈）
# ------------------------------------------------------------------
def draw_planets_on_chart(c, center_x, center_y, radius, planets, color_rgb):
    # 点的半径
    dot_r = 3
    dot_radius = radius * 0.62      # 小圆点所在半径（靠内圈）
    text_radius = radius * 0.48     # 文字所在半径（更靠内）

    # 先画点（彩色）
    c.setFillColorRGB(*color_rgb)
    c.setStrokeColorRGB(*color_rgb)

    for p in planets:
        x, y = polar_to_xy(center_x, center_y, dot_radius, p["lon"])
        c.circle(x, y, dot_r, stroke=1, fill=1)

    # 再画文字（黑色，细字）
    c.setFillColorRGB(0, 0, 0)
    c.setFont(JP_FONT, 7)   # 内圈符号稍大一点点

    for p in planets:
        x, y = polar_to_xy(center_x, center_y, text_radius, p["lon"])
        label = p["symbol"]          # ☉☽♀♂ 或 ASC
        c.drawCentredString(x, y - 2, label)


# ------------------------------------------------------------------
# 星盘下方的 5 行行星列表（居中 + 小号字）
# ------------------------------------------------------------------
def draw_planet_table(c, center_x, top_y, line_height, planets):
    c.setFont(JP_FONT, 8)          # 比正文小一号，细一点
    c.setFillColorRGB(0, 0, 0)

    for i, p in enumerate(planets):
        text = f"{p['label']}：{p['sign']} {p['degree']}"
        y = top_y - i * line_height
        c.drawCentredString(center_x, y, text)


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
# GET /api/generate_report?male_name=太郎&female_name=花子&date=2025-01-01
# ------------------------------------------------------------------
@app.route("/api/generate_report", methods=["GET"])
def generate_report():
    # ---- 1. 读取参数 ----
    male_name = request.args.get("male_name", "太郎")
    female_name = request.args.get("female_name", "花子")
    raw_date = request.args.get("date")  # 期望格式：YYYY-MM-DD
    date_display = get_display_date(raw_date)

    # ---- 2. 准备 PDF 缓冲区 ----
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)

    # 统一字体
    font = JP_FONT

    # ------------------------------------------------------------------
    # 封面：cover.jpg
    # 只在指定位置加「太郎 さん ＆ 花子 さん」和「作成日：2025年11月13日」
    # ------------------------------------------------------------------
    draw_full_bg(c, "cover.jpg")

    # 姓名：放在金色「恋愛占星レポート」正上方（居中）
    c.setFont(font, 18)
    c.setFillColorRGB(0.3, 0.3, 0.3)
    couple_text = f"{male_name} さん ＆ {female_name} さん"
    c.drawCentredString(PAGE_WIDTH / 2, 420, couple_text)

    # 作成日：底部中央
    c.setFont(font, 12)
    date_text = f"作成日：{date_display}"
    c.drawCentredString(PAGE_WIDTH / 2, 80, date_text)

    c.showPage()

    # ------------------------------------------------------------------
    # 第 2 页：目录 / 说明页，直接用 index.jpg
    # ------------------------------------------------------------------
    draw_full_bg(c, "index.jpg")
    c.showPage()

    # ------------------------------------------------------------------
    # 第 3 页：基本ホロスコープと総合相性 + 两个星盘
    # 背景：page_basic.jpg
    # 星盘：chart_base.png 一左一右，下方分别写姓名 + 行星列表
    # ------------------------------------------------------------------
    draw_full_bg(c, "page_basic.jpg")

    chart_path = os.path.join(ASSETS_DIR, "chart_base.png")
    chart_img = ImageReader(chart_path)

    # 星盘尺寸 + 位置
    chart_size = 180
    left_x = 90
    left_y = 500
    right_x = PAGE_WIDTH - chart_size - 90
    right_y = left_y

    # 画星盘底图
    c.drawImage(chart_img, left_x, left_y,
                width=chart_size, height=chart_size, mask="auto")
    c.drawImage(chart_img, right_x, right_y,
                width=chart_size, height=chart_size, mask="auto")

    # 画行星点 + 符号
    left_cx = left_x + chart_size / 2
    left_cy = left_y + chart_size / 2
    right_cx = right_x + chart_size / 2
    right_cy = right_y + chart_size / 2
    radius = chart_size / 2

    # 男：蓝色；女：粉色
    male_color = (0.2, 0.4, 0.9)
    female_color = (0.9, 0.3, 0.6)

    draw_planets_on_chart(c, left_cx, left_cy, radius, SAMPLE_MALE_PLANETS, male_color)
    draw_planets_on_chart(c, right_cx, right_cy, radius, SAMPLE_FEMALE_PLANETS, female_color)

    # 星盘下方姓名
    c.setFont(font, 14)
    c.setFillColorRGB(0, 0, 0)
    c.drawCentredString(left_cx, left_y - 30, f"{male_name} さん")
    c.drawCentredString(right_cx, right_y - 30, f"{female_name} さん")

    # 星盘下方行星列表（靠姓名上方一点，居中）
    table_line_height = 12
    male_table_top = left_y - 45
    female_table_top = right_y - 45

    draw_planet_table(c, left_cx, male_table_top, table_line_height, SAMPLE_MALE_PLANETS)
    draw_planet_table(c, right_cx, female_table_top, table_line_height, SAMPLE_FEMALE_PLANETS)

    # 勾选项的文字保持不变（图片里自带勾选框）
    c.setFont(font, 12)
    c.setFillColorRGB(0, 0, 0)
    c.drawString(90, 415, "総合相性スコア")
    c.drawString(90, 360, "太陽・月・上昇の分析")

    c.showPage()

    # ------------------------------------------------------------------
    # 第 4~? 页：先只铺背景图（模板），文字逻辑之后再加
    # 顺序：page_communication -> page_points -> page_trend
    #      -> page_advice -> page_summary
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
    # 收尾 & 返回 PDF
    # ------------------------------------------------------------------
    c.save()
    buffer.seek(0)

    filename = f"love_report_{male_name}_{female_name}.pdf"

    return send_file(
        buffer,
        as_attachment=True,
        download_name=filename,
        mimetype="application/pdf"
    )


if __name__ == "__main__":
    # 本地跑可以用 10000，Render 上会用自己的 PORT 环境变量
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
